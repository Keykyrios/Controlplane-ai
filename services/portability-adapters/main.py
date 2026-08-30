"""
Portability Adapter Service — Section 12
==========================================
Implements the categorical guarantee of model-agnostic portability.

F : Pipe → Risk   (a functor)

F(g ∘ f) = F(g) ∘ F(f)   — composition respected
F(id_X) = id_{F(X)}       — identity preserved

The Yoneda argument: two pipelines indistinguishable by every probe
are, as far as F is concerned, the same object. The checker never reads
weights or activations — only the probe-observable input/output stream.

Whitepaper: Section 12, Eq. 30-31
Blueprint: Section 8
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Portability Adapters",
    description="Section 12: model-agnostic pipeline adapters (Yoneda)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# PipelineAdapter ABC
# ---------------------------------------------------------------------------

class PipelineAdapter(ABC):
    """
    Abstract adapter translating a pipeline's I/O conventions
    into the probe interface ControlPlane requires.
    
    Every adapter exposes only:
    - Token stream (text content)
    - Tool-call records
    - Timing information
    - Token usage
    
    It NEVER accesses model weights or activations.
    This is Assumption 4.1 (probe-only instrumentation).
    """
    
    @abstractmethod
    def extract_response_text(self, raw: dict) -> str:
        """Extract the response text from the pipeline's native format."""
        ...
    
    @abstractmethod
    def extract_prompt_text(self, raw: dict) -> str:
        """Extract the prompt text."""
        ...
    
    @abstractmethod
    def extract_tool_calls(self, raw: dict) -> list[dict]:
        """Extract tool calls."""
        ...
    
    @abstractmethod
    def extract_token_usage(self, raw: dict) -> dict:
        """Extract token usage (input, output, total)."""
        ...
    
    @abstractmethod
    def extract_model_confidence(self, raw: dict) -> Optional[float]:
        """Extract ŷ_t if available (e.g. from logprobs)."""
        ...
    
    @abstractmethod
    def extract_grounding_context(self, raw: dict) -> str:
        """Extract any grounding/retrieval context."""
        ...
    
    def to_probe_format(self, raw: dict) -> dict:
        """Convert to the universal probe format."""
        return {
            "response_text": self.extract_response_text(raw),
            "prompt_text": self.extract_prompt_text(raw),
            "tool_calls": self.extract_tool_calls(raw),
            "token_usage": self.extract_token_usage(raw),
            "model_confidence": self.extract_model_confidence(raw),
            "grounding_context": self.extract_grounding_context(raw),
        }


# ---------------------------------------------------------------------------
# Concrete Adapters
# ---------------------------------------------------------------------------

class OpenAIChatAdapter(PipelineAdapter):
    """Adapter for OpenAI Chat Completions API responses."""
    
    def extract_response_text(self, raw: dict) -> str:
        choices = raw.get("choices", [{}])
        return choices[0].get("message", {}).get("content", "")
    
    def extract_prompt_text(self, raw: dict) -> str:
        messages = raw.get("_request", {}).get("messages", [])
        return "\n".join(m.get("content", "") for m in messages if m.get("role") != "assistant")
    
    def extract_tool_calls(self, raw: dict) -> list[dict]:
        choices = raw.get("choices", [{}])
        return choices[0].get("message", {}).get("tool_calls", [])
    
    def extract_token_usage(self, raw: dict) -> dict:
        usage = raw.get("usage", {})
        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    
    def extract_model_confidence(self, raw: dict) -> Optional[float]:
        choices = raw.get("choices", [{}])
        logprobs = choices[0].get("logprobs")
        if logprobs and logprobs.get("content"):
            import math
            avg_logprob = sum(
                t.get("logprob", 0) for t in logprobs["content"]
            ) / max(1, len(logprobs["content"]))
            return min(1.0, math.exp(avg_logprob))
        return None
    
    def extract_grounding_context(self, raw: dict) -> str:
        messages = raw.get("_request", {}).get("messages", [])
        system_msgs = [m.get("content", "") for m in messages if m.get("role") == "system"]
        return "\n".join(system_msgs)


class AnthropicMessagesAdapter(PipelineAdapter):
    """Adapter for Anthropic Messages API responses."""
    
    def extract_response_text(self, raw: dict) -> str:
        content = raw.get("content", [])
        return " ".join(
            block.get("text", "") for block in content
            if block.get("type") == "text"
        )
    
    def extract_prompt_text(self, raw: dict) -> str:
        messages = raw.get("_request", {}).get("messages", [])
        return "\n".join(
            m.get("content", "") if isinstance(m.get("content"), str)
            else " ".join(b.get("text", "") for b in m.get("content", []) if b.get("type") == "text")
            for m in messages if m.get("role") != "assistant"
        )
    
    def extract_tool_calls(self, raw: dict) -> list[dict]:
        content = raw.get("content", [])
        return [
            {"name": block.get("name"), "input": block.get("input")}
            for block in content if block.get("type") == "tool_use"
        ]
    
    def extract_token_usage(self, raw: dict) -> dict:
        usage = raw.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }
    
    def extract_model_confidence(self, raw: dict) -> Optional[float]:
        return None  # Anthropic doesn't expose logprobs
    
    def extract_grounding_context(self, raw: dict) -> str:
        return raw.get("_request", {}).get("system", "")


class GenericHTTPJSONAdapter(PipelineAdapter):
    """Generic adapter for any HTTP JSON API with configurable field mapping."""
    
    def __init__(self, field_map: Optional[dict] = None):
        self.field_map = field_map or {
            "response_text": "response",
            "prompt_text": "prompt",
            "tool_calls": "tools",
            "token_usage": "usage",
            "model_confidence": "confidence",
            "grounding_context": "context",
        }
    
    def _get(self, raw: dict, field: str) -> any:
        key = self.field_map.get(field, field)
        parts = key.split(".")
        obj = raw
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part, "")
            else:
                return ""
        return obj
    
    def extract_response_text(self, raw: dict) -> str:
        return str(self._get(raw, "response_text"))
    
    def extract_prompt_text(self, raw: dict) -> str:
        return str(self._get(raw, "prompt_text"))
    
    def extract_tool_calls(self, raw: dict) -> list[dict]:
        tc = self._get(raw, "tool_calls")
        return tc if isinstance(tc, list) else []
    
    def extract_token_usage(self, raw: dict) -> dict:
        u = self._get(raw, "token_usage")
        return u if isinstance(u, dict) else {}
    
    def extract_model_confidence(self, raw: dict) -> Optional[float]:
        c = self._get(raw, "model_confidence")
        return float(c) if c and c != "" else None
    
    def extract_grounding_context(self, raw: dict) -> str:
        return str(self._get(raw, "grounding_context"))


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, PipelineAdapter] = {
    "openai-chat": OpenAIChatAdapter(),
    "anthropic-messages": AnthropicMessagesAdapter(),
    "generic-http-json": GenericHTTPJSONAdapter(),
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class AdaptRequest(BaseModel):
    adapter_name: str
    raw_response: dict


class AdaptResponse(BaseModel):
    response_text: str
    prompt_text: str
    tool_calls: list[dict]
    token_usage: dict
    model_confidence: Optional[float]
    grounding_context: str


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "portability-adapters", "section": "12"}


@app.post("/adapt", response_model=AdaptResponse)
async def adapt_response(req: AdaptRequest):
    """Convert a pipeline-specific response to the universal probe format."""
    adapter = ADAPTERS.get(req.adapter_name)
    if not adapter:
        raise HTTPException(404, f"Adapter '{req.adapter_name}' not found")
    result = adapter.to_probe_format(req.raw_response)
    return AdaptResponse(**result)


@app.get("/adapters")
async def list_adapters():
    """List all registered pipeline adapters."""
    return {
        "adapters": list(ADAPTERS.keys()),
        "yoneda_claim": (
            "Two pipelines indistinguishable by every probe are, "
            "as far as F is concerned, the same object (Section 12, Eq. 31)"
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)

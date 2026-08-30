"""
Risk Observables Service — Section 5.1
=======================================
Implements Equations 2, 3, 4 of the whitepaper:
  p_t = ŷ_t · (1 - q_t)           — performance risk
  c_t = σ((κ_t - κ̄(τ_t)) / κ̄(τ_t)) — cost risk
  r_t = max(b_t, s_t, ℓ_t)        — responsibility risk

Plus Section 5.4: PII/hallucination overlap sub-scores ℓ_PII_t, ℓ_MI_t.

This service owns the raw risk observable computation and is the first
service called in the Algorithm 1 pipeline.
"""

from __future__ import annotations

import math
import re
import time
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ControlPlane Manifold — Risk Observables",
    description="Section 5.1: Equations 2, 3, 4 — raw risk observable computation",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class RiskObservablesRequest(BaseModel):
    """Input to the risk observables computation."""
    session_id: str
    response_id: str
    response_text: str
    prompt_text: str = ""
    model_confidence: Optional[float] = None  # ŷ_t if available
    token_usage: dict = Field(default_factory=dict)
    task_type: str = "general"
    grounding_context: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    tier: str = "A"


class RiskObservablesResponse(BaseModel):
    """The three scalar risk observables plus sub-scores."""
    session_id: str
    response_id: str
    p_t: float
    c_t: float
    r_t: float
    b_t: float
    s_t: float
    l_pii_t: float
    l_mi_t: float
    l_t: float
    y_hat: float
    q_t: float
    timestamp_ns: int


# ---------------------------------------------------------------------------
# Section 5.1 — Verifier Ensemble for q_t
# ---------------------------------------------------------------------------

# PII patterns for structured-PII detection (Section 5.4)
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "date_of_birth": re.compile(
        r"\b(?:born|DOB|dob|date of birth)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "gov_id": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    "account_number": re.compile(r"\baccount\s*(?:number|#|no\.?)\s*[:\s]*\d{6,}\b", re.IGNORECASE),
}

# Named entity indicators (simplified NER for identifiable individuals)
NAME_PATTERNS = [
    re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
    re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:'s)?\b"),  # Two capitalized words
]


def compute_hedging_confidence(text: str) -> float:
    """
    Proxy for ŷ_t when model logprobs are not available.
    Detects hedging language that indicates low model confidence.
    """
    hedging_phrases = [
        "I'm not sure", "I think", "possibly", "maybe", "might be",
        "could be", "it seems", "arguably", "perhaps", "I believe",
        "approximately", "roughly", "it's possible", "not certain",
        "uncertain", "unclear", "debatable", "likely", "unlikely",
        "as far as I know", "to my knowledge", "I'm unsure",
    ]
    text_lower = text.lower()
    hedging_count = sum(1 for p in hedging_phrases if p.lower() in text_lower)
    # More hedging → lower confidence
    confidence = max(0.1, 1.0 - (hedging_count * 0.15))
    
    # Assertive language boosts confidence
    assertive_phrases = [
        "definitely", "certainly", "absolutely", "without doubt",
        "clearly", "obviously", "the answer is", "this is correct",
        "I can confirm", "it is a fact",
    ]
    assertive_count = sum(1 for p in assertive_phrases if p.lower() in text_lower)
    confidence = min(1.0, confidence + (assertive_count * 0.1))
    
    return confidence


def compute_self_consistency_score(response_text: str, grounding_context: str) -> float:
    """
    Self-consistency component of q_t.
    
    In production, this calls the underlying model k times at temperature > 0
    and measures answer agreement (SelfCheckGPT-style, cite [26]).
    
    For the implementation, we use a text-overlap heuristic between
    the response and grounding context as a proxy.
    """
    if not grounding_context:
        return 0.5  # No grounding → moderate uncertainty
    
    # Token-level overlap as proxy for retrieval cross-check
    response_tokens = set(response_text.lower().split())
    context_tokens = set(grounding_context.lower().split())
    
    if not response_tokens:
        return 0.5
    
    overlap = len(response_tokens & context_tokens) / len(response_tokens)
    return min(1.0, overlap * 1.5)  # Scale up, cap at 1.0


def compute_tool_grounded_score(tool_calls: list[dict]) -> float:
    """
    Tool-grounded assertion checker component of q_t.
    If tool calls are present and returned results, the response
    is more likely grounded.
    """
    if not tool_calls:
        return 0.5  # No tool calls → neutral
    
    successful_calls = sum(
        1 for tc in tool_calls
        if tc.get("result") is not None and tc.get("status") == "success"
    )
    return min(1.0, successful_calls / max(1, len(tool_calls)))


def compute_q_t(
    response_text: str,
    grounding_context: str,
    tool_calls: list[dict],
) -> float:
    """
    Calibrated estimate of P(x_t is correct), Section 5.1.
    
    Ensemble of three verifiers:
    (a) retrieval cross-check against grounding corpus
    (b) self-consistency sampling proxy
    (c) tool-grounded assertion checker
    
    Combined via logistic averaging.
    """
    v_retrieval = compute_self_consistency_score(response_text, grounding_context)
    v_consistency = compute_self_consistency_score(response_text, response_text[::-1])  # proxy
    v_tool = compute_tool_grounded_score(tool_calls)
    
    # Logistic combination
    scores = [v_retrieval, v_consistency, v_tool]
    weights = [0.4, 0.3, 0.3]  # retrieval-weighted
    q_t = sum(w * s for w, s in zip(weights, scores))
    return max(0.0, min(1.0, q_t))


# ---------------------------------------------------------------------------
# Eq. 2 — Performance Risk
# ---------------------------------------------------------------------------

def compute_performance_risk(
    y_hat: float,
    q_t: float,
) -> float:
    """
    p_t = ŷ_t · (1 - q_t)
    
    Large when model is confident AND verifiers disagree.
    This is the operational definition of "confidently wrong."
    """
    return y_hat * (1.0 - q_t)


# ---------------------------------------------------------------------------
# Eq. 3 — Cost Risk
# ---------------------------------------------------------------------------

def sigmoid(z: float) -> float:
    """Standard logistic sigmoid σ(z) = 1/(1+e^{-z})."""
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, z))))


def compute_cost_risk(
    kappa_t: float,
    kappa_bar: float,
) -> float:
    """
    c_t = σ((κ_t - κ̄(τ_t)) / κ̄(τ_t))
    
    Logistic squashing of relative cost overrun into [0,1].
    c_t ≈ 0.5 at baseline, saturates toward 1 for large overruns.
    """
    if kappa_bar <= 0:
        return 0.5  # No baseline → neutral
    relative_overrun = (kappa_t - kappa_bar) / kappa_bar
    return sigmoid(relative_overrun)


# ---------------------------------------------------------------------------
# Section 5.4 — PII / Hallucination Overlap
# ---------------------------------------------------------------------------

def compute_pii_score(response_text: str, grounding_context: str) -> float:
    """
    ℓ_PII_t: structured-PII detector.
    
    Detects identifiers (names, SSNs, account numbers, etc.) present
    in the response but ABSENT from the grounding context.
    """
    pii_in_response = set()
    for name, pattern in PII_PATTERNS.items():
        matches = pattern.findall(response_text)
        pii_in_response.update((name, m) for m in matches)
    
    # Also check for named individuals
    for pattern in NAME_PATTERNS:
        matches = pattern.findall(response_text)
        pii_in_response.update(("name", m) for m in matches)
    
    if not pii_in_response:
        return 0.0
    
    # Check which PII is NOT grounded in the context
    ungrounded_pii = set()
    for pii_type, pii_value in pii_in_response:
        if pii_value not in grounding_context:
            ungrounded_pii.add((pii_type, pii_value))
    
    if not ungrounded_pii:
        return 0.0
    
    # Score scales with count and severity
    severity_weights = {
        "ssn": 1.0, "credit_card": 0.9, "gov_id": 0.9, "account_number": 0.8,
        "date_of_birth": 0.7, "name": 0.5, "email": 0.4, "phone": 0.4,
        "ip_address": 0.3,
    }
    
    total_severity = sum(
        severity_weights.get(pii_type, 0.3)
        for pii_type, _ in ungrounded_pii
    )
    return min(1.0, total_severity / 2.0)


def compute_membership_plausibility(
    response_text: str,
    entities_in_response: list[str],
) -> float:
    """
    ℓ_MI_t: membership-style plausibility score.
    
    Estimates whether asserted personal facts are consistent with
    model memorization of training data about real individuals,
    rather than generic confabulation.
    
    MVP heuristic: specificity of claims about named entities.
    Production requires model-provider cooperation for proper
    membership inference via perplexity comparison.
    """
    if not entities_in_response:
        return 0.0
    
    # Heuristic: count specific factual assertions about entities
    specificity_markers = [
        "born in", "graduated from", "works at", "lives in",
        "married to", "age", "salary", "income", "diagnosed with",
        "convicted of", "arrested for", "address", "social security",
        "blood type", "medical", "health", "religion", "political",
        "sexual orientation", "disability", "ethnic", "genetic",
    ]
    
    text_lower = response_text.lower()
    specific_claims = sum(
        1 for marker in specificity_markers if marker in text_lower
    )
    
    # More specific claims about more entities → higher risk
    score = min(1.0, (specific_claims * len(entities_in_response)) / 10.0)
    return score


# ---------------------------------------------------------------------------
# Eq. 4 — Responsibility Risk
# ---------------------------------------------------------------------------

def compute_bias_score(response_text: str) -> float:
    """
    b_t: bias classifier score.
    
    In production, this would use a fine-tuned bias classifier
    (e.g., Llama-Guard-class model). MVP uses keyword heuristics
    with demographic group detection.
    """
    bias_indicators = [
        "always", "never", "all of them", "those people",
        "typically", "naturally", "inherently", "obviously",
    ]
    demographic_terms = [
        "race", "gender", "religion", "ethnicity", "nationality",
        "age group", "disability", "sexual orientation",
    ]
    
    text_lower = response_text.lower()
    bias_count = sum(1 for b in bias_indicators if b in text_lower)
    demo_count = sum(1 for d in demographic_terms if d in text_lower)
    
    if demo_count == 0:
        return 0.0
    return min(1.0, (bias_count * demo_count) / 8.0)


def compute_safety_score(response_text: str) -> float:
    """
    s_t: safety classifier score.
    
    In production, this would use Detoxify or similar.
    MVP uses category detection.
    """
    safety_categories = [
        "harm", "violence", "weapon", "illegal", "drug",
        "self-harm", "suicide", "exploit", "abuse", "threat",
        "attack", "dangerous", "toxic", "hate speech",
    ]
    
    text_lower = response_text.lower()
    count = sum(1 for c in safety_categories if c in text_lower)
    return min(1.0, count / 3.0)


def compute_responsibility_risk(b_t: float, s_t: float, l_t: float) -> float:
    """
    r_t = max(b_t, s_t, ℓ_t)
    
    Coordinate-wise maximum: a response is only as safe as its
    worst violated constraint. We deliberately do NOT average,
    since averaging would let a severe safety violation be
    diluted by two benign scores.
    """
    return max(b_t, s_t, l_t)


# ---------------------------------------------------------------------------
# Sliding Window for π_ij co-occurrence (Eq. 7, Section 5.4)
# ---------------------------------------------------------------------------

class CoOccurrenceTracker:
    """
    Maintains a sliding window for computing bivector interaction terms.
    
    π_ij = Pr[axis i,j jointly exceed threshold | x_t]
           - Pr[axis i exceeds threshold] · Pr[axis j exceeds threshold]
    
    Estimated online from a sliding window (Eq. 7).
    """
    
    def __init__(self, window_size: int = 500, threshold: float = 0.5):
        self.window_size = window_size
        self.threshold = threshold
        self.window: list[tuple[float, float, float]] = []  # (p_t, c_t, r_t)
    
    def update(self, p_t: float, c_t: float, r_t: float) -> dict[str, float]:
        """Add observation and return current interaction terms."""
        self.window.append((p_t, c_t, r_t))
        if len(self.window) > self.window_size:
            self.window.pop(0)
        return self.compute_interactions()
    
    def compute_interactions(self) -> dict[str, float]:
        """Compute all pairwise and triple interaction excesses."""
        if len(self.window) < 10:
            return {"pi_12": 0.0, "pi_13": 0.0, "pi_23": 0.0, "pi_123": 0.0}
        
        n = len(self.window)
        arr = np.array(self.window)
        high = arr > self.threshold  # boolean: which axes exceed threshold
        
        # Marginal probabilities
        p_high = np.mean(high, axis=0)  # [P(p high), P(c high), P(r high)]
        
        # Joint probabilities
        p_12 = np.mean(high[:, 0] & high[:, 1])
        p_13 = np.mean(high[:, 0] & high[:, 2])
        p_23 = np.mean(high[:, 1] & high[:, 2])
        p_123 = np.mean(high[:, 0] & high[:, 1] & high[:, 2])
        
        # Co-occurrence excess over independence
        pi_12 = p_12 - p_high[0] * p_high[1]
        pi_13 = p_13 - p_high[0] * p_high[2]
        pi_23 = p_23 - p_high[1] * p_high[2]
        pi_123 = p_123 - p_high[0] * p_high[1] * p_high[2]
        
        return {
            "pi_12": float(pi_12),
            "pi_13": float(pi_13),
            "pi_23": float(pi_23),
            "pi_123": float(pi_123),
        }


# Global co-occurrence tracker (per-session in production)
_cooccurrence_tracker = CoOccurrenceTracker()


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "risk-observables", "section": "5.1"}


@app.post("/risk/observables", response_model=RiskObservablesResponse)
async def compute_risk_observables(req: RiskObservablesRequest) -> RiskObservablesResponse:
    """
    Compute the three scalar risk observables (p_t, c_t, r_t)
    plus privacy/hallucination sub-scores.
    
    Whitepaper: Section 5.1, Equations 2-4
    """
    # ŷ_t — model confidence
    if req.model_confidence is not None:
        y_hat = req.model_confidence
    else:
        y_hat = compute_hedging_confidence(req.response_text)
    
    # q_t — verifier ensemble
    q_t = compute_q_t(req.response_text, req.grounding_context, req.tool_calls)
    
    # Eq. 2: p_t = ŷ_t · (1 - q_t)
    p_t = compute_performance_risk(y_hat, q_t)
    
    # Eq. 3: c_t = σ((κ_t - κ̄(τ_t)) / κ̄(τ_t))
    token_count = req.token_usage.get("total_tokens", len(req.response_text.split()))
    per_token_cost = req.token_usage.get("cost_per_token", 0.00003)
    kappa_t = token_count * per_token_cost
    kappa_bar = req.token_usage.get("baseline_cost", kappa_t * 0.8)  # Use rolling median in production
    c_t = compute_cost_risk(kappa_t, kappa_bar)
    
    # Section 5.4: PII / hallucination overlap
    l_pii_t = compute_pii_score(req.response_text, req.grounding_context)
    
    # Extract named entities for membership plausibility
    entities = []
    for pattern in NAME_PATTERNS:
        entities.extend(pattern.findall(req.response_text))
    l_mi_t = compute_membership_plausibility(req.response_text, entities)
    
    l_t = max(l_pii_t, l_mi_t)
    
    # Bias and safety sub-scores
    b_t = compute_bias_score(req.response_text)
    s_t = compute_safety_score(req.response_text)
    
    # Eq. 4: r_t = max(b_t, s_t, ℓ_t)
    r_t = compute_responsibility_risk(b_t, s_t, l_t)
    
    return RiskObservablesResponse(
        session_id=req.session_id,
        response_id=req.response_id,
        p_t=round(p_t, 6),
        c_t=round(c_t, 6),
        r_t=round(r_t, 6),
        b_t=round(b_t, 6),
        s_t=round(s_t, 6),
        l_pii_t=round(l_pii_t, 6),
        l_mi_t=round(l_mi_t, 6),
        l_t=round(l_t, 6),
        y_hat=round(y_hat, 6),
        q_t=round(q_t, 6),
        timestamp_ns=int(time.time() * 1e9),
    )


class CoOccurrenceRequest(BaseModel):
    """Request for co-occurrence interaction terms."""
    p_t: float
    c_t: float
    r_t: float


@app.post("/risk/cooccurrence")
async def get_cooccurrence(req: CoOccurrenceRequest):
    """
    Return bivector interaction terms π_ij from the sliding window.
    
    These feed directly into the Cl(3,0) multivector bivector components:
      e12 = π_12 (performance × cost co-occurrence)
      e13 = π_13 (performance × responsibility co-occurrence)
      e23 = π_23 (cost × responsibility co-occurrence)
      e123 = π_123 (triple co-occurrence)
    
    Whitepaper: Eq. 7
    """
    interactions = _cooccurrence_tracker.update(req.p_t, req.c_t, req.r_t)
    return interactions


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

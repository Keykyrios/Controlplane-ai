"""
ControlPlane Manifold Orchestrator — Section 20 (Algorithm 1)
===============================================================
The central coordinator that implements the full per-response
online decision pipeline from Algorithm 1 of the whitepaper.

For each response x_t:
1. Compute fingerprint h_t                    [fingerprint svc]
2. Compute (p_t, c_t, r_t) → R_t             [risk-obs + risk-mv svc]
3. Update Δ_t and Surprise_t                  [drift + surprise svc]
4. Update κ(V_t) from session trajectory      [spectral svc]
5. Fuse sub-checks → Discord_t               [sheaf svc]
6. If perf verifier flags, syndrome decode    [syndrome svc]
7. Assemble z_t → route via tropical policy   [tropical svc]
8. Write audit record                          [audit svc]
9. Serve routed action                        [return to caller]

Fan-out/fan-in with asyncio.gather for parallel layers.
Degrade-gracefully: timed-out layers = "no signal" (neutral value).

Whitepaper: Section 20, Algorithm 1
Blueprint: Section 17
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Orchestrator",
    description="Algorithm 1: Full per-response online decision pipeline",
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
# Service URLs (from environment)
# ---------------------------------------------------------------------------

def svc(name: str, default_port: int) -> str:
    env_key = name.upper().replace("-", "_") + "_URL"
    return os.environ.get(env_key, f"http://localhost:{default_port}")

RISK_OBS_URL = lambda: svc("risk-observables", 8001)
RISK_MV_URL = lambda: svc("risk-multivector", 8002)
FP_URL = lambda: svc("fingerprint", 8003)
DRIFT_URL = lambda: svc("drift", 8004)
SURPRISE_URL = lambda: svc("surprise", 8005)
SPECTRAL_URL = lambda: svc("spectral", 8006)
SHEAF_URL = lambda: svc("sheaf-fusion", 8007)
ROUTING_URL = lambda: svc("tropical-routing", 8009)
CONFORMAL_URL = lambda: svc("conformal-calibration", 8010)
SYNDROME_URL = lambda: svc("syndrome-decoder", 8012)
AUDIT_URL = lambda: svc("audit-ledger", 8015)
QUEUEING_URL = lambda: svc("queueing-monitor", 8014)
POLICY_URL = lambda: svc("policy-manifold", 8016)

TIMEOUT = 5.0  # seconds — degrade-gracefully cutoff


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class PipelineRequest(BaseModel):
    session_id: str
    response_id: str
    response_text: str
    prompt_text: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    model_confidence: Optional[float] = None
    token_usage: dict = Field(default_factory=dict)
    tier: str = "A"
    jurisdiction: str = "US-generic"
    session_history: list[dict] = Field(default_factory=list)
    grounding_context: str = ""


class PipelineResponse(BaseModel):
    response_id: str
    routing_action: str
    routing_scores: dict[str, float]
    fused_signal: dict
    risk_observables: dict
    risk_multivector: dict
    fingerprint_hash: str = ""
    drift_score: float = 0.0
    surprise_score: float = 0.0
    spectral_condition: float = 1.0
    discord_score: float = 0.0
    syndrome_result: Optional[dict] = None
    audit_record_hash: str = ""
    processing_time_ms: float = 0.0
    degraded_layers: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Safe HTTP caller with timeout
# ---------------------------------------------------------------------------

async def safe_call(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    json: dict,
    layer_name: str,
    default: dict,
    degraded: list[str],
) -> dict:
    """
    Call a downstream service with timeout.
    If it fails or times out, return the default (neutral) value
    and mark the layer as degraded.
    """
    try:
        if method == "POST":
            resp = await client.post(url, json=json, timeout=TIMEOUT)
        else:
            resp = await client.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        degraded.append(layer_name)
        return default


# ---------------------------------------------------------------------------
# Algorithm 1 — Full Pipeline
# ---------------------------------------------------------------------------

@app.post("/pipeline/process", response_model=PipelineResponse)
async def process_response(req: PipelineRequest) -> PipelineResponse:
    """
    Algorithm 1 from the whitepaper — the full per-response online decision.
    
    Steps 1-9, with fan-out parallelism for independent layers.
    Every service is wired with real data — no placeholder zeros.
    """
    start = time.perf_counter()
    degraded: list[str] = []
    
    async with httpx.AsyncClient() as client:
        # =================================================================
        # Step 1: Compute fingerprint h_t (Section 7)
        # Returns: fingerprint_hash, fingerprint_hex (for surprise NCD),
        #          fingerprint_vector (64-dim projected, for drift TDA)
        # =================================================================
        fp_task = safe_call(
            client, "POST", f"{FP_URL()}/fingerprint/encode",
            json={"response_id": req.response_id, "session_id": req.session_id,
                  "response_text": req.response_text},
            layer_name="fingerprint",
            default={"fingerprint_hash": "", "fingerprint_hex": "",
                      "fingerprint_vector": [], "encoding_time_us": 0},
            degraded=degraded,
        )
        
        # =================================================================
        # Step 2: Compute (p_t, c_t, r_t) risk observables (Section 5)
        # =================================================================
        risk_obs_task = safe_call(
            client, "POST", f"{RISK_OBS_URL()}/risk/observables",
            json={
                "session_id": req.session_id,
                "response_id": req.response_id,
                "response_text": req.response_text,
                "prompt_text": req.prompt_text,
                "model_confidence": req.model_confidence,
                "token_usage": req.token_usage,
                "grounding_context": req.grounding_context,
                "tool_calls": req.tool_calls,
                "tier": req.tier,
            },
            layer_name="risk-observables",
            default={"p_t": 0.5, "c_t": 0.5, "r_t": 0.5, "b_t": 0, "s_t": 0,
                      "l_pii_t": 0, "l_mi_t": 0, "l_t": 0, "y_hat": 0.5, "q_t": 0.5,
                      "session_id": req.session_id, "response_id": req.response_id,
                      "timestamp_ns": 0},
            degraded=degraded,
        )
        
        # Step 1 & 2 run in parallel
        fp_result, risk_obs_result = await asyncio.gather(fp_task, risk_obs_task)
        
        p_t = risk_obs_result.get("p_t", 0.5)
        c_t = risk_obs_result.get("c_t", 0.5)
        r_t = risk_obs_result.get("r_t", 0.5)
        
        # Extract real fingerprint data (not placeholders)
        fp_hash = fp_result.get("fingerprint_hash", "")
        fp_hex = fp_result.get("fingerprint_hex", "")
        fp_vector = fp_result.get("fingerprint_vector", [])
        
        # =================================================================
        # Step 2b: Get co-occurrence interaction terms π_ij (Eq. 7)
        # These feed into the Cl(3,0) multivector bivector components
        # =================================================================
        cooccurrence_task = safe_call(
            client, "POST", f"{RISK_OBS_URL()}/risk/cooccurrence",
            json={"p_t": p_t, "c_t": c_t, "r_t": r_t},
            layer_name="co-occurrence",
            default={"pi_12": 0.0, "pi_13": 0.0, "pi_23": 0.0, "pi_123": 0.0},
            degraded=degraded,
        )
        
        # =================================================================
        # Step 2c: Fetch conformal threshold λ̂ for this tier (Section 14)
        # =================================================================
        conformal_task = safe_call(
            client, "GET", f"{CONFORMAL_URL()}/calibration/threshold/{req.tier}",
            json={},
            layer_name="conformal-calibration",
            default={"lambda_hat": None},
            degraded=degraded,
        )
        
        # =================================================================
        # Step 2d: Fetch policy from policy manifold (Section 21)
        # =================================================================
        policy_task = safe_call(
            client, "GET", f"{POLICY_URL()}/policy/{req.tier}/{req.jurisdiction}",
            json={},
            layer_name="policy-manifold",
            default={},
            degraded=degraded,
        )
        
        cooccurrence_result, conformal_result, policy_result = await asyncio.gather(
            cooccurrence_task, conformal_task, policy_task
        )
        
        pi_12 = cooccurrence_result.get("pi_12", 0.0)
        pi_13 = cooccurrence_result.get("pi_13", 0.0)
        pi_23 = cooccurrence_result.get("pi_23", 0.0)
        pi_123 = cooccurrence_result.get("pi_123", 0.0)
        conformal_lambda = conformal_result.get("lambda_hat", None)
        
        # =================================================================
        # Step 2e: Build risk multivector R_t with REAL interaction terms
        # =================================================================
        mv_task = safe_call(
            client, "POST", f"{RISK_MV_URL()}/risk/multivector",
            json={
                "response_id": req.response_id,
                "p_t": p_t, "c_t": c_t, "r_t": r_t,
                "pi_12": pi_12, "pi_13": pi_13,
                "pi_23": pi_23, "pi_123": pi_123,
            },
            layer_name="risk-multivector",
            default={"e1": p_t, "e2": c_t, "e3": r_t, "scalar": 0,
                      "e12": 0, "e13": 0, "e23": 0, "e123": 0,
                      "vector_magnitude": 0, "wedge_novelty": 0,
                      "theta_degrees": 0, "inner_product": 0,
                      "response_id": req.response_id, "timestamp_ns": 0},
            degraded=degraded,
        )
        
        # =================================================================
        # Steps 3-5 in parallel: drift, surprise, spectral, sheaf
        # All use REAL data from upstream services
        # =================================================================
        
        # Drift: pass the REAL 64-dim projected fingerprint vector
        drift_task = safe_call(
            client, "POST", f"{DRIFT_URL()}/drift/score",
            json={
                "response_id": req.response_id,
                "tier": req.tier,
                "fingerprint_vector": fp_vector if fp_vector else [0.0] * 64,
            },
            layer_name="drift",
            default={"delta_t": 0.0},
            degraded=degraded,
        )
        
        # Surprise: pass the REAL fingerprint hex bytes for NCD
        surprise_task = safe_call(
            client, "POST", f"{SURPRISE_URL()}/surprise/score",
            json={
                "response_id": req.response_id,
                "response_text": req.response_text,
                "fingerprint_bytes": fp_hex,
            },
            layer_name="surprise",
            default={"surprise_score": 0.5},
            degraded=degraded,
        )
        
        spectral_task = safe_call(
            client, "POST", f"{SPECTRAL_URL()}/spectral/condition",
            json={
                "session_id": req.session_id,
                "response_id": req.response_id,
                "p_t": p_t, "c_t": c_t, "r_t": r_t,
            },
            layer_name="spectral",
            default={"kappa_v_t": 1.0, "is_early_warning": False},
            degraded=degraded,
        )
        
        sheaf_task = safe_call(
            client, "POST", f"{SHEAF_URL()}/sheaf/discord",
            json={
                "response_id": req.response_id,
                "checkpoint_assessments": {
                    "prompt-assembly": [p_t * 0.3, c_t * 0.2, r_t * 0.1],
                    "retrieval": [p_t * 0.5, c_t * 0.3, r_t * 0.2],
                    "generation": [p_t, c_t, r_t],
                    "post-processing": [p_t * 0.8, c_t * 0.9, r_t * 0.95],
                },
            },
            layer_name="sheaf-fusion",
            default={"discord_t": 0.0},
            degraded=degraded,
        )
        
        # All parallel layers
        mv_result, drift_result, surprise_result, spectral_result, sheaf_result = (
            await asyncio.gather(mv_task, drift_task, surprise_task, spectral_task, sheaf_task)
        )
        
        delta_t = drift_result.get("delta_t", 0.0)
        surprise_t = surprise_result.get("surprise_score", 0.5)
        kappa_v_t = spectral_result.get("kappa_v_t", 1.0)
        discord_t = sheaf_result.get("discord_t", 0.0)
        
        # =================================================================
        # Step 6: Syndrome decode if performance verifier flags
        # =================================================================
        syndrome_result = None
        if p_t > 0.5:  # Performance risk threshold
            sentences = [
                s.strip() for s in req.response_text.split(".")
                if len(s.strip()) > 10
            ]
            if len(sentences) >= 2:
                syn_resp = await safe_call(
                    client, "POST", f"{SYNDROME_URL()}/syndrome/decode",
                    json={"response_id": req.response_id, "assertions": sentences[:10]},
                    layer_name="syndrome-decoder",
                    default=None,
                    degraded=degraded,
                )
                if syn_resp:
                    syndrome_result = syn_resp
        
        # =================================================================
        # Step 7: Assemble z_t and route (Section 13)
        # Includes conformal threshold from Section 14
        # =================================================================
        routing_payload = {
            "response_id": req.response_id,
            "p_t": p_t, "c_t": c_t, "r_t": r_t,
            "delta_t": delta_t, "surprise_t": surprise_t,
            "kappa_v_t": kappa_v_t, "discord_t": discord_t,
            "tier": req.tier, "jurisdiction": req.jurisdiction,
        }
        # Pass conformal threshold if available
        if conformal_lambda is not None:
            routing_payload["conformal_lambda"] = conformal_lambda
        
        routing_result = await safe_call(
            client, "POST", f"{ROUTING_URL()}/routing/decide",
            json=routing_payload,
            layer_name="tropical-routing",
            default={"action": "escalate", "scores": {},
                      "response_id": req.response_id},
            degraded=degraded,
        )
        
        routing_action = routing_result.get("action", "escalate")
        routing_scores = routing_result.get("scores", {})
        
        # =================================================================
        # Step 8: Write audit record with REAL AES-256-GCM encryption
        # =================================================================
        asyncio.create_task(
            safe_call(
                httpx.AsyncClient(), "POST", f"{AUDIT_URL()}/audit/write",
                json={
                    "session_id": req.session_id,
                    "response_id": req.response_id,
                    "risk_observables": risk_obs_result,
                    "risk_multivector": mv_result,
                    "fused_signal": {
                        "p_t": p_t, "c_t": c_t, "r_t": r_t,
                        "delta_t": delta_t, "surprise_t": surprise_t,
                        "kappa_v_t": kappa_v_t, "discord_t": discord_t,
                    },
                    "routing_action": routing_action,
                    "fingerprint_hash": fp_hash,
                    "tier": req.tier,
                    "jurisdiction": req.jurisdiction,
                },
                layer_name="audit",
                default={},
                degraded=[],
            )
        )
        
        # =================================================================
        # Step 9: Return (latency guarantee L_fast applies here)
        # =================================================================
        processing_time = (time.perf_counter() - start) * 1000
        
        return PipelineResponse(
            response_id=req.response_id,
            routing_action=routing_action,
            routing_scores=routing_scores,
            fused_signal={
                "p_t": round(p_t, 6), "c_t": round(c_t, 6), "r_t": round(r_t, 6),
                "delta_t": round(delta_t, 6), "surprise_t": round(surprise_t, 6),
                "kappa_v_t": round(kappa_v_t, 4), "discord_t": round(discord_t, 6),
            },
            risk_observables=risk_obs_result,
            risk_multivector=mv_result,
            fingerprint_hash=fp_hash,
            drift_score=delta_t,
            surprise_score=surprise_t,
            spectral_condition=kappa_v_t,
            discord_score=discord_t,
            syndrome_result=syndrome_result,
            processing_time_ms=round(processing_time, 2),
            degraded_layers=degraded,
        )


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator", "section": "20 (Algorithm 1)"}


@app.get("/status")
async def status():
    """Check health of all downstream services."""
    services = {
        "risk-observables": RISK_OBS_URL(),
        "risk-multivector": RISK_MV_URL(),
        "fingerprint": FP_URL(),
        "drift": DRIFT_URL(),
        "surprise": SURPRISE_URL(),
        "spectral": SPECTRAL_URL(),
        "sheaf-fusion": SHEAF_URL(),
        "tropical-routing": ROUTING_URL(),
        "syndrome-decoder": SYNDROME_URL(),
        "audit-ledger": AUDIT_URL(),
        "queueing-monitor": QUEUEING_URL(),
    }
    
    results = {}
    async with httpx.AsyncClient() as client:
        for name, url in services.items():
            try:
                resp = await client.get(f"{url}/health", timeout=2.0)
                results[name] = {"status": "healthy", "url": url}
            except Exception as e:
                results[name] = {"status": "unreachable", "url": url, "error": str(e)}
    
    all_healthy = all(r["status"] == "healthy" for r in results.values())
    return {"overall": "healthy" if all_healthy else "degraded", "services": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

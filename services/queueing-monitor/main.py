"""
Queueing-Theoretic Latency Budget Service — Section 18
========================================================
Implements Equations 44-45: M/M/1 and M/M/c queueing models.

L_fast = 1/(μ_fast - λ)                    (Eq. 44)
L_human = C(c,ρ)/(c·μ_human - φλ)         (Eq. 45)

The two queues are architecturally decoupled: a backlog in L_human
has no coupling into μ_fast.

Whitepaper: Section 18, Eq. 44-45, Appendix B.3
Blueprint: Section 14
"""

from __future__ import annotations

import math
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="ControlPlane Manifold — Queueing Monitor",
    description="Section 18: Eq. 44-45 — M/M/1 and M/M/c latency budget",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def mm1_wait(lmbda: float, mu_fast: float) -> float:
    """L_fast = 1/(μ_fast - λ) — Eq. 44"""
    if mu_fast <= lmbda:
        return float('inf')
    return 1.0 / (mu_fast - lmbda)


def erlang_c(c: int, rho: float) -> float:
    """Standard Erlang-C formula: P(wait > 0)"""
    if rho >= 1.0 or c <= 0:
        return 1.0
    a = c * rho
    num = (a ** c / math.factorial(c)) * (c / (c - a))
    den = sum(a ** k / math.factorial(k) for k in range(c)) + num
    return num / den


def mmc_wait(phi_lambda: float, c: int, mu_human: float) -> float:
    """L_human = C(c,ρ)/(c·μ_human - φλ) — Eq. 45"""
    if c <= 0 or mu_human <= 0:
        return float('inf')
    rho = phi_lambda / (c * mu_human)
    if rho >= 1.0:
        return float('inf')
    C = erlang_c(c, rho)
    denom = c * mu_human - phi_lambda
    if denom <= 0:
        return float('inf')
    return C / denom


# Measured latency tracking
_request_timestamps: list[float] = []
_processing_times: list[float] = []


class QueueingRequest(BaseModel):
    lambda_rate: float = 10.0        # arrival rate (req/s)
    mu_fast: float = 100.0           # fast-path service rate
    mu_human: float = 0.1            # human reviewer rate
    escalation_rate: float = 0.05    # φ = P[escalate]
    num_reviewers: int = 3           # c


class QueueingResponse(BaseModel):
    l_fast_theoretical: float
    l_human_theoretical: float
    l_fast_measured: float
    utilization_fast: float
    utilization_human: float
    erlang_c_probability: float
    queue_stable: bool


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "queueing-monitor", "section": "18"}


@app.post("/queueing/latency", response_model=QueueingResponse)
async def compute_latency(req: QueueingRequest) -> QueueingResponse:
    """Compute theoretical and measured latency budgets. (Eq. 44-45)"""
    l_fast = mm1_wait(req.lambda_rate, req.mu_fast)
    phi_lambda = req.escalation_rate * req.lambda_rate
    l_human = mmc_wait(phi_lambda, req.num_reviewers, req.mu_human)
    
    rho_fast = req.lambda_rate / req.mu_fast if req.mu_fast > 0 else 1.0
    rho_human = phi_lambda / (req.num_reviewers * req.mu_human) if req.mu_human > 0 else 1.0
    ec = erlang_c(req.num_reviewers, min(rho_human, 0.999))
    
    l_fast_measured = sum(_processing_times[-100:]) / max(1, len(_processing_times[-100:])) if _processing_times else l_fast
    
    return QueueingResponse(
        l_fast_theoretical=round(l_fast * 1000, 2),  # ms
        l_human_theoretical=round(l_human * 1000, 2),
        l_fast_measured=round(l_fast_measured * 1000, 2),
        utilization_fast=round(rho_fast, 4),
        utilization_human=round(min(rho_human, 0.999), 4),
        erlang_c_probability=round(ec, 4),
        queue_stable=rho_fast < 1.0 and rho_human < 1.0,
    )


@app.post("/queueing/record")
async def record_processing_time(processing_time_s: float):
    """Record a measured processing time for empirical tracking."""
    _request_timestamps.append(time.time())
    _processing_times.append(processing_time_s)
    if len(_processing_times) > 10000:
        _processing_times.pop(0)
        _request_timestamps.pop(0)
    return {"recorded": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8014)

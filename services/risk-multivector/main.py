"""
Risk Multivector Service — Section 5.2–5.4
============================================
Implements the geometric algebra lift of (p_t, c_t, r_t) into Cl(3,0),
the pairwise bivector interaction terms π_ij (Eq. 7), the trivector
π_123, and the wedge-product novelty alarm (Proposition 5.4).

This is the mathematical core of the ControlPlane Manifold: the claim
that risk is a multivector, not three scalars, and that the interaction
structure carries information no single axis carries alone.

Whitepaper: Section 5.2 (Eq. 5-6), Section 5.3 (worked example),
            Proposition 5.4 (Eq. 8-9)
"""

from __future__ import annotations

import math
import time
from typing import Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Clifford Algebra Cl(3,0) — hand-rolled for zero external dependency
# on the critical path. The `clifford` library is used in tests only.
# ---------------------------------------------------------------------------
# Basis: {1, e1, e2, e3, e12, e13, e23, e123}
# Geometric product: e_i * e_j = -e_j * e_i for i≠j, e_i^2 = 1

app = FastAPI(
    title="ControlPlane Manifold — Risk Multivector",
    description="Section 5.2-5.4: Geometric algebra lift, interaction terms, wedge novelty",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class MultivectorRequest(BaseModel):
    """Input: the three risk observables and interaction terms."""
    response_id: str
    p_t: float
    c_t: float
    r_t: float
    pi_12: float = 0.0  # perf×cost co-occurrence excess, Eq. 7
    pi_13: float = 0.0  # perf×resp co-occurrence excess (hallucination×privacy)
    pi_23: float = 0.0  # cost×resp co-occurrence excess
    pi_123: float = 0.0  # triple interaction excess
    prev_p: Optional[float] = None  # R_{t-1} for wedge novelty
    prev_c: Optional[float] = None
    prev_r: Optional[float] = None


class MultivectorResponse(BaseModel):
    """The full risk multivector and derived quantities."""
    response_id: str
    # 8 Cl(3,0) components
    scalar: float = 0.0
    e1: float  # p_t
    e2: float  # c_t
    e3: float  # r_t
    e12: float  # π_12
    e13: float  # π_13
    e23: float  # π_23
    e123: float  # π_123
    # Derived quantities
    vector_magnitude: float  # ||R_t|| (vector part)
    wedge_novelty: float  # ||R_t ∧ R_{t-1}||, Proposition 5.4
    theta_degrees: float  # rotation angle between consecutive risk vectors
    inner_product: float  # R_t · R_{t-1}
    timestamp_ns: int


# ---------------------------------------------------------------------------
# Section 5.2 — Build the Risk Multivector
# ---------------------------------------------------------------------------

def build_multivector(
    p: float, c: float, r: float,
    pi12: float = 0.0, pi13: float = 0.0,
    pi23: float = 0.0, pi123: float = 0.0,
) -> dict[str, float]:
    """
    Construct R_t ∈ Cl(3,0) from the three risk observables and
    their pairwise/triple interaction excesses.
    
    R_t = p·e1 + c·e2 + r·e3 + π_12·e12 + π_13·e13 + π_23·e23 + π_123·e123
    
    Whitepaper Eq. 5-6.
    """
    return {
        "scalar": 0.0,
        "e1": p,
        "e2": c,
        "e3": r,
        "e12": pi12,
        "e13": pi13,
        "e23": pi23,
        "e123": pi123,
    }


def vector_magnitude(p: float, c: float, r: float) -> float:
    """||R_t|| = sqrt(p² + c² + r²) — magnitude of the vector part."""
    return math.sqrt(p * p + c * c + r * r)


# ---------------------------------------------------------------------------
# Proposition 5.4 — Wedge Product Novelty Alarm
# ---------------------------------------------------------------------------

def wedge_novelty(
    R_vec_t: np.ndarray,
    R_vec_tm1: np.ndarray,
) -> tuple[float, float, float]:
    """
    Compute the wedge-product novelty alarm.
    
    ||R_t ∧ R_{t-1}|| = ||R_t|| · ||R_{t-1}|| · sin(θ_t)
    
    This is nonzero exactly when the risk vector has ROTATED in
    the (p,c,r) space between t-1 and t, i.e. when a qualitatively
    new failure mode combination has appeared.
    
    Returns: (wedge_magnitude, theta_degrees, inner_product)
    
    Whitepaper: Proposition 5.4, Eq. 8-9.
    """
    norm_t = float(np.linalg.norm(R_vec_t))
    norm_tm1 = float(np.linalg.norm(R_vec_tm1))
    
    if norm_t < 1e-12 or norm_tm1 < 1e-12:
        return 0.0, 0.0, 0.0
    
    inner = float(np.dot(R_vec_t, R_vec_tm1))
    cos_theta = inner / (norm_t * norm_tm1)
    # Clamp for numerical stability
    cos_theta = max(-1.0, min(1.0, cos_theta))
    sin_theta = math.sqrt(max(0.0, 1.0 - cos_theta * cos_theta))
    theta_degrees = math.degrees(math.acos(cos_theta))
    
    wedge_mag = norm_t * norm_tm1 * sin_theta
    
    return wedge_mag, theta_degrees, inner


# ---------------------------------------------------------------------------
# Geometric Product Decomposition (Proposition 5.4, full)
# ---------------------------------------------------------------------------

def geometric_product_decomposition(
    R_t: np.ndarray,
    R_tm1: np.ndarray,
) -> dict:
    """
    Full geometric product decomposition R_t · R_{t-1}:
    
    R_t R_{t-1} = R_t · R_{t-1} + R_t ∧ R_{t-1}
    
    Inner product (symmetric): measures persistence of risk direction.
    Outer product (antisymmetric bivector): measures rotation to new mode.
    """
    inner = float(np.dot(R_t, R_tm1))
    
    # Cross product in 3D is the Hodge dual of the wedge product
    cross = np.cross(R_t, R_tm1)
    wedge_mag = float(np.linalg.norm(cross))
    
    # The three bivector components of the wedge
    # R_t ∧ R_{t-1} = (p_t c_{t-1} - c_t p_{t-1})e12 + ...
    e12_component = R_t[0] * R_tm1[1] - R_t[1] * R_tm1[0]
    e13_component = R_t[0] * R_tm1[2] - R_t[2] * R_tm1[0]
    e23_component = R_t[1] * R_tm1[2] - R_t[2] * R_tm1[1]
    
    return {
        "inner_product": inner,
        "wedge_magnitude": wedge_mag,
        "wedge_e12": float(e12_component),
        "wedge_e13": float(e13_component),
        "wedge_e23": float(e23_component),
    }


# ---------------------------------------------------------------------------
# Session history for tracking consecutive multivectors
# ---------------------------------------------------------------------------

_session_history: dict[str, np.ndarray] = {}


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "risk-multivector", "section": "5.2-5.4"}


@app.post("/risk/multivector", response_model=MultivectorResponse)
async def compute_multivector(req: MultivectorRequest) -> MultivectorResponse:
    """
    Compute the full risk multivector R_t and the wedge novelty alarm.
    
    Whitepaper: Section 5.2 (Eq. 5-6), Proposition 5.4 (Eq. 8-9)
    """
    mv = build_multivector(
        req.p_t, req.c_t, req.r_t,
        req.pi_12, req.pi_13, req.pi_23, req.pi_123,
    )
    
    vec_mag = vector_magnitude(req.p_t, req.c_t, req.r_t)
    
    # Wedge novelty
    R_vec_t = np.array([req.p_t, req.c_t, req.r_t])
    
    if req.prev_p is not None and req.prev_c is not None and req.prev_r is not None:
        R_vec_tm1 = np.array([req.prev_p, req.prev_c, req.prev_r])
    else:
        # Use session history
        session_key = req.response_id.rsplit("-", 1)[0] if "-" in req.response_id else "default"
        R_vec_tm1 = _session_history.get(session_key, np.zeros(3))
    
    wedge_mag, theta_deg, inner = wedge_novelty(R_vec_t, R_vec_tm1)
    
    # Update session history
    session_key = req.response_id.rsplit("-", 1)[0] if "-" in req.response_id else "default"
    _session_history[session_key] = R_vec_t
    
    return MultivectorResponse(
        response_id=req.response_id,
        scalar=mv["scalar"],
        e1=mv["e1"],
        e2=mv["e2"],
        e3=mv["e3"],
        e12=mv["e12"],
        e13=mv["e13"],
        e23=mv["e23"],
        e123=mv["e123"],
        vector_magnitude=round(vec_mag, 6),
        wedge_novelty=round(wedge_mag, 6),
        theta_degrees=round(theta_deg, 1),
        inner_product=round(inner, 6),
        timestamp_ns=int(time.time() * 1e9),
    )


@app.post("/risk/geometric-product")
async def compute_geometric_product(
    p_t: float, c_t: float, r_t: float,
    p_tm1: float, c_tm1: float, r_tm1: float,
):
    """
    Full geometric product decomposition between two consecutive
    risk vectors. Used for visualization (Figure 1 reproduction).
    """
    R_t = np.array([p_t, c_t, r_t])
    R_tm1 = np.array([p_tm1, c_tm1, r_tm1])
    
    decomp = geometric_product_decomposition(R_t, R_tm1)
    wedge_mag, theta_deg, inner = wedge_novelty(R_t, R_tm1)
    
    return {
        **decomp,
        "wedge_novelty": round(wedge_mag, 6),
        "theta_degrees": round(theta_deg, 1),
        "norm_R_t": round(float(np.linalg.norm(R_t)), 6),
        "norm_R_tm1": round(float(np.linalg.norm(R_tm1)), 6),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

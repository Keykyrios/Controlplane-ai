"""
Non-Hermitian Spectral Early Warning Service — Section 10 (+ 10.1 agentic extension)
======================================================================================
Implements Equations 20-23 and the agentic extension (Eq. 24).

J_t = ∂s_{t+1}/∂s_t  — empirical risk-propagator Jacobian (non-normal)
κ(V_t) = ||V_t|| · ||V_t^{-1}||  — eigenvector condition number

A rising κ(V_t) is the early-warning signature of an imminent hallucination
cascade: the mathematical signature that the session is approaching a
qualitative regime change (exceptional point) before ||s_t|| crosses
any fixed threshold.

Section 10.1: Extension to agent action graphs via block Jacobian J^A_t.

Whitepaper: Section 10, Eq. 20-23; Section 10.1 (agentic), Eq. 24
Blueprint: Section 6
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Non-Hermitian Spectral Early Warning",
    description="Section 10: Eq. 20-23 — spectral condition number κ(V_t)",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_SESSION_LENGTH = 4  # Minimum turns for Jacobian estimation


# ---------------------------------------------------------------------------
# Eq. 20 — Empirical Risk-Propagator Jacobian
# ---------------------------------------------------------------------------

def estimate_jacobian(session_states: list[np.ndarray]) -> np.ndarray:
    """
    Finite-difference Jacobian of s_{t+1} wrt s_t over a session.
    
    J_t = ∂s_{t+1}/∂s_t ∈ R^{3×3}
    
    Because generation is causal and asymmetric, J_t is generically
    non-normal: J_t J_t^T ≠ J_t^T J_t.
    
    Whitepaper: Eq. 20
    """
    states = np.array(session_states)  # (T, 3)
    
    if len(states) < MIN_SESSION_LENGTH:
        return np.eye(3)  # Not enough data
    
    # Finite differences
    diffs_in = np.diff(states[:-1], axis=0)   # s_t - s_{t-1}
    diffs_out = np.diff(states[1:], axis=0)   # s_{t+1} - s_t
    
    # Least-squares fit: diffs_out ≈ J · diffs_in
    # J = (diffs_out^T · diffs_in) · (diffs_in^T · diffs_in)^{-1}
    try:
        J, residuals, rank, sv = np.linalg.lstsq(diffs_in, diffs_out, rcond=None)
        return J.T  # 3×3
    except np.linalg.LinAlgError:
        return np.eye(3)


# ---------------------------------------------------------------------------
# Eq. 22 — Eigenvector Condition Number κ(V_t)
# ---------------------------------------------------------------------------

def condition_number(J: np.ndarray) -> float:
    """
    Compute the eigenvector matrix condition number κ(V_t).
    
    κ(V_t) = ||V_t|| · ||V_t^{-1}||
    
    where J_t = V_t Λ_t V_t^{-1} is the eigendecomposition.
    
    As J_t approaches an exceptional point (eigenvalue coalescence),
    V_t approaches singularity and κ(V_t) → ∞.
    
    Whitepaper: Eq. 22
    """
    try:
        eigvals, eigvecs = np.linalg.eig(J)
        # κ(V) = cond(eigenvector matrix)
        kappa = float(np.linalg.cond(eigvecs))
        return kappa
    except np.linalg.LinAlgError:
        return float('inf')


def pseudospectral_radius(J: np.ndarray, epsilon: float = 0.1) -> float:
    """
    Estimate the ε-pseudospectral radius.
    
    Λ_ε(J) = {z ∈ C : ||(zI - J)^{-1}|| ≥ ε^{-1}}
    
    The extent of the pseudospectrum beyond eigenvalues quantifies
    the potential for transient amplification.
    
    Whitepaper: Eq. 21
    """
    eigvals = np.linalg.eigvals(J)
    spectral_radius = float(np.max(np.abs(eigvals)))
    
    # Kreiss constant approximation for non-normal matrices
    try:
        # Sample resolvent norm at points near the spectral radius
        test_points = spectral_radius + np.array([0.1, 0.2, 0.5]) * epsilon
        max_resolvent = 0.0
        for z in test_points:
            resolvent = np.linalg.inv(z * np.eye(J.shape[0]) - J)
            norm = float(np.linalg.norm(resolvent, ord=2))
            max_resolvent = max(max_resolvent, norm)
        
        # Pseudospectral radius ≈ spectral radius + ε where resolvent blows up
        return spectral_radius + epsilon * max_resolvent
    except np.linalg.LinAlgError:
        return spectral_radius


# ---------------------------------------------------------------------------
# Section 10.1 — Agentic Extension (Block Jacobian)
# ---------------------------------------------------------------------------

def estimate_block_jacobian(
    agent_states: dict[str, list[np.ndarray]],
    agent_graph: list[tuple[str, str]],
) -> np.ndarray:
    """
    Build the block-structured propagator J^A_t for an agent action graph.
    
    J^A_t = [J_{11} J_{12} ...]
            [J_{21} J_{22} ...]
            [...              ]
    
    where J_{ab} = ∂s^{(b)}_{t+1}/∂s^{(a)}_t
    
    This is generically MORE non-normal than a single-thread Jacobian,
    since the off-diagonal blocks J_{ab} for a≠b are exactly the
    cross-agent influence terms that the trajectory-collapse literature
    identifies as the mechanism of silent error amplification.
    
    Whitepaper: Eq. 24
    """
    agents = list(agent_states.keys())
    n_agents = len(agents)
    dim = 3  # (p, c, r) per agent
    
    J_block = np.zeros((n_agents * dim, n_agents * dim))
    
    for a_idx, agent_a in enumerate(agents):
        states_a = agent_states[agent_a]
        if len(states_a) < 2:
            J_block[a_idx*dim:(a_idx+1)*dim, a_idx*dim:(a_idx+1)*dim] = np.eye(dim)
            continue
        
        # Diagonal block: self-influence
        J_self = estimate_jacobian(states_a)
        J_block[a_idx*dim:(a_idx+1)*dim, a_idx*dim:(a_idx+1)*dim] = J_self
        
        # Off-diagonal blocks: cross-agent influence
        for b_idx, agent_b in enumerate(agents):
            if a_idx == b_idx:
                continue
            if (agent_a, agent_b) in agent_graph or (agent_b, agent_a) in agent_graph:
                states_b = agent_states[agent_b]
                if len(states_a) >= 2 and len(states_b) >= 2:
                    # Cross-agent Jacobian via finite differences
                    min_len = min(len(states_a), len(states_b))
                    if min_len >= 3:
                        sa = np.array(states_a[:min_len])
                        sb = np.array(states_b[:min_len])
                        diffs_a = np.diff(sa[:-1], axis=0)
                        diffs_b = np.diff(sb[1:], axis=0)
                        try:
                            J_cross, _, _, _ = np.linalg.lstsq(diffs_a, diffs_b, rcond=None)
                            J_block[b_idx*dim:(b_idx+1)*dim, a_idx*dim:(a_idx+1)*dim] = J_cross.T
                        except np.linalg.LinAlgError:
                            pass
    
    return J_block


# ---------------------------------------------------------------------------
# Toy Two-Eigenvalue Model (Figure 4 reproduction)
# ---------------------------------------------------------------------------

def toy_exceptional_point_model(g: float) -> dict:
    """
    Minimal two-eigenvalue toy model for Figure 4.
    
    J_g = [[1, g], [g, 2]]  (non-Hermitian for g ≠ 0)
    
    As g increases, eigenvalues approach coalescence at the
    exceptional point, and κ(V_g) → ∞.
    """
    J_g = np.array([[1.0, g], [g, 2.0]])
    
    eigvals = np.linalg.eigvals(J_g)
    kappa = condition_number(J_g)
    
    # Check non-normality
    commutator = J_g @ J_g.T - J_g.T @ J_g
    non_normality = float(np.linalg.norm(commutator, 'fro'))
    
    return {
        "g": g,
        "eigenvalues_real": [float(e.real) for e in eigvals],
        "eigenvalues_imag": [float(e.imag) for e in eigvals],
        "kappa_V": kappa,
        "non_normality": non_normality,
        "is_near_exceptional_point": kappa > 100,
    }


# ---------------------------------------------------------------------------
# Session State Management
# ---------------------------------------------------------------------------

_session_states: dict[str, list[np.ndarray]] = {}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class SpectralRequest(BaseModel):
    session_id: str
    response_id: str
    p_t: float
    c_t: float
    r_t: float
    turn_index: int = -1


class SpectralResponse(BaseModel):
    response_id: str
    kappa_v_t: float  # κ(V_t)
    spectral_radius: float
    eigenvalues_real: list[float]
    eigenvalues_imag: list[float]
    non_normality: float
    session_length: int
    is_early_warning: bool


class AgenticSpectralRequest(BaseModel):
    """Request for agentic multi-agent spectral analysis."""
    session_id: str
    agent_states: dict[str, list[list[float]]]  # agent_id -> list of [p, c, r]
    agent_graph: list[list[str]]  # edges [(a, b), ...]


class AgenticSpectralResponse(BaseModel):
    session_id: str
    kappa_v_agentic: float
    block_jacobian_size: int
    eigenvalues_real: list[float]
    eigenvalues_imag: list[float]
    is_early_warning: bool


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "spectral", "section": "10"}


@app.post("/spectral/condition", response_model=SpectralResponse)
async def compute_spectral_condition(req: SpectralRequest) -> SpectralResponse:
    """
    Compute the eigenvector condition number κ(V_t) for a session.
    
    Whitepaper: Section 10, Eq. 20-22
    """
    state = np.array([req.p_t, req.c_t, req.r_t])
    
    if req.session_id not in _session_states:
        _session_states[req.session_id] = []
    _session_states[req.session_id].append(state)
    
    session = _session_states[req.session_id]
    
    if len(session) < MIN_SESSION_LENGTH:
        return SpectralResponse(
            response_id=req.response_id,
            kappa_v_t=1.0,
            spectral_radius=0.0,
            eigenvalues_real=[0.0],
            eigenvalues_imag=[0.0],
            non_normality=0.0,
            session_length=len(session),
            is_early_warning=False,
        )
    
    J = estimate_jacobian(session)
    kappa = condition_number(J)
    eigvals = np.linalg.eigvals(J)
    spectral_radius = float(np.max(np.abs(eigvals)))
    
    # Non-normality measure: ||JJ^T - J^TJ||_F
    commutator = J @ J.T - J.T @ J
    non_normality = float(np.linalg.norm(commutator, 'fro'))
    
    # Early warning: κ(V_t) is rising and exceeds threshold
    is_warning = kappa > 50 or (len(session) > 5 and kappa > 10)
    
    return SpectralResponse(
        response_id=req.response_id,
        kappa_v_t=round(kappa, 4),
        spectral_radius=round(spectral_radius, 6),
        eigenvalues_real=[round(float(e.real), 6) for e in eigvals],
        eigenvalues_imag=[round(float(e.imag), 6) for e in eigvals],
        non_normality=round(non_normality, 6),
        session_length=len(session),
        is_early_warning=is_warning,
    )


@app.post("/spectral/agentic", response_model=AgenticSpectralResponse)
async def compute_agentic_spectral(req: AgenticSpectralRequest) -> AgenticSpectralResponse:
    """
    Compute the agentic block-Jacobian condition number κ(V^A_t).
    
    Whitepaper: Section 10.1, Eq. 24
    """
    agent_states = {
        k: [np.array(s) for s in v]
        for k, v in req.agent_states.items()
    }
    agent_graph = [(e[0], e[1]) for e in req.agent_graph]
    
    J_block = estimate_block_jacobian(agent_states, agent_graph)
    kappa = condition_number(J_block)
    eigvals = np.linalg.eigvals(J_block)
    
    is_warning = kappa > 100  # Higher threshold for multi-agent
    
    return AgenticSpectralResponse(
        session_id=req.session_id,
        kappa_v_agentic=round(kappa, 4),
        block_jacobian_size=J_block.shape[0],
        eigenvalues_real=[round(float(e.real), 6) for e in eigvals[:10]],
        eigenvalues_imag=[round(float(e.imag), 6) for e in eigvals[:10]],
        is_early_warning=is_warning,
    )


@app.get("/spectral/toy-model")
async def toy_model(g_values: str = "0.0,0.2,0.4,0.6,0.8,0.9,0.95,0.99,1.0"):
    """
    Run the toy two-eigenvalue exceptional-point model for Figure 4.
    """
    gs = [float(g) for g in g_values.split(",")]
    results = [toy_exceptional_point_model(g) for g in gs]
    return {"model": "toy_exceptional_point", "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

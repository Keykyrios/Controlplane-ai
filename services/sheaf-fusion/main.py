"""
Sheaf-Theoretic Fusion Service — Section 11
=============================================
Implements Definition 11.1, Equations 25-28, and Proposition B.1.

The pipeline sheaf F assigns a risk-assessment space F(v) to each
pipeline checkpoint v, restriction maps F_{v◁e} between adjacent
checkpoints, and measures global consistency via the sheaf Laplacian:

Discord_t = x_t^T L_F x_t = ||δx_t||^2

Discord is 0 when all sub-checks agree, and positive when they disagree,
surfacing failures that independent, unfused checks are structurally blind to.

Whitepaper: Section 11, Eq. 25-28, Proposition B.1, Appendix B.1
Blueprint: Section 7
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Sheaf-Theoretic Fusion",
    description="Section 11: Eq. 25-28 — sheaf Laplacian, pipeline discord",
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
# Pipeline Checkpoints (Section 11)
# ---------------------------------------------------------------------------
DEFAULT_CHECKPOINTS = [
    "prompt-assembly",
    "retrieval",
    "tool-call",
    "generation",
    "post-processing",
]

DEFAULT_EDGES = [
    ("prompt-assembly", "retrieval"),
    ("retrieval", "tool-call"),
    ("retrieval", "generation"),
    ("tool-call", "generation"),
    ("generation", "post-processing"),
]


# ---------------------------------------------------------------------------
# Definition 11.1 — Pipeline Sheaf
# ---------------------------------------------------------------------------

class PipelineSheaf:
    """
    A cellular sheaf F on the pipeline graph G = (V, E).
    
    Assigns:
    - F(v): finite-dimensional real inner-product space to each vertex
    - F(e): space to each edge
    - F_{v◁e}: linear restriction map for each incident pair
    
    Following Hansen and Ghrist [5,6].
    
    Whitepaper: Definition 11.1
    """
    
    def __init__(
        self,
        vertices: list[str],
        edges: list[tuple[str, str]],
        stalk_dim: int = 3,
    ):
        self.vertices = vertices
        self.edges = edges
        self.stalk_dim = stalk_dim  # dim F(v) for all v
        
        # Restriction maps F_{v◁e}: F(v) → F(e)
        # Initially identity (or learned linear maps if checkpoints
        # report in different sub-check output spaces)
        self.restriction_maps: dict[tuple[str, tuple[str, str]], np.ndarray] = {}
        self._init_restriction_maps()
    
    def _init_restriction_maps(self):
        """Initialize restriction maps as identity matrices."""
        for u, v in self.edges:
            edge = (u, v)
            # F_{u◁e} and F_{v◁e} — maps from vertex stalk to edge stalk
            self.restriction_maps[(u, edge)] = np.eye(self.stalk_dim)
            self.restriction_maps[(v, edge)] = np.eye(self.stalk_dim)
    
    def coboundary(self, x: dict[str, np.ndarray]) -> np.ndarray:
        """
        Compute the coboundary map δ: C^0(G; F) → C^1(G; F).
        
        (δx)_e = F_{v◁e}(x_v) - F_{u◁e}(x_u)
        
        for each edge e = (u, v).
        
        Whitepaper: Below Definition 11.1
        """
        rows = []
        for u, v in self.edges:
            edge = (u, v)
            Fu = self.restriction_maps.get((u, edge), np.eye(self.stalk_dim))
            Fv = self.restriction_maps.get((v, edge), np.eye(self.stalk_dim))
            
            xu = x.get(u, np.zeros(self.stalk_dim))
            xv = x.get(v, np.zeros(self.stalk_dim))
            
            # (δx)_e = F_{v◁e}(x_v) - F_{u◁e}(x_u)
            delta_e = Fv @ xv - Fu @ xu
            rows.append(delta_e)
        
        if not rows:
            return np.zeros(self.stalk_dim)
        return np.concatenate(rows)
    
    def laplacian_quadratic_form(self, x: dict[str, np.ndarray]) -> float:
        """
        Compute the sheaf Laplacian quadratic form.
        
        Discord_t = x^T L_F x = ||δx||^2
        
        This is the pipeline discord score, Eq. 28.
        Whitepaper: Eq. 28
        """
        dx = self.coboundary(x)
        return float(dx @ dx)  # ||δx||^2 ≥ 0
    
    def build_laplacian_matrix(self) -> np.ndarray:
        """
        Build the full sheaf Laplacian matrix L_F = δ^T δ.
        
        L_F ∈ R^{n×n} where n = Σ_v dim F(v)
        
        Whitepaper: Eq. 27
        """
        n = len(self.vertices) * self.stalk_dim
        m = len(self.edges) * self.stalk_dim
        
        # Build coboundary matrix δ
        delta = np.zeros((m, n))
        
        vertex_idx = {v: i for i, v in enumerate(self.vertices)}
        
        for e_idx, (u, v) in enumerate(self.edges):
            edge = (u, v)
            u_idx = vertex_idx[u]
            v_idx = vertex_idx[v]
            
            Fu = self.restriction_maps.get((u, edge), np.eye(self.stalk_dim))
            Fv = self.restriction_maps.get((v, edge), np.eye(self.stalk_dim))
            
            row_start = e_idx * self.stalk_dim
            
            # -F_{u◁e} block
            delta[row_start:row_start + self.stalk_dim,
                  u_idx * self.stalk_dim:(u_idx + 1) * self.stalk_dim] = -Fu
            
            # +F_{v◁e} block
            delta[row_start:row_start + self.stalk_dim,
                  v_idx * self.stalk_dim:(v_idx + 1) * self.stalk_dim] = Fv
        
        # L_F = δ^T δ
        return delta.T @ delta
    
    def recalibrate_restriction_maps(
        self,
        calibration_data: list[dict[str, np.ndarray]],
        learning_rate: float = 0.01,
    ):
        """
        "Learning to lie" — online restriction-map re-estimation.
        
        Nudge F_{v◁e} toward reducing average discord on a
        labeled-consistent calibration batch.
        
        Flag any checkpoint whose map has drifted far from identity
        as a candidate for drift-svc's attention.
        
        Whitepaper: End of Section 11
        """
        for x in calibration_data:
            dx = self.coboundary(x)
            
            # Gradient descent on ||δx||^2 w.r.t. restriction maps
            for e_idx, (u, v) in enumerate(self.edges):
                edge = (u, v)
                delta_e = dx[e_idx * self.stalk_dim:(e_idx + 1) * self.stalk_dim]
                
                xu = x.get(u, np.zeros(self.stalk_dim))
                xv = x.get(v, np.zeros(self.stalk_dim))
                
                # Gradient w.r.t. F_{u◁e}: -2 · δ_e · x_u^T
                grad_Fu = -2 * np.outer(delta_e, xu) * (-1)  # negative sign from coboundary
                # Gradient w.r.t. F_{v◁e}: 2 · δ_e · x_v^T
                grad_Fv = 2 * np.outer(delta_e, xv)
                
                self.restriction_maps[(u, edge)] -= learning_rate * grad_Fu
                self.restriction_maps[(v, edge)] -= learning_rate * grad_Fv
    
    def get_drifted_checkpoints(self, threshold: float = 0.5) -> list[str]:
        """
        Identify checkpoints whose restriction maps have drifted
        far from identity — candidates for recalibration.
        """
        drifted = set()
        for (vertex, edge), F in self.restriction_maps.items():
            deviation = float(np.linalg.norm(F - np.eye(self.stalk_dim), 'fro'))
            if deviation > threshold:
                drifted.add(vertex)
        return list(drifted)


# ---------------------------------------------------------------------------
# Global Sheaf Instance
# ---------------------------------------------------------------------------

_sheaf = PipelineSheaf(
    vertices=DEFAULT_CHECKPOINTS,
    edges=DEFAULT_EDGES,
    stalk_dim=3,  # (p, c, r) per checkpoint
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class DiscordRequest(BaseModel):
    """Input: local risk assessments from each pipeline checkpoint."""
    response_id: str
    checkpoint_assessments: dict[str, list[float]]
    # e.g. {"prompt-assembly": [0.1, 0.2, 0.05], "generation": [0.8, 0.3, 0.7]}


class DiscordResponse(BaseModel):
    """Output: the pipeline discord score and diagnostics."""
    response_id: str
    discord_t: float  # ||δx||^2 — Eq. 28
    coboundary_norm: float
    per_edge_discord: dict[str, float]
    drifted_checkpoints: list[str]
    computation_time_us: float


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sheaf-fusion", "section": "11"}


@app.post("/sheaf/discord", response_model=DiscordResponse)
async def compute_discord(req: DiscordRequest) -> DiscordResponse:
    """
    Compute the pipeline discord score Discord_t = x_t^T L_F x_t.
    
    Discord is 0 when all sub-checks agree on overlapping claims,
    and positive when they disagree — surfacing exactly the class
    of failure that independent checks are structurally blind to.
    
    Whitepaper: Section 11, Eq. 28
    """
    start = time.perf_counter_ns()
    
    # Build cochain from checkpoint assessments
    x = {}
    for checkpoint, values in req.checkpoint_assessments.items():
        x[checkpoint] = np.array(values[:_sheaf.stalk_dim])
    
    # Fill missing checkpoints with zeros
    for v in _sheaf.vertices:
        if v not in x:
            x[v] = np.zeros(_sheaf.stalk_dim)
    
    # Compute discord
    discord_t = _sheaf.laplacian_quadratic_form(x)
    
    # Per-edge discord for diagnostics
    per_edge = {}
    for u, v in _sheaf.edges:
        edge = (u, v)
        Fu = _sheaf.restriction_maps.get((u, edge), np.eye(_sheaf.stalk_dim))
        Fv = _sheaf.restriction_maps.get((v, edge), np.eye(_sheaf.stalk_dim))
        xu = x.get(u, np.zeros(_sheaf.stalk_dim))
        xv = x.get(v, np.zeros(_sheaf.stalk_dim))
        delta_e = Fv @ xv - Fu @ xu
        per_edge[f"{u}->{v}"] = round(float(delta_e @ delta_e), 6)
    
    # Coboundary norm
    dx = _sheaf.coboundary(x)
    coboundary_norm = float(np.linalg.norm(dx))
    
    # Check for drifted checkpoints
    drifted = _sheaf.get_drifted_checkpoints()
    
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    
    return DiscordResponse(
        response_id=req.response_id,
        discord_t=round(discord_t, 6),
        coboundary_norm=round(coboundary_norm, 6),
        per_edge_discord=per_edge,
        drifted_checkpoints=drifted,
        computation_time_us=round(elapsed_us, 2),
    )


@app.get("/sheaf/laplacian")
async def get_laplacian():
    """Return the full sheaf Laplacian matrix L_F for inspection."""
    L = _sheaf.build_laplacian_matrix()
    eigvals = np.linalg.eigvalsh(L)
    return {
        "matrix": L.tolist(),
        "shape": list(L.shape),
        "eigenvalues": [round(float(e), 6) for e in eigvals],
        "is_psd": bool(np.all(eigvals >= -1e-10)),
        "kernel_dimension": int(np.sum(np.abs(eigvals) < 1e-8)),
    }


@app.post("/sheaf/recalibrate")
async def recalibrate(calibration_data: list[dict[str, list[float]]]):
    """
    Re-estimate restriction maps from labeled-consistent data.
    
    'Learning to lie' extension — Section 11.
    """
    data = [
        {k: np.array(v) for k, v in item.items()}
        for item in calibration_data
    ]
    _sheaf.recalibrate_restriction_maps(data)
    drifted = _sheaf.get_drifted_checkpoints()
    return {"recalibrated": True, "drifted_checkpoints": drifted}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

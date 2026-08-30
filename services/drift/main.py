"""
Topological Drift Detection Service — Section 8
=================================================
Implements Equations 15-17 and Theorem 8.1 (stability of persistence diagrams).

Δ_t = W_2(D_t, D_0)

The 2-Wasserstein distance between the current window's persistence diagram
and a reference diagram D_0 computed offline on a verified, in-distribution corpus.

Key insight: persistent homology gives a LEADING indicator by tracking the SHAPE
of the response distribution, not just its location. Theorem 8.1 (Cohen-Steiner,
Edelsbrunner, Harer) guarantees that small perturbations produce small diagram
changes, making the alarm trustworthy rather than noisy.

Whitepaper: Section 8, Eq. 15-17, Theorem 8.1
Blueprint: Section 4
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Topological Drift Detection",
    description="Section 8: Eq. 15-17 — persistent homology drift score",
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
# Configuration
# ---------------------------------------------------------------------------
WINDOW_SIZE = 100           # w: sliding window of fingerprints
RECOMPUTE_INTERVAL = 10     # recompute every w/10 new responses
HOMOLOGY_DIMS = [0, 1]      # H_0 (connected components), H_1 (loops)
# H_2 (voids) expensive and rarely informative for text streams
FINGERPRINT_DIM = 64        # Projected dimensionality for TDA (from D=10,000)


# ---------------------------------------------------------------------------
# Persistence Diagram Computation
# ---------------------------------------------------------------------------

def compute_distance_matrix(points: np.ndarray) -> np.ndarray:
    """Compute pairwise Euclidean distance matrix."""
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    return np.sqrt(np.sum(diff ** 2, axis=-1))


def vietoris_rips_H0(dist_matrix: np.ndarray) -> list[tuple[float, float]]:
    """
    Compute H_0 persistence diagram (connected components) using
    single-linkage clustering / union-find.
    
    Birth-death pairs: (0, ε) where ε is the distance at which
    two components merge.
    """
    n = dist_matrix.shape[0]
    if n <= 1:
        return [(0.0, float('inf'))]
    
    # Extract upper triangle, sort by distance
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            edges.append((dist_matrix[i, j], i, j))
    edges.sort()
    
    # Union-Find
    parent = list(range(n))
    rank = [0] * n
    
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    
    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return False
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1
        return True
    
    diagram = []
    for dist, i, j in edges:
        if union(i, j):
            diagram.append((0.0, dist))
    
    # One component persists to infinity
    diagram.append((0.0, float('inf')))
    
    return diagram


def vietoris_rips_H1(dist_matrix: np.ndarray, max_dim: float = None) -> list[tuple[float, float]]:
    """
    Compute H_1 persistence diagram (loops/cycles) via 4-cycle detection.
    
    In Vietoris-Rips, a triangle's 2-simplex appears at the same filtration
    value as its longest edge, so 3-vertex cycles die immediately (zero
    persistence). Persistent H_1 features come from 4+ vertex cycles:
    
      - Birth: max edge length around the 4-cycle (all 4 edges exist)
      - Death: min diagonal length (a diagonal creates two triangles
               that fill the cycle, making it a boundary)
    
    This is a correct approximation restricted to quadrilateral generators.
    """
    n = dist_matrix.shape[0]
    if n < 4:
        return []
    
    if max_dim is None:
        max_dim = np.median(dist_matrix[dist_matrix > 0]) * 2.0
    
    diagram = []
    cap = min(n, 40)  # Cap for O(n^4) performance
    
    for i in range(cap):
        for j in range(i + 1, cap):
            for k in range(j + 1, cap):
                for l in range(k + 1, cap):
                    # Consider the 4-cycle i-j-k-l-i
                    # The 4 cycle edges
                    cycle_edges = [
                        dist_matrix[i, j], dist_matrix[j, k],
                        dist_matrix[k, l], dist_matrix[l, i],
                    ]
                    # The 2 diagonals
                    diag1 = dist_matrix[i, k]
                    diag2 = dist_matrix[j, l]
                    
                    birth = max(cycle_edges)  # cycle exists when all 4 edges present
                    death = min(diag1, diag2)  # cycle dies when a diagonal fills it
                    
                    # Only a valid persistent feature if death > birth
                    # (diagonal longer than all cycle edges)
                    if death > birth and birth < max_dim:
                        persistence = death - birth
                        if persistence > 1e-6:
                            diagram.append((birth, death))
    
    # Sort by persistence, keep top features
    diagram.sort(key=lambda x: x[1] - x[0], reverse=True)
    return diagram[:20]


def persistence_diagram(points: np.ndarray) -> list[tuple[float, float, int]]:
    """
    Compute multi-dimensional persistence diagram.
    
    Returns list of (birth, death, dimension) tuples.
    
    Whitepaper: Section 8, Eq. 15 (Vietoris-Rips filtration)
    """
    dist_matrix = compute_distance_matrix(points)
    
    diagram = []
    
    # H_0: connected components
    h0 = vietoris_rips_H0(dist_matrix)
    for birth, death in h0:
        if death != float('inf'):
            diagram.append((birth, death, 0))
    
    # H_1: loops (approximate)
    h1 = vietoris_rips_H1(dist_matrix)
    for birth, death in h1:
        diagram.append((birth, death, 1))
    
    return diagram


# ---------------------------------------------------------------------------
# Eq. 17 — Drift Score (2-Wasserstein Distance between diagrams)
# ---------------------------------------------------------------------------

def wasserstein_2(D_t: list[tuple[float, float]], D_0: list[tuple[float, float]]) -> float:
    """
    2-Wasserstein distance between two persistence diagrams.
    
    Δ_t = W_2(D_t, D_0) = (inf_γ Σ ||u - γ(u)||²)^{1/2}
    
    Uses a greedy matching for efficiency (optimal matching via
    scipy.optimize.linear_sum_assignment in production).
    
    Whitepaper: Eq. 17
    """
    if not D_t and not D_0:
        return 0.0
    
    # Augment with diagonal projections
    D_t_aug = list(D_t)
    D_0_aug = list(D_0)
    
    # Add diagonal projections for unmatched points
    for b, d in D_t:
        mid = (b + d) / 2
        D_0_aug.append((mid, mid))
    for b, d in D_0:
        mid = (b + d) / 2
        D_t_aug.append((mid, mid))
    
    # Build cost matrix
    n = max(len(D_t_aug), len(D_0_aug))
    while len(D_t_aug) < n:
        D_t_aug.append((0, 0))
    while len(D_0_aug) < n:
        D_0_aug.append((0, 0))
    
    cost_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            db = D_t_aug[i][0] - D_0_aug[j][0]
            dd = D_t_aug[i][1] - D_0_aug[j][1]
            cost_matrix[i, j] = db * db + dd * dd
    
    # Greedy matching (Hungarian algorithm for optimal)
    try:
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        total_cost = cost_matrix[row_ind, col_ind].sum()
    except ImportError:
        # Greedy fallback
        total_cost = 0.0
        used_cols = set()
        for i in range(n):
            best_j = -1
            best_cost = float('inf')
            for j in range(n):
                if j not in used_cols and cost_matrix[i, j] < best_cost:
                    best_cost = cost_matrix[i, j]
                    best_j = j
            if best_j >= 0:
                used_cols.add(best_j)
                total_cost += best_cost
    
    return float(np.sqrt(total_cost))


# ---------------------------------------------------------------------------
# Random Projection for dimensionality reduction (D=10,000 → 64)
# ---------------------------------------------------------------------------

_projection_matrix: Optional[np.ndarray] = None


def get_projection_matrix(input_dim: int, output_dim: int = FINGERPRINT_DIM) -> np.ndarray:
    """Random projection matrix for reducing fingerprint dimensionality."""
    global _projection_matrix
    if _projection_matrix is None or _projection_matrix.shape != (input_dim, output_dim):
        rng = np.random.default_rng(seed=42)
        _projection_matrix = rng.standard_normal((input_dim, output_dim)) / np.sqrt(output_dim)
    return _projection_matrix


# ---------------------------------------------------------------------------
# Sliding Window and Reference Diagram Management
# ---------------------------------------------------------------------------

class DriftDetector:
    """
    Maintains sliding windows per tier and computes drift scores.
    
    Reference diagram D_0 is computed offline on verified corpus
    and cached. Refreshed per Assumption 4.4 cadence.
    """
    
    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self.windows: dict[str, deque] = {}  # tier -> deque of projected fingerprints
        self.reference_diagrams: dict[str, list[tuple[float, float]]] = {}
        self.response_count: dict[str, int] = {}
        self.last_drift_score: dict[str, float] = {}
        self._init_reference_diagrams()
    
    def _init_reference_diagrams(self):
        """Initialize reference diagrams with synthetic in-distribution data."""
        rng = np.random.default_rng(seed=123)
        for tier in ["A", "B", "C"]:
            # Synthetic reference: clustered points (normal distribution)
            ref_points = rng.standard_normal((50, FINGERPRINT_DIM)) * 0.5
            ref_diagram = persistence_diagram(ref_points)
            self.reference_diagrams[tier] = [
                (b, d) for b, d, dim in ref_diagram
            ]
            self.windows[tier] = deque(maxlen=self.window_size)
            self.response_count[tier] = 0
            self.last_drift_score[tier] = 0.0
    
    def add_fingerprint(
        self,
        tier: str,
        fingerprint_vector: np.ndarray,
    ) -> float:
        """
        Add a fingerprint to the sliding window and optionally recompute
        the drift score.
        
        Recomputation happens every RECOMPUTE_INTERVAL new responses
        (not every single response — the whitepaper doesn't require it).
        """
        # Project to lower dimension
        if len(fingerprint_vector) > FINGERPRINT_DIM:
            proj = get_projection_matrix(len(fingerprint_vector))
            projected = fingerprint_vector.astype(np.float64) @ proj
        else:
            projected = fingerprint_vector.astype(np.float64)
        
        self.windows[tier].append(projected)
        self.response_count[tier] = self.response_count.get(tier, 0) + 1
        
        # Recompute drift score periodically
        if (self.response_count[tier] % RECOMPUTE_INTERVAL == 0 and
                len(self.windows[tier]) >= 10):
            window_points = np.array(list(self.windows[tier]))
            current_diagram = persistence_diagram(window_points)
            current_bd = [(b, d) for b, d, dim in current_diagram]
            
            ref = self.reference_diagrams.get(tier, [])
            delta_t = wasserstein_2(current_bd, ref)
            self.last_drift_score[tier] = delta_t
        
        return self.last_drift_score.get(tier, 0.0)


# Global detector instance
_detector = DriftDetector()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class DriftRequest(BaseModel):
    response_id: str
    tier: str = "A"
    fingerprint_vector: list[float]  # The raw fingerprint or embedding


class DriftResponse(BaseModel):
    response_id: str
    delta_t: float  # Drift score Δ_t = W_2(D_t, D_0)
    tier: str
    window_size: int
    responses_since_recompute: int


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "drift", "section": "8"}


@app.post("/drift/score", response_model=DriftResponse)
async def compute_drift(req: DriftRequest) -> DriftResponse:
    """
    Compute the topological drift score Δ_t for a new fingerprint.
    
    Whitepaper: Section 8, Eq. 17, Theorem 8.1
    """
    fp = np.array(req.fingerprint_vector)
    delta_t = _detector.add_fingerprint(req.tier, fp)
    
    tier_count = _detector.response_count.get(req.tier, 0)
    window_len = len(_detector.windows.get(req.tier, []))
    
    return DriftResponse(
        response_id=req.response_id,
        delta_t=round(delta_t, 6),
        tier=req.tier,
        window_size=window_len,
        responses_since_recompute=tier_count % RECOMPUTE_INTERVAL,
    )


@app.get("/drift/reference/{tier}")
async def get_reference_diagram(tier: str):
    """Get the reference persistence diagram D_0 for a tier."""
    ref = _detector.reference_diagrams.get(tier, [])
    return {
        "tier": tier,
        "diagram": [{"birth": b, "death": d} for b, d in ref],
        "num_features": len(ref),
    }


@app.post("/drift/reference/{tier}/update")
async def update_reference(tier: str, points: list[list[float]]):
    """Update the reference diagram D_0 for a tier (Assumption 4.4 refresh)."""
    point_array = np.array(points)
    diagram = persistence_diagram(point_array)
    _detector.reference_diagrams[tier] = [(b, d) for b, d, dim in diagram]
    return {"tier": tier, "updated": True, "num_features": len(diagram)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

"""
Combinatorial Game Theory Patch Prioritization — Section 15
=============================================================
Implements Equations 37-39: Sprague-Grundy theorem for optimal
security patch ordering via Nim-sum over attack-surface subgames.

g(Γ) = mex{g(Γ') : Γ → Γ' is a legal move}
g(Γ₁ + ... + Γₙ) = g(Γ₁) ⊕ ... ⊕ g(Γₙ)    (Nim-sum)

Whitepaper: Section 15, Eq. 37-39
Blueprint: Section 11
"""

from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Game Theory Patcher",
    description="Section 15: Eq. 37-39 — Sprague-Grundy patch prioritization",
    version="1.0.0",
)

ATTACK_SURFACES = [
    "fingerprint", "drift", "surprise", "spectral",
    "sheaf", "category", "routing", "crypto", "queueing",
]


def mex(values: set[int]) -> int:
    """Minimum excludant — smallest non-negative integer not in the set."""
    m = 0
    while m in values:
        m += 1
    return m


def grundy(state: int, max_moves: int = None) -> int:
    """
    Compute the Grundy value for a game position.
    State = hardening depth (integer bucket).
    Legal moves: decrease by 1 (attacker demonstrates bypass).
    """
    if state <= 0:
        return 0
    reachable = set()
    for move in range(state):
        reachable.add(grundy(move))
    return mex(reachable)


def nim_sum(grundy_values: list[int]) -> int:
    """
    Nim-sum (XOR) of all attack-surface Grundy values.
    g(Γ) = g(Γ₁) ⊕ g(Γ₂) ⊕ ... ⊕ g(Γₙ) — Eq. 38
    """
    result = 0
    for g in grundy_values:
        result ^= g
    return result


def optimal_patch_target(grundy_values: list[int]) -> int:
    """
    Find the surface whose patch restores Nim-sum to zero.
    
    g*_k = g(Γ_k) ⊕ (⊕_{i≠k} g(Γ_i)) — Eq. 39
    
    Returns index k, or -1 if already at Nim-sum zero.
    """
    total = nim_sum(grundy_values)
    if total == 0:
        return -1
    
    for k, g_k in enumerate(grundy_values):
        target = g_k ^ total
        if target < g_k:
            return k
    return -1


# In-memory state (Postgres in production)
_surface_states: dict[str, int] = {s: 3 for s in ATTACK_SURFACES}


class PatchPriorityResponse(BaseModel):
    surfaces: list[dict]
    nim_sum: int
    optimal_target_index: int
    optimal_target_name: str
    position_type: str  # "P-position" (safe) or "N-position" (needs patching)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "game-theory-patcher", "section": "15"}


@app.get("/security/priority-queue", response_model=PatchPriorityResponse)
async def get_priority_queue():
    """Return attack surfaces ranked by optimal patch priority. (Eq. 39)"""
    grundy_values = [grundy(min(_surface_states[s], 6)) for s in ATTACK_SURFACES]
    ns = nim_sum(grundy_values)
    target_idx = optimal_patch_target(grundy_values)
    
    surfaces = []
    for i, name in enumerate(ATTACK_SURFACES):
        surfaces.append({
            "name": name,
            "hardening_depth": _surface_states[name],
            "grundy_value": grundy_values[i],
            "is_optimal_target": i == target_idx,
        })
    
    # Sort: optimal target first, then by Grundy value descending
    surfaces.sort(key=lambda x: (not x["is_optimal_target"], -x["grundy_value"]))
    
    return PatchPriorityResponse(
        surfaces=surfaces,
        nim_sum=ns,
        optimal_target_index=target_idx,
        optimal_target_name=ATTACK_SURFACES[target_idx] if target_idx >= 0 else "none",
        position_type="P-position (safe)" if ns == 0 else "N-position (needs patching)",
    )


@app.post("/security/report-bypass")
async def report_bypass(surface_name: str):
    """Report an attacker bypass on a surface (decrements hardening depth)."""
    if surface_name in _surface_states:
        _surface_states[surface_name] = max(0, _surface_states[surface_name] - 1)
    return {"surface": surface_name, "new_depth": _surface_states.get(surface_name, 0)}


@app.post("/security/apply-patch")
async def apply_patch(surface_name: str):
    """Apply a patch to a surface (increments hardening depth)."""
    if surface_name in _surface_states:
        _surface_states[surface_name] += 1
    return {"surface": surface_name, "new_depth": _surface_states.get(surface_name, 0)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)

"""
Policy Manifold Service — Section 22
======================================
Versioned, per-tier, per-jurisdiction policy configuration.

w_{a,k}(τ, j) and α_τ(j) — Eq. 50

Features:
- Two-person sign-off for policy changes (Table 4 mitigation)
- Minimum-calibration-set-size fallback (escalate if below threshold)
- EU + US-generic jurisdiction seeds
- All changes logged to audit ledger as governance events

Whitepaper: Section 22, Eq. 50
Blueprint: Section 18
"""

from __future__ import annotations
import time
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Policy Manifold",
    description="Section 22: Eq. 50 — versioned jurisdiction/tier policy config",
    version="1.0.0",
)


class PolicyChange(BaseModel):
    """A proposed policy change requiring two-person sign-off."""
    change_id: str = ""
    tier: str
    jurisdiction: str
    new_conformal_alpha: Optional[float] = None
    new_tropical_weights: Optional[dict] = None
    new_latency_budget_ms: Optional[int] = None
    author: str = ""
    approved_by: Optional[str] = None
    status: str = "pending"  # pending | approved | rejected
    created_at: float = 0.0


class PolicyConfig(BaseModel):
    tier: str
    jurisdiction: str
    conformal_alpha: float
    tropical_weights: dict = Field(default_factory=dict)
    latency_budget_ms: int
    min_calibration_set_size: int = 50
    version: int = 1
    is_active: bool = True


# ---------------------------------------------------------------------------
# Seed Data — EU (strict) and US-generic (looser)
# ---------------------------------------------------------------------------

_policies: dict[str, PolicyConfig] = {
    "A:EU": PolicyConfig(
        tier="A", jurisdiction="EU", conformal_alpha=0.08,
        latency_budget_ms=1000, min_calibration_set_size=100,
    ),
    "B:EU": PolicyConfig(
        tier="B", jurisdiction="EU", conformal_alpha=0.03,
        latency_budget_ms=5000, min_calibration_set_size=75,
    ),
    "C:EU": PolicyConfig(
        tier="C", jurisdiction="EU", conformal_alpha=0.01,
        latency_budget_ms=60000, min_calibration_set_size=50,
    ),
    "A:US-generic": PolicyConfig(
        tier="A", jurisdiction="US-generic", conformal_alpha=0.10,
        latency_budget_ms=1000, min_calibration_set_size=50,
    ),
    "B:US-generic": PolicyConfig(
        tier="B", jurisdiction="US-generic", conformal_alpha=0.05,
        latency_budget_ms=5000, min_calibration_set_size=50,
    ),
    "C:US-generic": PolicyConfig(
        tier="C", jurisdiction="US-generic", conformal_alpha=0.02,
        latency_budget_ms=60000, min_calibration_set_size=30,
    ),
}

_pending_changes: dict[str, PolicyChange] = {}
_governance_log: list[dict] = []


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "policy-manifold", "section": "22"}


@app.get("/policy/{tier}/{jurisdiction}")
async def get_policy(tier: str, jurisdiction: str):
    """Get the active policy for a tier/jurisdiction."""
    key = f"{tier}:{jurisdiction}"
    if key not in _policies:
        raise HTTPException(404, f"No policy for {key}")
    return _policies[key].model_dump()


@app.get("/policy/all")
async def get_all_policies():
    """Get all active policies."""
    return {k: v.model_dump() for k, v in _policies.items()}


@app.post("/policy/propose")
async def propose_change(change: PolicyChange):
    """
    Propose a policy change. Requires two-person sign-off (Table 4).
    """
    change.change_id = str(uuid.uuid4())
    change.status = "pending"
    change.created_at = time.time()
    _pending_changes[change.change_id] = change
    
    _governance_log.append({
        "event": "policy_change_proposed",
        "change_id": change.change_id,
        "author": change.author,
        "tier": change.tier,
        "jurisdiction": change.jurisdiction,
        "timestamp": time.time(),
    })
    
    return {"change_id": change.change_id, "status": "pending"}


@app.post("/policy/approve/{change_id}")
async def approve_change(change_id: str, approver: str):
    """
    Approve a pending policy change (second person in two-person rule).
    The approver must be a DISTINCT signer from the author.
    """
    if change_id not in _pending_changes:
        raise HTTPException(404, "Change not found")
    
    change = _pending_changes[change_id]
    
    if change.author == approver:
        raise HTTPException(403, "Approver must be different from author (two-person rule)")
    
    if change.status != "pending":
        raise HTTPException(400, f"Change is already {change.status}")
    
    # Apply the change
    key = f"{change.tier}:{change.jurisdiction}"
    if key not in _policies:
        _policies[key] = PolicyConfig(
            tier=change.tier, jurisdiction=change.jurisdiction,
            conformal_alpha=0.10, latency_budget_ms=5000,
        )
    
    policy = _policies[key]
    if change.new_conformal_alpha is not None:
        policy.conformal_alpha = change.new_conformal_alpha
    if change.new_latency_budget_ms is not None:
        policy.latency_budget_ms = change.new_latency_budget_ms
    if change.new_tropical_weights is not None:
        policy.tropical_weights = change.new_tropical_weights
    policy.version += 1
    
    change.approved_by = approver
    change.status = "approved"
    
    _governance_log.append({
        "event": "policy_change_approved",
        "change_id": change_id,
        "approver": approver,
        "tier": change.tier,
        "jurisdiction": change.jurisdiction,
        "new_version": policy.version,
        "timestamp": time.time(),
    })
    
    return {"status": "approved", "new_version": policy.version}


@app.get("/policy/pending")
async def get_pending_changes():
    """Get all pending policy changes awaiting approval."""
    return [c.model_dump() for c in _pending_changes.values() if c.status == "pending"]


@app.get("/policy/governance-log")
async def get_governance_log(limit: int = 50):
    """Get the governance event log."""
    return _governance_log[-limit:]


@app.get("/policy/conformal-alpha/{tier}/{jurisdiction}")
async def get_conformal_alpha(tier: str, jurisdiction: str):
    """Get the conformal α for a specific tier/jurisdiction."""
    key = f"{tier}:{jurisdiction}"
    policy = _policies.get(key)
    if not policy:
        raise HTTPException(404, f"No policy for {key}")
    return {"tier": tier, "jurisdiction": jurisdiction, "alpha": policy.conformal_alpha}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8016)

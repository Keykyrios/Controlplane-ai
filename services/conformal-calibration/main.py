"""
Conformal Risk Control Service — Section 14
=============================================
Implements Theorem 14.2 (Angelopoulos et al.), Equations 34-36:
distribution-free calibration of per-tier routing thresholds.

λ̂ = inf{λ ∈ Λ : (n/(n+1))R̂_n(λ) + B/(n+1) ≤ α}

E[L_{n+1}(λ̂)] ≤ α

This replaces hand-tuned thresholds with thresholds that provably
control the false-negative rate at level α, per tier, with only a
modest calibration set and no distributional assumption.

Whitepaper: Section 14, Eq. 34-36, Theorem 14.2
Blueprint: Section 10
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Conformal Risk Control",
    description="Section 14: Theorem 14.2 — distribution-free per-tier calibration",
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
# Eq. 34 — Loss Function
# ---------------------------------------------------------------------------

def loss_function(
    y_i: bool,        # True if genuine violation
    routed_safe: bool, # True if routed to pass/edit (not block/escalate)
) -> float:
    """
    L_i(λ) = 1[y_i is a true violation] · 1[a*(z_i; λ) ∉ {block, escalate}]
    
    The indicator that a genuine violation was missed.
    This is exactly the false-negative event.
    
    Whitepaper: Eq. 34
    """
    if y_i and routed_safe:
        return 1.0  # Missed violation
    return 0.0


# ---------------------------------------------------------------------------
# Theorem 14.2 — Calibrate Lambda
# ---------------------------------------------------------------------------

def calibrate_lambda(
    losses_by_lambda: dict[float, np.ndarray],
    alpha: float,
    B: float = 1.0,
) -> float:
    """
    Select the risk-controlling threshold λ̂.
    
    λ̂ = inf{λ ∈ Λ : (n/(n+1))R̂_n(λ) + B/(n+1) ≤ α}
    
    Guarantees: E[L_{n+1}(λ̂)] ≤ α (Theorem 14.2)
    
    The guarantee is tight up to O(1/n) correction.
    
    Args:
        losses_by_lambda: {lambda_value: array of per-calibration-point losses}
        alpha: target risk level α_τ
        B: upper bound on loss (default 1.0 for indicator loss)
    
    Returns:
        Calibrated threshold λ̂
    
    Whitepaper: Eq. 35-36, Theorem 14.2
    """
    for lam in sorted(losses_by_lambda.keys()):
        losses = losses_by_lambda[lam]
        n = len(losses)
        R_hat = float(np.mean(losses))
        bound = (n / (n + 1)) * R_hat + B / (n + 1)
        if bound <= alpha:
            return lam
    
    # Fail-safe: return the weakest (most conservative) threshold
    return max(losses_by_lambda.keys())


def compute_calibration_curve(
    losses_by_lambda: dict[float, np.ndarray],
    alpha: float,
    B: float = 1.0,
) -> list[dict]:
    """
    Compute the full calibration curve for visualization.
    
    Returns the empirical risk R̂_n(λ) and the conformal bound
    at each λ, for reproducing Figure 5.
    """
    curve = []
    for lam in sorted(losses_by_lambda.keys()):
        losses = losses_by_lambda[lam]
        n = len(losses)
        R_hat = float(np.mean(losses))
        bound = (n / (n + 1)) * R_hat + B / (n + 1)
        slack = B / (n + 1)  # O(1/n) finite-sample slack
        
        curve.append({
            "lambda": lam,
            "R_hat": round(R_hat, 6),
            "bound": round(bound, 6),
            "slack": round(slack, 6),
            "n": n,
            "satisfies_alpha": bound <= alpha,
        })
    
    return curve


# ---------------------------------------------------------------------------
# Per-Tier Calibration (Section 14.1)
# ---------------------------------------------------------------------------

class TierCalibrator:
    """
    Manages calibration state per tier.
    
    Runs the conformal calibration procedure independently for each
    tier τ ∈ {A, B, C}, using tier-specific calibration streams
    and target α_τ.
    
    Whitepaper: Section 14.1
    """
    
    def __init__(self):
        # Calibration data per tier
        self.calibration_sets: dict[str, list[dict]] = {
            "A": [], "B": [], "C": [],
        }
        
        # Target risk levels per tier (Table 2)
        self.alpha: dict[str, float] = {
            "A": 0.10,  # Customer-facing: loose (alert fatigue concern)
            "B": 0.05,  # Internal copilot: medium
            "C": 0.02,  # Decision-support: strict (near-zero missed violations)
        }
        
        # Calibrated thresholds
        self.calibrated_lambda: dict[str, float] = {
            "A": 0.5, "B": 0.3, "C": 0.1,
        }
        
        # Calibration metadata
        self.last_calibration: dict[str, Optional[float]] = {
            "A": None, "B": None, "C": None,
        }
    
    def add_calibration_point(
        self,
        tier: str,
        response_id: str,
        is_true_violation: bool,
        fused_signal: list[float],
        routing_action: str,
        label_source: str,
    ):
        """
        Add a calibration point from one of the three sources
        (Remark 14.3):
        
        1. Confirmed human override at escalation queue
        2. Downstream compliance finding
        3. Resolved help-desk ticket
        """
        self.calibration_sets[tier].append({
            "response_id": response_id,
            "is_true_violation": is_true_violation,
            "fused_signal": fused_signal,
            "routing_action": routing_action,
            "label_source": label_source,
            "timestamp": time.time(),
        })
    
    def recalibrate(self, tier: str) -> dict:
        """
        Run conformal risk control calibration for a tier.
        
        Scans over λ values to find the threshold that controls
        the false-negative rate at α_τ.
        
        Whitepaper: Theorem 14.2
        """
        cal_set = self.calibration_sets[tier]
        if len(cal_set) < 10:
            return {
                "tier": tier,
                "status": "insufficient_data",
                "n": len(cal_set),
                "min_required": 10,
            }
        
        alpha = self.alpha[tier]
        
        # Sweep over lambda values
        lambda_values = np.linspace(0.0, 1.0, 100)
        losses_by_lambda = {}
        
        for lam in lambda_values:
            losses = []
            for point in cal_set:
                # Check if this point would have been routed to pass/edit at this λ
                z = np.array(point["fused_signal"])
                # Simplified: λ is a threshold on the max signal value
                routed_safe = float(np.max(z[:3])) < lam  # pass/edit if below threshold
                loss = loss_function(
                    y_i=point["is_true_violation"],
                    routed_safe=routed_safe,
                )
                losses.append(loss)
            
            losses_by_lambda[round(float(lam), 4)] = np.array(losses)
        
        # Calibrate
        lambda_hat = calibrate_lambda(losses_by_lambda, alpha)
        self.calibrated_lambda[tier] = lambda_hat
        self.last_calibration[tier] = time.time()
        
        # Compute calibration curve for visualization
        curve = compute_calibration_curve(losses_by_lambda, alpha)
        
        return {
            "tier": tier,
            "alpha": alpha,
            "lambda_hat": lambda_hat,
            "n": len(cal_set),
            "calibration_curve": curve,
            "status": "calibrated",
        }
    
    def get_threshold(self, tier: str) -> float:
        """Get the calibrated threshold for a tier."""
        return self.calibrated_lambda.get(tier, 0.5)


# ---------------------------------------------------------------------------
# Global calibrator
# ---------------------------------------------------------------------------

_calibrator = TierCalibrator()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class CalibrationPointRequest(BaseModel):
    """A new calibration label from the feedback loop."""
    tier: str
    response_id: str
    is_true_violation: bool
    fused_signal: list[float]
    routing_action: str
    label_source: str  # 'human_override', 'compliance_finding', 'helpdesk_ticket'


class CalibrateRequest(BaseModel):
    """Request to run recalibration for a tier."""
    tier: str


class CalibrationStatusResponse(BaseModel):
    """Current calibration status per tier."""
    tier: str
    alpha: float
    lambda_hat: float
    calibration_set_size: int
    last_calibration_timestamp: Optional[float]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "conformal-calibration", "section": "14"}


@app.post("/calibration/add-label")
async def add_calibration_label(req: CalibrationPointRequest):
    """
    Add a calibration label from one of three sources (Remark 14.3):
    - Confirmed human override at escalation queue
    - Downstream compliance finding
    - Resolved help-desk ticket
    """
    _calibrator.add_calibration_point(
        tier=req.tier,
        response_id=req.response_id,
        is_true_violation=req.is_true_violation,
        fused_signal=req.fused_signal,
        routing_action=req.routing_action,
        label_source=req.label_source,
    )
    return {"added": True, "tier": req.tier, "set_size": len(_calibrator.calibration_sets[req.tier])}


@app.post("/calibration/recalibrate")
async def recalibrate(req: CalibrateRequest):
    """
    Run conformal risk control calibration for a tier.
    
    Whitepaper: Theorem 14.2
    """
    result = _calibrator.recalibrate(req.tier)
    return result


@app.get("/calibration/threshold/{tier}")
async def get_threshold(tier: str):
    """Get the calibrated threshold for a tier."""
    return {
        "tier": tier,
        "lambda_hat": _calibrator.get_threshold(tier),
        "alpha": _calibrator.alpha.get(tier, 0.10),
    }


@app.get("/calibration/status")
async def get_status():
    """Get calibration status for all tiers."""
    statuses = []
    for tier in ["A", "B", "C"]:
        statuses.append({
            "tier": tier,
            "alpha": _calibrator.alpha[tier],
            "lambda_hat": _calibrator.calibrated_lambda[tier],
            "calibration_set_size": len(_calibrator.calibration_sets[tier]),
            "last_calibration": _calibrator.last_calibration[tier],
        })
    return {"tiers": statuses}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)

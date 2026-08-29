"""
ControlPlane Manifold — Core Data Contracts
============================================
Pydantic models corresponding 1:1 to the protobuf schemas in proto/.
These are the objects every service reads and writes.

Whitepaper sections: 5 (RiskObservables, RiskMultivector), 11 (FusedSignal),
                     19 (AuditRecord), 22 (PolicyConfig)
Blueprint section:   1 (Core Data Contracts)
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoutingAction(str, Enum):
    """The four possible routing decisions, Section 13 / Eq. 33."""
    PASS = "pass"
    EDIT = "edit"
    BLOCK = "block"
    ESCALATE = "escalate"


class Tier(str, Enum):
    """Use-case tiers from Table 2 of the whitepaper."""
    A = "A"  # Customer-facing chatbot, <1s, loose α
    B = "B"  # Internal knowledge copilot, <5s, medium α
    C = "C"  # Decision-support (regulated), batch, strict α


class Severity(str, Enum):
    """Three-state severity traffic logic (pass/caution/critical)."""
    NOMINAL = "nominal"
    ELEVATED = "elevated"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Section 5.1 — Risk Observables (Eq. 2, 3, 4)
# ---------------------------------------------------------------------------

class RiskObservables(BaseModel):
    """
    The three scalar risk observables for a single response x_t.
    
    - p_t: performance risk = ŷ_t · (1 - q_t), Eq. 2
    - c_t: cost risk = σ((κ_t - κ̄(τ_t)) / κ̄(τ_t)), Eq. 3  
    - r_t: responsibility risk = max(b_t, s_t, ℓ_t), Eq. 4
    """
    session_id: str
    response_id: str
    p_t: float = Field(ge=0.0, le=1.0, description="Performance risk, Eq. 2")
    c_t: float = Field(ge=0.0, le=1.0, description="Cost risk, Eq. 3")
    r_t: float = Field(ge=0.0, le=1.0, description="Responsibility risk, Eq. 4")
    b_t: float = Field(ge=0.0, le=1.0, description="Bias sub-score")
    s_t: float = Field(ge=0.0, le=1.0, description="Safety sub-score")
    l_pii_t: float = Field(ge=0.0, le=1.0, description="Structured-PII sub-score, Section 5.4")
    l_mi_t: float = Field(ge=0.0, le=1.0, description="Membership-plausibility sub-score, Section 5.4")
    timestamp_ns: int = Field(default_factory=lambda: int(time.time() * 1e9))


# ---------------------------------------------------------------------------
# Section 5.2 — Risk Multivector (Eq. 5–9)
# ---------------------------------------------------------------------------

class RiskMultivector(BaseModel):
    """
    The risk multivector R_t in Cl(3,0), capturing pairwise and triple
    interactions between performance, cost, and responsibility axes.
    
    8 components: scalar + 3 vector + 3 bivector + 1 trivector
    """
    response_id: str
    scalar: float = 0.0           # grade 0 (kept for completeness)
    e1: float = 0.0               # p_t — performance axis
    e2: float = 0.0               # c_t — cost axis
    e3: float = 0.0               # r_t — responsibility axis
    e12: float = 0.0              # π_12 — perf×cost interaction
    e13: float = 0.0              # π_13 — perf×resp interaction (hallucination×privacy)
    e23: float = 0.0              # π_23 — cost×resp interaction
    e123: float = 0.0             # π_123 — triple interaction
    wedge_novelty: float = 0.0    # ||R_t ∧ R_{t-1}||, Proposition 5.4


# ---------------------------------------------------------------------------
# Section 11 / Table 3 — Fused Signal z_t
# ---------------------------------------------------------------------------

class FusedSignal(BaseModel):
    """
    The 7-dimensional fused signal z_t that feeds the tropical routing policy.
    One value per functional layer of Table 3.
    
    z = (p_t, c_t, r_t, Δ_t, Surprise_t, κ(V_t), Discord_t)
    """
    response_id: str
    p_t: float = 0.0             # Performance risk
    c_t: float = 0.0             # Cost risk
    r_t: float = 0.0             # Responsibility risk
    delta_t: float = 0.0         # Topological drift, Eq. 17
    surprise_t: float = 0.0      # Algorithmic surprise, Eq. 19
    kappa_v_t: float = 0.0       # Spectral condition number, Eq. 22
    discord_t: float = 0.0       # Sheaf discord, Eq. 28
    tier: Tier = Tier.A
    jurisdiction: str = "US-generic"


# ---------------------------------------------------------------------------
# Section 13 — Routing Decision
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """The output of the tropical routing policy, Section 13."""
    response_id: str
    action: RoutingAction
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="φ_a(z) for each action a"
    )
    tier: Tier
    jurisdiction: str
    fused_signal: FusedSignal
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Section 16 — Syndrome Decode Result
# ---------------------------------------------------------------------------

class SyndromeDecodeResult(BaseModel):
    """Output of syndrome decoding, Section 16 / Eq. 41."""
    response_id: str
    flagged_assertions: list[int] = Field(default_factory=list)
    syndrome_vector: list[int] = Field(default_factory=list)
    correctable: bool = False
    error_set_size: int = 0


# ---------------------------------------------------------------------------
# Section 19 — Audit Record
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    """
    A single immutable entry in the cryptographic audit ledger.
    Hash-linked to its predecessor (Section 19).
    """
    record_id: str
    prev_hash: str
    record_hash: str = ""
    session_id: str
    response_id: str
    timestamp_ns: int = Field(default_factory=lambda: int(time.time() * 1e9))
    
    # The payload — everything the orchestrator computed
    risk_observables: Optional[RiskObservables] = None
    risk_multivector: Optional[RiskMultivector] = None
    fused_signal: Optional[FusedSignal] = None
    routing_decision: Optional[RoutingDecision] = None
    syndrome_result: Optional[SyndromeDecodeResult] = None
    fingerprint_hash: str = ""  # h_t stored instead of raw content
    
    # Crypto metadata
    algo_id: str = "X25519-MLKEM768-v1"
    encrypted_payload: Optional[bytes] = None
    
    def compute_hash(self) -> str:
        """Compute SHA3-256 hash linking to previous record."""
        payload = self.model_dump(exclude={"record_hash", "encrypted_payload"})
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        self.record_hash = hashlib.sha3_256(
            self.prev_hash.encode() + body
        ).hexdigest()
        return self.record_hash


# ---------------------------------------------------------------------------
# Section 22 — Policy Configuration
# ---------------------------------------------------------------------------

class TropicalWeights(BaseModel):
    """Tropical polynomial weights for a single action, Section 13 / Eq. 32."""
    weights: list[float]                    # w_{a,k}
    exponents: list[list[int]]              # α_{a,k,i} for i in 1..7


class PolicyConfig(BaseModel):
    """
    Per-tier, per-jurisdiction policy configuration.
    The versioned store backing the policy manifold (Section 22).
    """
    tier: Tier
    jurisdiction: str
    conformal_alpha: float = Field(
        ge=0.0, le=1.0,
        description="Target risk level α_τ for conformal calibration"
    )
    tropical_weights: dict[str, TropicalWeights] = Field(
        default_factory=dict,
        description="Tropical polynomial coefficients per action"
    )
    latency_budget_ms: int = 1000
    min_calibration_set_size: int = 50
    version: int = 1
    author: str = ""
    approved_by: Optional[str] = None
    is_active: bool = False


# ---------------------------------------------------------------------------
# Orchestrator — Full Pipeline Request/Response
# ---------------------------------------------------------------------------

class PipelineRequest(BaseModel):
    """A single request through the full ControlPlane pipeline."""
    session_id: str
    response_id: str
    response_text: str
    prompt_text: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    model_confidence: Optional[float] = None
    token_usage: dict = Field(default_factory=dict)
    tier: Tier = Tier.A
    jurisdiction: str = "US-generic"
    session_history: list[dict] = Field(default_factory=list)
    grounding_context: str = ""


class PipelineResponse(BaseModel):
    """The full result of running a request through the ControlPlane pipeline."""
    response_id: str
    routing_decision: RoutingDecision
    risk_observables: RiskObservables
    risk_multivector: RiskMultivector
    fused_signal: FusedSignal
    syndrome_result: Optional[SyndromeDecodeResult] = None
    audit_record_hash: str = ""
    processing_time_ms: float = 0.0

"""
ControlPlane Manifold — System Constants
=========================================
Central configuration values referenced across all services.
"""

# ---------------------------------------------------------------------------
# Hyperdimensional Computing (Section 7)
# ---------------------------------------------------------------------------
HDC_DIMENSIONALITY = 10_000  # d = 10^4, per whitepaper
HDC_SEED = 42

# ---------------------------------------------------------------------------
# Topological Drift (Section 8)
# ---------------------------------------------------------------------------
DRIFT_WINDOW_SIZE = 100      # w: sliding window of fingerprints
DRIFT_RECOMPUTE_INTERVAL = 10  # recompute Δ_t every w/10 new responses
DRIFT_HOMOLOGY_DIMS = [0, 1, 2]  # H_0, H_1, H_2

# ---------------------------------------------------------------------------
# Algorithmic Surprise (Section 9)
# ---------------------------------------------------------------------------
NCD_SHORTLIST_SIZE = 50      # LSH/ANN shortlist before exact NCD
COMPRESSION_LEVEL = 9        # zlib max compression

# ---------------------------------------------------------------------------
# Non-Hermitian Spectral (Section 10)
# ---------------------------------------------------------------------------
MIN_SESSION_LENGTH = 4       # minimum turns for Jacobian estimation
KAPPA_LOG_SCALE = True       # display κ(V_t) on log scale

# ---------------------------------------------------------------------------
# Sheaf Fusion (Section 11)
# ---------------------------------------------------------------------------
PIPELINE_CHECKPOINTS = [
    "prompt-assembly",
    "retrieval",
    "tool-call",
    "generation",
    "post-processing",
]

# ---------------------------------------------------------------------------
# Tropical Routing (Section 13)
# ---------------------------------------------------------------------------
ROUTING_ACTIONS = ["pass", "edit", "block", "escalate"]
FUSED_SIGNAL_DIM = 7  # z ∈ R^7

# ---------------------------------------------------------------------------
# Conformal Calibration (Section 14)
# ---------------------------------------------------------------------------
DEFAULT_ALPHA = {
    "A": 0.10,  # Customer-facing: loose
    "B": 0.05,  # Internal copilot: medium
    "C": 0.02,  # Decision-support: strict
}
RECALIBRATION_CADENCE_DAYS = 7  # weekly

# ---------------------------------------------------------------------------
# Game Theory (Section 15)
# ---------------------------------------------------------------------------
ATTACK_SURFACES = [
    "fingerprint", "drift", "surprise", "spectral",
    "sheaf", "category", "routing", "crypto", "queueing",
]

# ---------------------------------------------------------------------------
# Queueing (Section 18)
# ---------------------------------------------------------------------------
MU_FAST_DEFAULT = 100.0      # fast-path service rate (responses/s)
MU_HUMAN_DEFAULT = 0.1       # human reviewer service rate (responses/s)
DEFAULT_REVIEWERS = 3        # c in M/M/c queue

# ---------------------------------------------------------------------------
# Cryptography (Section 19)
# ---------------------------------------------------------------------------
PQC_ALGO_ID = "X25519-MLKEM768-v1"
HASH_ALGORITHM = "sha3_256"
GENESIS_HASH = "0" * 64      # hash of the genesis record

# ---------------------------------------------------------------------------
# Thermodynamics (Section 17)
# ---------------------------------------------------------------------------
K_BOLTZMANN = 1.380649e-23   # J/K
DEFAULT_TEMPERATURE = 300.0   # Kelvin

# ---------------------------------------------------------------------------
# Service Ports
# ---------------------------------------------------------------------------
SERVICE_PORTS = {
    "orchestrator": 8000,
    "risk-observables": 8001,
    "risk-multivector": 8002,
    "fingerprint": 8003,
    "drift": 8004,
    "surprise": 8005,
    "spectral": 8006,
    "sheaf-fusion": 8007,
    "portability-adapters": 8008,
    "tropical-routing": 8009,
    "conformal-calibration": 8010,
    "game-theory-patcher": 8011,
    "syndrome-decoder": 8012,
    "thermo-accounting": 8013,
    "queueing-monitor": 8014,
    "audit-ledger": 8015,
    "policy-manifold": 8016,
    "frontend": 3000,
}

# ---------------------------------------------------------------------------
# Tier Configuration (Table 2)
# ---------------------------------------------------------------------------
TIER_CONFIG = {
    "A": {
        "name": "Customer-facing chatbot",
        "latency_budget_ms": 1000,
        "conformal_alpha": 0.10,
        "risk_appetite": "Moderate tolerance for missed low-severity issues",
        "volume_share": 0.60,
    },
    "B": {
        "name": "Internal knowledge copilot",
        "latency_budget_ms": 5000,
        "conformal_alpha": 0.05,
        "risk_appetite": "Low tolerance for data leakage",
        "volume_share": 0.30,
    },
    "C": {
        "name": "Decision-support tool (regulated)",
        "latency_budget_ms": 60000,
        "conformal_alpha": 0.02,
        "risk_appetite": "Near-zero tolerance for missed responsibility violations",
        "volume_share": 0.10,
    },
}

"""
Hyperdimensional Fingerprinting Service — Section 7
=====================================================
Implements Equations 13-14: sub-millisecond online encoding of every
response using hyperdimensional computing (bipolar vectors d=10,000).

h_t = ⊕_{k=1}^{n_t} (h_tok(w_k) ⊗ h_pos(k))

Operations:
  - Binding ⊗: coordinate-wise multiplication (bipolar XOR)
  - Bundling ⊕: coordinate-wise majority vote
  
Time complexity: O(n_t · d) — sub-millisecond for typical responses.

This fingerprint is the object every other layer operates on:
  - Drift (Section 8): embeds sliding window into metric point cloud
  - Surprise (Section 9): NCD on compressed bit-string
  - Audit ledger (Section 19): stores h_t instead of raw response

Whitepaper: Section 7, Eq. 13-14, Proposition 7.1
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants (Section 7)
# ---------------------------------------------------------------------------
D = 10_000  # Dimensionality of hypervectors
PROJECTED_DIM = 64  # Projected dimensionality for downstream TDA
SEED = 42
rng = np.random.default_rng(seed=SEED)

app = FastAPI(
    title="ControlPlane Manifold — Hyperdimensional Fingerprinting",
    description="Section 7: Eq. 13-14 — sub-millisecond online encoding via HDC",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Hyperdimensional Computing Primitives
# ---------------------------------------------------------------------------

def gen_hv() -> np.ndarray:
    """Generate a random bipolar hypervector h ∈ {-1, +1}^d."""
    return rng.choice([-1, 1], size=D).astype(np.int8)


# Token vocabulary → hypervector mapping (grown lazily)
token_hvs: dict[str, np.ndarray] = {}

# Position generator (repeated binding of a single generator, per §7)
GEN_POS = gen_hv()


def get_token_hv(token: str) -> np.ndarray:
    """Get or create the hypervector for a vocabulary token."""
    if token not in token_hvs:
        # Use deterministic seeding from token hash for reproducibility
        token_seed = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
        token_rng = np.random.default_rng(seed=token_seed)
        token_hvs[token] = token_rng.choice([-1, 1], size=D).astype(np.int8)
    return token_hvs[token]


def pos_hv(k: int) -> np.ndarray:
    """
    Position hypervector: repeated binding of a single generator.
    h_pos(k) = roll(GEN_POS, k)
    
    This gives positions a well-defined algebraic relationship
    to one another, per whitepaper §7.
    """
    return np.roll(GEN_POS, k)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Binding ⊗: coordinate-wise multiply (bipolar XOR).
    Distributes information across dimensions.
    """
    return (a * b).astype(np.int8)


def bundle(vs: np.ndarray) -> np.ndarray:
    """
    Bundling ⊕: coordinate-wise majority vote.
    Superimposes multiple hypervectors into one.
    """
    return np.sign(np.sum(vs, axis=0)).astype(np.int8)


def fingerprint(tokens: list[str]) -> np.ndarray:
    """
    Encode a sequence of tokens into a single fingerprint hypervector.
    
    h_t = ⊕_{k=1}^{n_t} (h_tok(w_k) ⊗ h_pos(k))
    
    Time complexity: O(n_t · d) — Eq. 14.
    """
    if not tokens:
        return np.zeros(D, dtype=np.int8)
    
    terms = np.stack([
        bind(get_token_hv(tok), pos_hv(k))
        for k, tok in enumerate(tokens)
    ])
    return bundle(terms)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two hypervectors."""
    dot = float(np.dot(a.astype(np.float64), b.astype(np.float64)))
    norm_a = float(np.linalg.norm(a.astype(np.float64)))
    norm_b = float(np.linalg.norm(b.astype(np.float64)))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return dot / (norm_a * norm_b)


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    """Hamming distance between two bipolar hypervectors."""
    return int(np.sum(a != b))


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class FingerprintRequest(BaseModel):
    """Input to fingerprint computation."""
    response_id: str
    session_id: str
    response_text: str
    tokens: Optional[list[str]] = None  # Pre-tokenized; if None, split on whitespace


class FingerprintResponse(BaseModel):
    """Output: the fingerprint hash, projected vector, and raw hex."""
    response_id: str
    fingerprint_hash: str  # SHA3-256 of the bipolar vector (for storage/comparison)
    fingerprint_hex: str = ""  # Raw bipolar vector as hex (for surprise NCD)
    fingerprint_vector: list[float] = Field(default_factory=list)  # 64-dim projected (for drift TDA)
    dimensionality: int = D
    num_tokens: int
    encoding_time_us: float  # Microseconds — must be << 1ms


class SimilarityRequest(BaseModel):
    """Compare two fingerprints."""
    response_id_a: str
    response_id_b: str
    text_a: str
    text_b: str


class SimilarityResponse(BaseModel):
    """Similarity metrics between two fingerprints."""
    cosine_similarity: float
    hamming_distance: int
    hamming_fraction: float


# ---------------------------------------------------------------------------
# In-memory fingerprint cache (Redis in production)
# ---------------------------------------------------------------------------

_fingerprint_cache: dict[str, np.ndarray] = {}

# Stable random projection matrix (computed once)
_projection_matrix: Optional[np.ndarray] = None

def _get_projection_matrix() -> np.ndarray:
    """Get or create the D→PROJECTED_DIM random projection matrix."""
    global _projection_matrix
    if _projection_matrix is None:
        proj_rng = np.random.default_rng(seed=99)
        _projection_matrix = proj_rng.standard_normal((D, PROJECTED_DIM)) / np.sqrt(PROJECTED_DIM)
    return _projection_matrix


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fingerprint", "section": "7"}


@app.post("/fingerprint/encode", response_model=FingerprintResponse)
async def encode_fingerprint(req: FingerprintRequest) -> FingerprintResponse:
    """
    Encode a response into a hyperdimensional fingerprint.
    
    Must complete in sub-millisecond time for typical responses
    (Proposition 7.1 claim).
    
    Whitepaper: Section 7, Eq. 13-14
    """
    start = time.perf_counter_ns()
    
    # Tokenize
    tokens = req.tokens or req.response_text.split()
    
    # Encode
    h_t = fingerprint(tokens)
    
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    
    # Hash for storage (audit ledger stores hash, not raw content)
    fp_hash = hashlib.sha3_256(h_t.tobytes()).hexdigest()
    
    # Raw hex for surprise NCD
    fp_hex = h_t.tobytes().hex()
    
    # Random projection to 64-dim for drift TDA
    proj_matrix = _get_projection_matrix()
    fp_vector = (h_t.astype(np.float64) @ proj_matrix).tolist()
    
    # Cache
    _fingerprint_cache[req.response_id] = h_t
    
    return FingerprintResponse(
        response_id=req.response_id,
        fingerprint_hash=fp_hash,
        fingerprint_hex=fp_hex,
        fingerprint_vector=fp_vector,
        dimensionality=D,
        num_tokens=len(tokens),
        encoding_time_us=round(elapsed_us, 2),
    )


@app.post("/fingerprint/similarity", response_model=SimilarityResponse)
async def compute_similarity(req: SimilarityRequest) -> SimilarityResponse:
    """
    Compute similarity between two response fingerprints.
    
    Proposition 7.1: independent fingerprints have cosine similarity O(1/√d),
    while similar responses maintain high cosine similarity.
    """
    tokens_a = req.text_a.split()
    tokens_b = req.text_b.split()
    
    h_a = fingerprint(tokens_a)
    h_b = fingerprint(tokens_b)
    
    cos_sim = cosine_similarity(h_a, h_b)
    ham_dist = hamming_distance(h_a, h_b)
    
    return SimilarityResponse(
        cosine_similarity=round(cos_sim, 6),
        hamming_distance=ham_dist,
        hamming_fraction=round(ham_dist / D, 6),
    )


@app.get("/fingerprint/{response_id}/raw")
async def get_raw_fingerprint(response_id: str):
    """Get the raw fingerprint bytes for a cached response."""
    if response_id not in _fingerprint_cache:
        return {"error": "Fingerprint not found in cache"}
    h = _fingerprint_cache[response_id]
    return {
        "response_id": response_id,
        "fingerprint_bytes": h.tobytes().hex(),
        "dimensionality": D,
    }


@app.get("/fingerprint/stats")
async def fingerprint_stats():
    """Return statistics about the fingerprint cache and vocabulary."""
    return {
        "vocabulary_size": len(token_hvs),
        "cached_fingerprints": len(_fingerprint_cache),
        "dimensionality": D,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

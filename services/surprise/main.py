"""
Algorithmic Surprise Service — Section 9
==========================================
Implements Equations 18-19: feature-free, domain-agnostic measure of
how atypical a response is using Normalized Compression Distance (NCD).

NCD(x,y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))

Surprise(x_t) = min_{v ∈ V} NCD(h̃_t, ṽ)

This is deliberately the layer of last resort: every other layer is
somewhat domain-tuned, and Surprise degrades gracefully to a domain-free
anomaly signal when more specialized layers have no training signal.

Whitepaper: Section 9, Eq. 18-19
Blueprint: Section 5
"""

from __future__ import annotations

import hashlib
import time
import zlib

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Algorithmic Surprise",
    description="Section 9: Eq. 18-19 — NCD-based algorithmic surprise score",
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
# Constants
# ---------------------------------------------------------------------------
COMPRESSION_LEVEL = 9  # zlib max compression
SHORTLIST_SIZE = 50    # LSH shortlist before exact NCD


# ---------------------------------------------------------------------------
# Normalized Compression Distance (Eq. 18)
# ---------------------------------------------------------------------------

def C(x: bytes) -> int:
    """
    Compressed length using a real-world lossless compressor.
    
    C(x) ≥ K(x) + O(1) for a good compressor, where K(x) is
    the Kolmogorov complexity.
    
    Section 9 explicitly says "any real-world lossless compressor";
    zlib is fine and fast.
    """
    return len(zlib.compress(x, level=COMPRESSION_LEVEL))


def ncd(x: bytes, y: bytes) -> float:
    """
    Normalized Compression Distance between two strings.
    
    NCD(x,y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))
    
    This is, up to the approximation error of C, an admissible
    normalized version of the information distance
    max(K(x|y), K(y|x)).
    
    Whitepaper: Eq. 18, citing Cilibrasi & Vitányi [6]
    """
    cx = C(x)
    cy = C(y)
    cxy = C(x + y)
    
    max_c = max(cx, cy)
    if max_c == 0:
        return 0.0
    
    return (cxy - min(cx, cy)) / max_c


def surprise(fp_bits: bytes, reference_corpus: list[bytes]) -> float:
    """
    Response-level surprise score.
    
    Surprise(x_t) = min_{v ∈ V} NCD(h̃_t, ṽ)
    
    A response that compresses well jointly with some verified example
    is treated as typical; one that is algorithmically incompressible
    relative to everything the corpus has seen is flagged.
    
    Whitepaper: Eq. 19
    """
    if not reference_corpus:
        return 1.0  # No reference → maximally surprising
    
    return min(ncd(fp_bits, v) for v in reference_corpus)


# ---------------------------------------------------------------------------
# LSH-based shortlisting for scale (Blueprint optimization)
# ---------------------------------------------------------------------------

class MinHashIndex:
    """
    MinHash-based locality-sensitive hashing for fast approximate
    nearest-neighbor shortlisting before exact NCD computation.
    
    This is an explicit engineering optimization on top of the
    whitepaper's exact formula (Eq. 19), not a deviation from it.
    """
    
    def __init__(self, num_hashes: int = 128):
        self.num_hashes = num_hashes
        self.corpus: list[bytes] = []
        self.signatures: list[np.ndarray] = []
        self._hash_seeds = np.random.default_rng(42).integers(
            0, 2**32, size=num_hashes
        )
    
    def _minhash(self, data: bytes) -> np.ndarray:
        """Compute MinHash signature for data."""
        # Use shingle-based approach
        shingles = set()
        for i in range(max(1, len(data) - 3)):
            shingles.add(data[i:i+4])
        
        if not shingles:
            return np.zeros(self.num_hashes, dtype=np.uint32)
        
        signature = np.full(self.num_hashes, np.iinfo(np.uint32).max, dtype=np.uint32)
        for shingle in shingles:
            h = int(hashlib.md5(shingle).hexdigest()[:8], 16)
            for i, seed in enumerate(self._hash_seeds):
                val = (h ^ int(seed)) % (2**32)
                if val < signature[i]:
                    signature[i] = val
        
        return signature
    
    def add(self, data: bytes):
        """Add a reference item to the corpus."""
        self.corpus.append(data)
        self.signatures.append(self._minhash(data))
    
    def shortlist(self, query: bytes, k: int = SHORTLIST_SIZE) -> list[int]:
        """Return indices of k most similar items by MinHash similarity."""
        if not self.signatures:
            return []
        
        query_sig = self._minhash(query)
        similarities = []
        
        for i, sig in enumerate(self.signatures):
            jaccard_est = np.mean(query_sig == sig)
            similarities.append((i, jaccard_est))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in similarities[:k]]


# ---------------------------------------------------------------------------
# Global reference corpus (per-tier in production)
# ---------------------------------------------------------------------------

_reference_index = MinHashIndex()
_reference_corpus: list[bytes] = []

# Seed with synthetic reference data
def _init_reference_corpus():
    """Initialize with synthetic verified-correct responses."""
    templates = [
        "The answer to your question is based on the following verified information.",
        "According to our records, the policy states the following terms and conditions.",
        "Based on the grounding context provided, the correct interpretation is as follows.",
        "The calculation yields the following result based on the input parameters.",
        "Per the regulatory framework, the applicable rules are summarized below.",
    ]
    for template in templates:
        data = template.encode()
        _reference_corpus.append(data)
        _reference_index.add(data)

_init_reference_corpus()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class SurpriseRequest(BaseModel):
    response_id: str
    response_text: str
    fingerprint_bytes: str = ""  # Hex-encoded fingerprint bytes


class SurpriseResponse(BaseModel):
    response_id: str
    surprise_score: float  # Surprise(x_t) = min NCD to reference
    nearest_ncd: float
    num_candidates_checked: int
    computation_time_us: float


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "surprise", "section": "9"}


@app.post("/surprise/score", response_model=SurpriseResponse)
async def compute_surprise(req: SurpriseRequest) -> SurpriseResponse:
    """
    Compute the algorithmic surprise score for a response.
    
    Uses LSH shortlisting followed by exact NCD computation
    against the shortlisted candidates.
    
    Whitepaper: Section 9, Eq. 19
    """
    start = time.perf_counter_ns()
    
    # Use fingerprint bytes if available, else response text
    if req.fingerprint_bytes:
        query = bytes.fromhex(req.fingerprint_bytes)
    else:
        query = req.response_text.encode()
    
    # Shortlist via MinHash
    shortlist_indices = _reference_index.shortlist(query, k=SHORTLIST_SIZE)
    
    if not shortlist_indices:
        # Fall back to full corpus
        candidates = _reference_corpus
    else:
        candidates = [_reference_corpus[i] for i in shortlist_indices]
    
    # Exact NCD against shortlisted candidates
    if not candidates:
        surprise_score = 1.0
        nearest_ncd = 1.0
    else:
        ncd_scores = [ncd(query, c) for c in candidates]
        surprise_score = min(ncd_scores)
        nearest_ncd = surprise_score
    
    elapsed_us = (time.perf_counter_ns() - start) / 1000.0
    
    return SurpriseResponse(
        response_id=req.response_id,
        surprise_score=round(surprise_score, 6),
        nearest_ncd=round(nearest_ncd, 6),
        num_candidates_checked=len(candidates),
        computation_time_us=round(elapsed_us, 2),
    )


@app.post("/surprise/reference/add")
async def add_reference(text: str):
    """Add a verified-correct response to the reference corpus V."""
    data = text.encode()
    _reference_corpus.append(data)
    _reference_index.add(data)
    return {"added": True, "corpus_size": len(_reference_corpus)}


@app.post("/surprise/ncd")
async def compute_ncd_direct(text_a: str, text_b: str):
    """Compute NCD between two arbitrary texts (diagnostic endpoint)."""
    score = ncd(text_a.encode(), text_b.encode())
    return {"ncd": round(score, 6)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

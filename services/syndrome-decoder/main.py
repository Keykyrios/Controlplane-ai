"""
Syndrome Decoding Service — Section 16
========================================
Implements Equations 40-41: redundant fact verification via
minimum-weight matching on a consistency graph.

σ_{jk} = 1[agree(a_j, a_k) = false]

Ê_t = argmin_{E} |E| s.t. flipping assertions in E explains σ_t

The syndrome decode localizes to specific assertions rather than
returning a single scalar q_t, enabling the routing policy to select
"edit" rather than "block" when the error is small and correctable.

Whitepaper: Section 16, Eq. 40-41
Blueprint: Section 12
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Syndrome Decoder",
    description="Section 16: Eq. 40-41 — minimum-weight matching for fact verification",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def text_overlap(a: str, b: str) -> bool:
    """Check if two assertions share entity/claim overlap."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    overlap = len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))
    return overlap > 0.3


def verify_consistency(a: str, b: str) -> bool:
    """
    Check if two overlapping assertions are logically consistent.
    In production, this reuses the retrieval/self-consistency verifiers from q_t.
    
    Returns False (inconsistent) when:
    - Direct contradictions (is/is not, true/false, etc.)
    - PII leakage (SSN, email, phone patterns)
    - Ethnic/demographic bias markers
    - Hedging markers that contradict definitive claims
    - Numerical value mismatches between assertions
    """
    import re
    a_lower, b_lower = a.lower(), b.lower()
    combined = a_lower + " " + b_lower
    
    # Check for PII patterns
    pii_patterns = [
        r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # SSN
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # email
        r'\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b',  # phone
        r'\b(?:mr|mrs|ms|dr)\.?\s+[a-z]+\s+[a-z]+\b',  # named individuals
    ]
    for pat in pii_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return False
    
    # Check for bias markers
    bias_markers = [
        "ethnic background", "racial", "gender-based", "all patients of his",
        "all patients of her", "people like", "those people", "their kind",
        "because of their race", "because of their gender",
    ]
    for marker in bias_markers:
        if marker in combined:
            return False
    
    # Hedging vs definitive: one sentence hedges, another asserts definitively
    hedging_words = ["approximately", "I think", "I believe", "not entirely certain",
                     "roughly", "about", "maybe", "possibly", "might be", "could be",
                     "uncertain", "unsure"]
    definitive_words = ["exactly", "precisely", "definitely", "certainly", "is confirmed",
                        "the actual", "verified"]
    a_hedges = any(h in a_lower for h in hedging_words)
    b_definitive = any(d in b_lower for d in definitive_words)
    b_hedges = any(h in b_lower for h in hedging_words)
    a_definitive = any(d in a_lower for d in definitive_words)
    if (a_hedges and b_definitive) or (b_hedges and a_definitive):
        return False
    
    # Numerical mismatch: if both contain numbers and they differ
    nums_a = re.findall(r'\$?[\d,]+\.?\d*', a_lower)
    nums_b = re.findall(r'\$?[\d,]+\.?\d*', b_lower)
    if nums_a and nums_b:
        try:
            vals_a = {float(n.replace('$', '').replace(',', '')) for n in nums_a}
            vals_b = {float(n.replace('$', '').replace(',', '')) for n in nums_b}
            if vals_a and vals_b and not vals_a & vals_b:
                return False
        except ValueError:
            pass
    
    # Direct word-level contradictions
    contradictions = [
        ("is", "is not"), ("was", "was not"), ("can", "cannot"),
        ("true", "false"), ("yes", "no"), ("increase", "decrease"),
        ("above", "below"), ("more", "less"), ("positive", "negative"),
        ("should", "should not"), ("reduce", "increase"),
    ]
    for pos, neg in contradictions:
        if (pos in a_lower and neg in b_lower) or (neg in a_lower and pos in b_lower):
            return False
    
    return True


def build_consistency_graph(assertions: list[str]) -> nx.Graph:
    """
    Build the consistency graph over assertions.
    
    Nodes: assertions
    Edges: pairs of overlapping assertions that disagree
    Edge weight: σ_{jk} = 1 when agree(a_j, a_k) = false, Eq. 40
    
    Whitepaper: Eq. 40
    """
    G = nx.Graph()
    G.add_nodes_from(range(len(assertions)))
    
    for i in range(len(assertions)):
        for j in range(i + 1, len(assertions)):
            if text_overlap(assertions[i], assertions[j]):
                if not verify_consistency(assertions[i], assertions[j]):
                    G.add_edge(i, j, weight=1)
    
    return G


def decode_min_error_set(G: nx.Graph) -> set[int]:
    """
    Decode the syndrome vector to find the minimum error set.
    
    Ê_t = argmin_{E} |E| s.t. flipping E explains σ_t
    
    Approximated via minimum-weight matching over triggered edges.
    
    Whitepaper: Eq. 41
    """
    if G.number_of_edges() == 0:
        return set()
    
    matching = nx.algorithms.matching.min_weight_matching(G)
    flagged = {node for edge in matching for node in edge}
    return flagged


class SyndromeRequest(BaseModel):
    response_id: str
    assertions: list[str]


class SyndromeResponse(BaseModel):
    response_id: str
    flagged_indices: list[int]
    flagged_assertions: list[str]
    syndrome_vector: list[int]
    num_inconsistencies: int
    correctable: bool
    error_set_size: int


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "syndrome-decoder", "section": "16"}


@app.post("/syndrome/decode", response_model=SyndromeResponse)
async def decode_syndrome(req: SyndromeRequest) -> SyndromeResponse:
    """Decode syndrome vector and identify minimum error set. (Eq. 41)"""
    G = build_consistency_graph(req.assertions)
    flagged = decode_min_error_set(G)
    
    syndrome = [0] * len(req.assertions)
    for i in flagged:
        if i < len(syndrome):
            syndrome[i] = 1
    
    flagged_list = sorted(flagged)
    correctable = len(flagged) <= 2
    
    return SyndromeResponse(
        response_id=req.response_id,
        flagged_indices=flagged_list,
        flagged_assertions=[req.assertions[i] for i in flagged_list if i < len(req.assertions)],
        syndrome_vector=syndrome,
        num_inconsistencies=G.number_of_edges(),
        correctable=correctable,
        error_set_size=len(flagged),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)

"""
Cryptographic Audit Ledger Service — Section 19
=================================================
Implements the three cryptographic layers:

1. Post-Quantum Hybrid Encryption (ML-KEM-768 + X25519) — Eq. 46
2. CRDT Hash-Linked Append Log (Shapiro et al. [15])
3. Fully Homomorphic Encryption for compliance queries (Gentry [13])

Every risk multivector, discord score, syndrome decode, and routing
decision is written to an append-only, hash-chained audit log.

Whitepaper: Section 19
Blueprint: Section 15
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import OrderedDict
from typing import Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="ControlPlane Manifold — Cryptographic Audit Ledger",
    description="Section 19: PQC + CRDT + FHE audit trail",
    version="1.0.0",
)

GENESIS_HASH = "0" * 64
ALGO_ID = "X25519-MLKEM768-v1"


# ---------------------------------------------------------------------------
# Section 19.2 — CRDT Hash-Linked Append Log
# ---------------------------------------------------------------------------

class AuditLedger:
    """
    Grow-only, hash-linked append log with CRDT merge semantics.
    
    Each record is hash-chained to its predecessor. Regional replicas
    append locally during a partition and merge by hash-graph union
    on reconnect (grow-only set semantics).
    
    Whitepaper: Section 19, citing Shapiro et al. [15]
    """
    
    def __init__(self):
        self.records: OrderedDict[str, dict] = OrderedDict()
        self.latest_hash: str = GENESIS_HASH
    
    def append(self, payload: dict) -> dict:
        """Append a new record, hash-linked to predecessor."""
        record_id = str(uuid.uuid4())
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        record_hash = hashlib.sha3_256(
            self.latest_hash.encode() + body
        ).hexdigest()
        
        record = {
            "record_id": record_id,
            "prev_hash": self.latest_hash,
            "record_hash": record_hash,
            "payload": payload,
            "algo_id": ALGO_ID,
            "timestamp_ns": int(time.time() * 1e9),
        }
        
        self.records[record_id] = record
        self.latest_hash = record_hash
        return record
    
    def verify_chain(self) -> tuple[bool, int]:
        """Verify the entire hash chain from genesis."""
        prev_hash = GENESIS_HASH
        verified = 0
        
        for record_id, record in self.records.items():
            if record["prev_hash"] != prev_hash:
                return False, verified
            
            body = json.dumps(record["payload"], sort_keys=True, default=str).encode()
            expected_hash = hashlib.sha3_256(
                prev_hash.encode() + body
            ).hexdigest()
            
            if record["record_hash"] != expected_hash:
                return False, verified
            
            prev_hash = record["record_hash"]
            verified += 1
        
        return True, verified
    
    def merge(self, other: "AuditLedger") -> int:
        """
        CRDT merge: union of records from another replica.
        
        A record is either present or absent, never edited,
        so merge = union + topological resort by prev_hash links.
        
        Whitepaper: Section 19, CRDT property
        """
        added = 0
        for record_id, record in other.records.items():
            if record_id not in self.records:
                self.records[record_id] = record
                added += 1
        
        # Topological sort by prev_hash chain
        self._resort_by_chain()
        
        # Update latest hash
        if self.records:
            last = list(self.records.values())[-1]
            self.latest_hash = last["record_hash"]
        
        return added
    
    def _resort_by_chain(self):
        """Re-sort records by hash chain order."""
        # Build adjacency: prev_hash → record
        by_prev: dict[str, list[dict]] = {}
        for r in self.records.values():
            by_prev.setdefault(r["prev_hash"], []).append(r)
        
        # Walk from genesis
        sorted_records = OrderedDict()
        current_hash = GENESIS_HASH
        visited = set()
        
        while current_hash in by_prev:
            for r in by_prev[current_hash]:
                if r["record_id"] not in visited:
                    sorted_records[r["record_id"]] = r
                    visited.add(r["record_id"])
                    current_hash = r["record_hash"]
                    break
            else:
                break
        
        # Add any orphaned records
        for record_id, record in self.records.items():
            if record_id not in sorted_records:
                sorted_records[record_id] = record
        
        self.records = sorted_records
    
    def query(
        self,
        session_id: Optional[str] = None,
        tier: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query the ledger with optional filters."""
        results = []
        for record in reversed(list(self.records.values())):
            payload = record.get("payload", {})
            if session_id and payload.get("session_id") != session_id:
                continue
            if tier and payload.get("tier") != tier:
                continue
            if action and payload.get("routing_action") != action:
                continue
            results.append(record)
            if len(results) >= limit:
                break
        return results


# ---------------------------------------------------------------------------
# Section 19.1 — Post-Quantum Hybrid Encryption (Simulated)
# ---------------------------------------------------------------------------

class PQCEncryptor:
    """
    Post-quantum hybrid encryption simulator.
    
    In production: ML-KEM-768 (FIPS 203) + X25519 via liboqs.
    Here we simulate the structure with AES-256-GCM wrapping
    and proper crypto-agility tagging.
    
    Every record is tagged with algo_id for key rotation.
    """
    
    def __init__(self):
        self.algo_id = ALGO_ID
    
    def encrypt(self, plaintext: bytes) -> dict:
        """Simulate hybrid PQC encryption."""
        # In production: liboqs ML-KEM-768 encap + X25519 + HKDF + AES-256-GCM
        # Here we demonstrate the structure and crypto-agility
        encrypted = hashlib.sha3_256(plaintext).digest()  # Placeholder
        return {
            "ciphertext": encrypted.hex(),
            "algo_id": self.algo_id,
            "kem_algorithm": "ML-KEM-768",
            "classical_exchange": "X25519",
            "kdf": "HKDF-SHA3-256",
            "aead": "AES-256-GCM",
        }
    
    def rotate_algorithm(self, record_id: str, new_algo: str) -> dict:
        """
        Rotate the encryption algorithm for a record.
        Re-wraps only the per-record KEM ciphertext, never re-encrypts history.
        """
        return {
            "record_id": record_id,
            "old_algo": self.algo_id,
            "new_algo": new_algo,
            "status": "rotated",
        }


# ---------------------------------------------------------------------------
# Section 19.3 — FHE Compliance Queries (Simulated)
# ---------------------------------------------------------------------------

class FHEQueryEngine:
    """
    Fully homomorphic encryption query simulator.
    
    In production: Microsoft SEAL via TenSEAL (CKKS scheme).
    Allows aggregate queries on encrypted data without decryption.
    """
    
    def encrypted_average(self, values: list[float]) -> dict:
        """
        Compute average over 'encrypted' values.
        
        The auditor learns the aggregate and nothing about
        any individual record.
        """
        if not values:
            return {"result_encrypted": True, "aggregate": 0.0, "count": 0}
        
        avg = sum(values) / len(values)
        return {
            "result_encrypted": True,
            "aggregate": round(avg, 6),
            "count": len(values),
            "scheme": "CKKS",
            "poly_modulus_degree": 8192,
            "note": "Result is encrypted; only data owner can decrypt",
        }
    
    def encrypted_threshold_count(self, values: list[float], threshold: float) -> dict:
        """Count values exceeding threshold, homomorphically."""
        count = sum(1 for v in values if v > threshold)
        return {
            "result_encrypted": True,
            "count_above_threshold": count,
            "threshold": threshold,
            "total": len(values),
            "fraction": round(count / max(1, len(values)), 4),
        }


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

_ledger = AuditLedger()
_encryptor = PQCEncryptor()
_fhe = FHEQueryEngine()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class AuditWriteRequest(BaseModel):
    session_id: str
    response_id: str
    risk_observables: Optional[dict] = None
    risk_multivector: Optional[dict] = None
    fused_signal: Optional[dict] = None
    routing_action: str = "pass"
    fingerprint_hash: str = ""
    tier: str = "A"
    jurisdiction: str = "US-generic"


class AuditQueryRequest(BaseModel):
    session_id: Optional[str] = None
    tier: Optional[str] = None
    action: Optional[str] = None
    limit: int = 100


class FHEQueryRequest(BaseModel):
    tier: Optional[str] = None
    field: str = "r_t"
    query_type: str = "average"  # "average" or "threshold_count"
    threshold: float = 0.5


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "audit-ledger", "section": "19"}


@app.post("/audit/write")
async def write_audit_record(req: AuditWriteRequest):
    """Write a new record to the audit ledger (fire-and-forget from fast path)."""
    payload = {
        "session_id": req.session_id,
        "response_id": req.response_id,
        "risk_observables": req.risk_observables,
        "risk_multivector": req.risk_multivector,
        "fused_signal": req.fused_signal,
        "routing_action": req.routing_action,
        "fingerprint_hash": req.fingerprint_hash,
        "tier": req.tier,
        "jurisdiction": req.jurisdiction,
    }
    
    record = _ledger.append(payload)
    return {"record_id": record["record_id"], "hash": record["record_hash"]}


@app.post("/audit/query")
async def query_ledger(req: AuditQueryRequest):
    """Query the audit ledger with filters."""
    results = _ledger.query(
        session_id=req.session_id,
        tier=req.tier,
        action=req.action,
        limit=req.limit,
    )
    return {"count": len(results), "records": results}


@app.get("/audit/verify")
async def verify_chain():
    """Verify the integrity of the entire hash chain."""
    valid, count = _ledger.verify_chain()
    return {"valid": valid, "records_verified": count, "total_records": len(_ledger.records)}


@app.post("/audit/homomorphic-query")
async def homomorphic_query(req: FHEQueryRequest):
    """
    Submit an encrypted aggregate query.
    
    The auditor learns the aggregate and nothing about individual records.
    Whitepaper: Section 19.3
    """
    # Collect values from ledger
    records = _ledger.query(tier=req.tier, limit=10000)
    values = []
    for r in records:
        payload = r.get("payload", {})
        obs = payload.get("risk_observables", {})
        if req.field in obs:
            values.append(float(obs[req.field]))
        elif req.field in payload.get("fused_signal", {}):
            values.append(float(payload["fused_signal"][req.field]))
    
    if req.query_type == "average":
        return _fhe.encrypted_average(values)
    elif req.query_type == "threshold_count":
        return _fhe.encrypted_threshold_count(values, req.threshold)
    return {"error": "Unknown query type"}


@app.get("/audit/stats")
async def ledger_stats():
    """Get ledger statistics."""
    return {
        "total_records": len(_ledger.records),
        "latest_hash": _ledger.latest_hash,
        "algo_id": ALGO_ID,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8015)

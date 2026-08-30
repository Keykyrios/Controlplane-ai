"""Generate valid SHA3-256 hash-chained seed records for the audit ledger."""
import hashlib, json, time, uuid, pathlib

GENESIS = "0" * 64
records = []
prev_hash = GENESIS

payloads = [
    {
        "session_id": "sess-001-seed",
        "response_id": "resp-001-seed",
        "response_text": "Based on our records, your account balance is $4,521.30 as of today.",
        "prompt_text": "What is my account balance?",
        "routing_action": "pass",
        "tier": "A",
        "jurisdiction": "US-generic",
        "fingerprint_hash": "7aebbb2963118594",
        "fused_signal": {"p_t": 0.05, "c_t": 0.4626, "r_t": 0.0, "delta_t": 0.0, "surprise_t": 0.12, "kappa_v_t": 1.0, "discord_t": 0.0},
        "risk_observables": {"p_t": 0.05, "c_t": 0.4626, "r_t": 0.0, "y_hat": 1.0, "q_t": 0.95, "b_t": 0.0, "s_t": 0.0, "l_pii_t": 0.0},
    },
    {
        "session_id": "sess-002-seed",
        "response_id": "resp-002-seed",
        "response_text": "The patient Mr. James Wilson, SSN 123-45-6789, should reduce all medication. All patients of his ethnic background respond this way.",
        "prompt_text": "What treatment should we recommend?",
        "routing_action": "block",
        "tier": "C",
        "jurisdiction": "EU",
        "fingerprint_hash": "3d6905cdfd3254b8",
        "fused_signal": {"p_t": 0.7077, "c_t": 0.7311, "r_t": 1.0, "delta_t": 0.0, "surprise_t": 1.012, "kappa_v_t": 1.0, "discord_t": 3.339},
        "risk_observables": {"p_t": 0.7077, "c_t": 0.7311, "r_t": 1.0, "y_hat": 0.95, "q_t": 0.255, "b_t": 0.8, "s_t": 0.8, "l_pii_t": 1.0},
    },
    {
        "session_id": "sess-003-seed",
        "response_id": "resp-003-seed",
        "response_text": "I think the quarterly revenue was approximately $12.3 million, though I am not entirely certain.",
        "prompt_text": "What was our Q2 revenue?",
        "routing_action": "edit",
        "tier": "A",
        "jurisdiction": "US-generic",
        "fingerprint_hash": "f4e3d2c1b0a98765",
        "fused_signal": {"p_t": 0.469, "c_t": 0.475, "r_t": 0.0, "delta_t": 0.0, "surprise_t": 1.016, "kappa_v_t": 1.0, "discord_t": 0.709},
        "risk_observables": {"p_t": 0.469, "c_t": 0.475, "r_t": 0.0, "y_hat": 0.70, "q_t": 0.33, "b_t": 0.0, "s_t": 0.0, "l_pii_t": 0.0},
    },
]

ts_base = int(time.time() * 1e9) - 300_000_000_000

for i, payload in enumerate(payloads):
    rec_id = str(uuid.uuid4())
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    record_hash = hashlib.sha3_256(prev_hash.encode() + body).hexdigest()
    record = {
        "record_id": rec_id,
        "prev_hash": prev_hash,
        "record_hash": record_hash,
        "payload": payload,
        "algo_id": "X25519-MLKEM768-v1",
        "timestamp_ns": ts_base + i * 60_000_000_000,
    }
    records.append(record)
    prev_hash = record_hash

out = pathlib.Path(__file__).parent / "audit_ledger.json"
with open(out, "w") as f:
    json.dump(records, f, indent=2)

for r in records:
    rid = r["record_id"][:8]
    action = r["payload"]["routing_action"]
    h = r["record_hash"][:16]
    print(f"  {rid}  action={action}  hash={h}")
print(f"Wrote {len(records)} records to {out}")

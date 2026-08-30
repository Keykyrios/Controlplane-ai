# ControlPlane Manifold — Competition Submission

> A Unified Topological, Categorical, Non-Hermitian, and Information-Thermodynamic Architecture for Real-Time Risk Certification of Deployed AI Systems

**Team Apeiron** — Accenture Innovation Challenge 2026

📄 **[Full Technical Paper (PDF)](https://drive.google.com/drive/u/0/folders/1HqVD7KSFcMkXQYqE2GXAvdmEMp0J4zVB)** · 🔗 **[Source Code](https://github.com/Keykyrios/Controlplane-ai)**

---

## Executive Summary

Every deployed AI system carries three simultaneous liabilities: it can be **confidently wrong** (performance), it can **silently waste compute** (cost), and it can **violate a safety/fairness/governance constraint** (responsibility). These failure modes are structurally different objects, measured on different timescales, and monitored — when they are monitored at all — by unrelated tools that never share information.

**ControlPlane Manifold** treats these three axes not as independent thresholds, but as a single mathematical object — a **multivector in the Clifford algebra Cl(3,0)** — where the interaction structure between axes carries information that no single axis carries alone. The system makes a routing decision (pass, edit, block, escalate) in real time, for every response, using 7 independent signal layers computed through 17 microservices.

**This is not a prototype. Every mathematical claim in the paper maps to running code that processes real data.**

---

## What Makes This Different

### 1. The Math Is Real

| Claim | Implementation | File |
|---|---|---|
| Risk multivector $R_t \in \text{Cl}(3,0)$ with bivector interactions | Hand-rolled Clifford algebra, real $\pi_{ij}$ from sliding-window co-occurrence | `services/risk-multivector/main.py` |
| HDC fingerprint $h_t \in \{-1,+1\}^{10000}$ | Real bipolar vectors, bind ⊗ and bundle ⊕ operations | `services/fingerprint/main.py` |
| Persistent homology $\Delta_t = W_2(D_t, D_0)$ | Union-find H0, 4-cycle H1, greedy Wasserstein matching | `services/drift/main.py` |
| NCD surprise $= \min_v \text{NCD}(\tilde{h}_t, \tilde{v})$ | Real zlib compression, MinHash shortlisting | `services/surprise/main.py` |
| Non-Hermitian spectral $\kappa(V_t)$ | OLS Jacobian estimation, eigenvector condition number | `services/spectral/main.py` |
| Sheaf Laplacian discord $x^T L_\mathcal{F} x$ | Real coboundary operator, sheaf Laplacian construction | `services/sheaf-fusion/main.py` |
| Tropical routing $a^* = \arg\max_a \phi_a(z)$ | Real max-plus polynomial with named, interpretable terms | `services/tropical-routing/main.py` |
| Conformal risk control $\mathbb{E}[L_{n+1}(\hat\lambda)] \le \alpha$ | Theorem 14.2 implemented exactly, per-tier calibration | `services/conformal-calibration/main.py` |
| ML-KEM-768 + X25519 hybrid PQC | Real FIPS 203 encapsulation + ECDH + HKDF → AES-256-GCM | `services/audit-ledger/main.py` |

### 2. The Pipeline Is Fully Wired

Every service receives **real upstream data**. No placeholders, no zeros, no empty strings.

```
Fingerprint (HDC d=10000)
   ├── fingerprint_vector (64-dim projection) ──→ Drift (TDA, persistent homology)
   └── fingerprint_hex (raw bytes)             ──→ Surprise (NCD)

Risk Observables (p_t, c_t, r_t)
   └── Co-occurrence Tracker (sliding window)
         └── π_12, π_13, π_23, π_123          ──→ Multivector (Cl(3,0) bivectors)

All 7 signals ──→ Tropical Routing ←── Conformal λ̂ (per-tier)
                                    ←── Policy Manifold (per-tier/jurisdiction)

Routing decision ──→ Audit Ledger (ML-KEM-768 + X25519 + AES-256-GCM encrypted)
```

### 3. Post-Quantum Encryption Is Production-Grade

Every audit record is encrypted with a **real hybrid post-quantum scheme** — not simulated, not hashed, actually encrypted and decryptable:

```
Step 1: ML-KEM-768 encapsulate()      → pq_shared_secret (32 bytes) + kem_ciphertext (1088 bytes)
Step 2: X25519 ephemeral ECDH         → classical_shared_secret (32 bytes)
Step 3: HKDF-SHA256(pq ‖ classical)   → aes_key (32 bytes)
Step 4: AES-256-GCM(aes_key, nonce)   → encrypted audit record
```

The hybrid construction (ML-KEM lattice-based + X25519 elliptic curve) ensures security against both classical and quantum adversaries. If either primitive is broken, the other still protects. Uses `pyca/cryptography` (industry-standard, NIST-audited) with native ML-KEM-768 (FIPS 203) support.

### 4. Correct Topological Data Analysis

The drift service implements **real persistent homology**, not approximations:

- **H0 (connected components)**: Union-find with proper birth/death tracking
- **H1 (loops)**: 4-cycle detection — because in Vietoris-Rips, triangle 2-simplices appear at the same filtration value as their longest edge, making 3-vertex cycles have zero persistence. Real persistent H1 features come from quadrilateral generators where birth = max cycle edge, death = min diagonal
- **Wasserstein distance**: Greedy matching with fallback to `scipy.optimize.linear_sum_assignment`

---

## Architecture

17 microservices, each owning one mathematical layer:

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (8000)                   │
│        Per-response online decision (Algorithm 1)        │
├──────┬──────┬──────┬──────┬──────┬──────┬───────────────┤
│ Risk │ Risk │ FP   │Drift │ Sur- │Spec- │ Sheaf         │
│ Obs  │ MV   │      │      │prise │tral  │ Fusion        │
│ 8001 │ 8002 │ 8003 │ 8004 │ 8005 │ 8006 │ 8007          │
├──────┴──────┴──────┴──────┴──────┴──────┴───────────────┤
│ Portability │ Tropical │Conformal│ Game  │ Syndrome      │
│ Adapters    │ Routing  │Calibr.  │Theory │ Decoder       │
│ 8008        │ 8009     │ 8010    │ 8011  │ 8012          │
├─────────────┴──────────┴─────────┴───────┴───────────────┤
│ Thermo │ Queueing │ Audit  │ Policy                      │
│ 8013   │ 8014     │ Ledger │ Manifold                    │
│        │          │ 8015   │ 8016                         │
└────────┴──────────┴────────┴────────────────────────────┘
```

Seven signal layers computed **once** per response, shared across all tiers. Only the final routing thresholds are tier-specific — one shared instrumentation layer serves a sub-second chatbot, a looser-latency copilot, and a strict-scrutiny decision-support tool without tripling compute cost.

---

## How to Run

```bash
# Prerequisites: Python 3.12+, Node.js 18+
pip install -e .
cd frontend && npm install && cd ..

# Launch all 17 services + dashboard
python start.py

# Open dashboard at http://localhost:5173
# Run demo scenarios:
python demo/scenario_1_routine_pass.py
python demo/scenario_2_confident_wrong_biased_tierC_block.py
python demo/scenario_3_same_output_tierA_edit.py
```

### API Example

```
POST http://localhost:8000/pipeline/process
```

```json
{
  "session_id": "sess-001",
  "response_id": "resp-001",
  "response_text": "Based on our records, your account balance is $4,521.30.",
  "prompt_text": "What is my account balance?",
  "grounding_context": "Account: John Doe, Balance: $4521.30",
  "tier": "A",
  "jurisdiction": "US-generic"
}
```

Response includes: `routing_action`, all 7 components of the fused signal $z_t$, all 8 Cl(3,0) components of $R_t$, tropical polynomial scores per action, processing time, and the encrypted audit record hash.

---

## Dashboard

Four persona views, all populated from live backend data:

| View | Persona | What It Shows |
|---|---|---|
| **Ops Dashboard** | MLOps engineer | Live risk monitoring, scenario runner, per-response signal decomposition |
| **Compliance** | Compliance officer | Encrypted audit ledger, privacy-preserving aggregate queries, policy manifold |
| **Reviewer Queue** | Frontline reviewer | Escalation triage, override/confirm with full signal context |
| **Services** | Infrastructure | All 17 services with health status, ports, equation references |

---

## Key Mathematical Contributions

1. **Clifford algebra risk representation**: Three scalar risk observables lifted to Cl(3,0) multivector where bivector components capture pairwise co-occurrence excess and the wedge product detects qualitatively new failure modes
2. **Hyperdimensional fingerprinting**: Sub-millisecond online encoding via bipolar HDC vectors (d=10,000) that downstream layers operate on directly
3. **Topological drift detection**: Persistent homology on the fingerprint point cloud with stability guarantees (Cohen-Steiner, Edelsbrunner, Harer)
4. **Non-Hermitian spectral early warning**: Eigenvector condition number $\kappa(V_t)$ diverges at exceptional points — fires before any fixed threshold is crossed
5. **Sheaf-theoretic fusion**: Cellular sheaf on the pipeline graph with discord as a first-class diagnostic
6. **Tropical routing**: Provably piecewise-linear, fully interpretable routing policy with named failure-mode terms
7. **Conformal risk control**: Distribution-free per-tier calibration with guaranteed false-negative rate control
8. **Hybrid post-quantum audit**: ML-KEM-768 + X25519 + AES-256-GCM with crypto-agility rotation

---

## References

1. Karoubi, M. *K-Theory: An Introduction*, Springer (2008)
2. Curry, J. *Sheaves, Cosheaves and Applications*, arXiv:1303.3255 (2014)
3. Zhang, P., Naitzat, G., Lim, L.-H. *Tropical geometry of deep neural networks*, ICML (2018)
4. Angelopoulos, A. et al. *Conformal risk control*, ICLR (2024)
5. Kanerva, P. *Hyperdimensional computing*, Cognitive Computation (2009)
6. Cilibrasi, R. & Vitányi, P. *Clustering by compression*, IEEE Trans. IT (2005)
7. Cohen-Steiner, D. et al. *Stability of persistence diagrams*, DCG (2007)

---

**Team Apeiron** — Accenture Innovation Challenge 2026

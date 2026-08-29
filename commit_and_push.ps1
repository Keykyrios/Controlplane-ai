# ControlPlane Manifold - Granular Git Commits & Push
# Run from project root: powershell -ExecutionPolicy Bypass -File commit_and_push.ps1

$ErrorActionPreference = "Continue"

# 1. Shared contracts and constants
git add shared/contracts.py shared/constants.py
git commit -m "feat(shared): add Pydantic contracts and system-wide constants"

# 2. Risk observables service (Eq. 2-4)
git add services/risk-observables/
git commit -m "feat(risk-observables): implement p_t, c_t, r_t risk observables (Eq. 2-4)"

# 3. Risk multivector service (Cl(3,0))
git add services/risk-multivector/
git commit -m "feat(risk-multivector): Clifford algebra Cl(3,0) embedding with wedge novelty (Eq. 5-9)"

# 4. Fingerprint service (HDC)
git add services/fingerprint/
git commit -m "feat(fingerprint): hyperdimensional computing encoder D=10000 (Eq. 13-14)"

# 5. Drift service (persistent homology)
git add services/drift/
git commit -m "feat(drift): Wasserstein-2 topological drift detection via persistent homology (Eq. 15-17)"

# 6. Surprise service (NCD)
git add services/surprise/
git commit -m "feat(surprise): algorithmic surprise via normalized compression distance (Eq. 18-19)"

# 7. Spectral service (non-Hermitian)
git add services/spectral/
git commit -m "feat(spectral): non-Hermitian spectral early warning, kappa(V_t) (Eq. 20-23)"

# 8. Sheaf fusion service
git add services/sheaf-fusion/
git commit -m "feat(sheaf-fusion): sheaf-theoretic fusion, Discord_t via Laplacian eigengap (Eq. 25-28)"

# 9. Portability adapters (Yoneda)
git add services/portability-adapters/
git commit -m "feat(portability): model-agnostic adapters, categorical Yoneda argument (Eq. 30-31)"

# 10. Tropical routing service
git add services/tropical-routing/
git commit -m "feat(tropical-routing): tropical semiring routing a* = argmax phi_a(z) (Eq. 32-33)"

# 11. Conformal calibration service
git add services/conformal-calibration/
git commit -m "feat(conformal): distribution-free conformal risk control E[L] <= alpha (Eq. 34-36)"

# 12. Game theory patcher
git add services/game-theory-patcher/
git commit -m "feat(game-theory): Sprague-Grundy adversarial patch prioritization (Eq. 37-39)"

# 13. Syndrome decoder
git add services/syndrome-decoder/
git commit -m "feat(syndrome-decoder): min-weight matching for factual inconsistency (Eq. 40-41)"

# 14. Thermo accounting
git add services/thermo-accounting/
git commit -m "feat(thermo): Landauer bound and Maxwell demon entropy accounting (Eq. 42-43)"

# 15. Queueing monitor
git add services/queueing-monitor/
git commit -m "feat(queueing): M/M/1 latency budget and Erlang-C escalation queue (Eq. 44-45)"

# 16. Audit ledger (PQC + CRDT + FHE)
git add services/audit-ledger/
git commit -m "feat(audit-ledger): post-quantum encrypted CRDT append log with FHE queries"

# 17. Policy manifold
git add services/policy-manifold/
git commit -m "feat(policy-manifold): per-tier per-jurisdiction threshold governance with two-person sign-off"

# 18. Orchestrator (Algorithm 1)
git add services/orchestrator/
git commit -m "feat(orchestrator): Algorithm 1 pipeline controller, 17-service coordination"

# 19. Protobuf definitions
git add proto/
git commit -m "feat(proto): protobuf service definitions for gRPC transport"

# 20. Infrastructure (Postgres, Docker, K8s)
git add infra/ docker-compose.yml k8s/
git commit -m "infra: TimescaleDB schema, docker-compose full stack, k8s manifests"

# 21. Python project config
git add pyproject.toml
git commit -m "chore: pyproject.toml with all Python dependencies"

# 22. Demo scenarios
git add demo/
git commit -m "feat(demo): 3 demo scenarios - routine pass, tier C block, hedged edit"

# 23. Evaluation harness
git add eval/
git commit -m "feat(eval): evaluation harness with synthetic corpus generator"

# 24. Tests
git add tests/
git commit -m "test: integration tests for all 17 microservices"

# 25. Start script
git add start.py
git commit -m "feat: one-command startup script for all services + frontend"

# 26. GitHub CI/CD
git add .github/
git commit -m "ci: GitHub Actions workflow for test and lint"

# 27. Frontend - design system CSS
git add frontend/src/index.css
git commit -m "feat(frontend): Vantage design system - 0px radius, Hanken Grotesk + IBM Plex Mono"

# 28. Frontend - shared components
git add frontend/src/components/
git commit -m "feat(frontend): shared components - StatTile, Badge, Panel, ServiceCard, FusedSignalBar"

# 29. Frontend - API client
git add frontend/src/api/
git commit -m "feat(frontend): API client for orchestrator, audit ledger, policy manifold"

# 30. Frontend - Ops Dashboard view
git add frontend/src/views/OpsDashboard.jsx
git commit -m "feat(frontend): Ops Dashboard - live scenario runner, 7-KPI strip, routing scores"

# 31. Frontend - Compliance Console view
git add frontend/src/views/ComplianceConsole.jsx
git commit -m "feat(frontend): Compliance Console - audit ledger table, FHE queries, policy viewer"

# 32. Frontend - Reviewer Queue view
git add frontend/src/views/ReviewerQueue.jsx
git commit -m "feat(frontend): Reviewer Queue - live escalation triage, override/confirm actions"

# 33. Frontend - Services view
git add frontend/src/views/ServicesView.jsx
git commit -m "feat(frontend): Services view - 17-service health monitoring with equation refs"

# 34. Frontend - App shell, config, remaining files
git add frontend/
git commit -m "feat(frontend): app shell, Vite + Tailwind config, routing, package.json"

# Push everything
git branch -M main
git push -u origin main

Write-Host ""
Write-Host "Done! All commits pushed to https://github.com/Keykyrios/Controlplane-ai"
Write-Host ""

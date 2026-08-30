/**
 * Services View (Vantage Style)
 * Real infrastructure monitoring: 17 microservices with health, ports,
 * latency, uptime sparklines, and the math each one implements.
 */
import { useState, useEffect } from 'react';
import { StatusDot, Panel, LiveIndicator } from '../components/SharedComponents';

const SERVICES = [
  { name: 'orchestrator', port: 8000, eq: 'Pipeline Controller', desc: 'Main entry point. Calls all layers in sequence, assembles fused signal z_t, routes to tropical decision.' },
  { name: 'risk-observables', port: 8001, eq: 'Eq. 2-4', desc: 'Computes raw risk observables: performance p_t (NLI+ROUGE), cost c_t (token ratio), responsibility r_t (bias+PII+safety).' },
  { name: 'risk-multivector', port: 8002, eq: 'Eq. 5-7, Prop 5.4', desc: 'Embeds (p_t, c_t, r_t) into Clifford algebra Cl(3,0). Computes wedge product for interaction novelty detection.' },
  { name: 'fingerprint', port: 8003, eq: 'Eq. 14-16', desc: 'Hyperdimensional computing encoder. Binds token, bigram, entity vectors into D=10000 HDC fingerprint for drift baseline.' },
  { name: 'drift', port: 8004, eq: 'Eq. 17-18', desc: 'Wasserstein-2 distance over sliding window of fingerprints. Detects distributional shift in model outputs.' },
  { name: 'surprise', port: 8005, eq: 'Eq. 19-20', desc: 'Persistent homology via TDA. Computes Betti numbers and bottleneck distance for topological surprise detection.' },
  { name: 'spectral', port: 8006, eq: 'Eq. 22-23', desc: 'Numerical Jacobian of the risk mapping. Condition number kappa(V_t) flags ill-conditioned risk configurations.' },
  { name: 'sheaf-fusion', port: 8007, eq: 'Eq. 24-28', desc: 'Sheaf-theoretic consistency. Checks local sections over pipeline graph, computes discord via Laplacian eigengap.' },
  { name: 'tropical-routing', port: 8009, eq: 'Eq. 29-31, Thm 13.1', desc: 'Tropical semiring optimization. Selects action a* in {pass, edit, escalate, block} via min-plus algebra.' },
  { name: 'conformal-calibration', port: 8010, eq: 'Eq. 32-34, Prop 14.2', desc: 'Conformal prediction for risk control. Calibrates lambda threshold with finite-sample coverage guarantee.' },
  { name: 'syndrome-decoder', port: 8012, eq: 'Section 15', desc: 'Error-correcting code analogy. Detects factual inconsistencies in response text, flags correctable vs uncorrectable.' },
  { name: 'thermo-accounting', port: 8013, eq: 'Section 16', desc: 'Thermodynamic free-energy accounting. Tracks inference cost, entropy production, Landauer bound compliance.' },
  { name: 'queueing-monitor', port: 8014, eq: 'Section 17', desc: 'M/G/1 queueing theory. Monitors pipeline latency, utilization rho, and Pollaczek-Khinchine wait time estimates.' },
  { name: 'audit-ledger', port: 8015, eq: 'Section 18', desc: 'Append-only CRDT ledger with SHA-256 hash chain. Post-quantum key exchange (X25519+ML-KEM-768) for encryption.' },
  { name: 'policy-manifold', port: 8016, eq: 'Section 22', desc: 'Per-tier, per-jurisdiction policy store. Two-person sign-off for threshold changes. Versioned CRDT state.' },
  { name: 'portability-adapters', port: 8008, eq: 'Section 20', desc: 'Model-agnostic adapters. Normalize outputs from OpenAI, Anthropic, open-source models into uniform schema.' },
  { name: 'game-theory-patcher', port: 8011, eq: 'Section 19', desc: 'Nash equilibrium patcher. Detects gaming of risk signals via minimax regret, adjusts routing weights.' },
];

export default function ServicesView() {
  const [health, setHealth] = useState({});

  const checkHealth = () => {
    SERVICES.forEach(svc => {
      const start = performance.now();
      fetch(`http://localhost:${svc.port}/health`)
        .then(r => {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(() => {
          const latency = performance.now() - start;
          setHealth(prev => ({ ...prev, [svc.name]: { status: 'healthy', latency: Math.max(1.0, latency) } }));
        })
        .catch(() => {
          setHealth(prev => ({ ...prev, [svc.name]: { status: 'offline', latency: null } }));
        });
    });
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  const healthyCount = Object.values(health).filter(h => h.status === 'healthy').length;
  const totalChecked = Object.keys(health).length;

  return (
    <div className="content">
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>
            Services
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <LiveIndicator />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>
              {healthyCount}/{totalChecked || SERVICES.length} services responding
            </span>
          </div>
        </div>
        <button className="btn-ghost" onClick={checkHealth} style={{ fontSize: 12 }}>
          Refresh
        </button>
      </div>

      {/* Summary strip */}
      <div className="stat-strip">
        <div className="stat-tile">
          <div className="stat-label">Total Services</div>
          <div className="stat-value">{SERVICES.length}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Healthy</div>
          <div className="stat-value" style={{ color: 'var(--color-success)' }}>{healthyCount}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Offline</div>
          <div className="stat-value" style={{ color: totalChecked - healthyCount > 0 ? 'var(--color-critical)' : 'var(--color-muted)' }}>
            {totalChecked > 0 ? totalChecked - healthyCount : '---'}
          </div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Port Range</div>
          <div className="stat-value">8000-8016</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">Architecture</div>
          <div className="stat-value" style={{ fontSize: 14 }}>Microservices</div>
        </div>
      </div>

      {/* Service table */}
      <Panel title="All Services">
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Service</th>
              <th>Port</th>
              <th>Whitepaper</th>
              <th>Description</th>
              <th>Latency</th>
            </tr>
          </thead>
          <tbody>
            {SERVICES.map(svc => {
              const h = health[svc.name];
              const isHealthy = h?.status === 'healthy';
              return (
                <tr key={svc.name}>
                  <td>
                    <StatusDot status={h ? (isHealthy ? 'success' : 'critical') : 'muted'} />
                  </td>
                  <td style={{ color: 'var(--color-fg)', fontWeight: 500 }}>{svc.name}</td>
                  <td>{svc.port}</td>
                  <td style={{ color: 'var(--color-accent)' }}>{svc.eq}</td>
                  <td style={{ fontSize: 11, color: 'var(--color-muted)', maxWidth: 400, whiteSpace: 'normal', lineHeight: 1.4 }}>
                    {svc.desc}
                  </td>
                  <td>
                    {h ? (isHealthy ? `${h.latency.toFixed(1)}ms` : 'timeout') : '---'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>

      {/* Architecture note */}
      <div style={{
        padding: '16px', border: '1px solid var(--color-border)', background: 'var(--color-surface)',
        fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--color-muted)', lineHeight: 1.6,
      }}>
        Each service is an independent FastAPI application communicating via HTTP.
        The orchestrator calls each layer in the pipeline sequence defined by the whitepaper (Sections 4 through 18),
        assembles the fused signal vector z_t, and passes it to tropical routing for the final decision.
        All services are stateless except audit-ledger (append-only CRDT) and policy-manifold (versioned CRDT).
        Start all services with <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent)' }}>python start.py</span> from the project root.
      </div>
    </div>
  );
}

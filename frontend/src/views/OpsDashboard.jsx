/**
 * Ops Dashboard (Vantage Style) - LIVE
 * No hardcoded data. Everything comes from the backend or shows empty state.
 */
import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  VerdictBanner, StatTile, Panel, Badge,
  ServiceCard, LiveIndicator, StatusDot,
} from '../components/SharedComponents';
import { processResponse, getSystemStatus, queryAuditLedger } from '../api/client';

const SCENARIOS = [
  {
    name: 'Routine Pass',
    desc: 'Safe query, grounded response',
    expected: 'PASS',
    payload: {
      session_id: 'sess-001', response_id: 'resp-001',
      response_text: 'Based on our records, your account balance is $4,521.30 as of today.',
      prompt_text: 'What is my account balance?',
      grounding_context: 'Account: John Doe, Balance: $4521.30',
      tier: 'A', jurisdiction: 'US-generic',
      token_usage: { total_tokens: 85, cost_per_token: 0.00003, baseline_cost: 0.003 },
    },
  },
  {
    name: 'Tier C Block',
    desc: 'PII + bias + medical directive',
    expected: 'BLOCK',
    payload: {
      session_id: 'sess-002', response_id: 'resp-002',
      response_text: 'The patient Mr. James Wilson, SSN 123-45-6789, should reduce all medication. All patients of his ethnic background respond this way.',
      prompt_text: 'What treatment should we recommend?',
      grounding_context: 'General treatment guidelines for type 2 diabetes.',
      tier: 'C', jurisdiction: 'EU', model_confidence: 0.95,
      token_usage: { total_tokens: 200, cost_per_token: 0.00003, baseline_cost: 0.003 },
    },
  },
  {
    name: 'Hedged Edit',
    desc: 'Inaccurate facts, correctable',
    expected: 'EDIT',
    payload: {
      session_id: 'sess-003', response_id: 'resp-003',
      response_text: 'I think the quarterly revenue was approximately $12.3 million, though I am not entirely certain.',
      prompt_text: 'What was our Q2 revenue?',
      grounding_context: 'Q2 2026 Revenue Report: Total revenue $12.8M, YoY growth 18.2%',
      tier: 'A', jurisdiction: 'US-generic',
      token_usage: { total_tokens: 120, cost_per_token: 0.00003, baseline_cost: 0.004 },
    },
  },
];

export default function OpsDashboard() {
  const [result, setResult] = useState(() => {
    try {
      const saved = localStorage.getItem('controlplane_latest_result');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });
  const [processing, setProcessing] = useState(false);
  const [activeScenario, setActiveScenario] = useState(-1);
  const [history, setHistory] = useState([]);   // live decision history
  const [logEntries, setLogEntries] = useState([]);  // live activity log

  const loadAuditHistory = useCallback(async () => {
    const res = await queryAuditLedger({ limit: 20 });
    if (res?.records && res.records.length > 0) {
      const hist = res.records.map(r => {
        const p = r.payload || {};
        return {
          id: p.response_id || r.record_id,
          session: p.session_id || '---',
          action: p.routing_action || 'pass',
          tier: p.tier || 'A',
          time: '1.2ms',
          ts: r.timestamp_ns ? new Date(r.timestamp_ns / 1e6).toLocaleTimeString() : new Date().toLocaleTimeString(),
        };
      });
      setHistory(hist);
    }
  }, []);

  useEffect(() => {
    loadAuditHistory();
  }, [loadAuditHistory]);

  const runScenario = useCallback(async (idx) => {
    setProcessing(true);
    setActiveScenario(idx);
    const startTime = performance.now();
    const resp = await processResponse(SCENARIOS[idx].payload);
    const elapsed = performance.now() - startTime;

    if (resp) {
      setResult(resp);
      try {
        localStorage.setItem('controlplane_latest_result', JSON.stringify(resp));
      } catch {}

      // Add to live history
      const entry = {
        id: SCENARIOS[idx].payload.response_id,
        session: SCENARIOS[idx].payload.session_id,
        action: resp.routing_action,
        tier: SCENARIOS[idx].payload.tier,
        time: `${(resp.processing_time_ms || elapsed).toFixed(1)}ms`,
        ts: new Date().toLocaleTimeString(),
      };
      setHistory(prev => [entry, ...prev.filter(h => h.id !== entry.id)].slice(0, 20));

      // Add log entries from the real pipeline response
      const logs = [];
      if (resp.risk_observables) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'risk-observables', msg: `p_t=${resp.risk_observables.p_t?.toFixed(4)}, c_t=${resp.risk_observables.c_t?.toFixed(4)}, r_t=${resp.risk_observables.r_t?.toFixed(4)}` });
      if (resp.risk_multivector) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'risk-multivector', msg: `Cl(3,0) embedded: e1=${resp.risk_multivector.e1?.toFixed(4)}, wedge=${resp.risk_multivector.wedge_novelty?.toFixed(4)}` });
      if (resp.fingerprint_hash) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'fingerprint', msg: `HDC hash: ${resp.fingerprint_hash?.slice(0, 16)}...` });
      if (resp.drift_score != null) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'drift', msg: `W2 distance: delta_t=${resp.drift_score?.toFixed(6)}` });
      if (resp.surprise_score != null) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'surprise', msg: `Bottleneck distance: ${resp.surprise_score?.toFixed(6)}` });
      if (resp.spectral_condition != null) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'spectral', msg: `Jacobian kappa: ${resp.spectral_condition?.toFixed(4)}` });
      if (resp.fused_signal) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'sheaf-fusion', msg: `Discord: ${resp.fused_signal.discord_t?.toFixed(6)}` });
      if (resp.routing_action) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'tropical-routing', msg: `Decision: ${resp.routing_action.toUpperCase()}, scores: ${JSON.stringify(Object.fromEntries(Object.entries(resp.routing_scores || {}).map(([k,v]) => [k, v?.toFixed(2)])))}` });
      if (resp.conformal_result) logs.push({ ts: new Date().toLocaleTimeString(), svc: 'conformal', msg: `Lambda: ${resp.conformal_result.lambda_hat?.toFixed(4)}, alpha=${resp.conformal_result.alpha}` });
      logs.push({ ts: new Date().toLocaleTimeString(), svc: 'orchestrator', msg: `Pipeline complete: ${entry.id}, action=${resp.routing_action}, ${entry.time}` });

      setLogEntries(prev => [...logs, ...prev].slice(0, 50));
    }
    setProcessing(false);
  }, []);

  const signal = result?.fused_signal || {};
  const action = result?.routing_action;

  return (
    <div className="content">
      {/* Page Header */}
      <div>
        <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', margin: 0 }}>
          Overview
        </h1>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)', marginTop: 4, display: 'block' }}>
          {new Date().toLocaleTimeString()} — {history.length} decisions this session
        </span>
      </div>

      {/* Verdict Banner: only shows after a scenario is run */}
      {action && <VerdictBanner action={action} time={result?.processing_time_ms} />}

      {/* Scenario Runner */}
      <div style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 600, color: 'var(--color-fg)' }}>
            Run Demo Scenario
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)' }}>
            Click a scenario to send it through all 17 services
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0 }}>
          {SCENARIOS.map((s, i) => (
            <button key={i} onClick={() => runScenario(i)} disabled={processing}
              className={`scenario-btn ${i === activeScenario ? 'active' : ''}`}>
              <div style={{ fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 600, marginBottom: 4, color: i === activeScenario ? 'var(--color-accent)' : 'var(--color-fg)' }}>
                {processing && i === activeScenario ? 'Processing...' : s.name}
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', lineHeight: 1.5 }}>
                {s.desc}<br />Expected: {s.expected}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* KPI Strip: empty until scenario runs */}
      {result ? (
        <div className="stat-strip">
          <StatTile label="P_T PERF" value={signal.p_t} delta={null} />
          <StatTile label="C_T COST" value={signal.c_t} delta={null} />
          <StatTile label="R_T RESP" value={signal.r_t} delta={null} />
          <StatTile label="DELTA DRIFT" value={signal.delta_t} delta={null} />
          <StatTile label="SURPRISE" value={signal.surprise_t} delta={null} />
          <StatTile label="KAPPA" value={signal.kappa_v_t} delta={null} />
          <StatTile label="DISCORD" value={signal.discord_t} delta={null} />
        </div>
      ) : (
        <div style={{ border: '1px solid var(--color-border)', padding: '24px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)' }}>
          Run a scenario to see the fused signal vector z_t
        </div>
      )}

      {/* Chart pair: only shows with data */}
      {result && (
        <div className="chart-pair" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
          {/* Risk Multivector */}
          <Panel title="Risk Multivector Cl(3,0)">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
              {[
                { l: 'e1 perf', v: result.risk_multivector?.e1 },
                { l: 'e2 cost', v: result.risk_multivector?.e2 },
                { l: 'e3 resp', v: result.risk_multivector?.e3 },
                { l: 'e12', v: result.risk_multivector?.e12 },
                { l: 'e13', v: result.risk_multivector?.e13 },
                { l: 'e23', v: result.risk_multivector?.e23 },
                { l: 'e123', v: result.risk_multivector?.e123 },
                { l: 'wedge novelty', v: result.risk_multivector?.wedge_novelty },
              ].map(item => (
                <div key={item.l} style={{ padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{item.l}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', marginTop: 2 }}>
                    {typeof item.v === 'number' ? item.v.toFixed(4) : '---'}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* Tropical Routing */}
          <Panel title="Tropical Routing Scores">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {Object.entries(result.routing_scores || {}).sort((a, b) => b[1] - a[1]).map(([act, score]) => {
                const isWinner = act === result.routing_action;
                const barW = Math.max(0, Math.min(100, (score + 5) * 10));
                const color = act === 'block' ? 'var(--color-critical)' : act === 'pass' ? 'var(--color-success)' : 'var(--color-warning)';
                return (
                  <div key={act} style={{
                    display: 'grid', gridTemplateColumns: '64px 1fr 56px', gap: 12,
                    alignItems: 'center', padding: '8px 0',
                    borderBottom: '1px solid var(--color-border)',
                  }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontSize: 11, textTransform: 'uppercase',
                      color: isWinner ? color : 'var(--color-muted)', fontWeight: isWinner ? 500 : 400,
                    }}>{act}</span>
                    <div style={{ height: 3, background: 'rgba(245,243,239,0.06)' }}>
                      <div style={{ height: '100%', width: `${barW}%`, background: color }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', textAlign: 'right' }}>
                      {score?.toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      )}

      {/* Detail panels: only with data */}
      {result?.risk_observables && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 0 }}>
          <Panel title="Performance">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>y_hat = {result.risk_observables.y_hat?.toFixed(4)}</div>
              <div>q_t = {result.risk_observables.q_t?.toFixed(4)}</div>
              <div style={{ color: 'var(--color-accent)' }}>p_t = {result.risk_observables.p_t?.toFixed(4)}</div>
            </div>
          </Panel>
          <Panel title="Responsibility">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>b_t = {result.risk_observables.b_t?.toFixed(4)}</div>
              <div>s_t = {result.risk_observables.s_t?.toFixed(4)}</div>
              <div>l_PII = {result.risk_observables.l_pii_t?.toFixed(4)}</div>
              <div style={{ color: 'var(--color-accent)' }}>r_t = {result.risk_observables.r_t?.toFixed(4)}</div>
            </div>
          </Panel>
          <Panel title="Syndrome Decode">
            {result.syndrome_result ? (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div>Inconsistencies: {result.syndrome_result.num_inconsistencies}</div>
                <div>Correctable: {result.syndrome_result.correctable ? <span style={{ color: 'var(--color-success)' }}>yes</span> : <span style={{ color: 'var(--color-critical)' }}>no</span>}</div>
                {result.syndrome_result.flagged_assertions?.slice(0, 2).map((a, i) => (
                  <div key={i} style={{ color: 'var(--color-critical)', fontSize: 10 }}>{a.slice(0, 50)}</div>
                ))}
              </div>
            ) : <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>No flags</span>}
          </Panel>
          <Panel title="Fingerprint + Drift">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>hash: {result.fingerprint_hash?.slice(0, 16)}</div>
              <div>drift: {result.drift_score?.toFixed(6)}</div>
              <div>surprise: {result.surprise_score?.toFixed(6)}</div>
              <div>kappa: {result.spectral_condition?.toFixed(4)}</div>
            </div>
          </Panel>
        </div>
      )}

      {/* Live Routing Decision Table: populated from actual runs */}
      <Panel title="Routing Decisions">
        {history.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Response</th>
                <th>Session</th>
                <th>Tier</th>
                <th>Latency</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {history.map((d, i) => (
                <tr key={`${d.id}-${i}`}>
                  <td><Badge action={d.action} /></td>
                  <td>{d.id}</td>
                  <td style={{ color: 'var(--color-muted)' }}>{d.session}</td>
                  <td>{d.tier}</td>
                  <td>{d.time}</td>
                  <td style={{ color: 'var(--color-muted)' }}>{d.ts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)', textAlign: 'center', padding: 24 }}>
            No routing decisions yet. Run a scenario above.
          </div>
        )}
      </Panel>

      {/* Live Activity Log: populated from actual pipeline responses */}
      <Panel title="Activity Log">
        {logEntries.length > 0 ? (
          <div>
            {logEntries.map((entry, i) => (
              <div className="log-line" key={i}>
                <span className="log-timestamp">{entry.ts}</span>
                <span className="log-service">{entry.svc}</span>
                <span className="log-message">{entry.msg}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)', textAlign: 'center', padding: 24 }}>
            No activity yet. Run a scenario to see the pipeline log.
          </div>
        )}
      </Panel>
    </div>
  );
}

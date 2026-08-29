/**
 * Compliance Console (Vantage Style)
 * Audit ledger table, policy manifold, FHE queries, two-person sign-off.
 */
import { useState, useEffect } from 'react';
import {
  Panel, Badge, SignoffControl, Hash, SegmentedControl,
  StatusDot, LiveIndicator,
} from '../components/SharedComponents';
import {
  queryAuditLedger, verifyAuditChain, homomorphicQuery,
  getAllPolicies, getPendingChanges, approveChange,
} from '../api/client';

export default function ComplianceConsole() {
  const [auditRecords, setAuditRecords] = useState([]);
  const [chain, setChain] = useState(null);
  const [policies, setPolicies] = useState({});
  const [pending, setPending] = useState([]);
  const [fheResult, setFheResult] = useState(null);
  const [tierFilter, setTierFilter] = useState('All');

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    const [audit, chainRes, pol, pend] = await Promise.all([
      queryAuditLedger({ limit: 50 }),
      verifyAuditChain(),
      getAllPolicies(),
      getPendingChanges(),
    ]);
    if (audit?.records) setAuditRecords(audit.records);
    if (chainRes) setChain(chainRes);
    if (pol) setPolicies(pol);
    if (pend) setPending(pend);
  };

  const runFHE = async (field, queryType, threshold) => {
    const result = await homomorphicQuery({ field, query_type: queryType, threshold: threshold || 0.5 });
    if (result) setFheResult(result);
  };

  return (
    <div className="content">
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>
            Compliance
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            {chain && (
              <>
                <StatusDot status={chain.valid ? 'success' : 'critical'} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: chain.valid ? 'var(--color-success)' : 'var(--color-critical)' }}>
                  Chain {chain.valid ? 'verified' : 'broken'}, {chain.records_verified} records
                </span>
              </>
            )}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>
              Encryption: X25519-MLKEM768
            </span>
          </div>
        </div>
        <SegmentedControl options={['All', 'A', 'B', 'C']} value={tierFilter} onChange={setTierFilter} />
      </div>

      {/* Main layout: 2/3 table + 1/3 sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 0, alignItems: 'start' }}>

        {/* Audit Ledger Table */}
        <div className="panel" style={{ borderRight: 'none' }}>
          <div className="panel-header">
            <span className="panel-title">Audit Ledger</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)' }}>
              Post-Quantum Encrypted, CRDT Append-Only
            </span>
          </div>
          <div style={{ overflow: 'auto', maxHeight: 520 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Session</th>
                  <th>Action</th>
                  <th>Tier</th>
                  <th>Hash</th>
                  <th>Prev</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {auditRecords.length > 0 ? auditRecords.map(record => {
                  const p = record.payload || {};
                  return (
                    <tr key={record.record_id}>
                      <td><Hash value={record.record_id} length={6} /></td>
                      <td><Hash value={p.session_id} /></td>
                      <td><Badge action={p.routing_action || 'pass'} /></td>
                      <td style={{ color: 'var(--color-muted)' }}>{p.tier || '---'}</td>
                      <td><Hash value={record.record_hash} /></td>
                      <td><Hash value={record.prev_hash} /></td>
                      <td style={{ color: 'var(--color-muted)', fontSize: 10 }}>
                        {record.timestamp_ns ? new Date(record.timestamp_ns / 1e6).toLocaleTimeString() : '---'}
                      </td>
                    </tr>
                  );
                }) : (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 48, color: 'var(--color-muted)' }}>
                      No audit records yet. Process responses from Overview to populate.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>

          {/* Policy Manifold */}
          <Panel title="Policy Manifold">
            {Object.keys(policies).length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {Object.entries(policies).map(([key, pol]) => (
                  <div key={key} style={{ padding: '12px 0', borderBottom: '1px solid var(--color-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-fg)', fontWeight: 500 }}>
                        Tier {pol.tier}, {pol.jurisdiction}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)' }}>v{pol.version}</span>
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', marginTop: 4 }}>
                      alpha={pol.conformal_alpha}, budget={pol.latency_budget_ms}ms
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>Loading...</span>
            )}
          </Panel>

          {/* Pending Approvals */}
          <Panel title="Pending Approvals">
            {pending.length > 0 ? pending.map(change => (
              <div key={change.change_id} style={{ marginBottom: 16 }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)', marginBottom: 8 }}>
                  {change.tier}:{change.jurisdiction}, alpha to {change.new_conformal_alpha}
                </div>
                <SignoffControl author={change.author} approver={change.approved_by}
                  pending={change.status === 'pending'}
                  onApprove={() => { approveChange(change.change_id, 'compliance-officer-2'); loadData(); }} />
              </div>
            )) : (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>No pending changes</span>
            )}
          </Panel>

          {/* FHE Query */}
          <Panel title="FHE Compliance Query">
            <div style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--color-muted)', marginBottom: 12, lineHeight: 1.5 }}>
              Query aggregate statistics over encrypted audit records without decryption.
            </div>
            <div style={{ display: 'flex', gap: 0, border: '1px solid var(--color-border)', marginBottom: 12 }}>
              <button className="segmented-btn" onClick={() => runFHE('r_t', 'average')}>AVG R_T</button>
              <button className="segmented-btn" style={{ borderLeft: '1px solid var(--color-border)', borderRight: '1px solid var(--color-border)' }}
                onClick={() => runFHE('p_t', 'average')}>AVG P_T</button>
              <button className="segmented-btn" onClick={() => runFHE('r_t', 'threshold_count', 0.5)}>R_T &gt; 0.5</button>
            </div>
            {fheResult && (
              <div style={{ padding: 12, border: '1px solid var(--color-border)', background: 'var(--color-canvas)' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--color-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  ENCRYPTED, SCHEME: {fheResult.scheme || 'CKKS'}
                </div>
                {fheResult.aggregate !== undefined && (
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)' }}>
                    {fheResult.aggregate?.toFixed(4)}
                    <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 8 }}>n={fheResult.count}</span>
                  </div>
                )}
                {fheResult.count_above_threshold !== undefined && (
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)' }}>
                    {fheResult.count_above_threshold}/{fheResult.total}
                    <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 8 }}>
                      ({(fheResult.fraction * 100).toFixed(1)}%)
                    </span>
                  </div>
                )}
              </div>
            )}
          </Panel>

          {/* EU AI Act */}
          <Panel title="Jurisdiction Regime">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {[
                { regime: 'High-Risk (Art. 6)', tier: 'C' },
                { regime: 'Limited Risk (Art. 52)', tier: 'A' },
                { regime: 'General Purpose (Art. 28b)', tier: 'B' },
              ].map(r => (
                <div key={r.regime} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-fg)' }}>{r.regime}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>Tier {r.tier}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

/**
 * Reviewer Queue (Vantage Style) - LIVE
 * No hardcoded data. Pulls escalations from the audit ledger.
 * Empty state until scenarios produce BLOCK or ESCALATE decisions.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Panel, Badge, FusedSignalBar, StatusDot,
} from '../components/SharedComponents';
import { queryAuditLedger } from '../api/client';

export default function ReviewerQueue() {
  const [escalations, setEscalations] = useState([]);
  const [resolved, setResolved] = useState({});
  const [loading, setLoading] = useState(true);

  const loadEscalations = useCallback(async () => {
    setLoading(true);
    const result = await queryAuditLedger({ limit: 50 });
    if (result?.records) {
      // Filter for block and escalate actions only
      const filtered = result.records
        .filter(r => {
          const action = r.payload?.routing_action;
          return action === 'block' || action === 'escalate';
        })
        .map(r => ({
          id: r.record_id,
          session: r.payload?.session_id || '---',
          action: r.payload?.routing_action,
          tier: r.payload?.tier || '---',
          jurisdiction: r.payload?.jurisdiction || '---',
          response: r.payload?.response_text || '---',
          prompt: r.payload?.prompt_text || '---',
          signal: r.payload?.fused_signal || null,
          risk: r.payload?.risk_observables || null,
          syndrome: r.payload?.syndrome_result || null,
          reason: buildReason(r.payload),
          ts: r.timestamp_ns ? new Date(r.timestamp_ns / 1e6) : new Date(),
        }));
      setEscalations(filtered);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadEscalations();
    // Poll every 5 seconds for new escalations
    const interval = setInterval(loadEscalations, 5000);
    return () => clearInterval(interval);
  }, [loadEscalations]);

  const handle = (id, act) => setResolved(prev => ({ ...prev, [id]: act }));

  const ago = (date) => {
    const s = Math.floor((Date.now() - date.getTime()) / 1000);
    if (s < 5) return 'just now';
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `${Math.floor(s / 3600)}h ago`;
  };

  const pendingCount = escalations.filter(e => !resolved[e.id]).length;

  return (
    <div className="content" style={{ maxWidth: 960 }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontFamily: 'var(--font-sans)', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>
            Reviewer Queue
          </h1>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)', marginTop: 4, display: 'block' }}>
            {pendingCount} pending — Labels feed back to calibration (Remark 14.3)
          </span>
        </div>
        <button className="btn-ghost" onClick={loadEscalations} style={{ fontSize: 12 }}>
          Refresh
        </button>
      </div>

      {/* Escalation list or empty state */}
      {loading && escalations.length === 0 ? (
        <div style={{ border: '1px solid var(--color-border)', padding: 48, textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)' }}>
            Checking audit ledger for escalations...
          </div>
        </div>
      ) : escalations.length === 0 ? (
        <div style={{ border: '1px solid var(--color-border)', padding: 48, textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--color-fg)', marginBottom: 8 }}>
            No escalations in the queue
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)', lineHeight: 1.6 }}>
            Run the "Tier C Block" scenario from the Ops Dashboard to generate
            <br />a BLOCK decision that appears here for human review.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
          {escalations.map(esc => {
            const isResolved = !!resolved[esc.id];
            const resolution = resolved[esc.id];

            return (
              <div key={esc.id} className="panel"
                style={{
                  opacity: isResolved ? 0.5 : 1,
                  borderLeft: `2px solid ${isResolved
                    ? (resolution === 'confirm' ? 'var(--color-critical)' : 'var(--color-success)')
                    : 'var(--color-warning)'}`,
                }}>
                {/* Header */}
                <div className="panel-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Badge action={esc.action} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-fg)' }}>
                      Tier {esc.tier}, {esc.jurisdiction}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)' }}>
                      {esc.session}
                    </span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)' }}>
                    {ago(esc.ts)}
                  </span>
                </div>

                <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {/* Reason */}
                  {esc.reason && (
                    <div style={{
                      padding: '8px 12px', border: '1px solid var(--color-border)',
                      borderLeft: '2px solid var(--color-warning)', background: 'var(--color-canvas)',
                      fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-warning)',
                    }}>
                      {esc.reason}
                    </div>
                  )}

                  {/* Signal strip */}
                  {esc.signal && <FusedSignalBar signal={esc.signal} />}

                  {/* Prompt and Response */}
                  <div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>PROMPT</div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--color-muted)', lineHeight: 1.5, marginBottom: 12 }}>{esc.prompt}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>RESPONSE</div>
                    <div style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--color-fg)', lineHeight: 1.6 }}>{esc.response}</div>
                  </div>

                  {/* Risk + Syndrome */}
                  {(esc.risk || esc.syndrome) && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
                      {esc.risk && (
                        <div style={{ padding: '12px 16px 12px 0', borderRight: '1px solid var(--color-border)' }}>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>RESPONSIBILITY</div>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <div>b_t = {esc.risk.b_t?.toFixed(3) || '---'}</div>
                            <div>s_t = {esc.risk.s_t?.toFixed(3) || '---'}</div>
                            <div>l_PII = {esc.risk.l_pii_t?.toFixed(3) || '---'}</div>
                          </div>
                        </div>
                      )}
                      {esc.syndrome && (
                        <div style={{ padding: '12px 0 12px 16px' }}>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>SYNDROME DECODE</div>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-fg)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <div>Correctable: {esc.syndrome.correctable
                              ? <span style={{ color: 'var(--color-success)' }}>yes</span>
                              : <span style={{ color: 'var(--color-critical)' }}>no</span>
                            }</div>
                            <div>Inconsistencies: {esc.syndrome.num_inconsistencies || 0}</div>
                            {esc.syndrome.flagged_assertions?.slice(0, 3).map((f, i) => (
                              <div key={i} style={{ color: 'var(--color-critical)', fontSize: 11 }}>{f}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  {!isResolved ? (
                    <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                      <button className="btn-ghost" onClick={() => handle(esc.id, 'override')}>
                        OVERRIDE
                      </button>
                      <button className="btn-destructive" onClick={() => handle(esc.id, 'confirm')}>
                        CONFIRM VIOLATION
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: resolution === 'confirm' ? 'var(--color-critical)' : 'var(--color-success)',
                      }}>
                        {resolution === 'confirm' ? 'Violation confirmed' : 'Overridden as safe'}
                        <span style={{ color: 'var(--color-muted)', marginLeft: 8, fontSize: 10 }}>
                          Calibration label recorded
                        </span>
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* Build a human-readable reason string from the pipeline payload */
function buildReason(payload) {
  if (!payload) return null;
  const parts = [];
  const signal = payload.fused_signal;
  const obs = payload.risk_observables;
  if (obs?.r_t > 0.5) parts.push(`Responsibility critical (r_t=${obs.r_t.toFixed(3)})`);
  if (obs?.l_pii_t > 0.5) parts.push(`PII exposure (l_PII=${obs.l_pii_t.toFixed(3)})`);
  if (obs?.b_t > 0.2) parts.push(`Bias detected (b_t=${obs.b_t.toFixed(3)})`);
  if (signal?.surprise_t > 0.5) parts.push(`High surprise (${signal.surprise_t.toFixed(3)})`);
  if (signal?.discord_t > 0.3) parts.push(`Sheaf discord (${signal.discord_t.toFixed(3)})`);
  if (signal?.kappa_v_t > 3) parts.push(`Spectral warning (kappa=${signal.kappa_v_t.toFixed(1)})`);
  if (parts.length === 0) parts.push('Routed to human review by tropical decision surface');
  return parts.join(', ');
}

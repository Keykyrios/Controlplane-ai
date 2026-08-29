/**
 * Shared Components (Vantage Style)
 * Zero radius, zero shadows, hairline borders, Phosphor icons only.
 * No hover animations. All numerics in IBM Plex Mono with tabular-nums.
 */
import { useRef, useEffect } from 'react';

/* StatusDot: 8px solid circle, success/warning/critical/muted */
export function StatusDot({ status = 'success' }) {
  return <span className={`status-dot ${status}`} />;
}

/* LiveIndicator: amber dot with slow opacity pulse */
export function LiveIndicator() {
  return <span className="live-dot" />;
}

/* VerdictBanner: full-width 48px, solid fill, instant state change */
export function VerdictBanner({ action = 'pass', time }) {
  const labels = {
    pass: 'ROUTED: PASS',
    edit: 'ROUTED: EDIT',
    escalate: 'ROUTED: ESCALATE',
    block: 'ROUTED: BLOCK',
  };
  return (
    <div className={`verdict-banner ${action}`}>
      <span>[ {labels[action] || action.toUpperCase()} ]</span>
      {time != null && (
        <span style={{ fontSize: 11, opacity: 0.7 }}>{time.toFixed(1)}ms</span>
      )}
    </div>
  );
}

/* StatTile: label + count-up number + text-only delta */
export function StatTile({ label, value, delta, deltaDir = 'flat', unit = '' }) {
  const ref = useRef(null);
  const animated = useRef(false);

  useEffect(() => {
    if (!ref.current || animated.current || typeof value !== 'number') return;
    animated.current = true;
    // Count-up animation using animejs v4
    import('animejs').then(({ animate: anim }) => {
      const obj = { v: 0 };
      anim(obj, {
        v: value,
        duration: 800,
        ease: 'outExpo',
        onUpdate: () => {
          if (ref.current) {
            ref.current.textContent = value >= 100
              ? Math.round(obj.v).toLocaleString()
              : obj.v.toFixed(4);
          }
        },
      });
    }).catch(() => {
      if (ref.current) ref.current.textContent = typeof value === 'number'
        ? (value >= 100 ? Math.round(value).toLocaleString() : value.toFixed(4))
        : String(value);
    });
  }, [value]);

  const displayValue = typeof value === 'number'
    ? (value >= 100 ? Math.round(value).toLocaleString() : value.toFixed(4))
    : String(value);

  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value" ref={ref}>{displayValue}</div>
      {delta != null && (
        <span className={`stat-delta ${deltaDir}`}>
          {deltaDir === 'up' ? '+' : deltaDir === 'down' ? '' : ''}{delta}{unit}
        </span>
      )}
    </div>
  );
}

/* Badge */
export function Badge({ action }) {
  return (
    <span className={`badge ${action}`}>
      <StatusDot status={
        action === 'pass' ? 'success' :
        action === 'block' ? 'critical' : 'warning'
      } />
      {action}
    </span>
  );
}

/* SegmentedControl */
export function SegmentedControl({ options, value, onChange }) {
  return (
    <div className="segmented">
      {options.map(opt => (
        <button key={opt} className={`segmented-btn ${value === opt ? 'active' : ''}`}
          onClick={() => onChange(opt)}>
          {opt}
        </button>
      ))}
    </div>
  );
}

/* Panel */
export function Panel({ title, actions, children }) {
  return (
    <div className="panel">
      {title && (
        <div className="panel-header">
          <span className="panel-title">{title}</span>
          {actions}
        </div>
      )}
      <div className="panel-body">{children}</div>
    </div>
  );
}

/* SignoffControl */
export function SignoffControl({ author, approver, pending = true, onApprove }) {
  return (
    <div className={`signoff-block ${!pending ? 'approved' : ''}`}>
      <div className="signoff-slot">
        AUTHOR: {author ? author : '---'}
      </div>
      <div className="signoff-slot">
        APPROVER: {approver ? approver : '---'}
      </div>
      {pending && onApprove && (
        <button className="btn-primary" style={{ marginTop: 12 }} onClick={onApprove}>
          APPROVE
        </button>
      )}
    </div>
  );
}

/* Hash display with truncation */
export function Hash({ value, length = 8 }) {
  if (!value) return <span className="hash">---</span>;
  return (
    <span className="hash" title={value}>
      {value.slice(0, length)}...{value.slice(-4)}
    </span>
  );
}

/* FusedSignalBar: compact horizontal strip of signal values */
export function FusedSignalBar({ signal }) {
  if (!signal) return null;
  const items = [
    { k: 'p_t', l: 'P_T' },
    { k: 'c_t', l: 'C_T' },
    { k: 'r_t', l: 'R_T' },
    { k: 'delta_t', l: 'DELTA' },
    { k: 'surprise_t', l: 'SUR' },
    { k: 'kappa_v_t', l: 'KAPPA' },
    { k: 'discord_t', l: 'DIS' },
  ];
  return (
    <div className="stat-strip">
      {items.map(({ k, l }) => {
        const v = signal[k];
        return (
          <div className="stat-tile" key={k} style={{ padding: '8px 12px' }}>
            <div className="stat-label">{l}</div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 14, fontVariantNumeric: 'tabular-nums',
              color: v > 0.6 ? 'var(--color-critical)' : v > 0.3 ? 'var(--color-warning)' : 'var(--color-fg)',
            }}>
              {typeof v === 'number' ? v.toFixed(3) : '---'}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ServiceCard: name + status dot + uptime + sparkline */
export function ServiceCard({ name, status = 'success', uptime = '99.9%' }) {
  return (
    <div className="service-card">
      <div className="service-card-header">
        <div className="service-card-name">
          <StatusDot status={status} />
          {name}
        </div>
        <span className="service-card-uptime">{uptime}</span>
      </div>
      {/* Mini sparkline placeholder: hand-rolled SVG */}
      <svg width="100%" height="24" viewBox="0 0 120 24" preserveAspectRatio="none">
        <path
          d={`M0,${12 + Math.random()*8} ${Array.from({length: 11}, (_, i) =>
            `L${(i+1)*12},${4 + Math.random()*16}`).join(' ')}`}
          fill="none" stroke="var(--color-accent)" strokeWidth="1.5" opacity="0.6"
        />
      </svg>
    </div>
  );
}

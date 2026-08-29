/**
 * ControlPlane Manifold - App Shell (Vantage Style)
 * Sidebar 240px + Topbar 56px.
 * Active state: filled bg block + amber icon. No colored left stripe.
 */
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { SquaresFour, ClipboardText, UserFocus, Stack } from '@phosphor-icons/react';
import OpsDashboard from './views/OpsDashboard';
import ComplianceConsole from './views/ComplianceConsole';
import ReviewerQueue from './views/ReviewerQueue';
import ServicesView from './views/ServicesView';
import { LiveIndicator } from './components/SharedComponents';
import { useState, useEffect } from 'react';
import './index.css';

function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-wordmark">
        ControlPlane
        <span>Manifold v1.0</span>
      </div>

      <div className="sidebar-section">Personas</div>

      <NavLink to="/ops" className={({ isActive }) => `sidebar-item ${isActive ? 'active' : ''}`}>
        <SquaresFour size={18} weight="regular" />
        <span className="sidebar-item-label">Ops Dashboard</span>
      </NavLink>

      <NavLink to="/compliance" className={({ isActive }) => `sidebar-item ${isActive ? 'active' : ''}`}>
        <ClipboardText size={18} weight="regular" />
        <span className="sidebar-item-label">Compliance</span>
      </NavLink>

      <NavLink to="/review" className={({ isActive }) => `sidebar-item ${isActive ? 'active' : ''}`}>
        <UserFocus size={18} weight="regular" />
        <span className="sidebar-item-label">Reviewer Queue</span>
      </NavLink>

      <div className="sidebar-section" style={{ marginTop: 24 }}>Infrastructure</div>

      <NavLink to="/services" className={({ isActive }) => `sidebar-item ${isActive ? 'active' : ''}`}>
        <Stack size={18} weight="regular" />
        <span className="sidebar-item-label">Services</span>
      </NavLink>

      {/* Footer: math stack summary */}
      <div style={{ marginTop: 'auto', padding: '16px 8px 0', borderTop: '1px solid var(--color-border)' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--color-muted)', lineHeight: 1.8 }}>
          17 microservices<br />
          Clifford Cl(3,0)<br />
          Topological Data Analysis<br />
          Post-Quantum Crypto<br />
          CRDT Audit Ledger<br />
          FHE Compliance<br />
          Sheaf-Theoretic Fusion
        </div>
      </div>
    </nav>
  );
}

function Topbar() {
  const [now, setNow] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <input type="text" className="topbar-search" placeholder="Search signals, sessions, services..." />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>
          {now}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-muted)' }}>
          Operator
        </span>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <Topbar />
        <main style={{ overflow: 'auto' }}>
          <Routes>
            <Route path="/ops" element={<OpsDashboard />} />
            <Route path="/compliance" element={<ComplianceConsole />} />
            <Route path="/review" element={<ReviewerQueue />} />
            <Route path="/services" element={<ServicesView />} />
            <Route path="*" element={<Navigate to="/ops" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

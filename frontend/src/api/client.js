/**
 * ControlPlane Manifold — API Client
 * 
 * Centralized HTTP client for all backend service calls.
 * Talks to the orchestrator (port 8000) which fans out to all services.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  try {
    const resp = await fetch(url, config);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    return await resp.json();
  } catch (err) {
    console.error(`[API] ${path}:`, err.message);
    return null;
  }
}

// Orchestrator — Algorithm 1 full pipeline
export async function processResponse(payload) {
  return request('/pipeline/process', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// System status
export async function getSystemStatus() {
  return request('/status');
}

// Health check
export async function getHealth() {
  return request('/health');
}

// Direct service calls (bypass orchestrator for dashboard data)
async function svcRequest(port, path, options = {}) {
  const base = `http://localhost:${port}`;
  try {
    const resp = await fetch(`${base}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

// Tropical routing — decision surface
export async function getDecisionSurface(params) {
  return svcRequest(8009, '/routing/decision-surface', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// Sheaf fusion — laplacian
export async function getSheafLaplacian() {
  return svcRequest(8007, '/sheaf/laplacian');
}

// Spectral — toy model
export async function getToyModel(gValues) {
  return svcRequest(8006, `/spectral/toy-model?g_values=${gValues}`);
}

// Audit ledger
export async function queryAuditLedger(params) {
  return svcRequest(8015, '/audit/query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function verifyAuditChain() {
  return svcRequest(8015, '/audit/verify');
}

export async function homomorphicQuery(params) {
  return svcRequest(8015, '/audit/homomorphic-query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// Policy manifold
export async function getAllPolicies() {
  return svcRequest(8016, '/policy/all');
}

export async function getPendingChanges() {
  return svcRequest(8016, '/policy/pending');
}

export async function proposeChange(change) {
  return svcRequest(8016, '/policy/propose', {
    method: 'POST',
    body: JSON.stringify(change),
  });
}

export async function approveChange(changeId, approver) {
  return svcRequest(8016, `/policy/approve/${changeId}?approver=${approver}`, {
    method: 'POST',
  });
}

// Game theory
export async function getSecurityPriority() {
  return svcRequest(8011, '/security/priority-queue');
}

// Queueing
export async function getQueueingLatency(params) {
  return svcRequest(8014, '/queueing/latency', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// Conformal calibration
export async function getCalibrationStatus() {
  return svcRequest(8010, '/calibration/status');
}

// Adapters
export async function listAdapters() {
  return svcRequest(8008, '/adapters');
}

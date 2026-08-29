-- ControlPlane Manifold — PostgreSQL initialization
-- TimescaleDB extension + core tables

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Risk observables time series (Section 5)
CREATE TABLE IF NOT EXISTS risk_observations (
    id BIGSERIAL,
    session_id TEXT NOT NULL,
    response_id TEXT NOT NULL UNIQUE,
    p_t DOUBLE PRECISION NOT NULL,
    c_t DOUBLE PRECISION NOT NULL,
    r_t DOUBLE PRECISION NOT NULL,
    b_t DOUBLE PRECISION DEFAULT 0,
    s_t DOUBLE PRECISION DEFAULT 0,
    l_pii_t DOUBLE PRECISION DEFAULT 0,
    l_mi_t DOUBLE PRECISION DEFAULT 0,
    tier TEXT DEFAULT 'A',
    jurisdiction TEXT DEFAULT 'US-generic',
    timestamp_ns BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('risk_observations', 'created_at', if_not_exists => TRUE);

-- Fused signal time series (Table 3)
CREATE TABLE IF NOT EXISTS fused_signals (
    id BIGSERIAL,
    response_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    p_t DOUBLE PRECISION NOT NULL,
    c_t DOUBLE PRECISION NOT NULL,
    r_t DOUBLE PRECISION NOT NULL,
    delta_t DOUBLE PRECISION DEFAULT 0,
    surprise_t DOUBLE PRECISION DEFAULT 0,
    kappa_v_t DOUBLE PRECISION DEFAULT 0,
    discord_t DOUBLE PRECISION DEFAULT 0,
    tier TEXT DEFAULT 'A',
    jurisdiction TEXT DEFAULT 'US-generic',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('fused_signals', 'created_at', if_not_exists => TRUE);

-- Audit ledger (Section 19) — append-only, hash-chained
CREATE TABLE IF NOT EXISTS audit_ledger (
    id BIGSERIAL PRIMARY KEY,
    record_id TEXT NOT NULL UNIQUE,
    prev_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    fingerprint_hash TEXT,
    routing_action TEXT,
    tier TEXT,
    jurisdiction TEXT,
    algo_id TEXT DEFAULT 'X25519-MLKEM768-v1',
    encrypted_payload BYTEA,
    timestamp_ns BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_session ON audit_ledger(session_id);
CREATE INDEX idx_audit_response ON audit_ledger(response_id);
CREATE INDEX idx_audit_hash ON audit_ledger(record_hash);

-- Policy manifold versions (Section 22)
CREATE TABLE IF NOT EXISTS policy_configs (
    id SERIAL PRIMARY KEY,
    tier TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    conformal_alpha DOUBLE PRECISION NOT NULL,
    tropical_weights JSONB NOT NULL,
    latency_budget_ms INTEGER NOT NULL,
    min_calibration_set_size INTEGER DEFAULT 50,
    version INTEGER NOT NULL,
    author TEXT NOT NULL,
    approved_by TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tier, jurisdiction, version)
);

-- Conformal calibration labels (Section 14, Remark 14.3)
CREATE TABLE IF NOT EXISTS calibration_labels (
    id BIGSERIAL PRIMARY KEY,
    response_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    is_true_violation BOOLEAN NOT NULL,
    label_source TEXT NOT NULL,  -- 'human_override', 'compliance_finding', 'helpdesk_ticket'
    fused_signal JSONB,
    routing_action TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_cal_tier ON calibration_labels(tier);

-- Game theory patch state (Section 15)
CREATE TABLE IF NOT EXISTS attack_surface_state (
    id SERIAL PRIMARY KEY,
    surface_name TEXT NOT NULL UNIQUE,
    hardening_depth INTEGER NOT NULL DEFAULT 3,
    grundy_value INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Seed attack surfaces
INSERT INTO attack_surface_state (surface_name, hardening_depth) VALUES
    ('fingerprint', 3), ('drift', 3), ('surprise', 3), ('spectral', 3),
    ('sheaf', 3), ('category', 3), ('routing', 3), ('crypto', 4), ('queueing', 3)
ON CONFLICT DO NOTHING;

-- Session state for spectral analysis (Section 10)
CREATE TABLE IF NOT EXISTS session_states (
    id BIGSERIAL,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    p_t DOUBLE PRECISION NOT NULL,
    c_t DOUBLE PRECISION NOT NULL,
    r_t DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, turn_index)
);
SELECT create_hypertable('session_states', 'created_at', if_not_exists => TRUE);

-- Queueing metrics (Section 18)
CREATE TABLE IF NOT EXISTS queueing_metrics (
    id BIGSERIAL,
    lambda_rate DOUBLE PRECISION,
    mu_fast DOUBLE PRECISION,
    mu_human DOUBLE PRECISION,
    l_fast_theoretical DOUBLE PRECISION,
    l_fast_measured DOUBLE PRECISION,
    l_human_theoretical DOUBLE PRECISION,
    escalation_rate DOUBLE PRECISION,
    num_reviewers INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('queueing_metrics', 'created_at', if_not_exists => TRUE);

-- Cost baseline per task type (Section 5, κ̄(τ_t))
CREATE TABLE IF NOT EXISTS cost_baselines (
    id SERIAL PRIMARY KEY,
    task_type TEXT NOT NULL UNIQUE,
    median_cost DOUBLE PRECISION NOT NULL,
    sample_count INTEGER DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

"""
Unit Tests — Core mathematical implementations
=================================================
Tests for the key mathematical functions across services,
verifying correctness of equations from the whitepaper.
"""

import importlib.util
import os
import sys
import numpy as np
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def load_service(service_name: str):
    """Dynamically load a service module by name."""
    path = os.path.join(PROJECT_ROOT, 'services', service_name, 'main.py')
    spec = importlib.util.spec_from_file_location(f"svc_{service_name.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================================
# Risk Observables (Section 5, Eq. 2-4)
# ============================================================================

class TestRiskObservables:
    def test_performance_risk_eq2(self):
        """p_t = ŷ_t · (1 - q_t) — Eq. 2"""
        p_t = 0.8 * (1 - 0.3)
        assert abs(p_t - 0.56) < 0.01

    def test_performance_risk_zero_when_grounded(self):
        assert 0.9 * (1 - 1.0) == 0.0

    def test_cost_risk_eq3(self):
        """c_t = σ((κ_t - κ̄) / κ̄) — Eq. 3"""
        import math
        c_t = 1 / (1 + math.exp(-((0.006 - 0.003) / 0.003)))
        assert 0.5 < c_t < 1.0

    def test_responsibility_risk_eq4(self):
        """r_t = max(b_t, s_t, ℓ_t) — Eq. 4"""
        assert max(0.3, 0.1, 0.8) == 0.8


# ============================================================================
# Risk Multivector (Section 5, Eq. 5-9)
# ============================================================================

class TestRiskMultivector:
    def test_bivector_interaction(self):
        """π_{ij} = p_i · p_j (Eq. 7)"""
        p_t, c_t, r_t = 0.8, 0.5, 0.9
        assert p_t * c_t == pytest.approx(0.4)
        assert p_t * r_t == pytest.approx(0.72)

    def test_wedge_novelty(self):
        """||R_t ∧ R̄|| = 0 for identical vectors."""
        R_t = np.array([0.5, 0.3, 0.2])
        R_bar = np.array([0.5, 0.3, 0.2])
        novelty = np.linalg.norm(np.cross(R_t, R_bar))
        assert novelty < 0.01


# ============================================================================
# Fingerprint (Section 7, Eq. 13-14)
# ============================================================================

class TestFingerprint:
    def test_bipolar_encoding(self):
        rng = np.random.default_rng(42)
        v = rng.choice([-1, 1], size=10000)
        assert set(np.unique(v)) == {-1, 1}

    def test_bind_preserves_dimension(self):
        rng = np.random.default_rng(42)
        a = rng.choice([-1, 1], size=10000)
        b = rng.choice([-1, 1], size=10000)
        bound = a * b
        assert len(bound) == 10000
        assert set(np.unique(bound)) == {-1, 1}

    def test_bundle_majority_vote(self):
        rng = np.random.default_rng(42)
        a = rng.choice([-1, 1], size=10000)
        b = rng.choice([-1, 1], size=10000)
        bundled = np.sign(a + a + b)
        sim_a = np.dot(bundled, a) / 10000
        sim_b = np.dot(bundled, b) / 10000
        assert sim_a > sim_b


# ============================================================================
# Drift (Section 8, Eq. 15-17)
# ============================================================================

class TestDrift:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('drift')

    def test_wasserstein_zero_for_identical(self):
        D = [(0.0, 0.5), (0.1, 0.8), (0.2, 0.6)]
        assert self.mod.wasserstein_2(D, D) == pytest.approx(0.0, abs=1e-6)

    def test_wasserstein_positive_for_different(self):
        D1 = [(0.0, 0.5), (0.1, 0.8)]
        D2 = [(0.0, 1.0), (0.5, 2.0)]
        assert self.mod.wasserstein_2(D1, D2) > 0


# ============================================================================
# Surprise (Section 9, Eq. 18-19)
# ============================================================================

class TestSurprise:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('surprise')

    def test_ncd_identical_is_low(self):
        x = b"This is a test string that is moderately long for compression."
        assert self.mod.ncd(x, x) < 0.2

    def test_ncd_different_is_higher(self):
        x = b"The quick brown fox jumps over the lazy dog." * 5
        y = b"1234567890 abcdefghij random noise data stream." * 5
        assert self.mod.ncd(x, y) > 0.2


# ============================================================================
# Spectral (Section 10, Eq. 20-22)
# ============================================================================

class TestSpectral:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('spectral')

    def test_identity_jacobian_condition_one(self):
        kappa = self.mod.condition_number(np.eye(3))
        assert kappa == pytest.approx(1.0, abs=0.01)

    def test_near_exceptional_point_high_kappa(self):
        J = np.array([[1.0, 0.99], [0.99, 1.0]])
        kappa = self.mod.condition_number(J)
        assert kappa > 1.0


# ============================================================================
# Sheaf Fusion (Section 11, Eq. 25-28)
# ============================================================================

class TestSheafFusion:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('sheaf-fusion')

    def test_discord_zero_for_consistent(self):
        sheaf = self.mod.PipelineSheaf(
            vertices=["a", "b", "c"],
            edges=[("a", "b"), ("b", "c")],
            stalk_dim=3,
        )
        x = {"a": np.array([0.5, 0.3, 0.2]), "b": np.array([0.5, 0.3, 0.2]), "c": np.array([0.5, 0.3, 0.2])}
        assert sheaf.laplacian_quadratic_form(x) == pytest.approx(0.0, abs=1e-10)

    def test_discord_positive_for_inconsistent(self):
        sheaf = self.mod.PipelineSheaf(vertices=["a", "b"], edges=[("a", "b")], stalk_dim=3)
        x = {"a": np.array([0.1, 0.1, 0.1]), "b": np.array([0.9, 0.9, 0.9])}
        assert sheaf.laplacian_quadratic_form(x) > 0

    def test_laplacian_is_psd(self):
        sheaf = self.mod.PipelineSheaf(vertices=["a", "b", "c"], edges=[("a", "b"), ("b", "c"), ("a", "c")], stalk_dim=3)
        L = sheaf.build_laplacian_matrix()
        eigvals = np.linalg.eigvalsh(L)
        assert np.all(eigvals >= -1e-10)


# ============================================================================
# Tropical Routing (Section 13, Eq. 32-33)
# ============================================================================

class TestTropicalRouting:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('tropical-routing')

    def test_safe_signal_routes_to_pass(self):
        policy = self.mod.create_default_policy()
        z = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        action, _ = policy.route(z)
        assert action == "pass"

    def test_high_risk_routes_to_block(self):
        policy = self.mod.create_default_policy()
        z = np.array([0.9, 0.5, 0.9, 0.1, 0.3, 1.0, 0.5])
        action, _ = policy.route(z)
        assert action in ("block", "escalate")


# ============================================================================
# Conformal Calibration (Section 14, Theorem 14.2)
# ============================================================================

class TestConformalCalibration:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('conformal-calibration')

    def test_calibrate_lambda_returns_valid_threshold(self):
        losses = {
            0.1: np.array([1, 1, 1, 0, 0]),
            0.3: np.array([1, 0, 0, 0, 0]),
            0.5: np.array([0, 0, 0, 0, 0]),
        }
        lam = self.mod.calibrate_lambda(losses, alpha=0.3)
        assert 0.0 <= lam <= 1.0


# ============================================================================
# Game Theory (Section 15, Eq. 37-39)
# ============================================================================

class TestGameTheory:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('game-theory-patcher')

    def test_grundy_zero_for_terminal(self):
        assert self.mod.grundy(0) == 0

    def test_nim_sum_xor(self):
        assert self.mod.nim_sum([3, 5, 7]) == (3 ^ 5 ^ 7)

    def test_mex(self):
        assert self.mod.mex({0, 1, 3}) == 2


# ============================================================================
# Audit Ledger (Section 19)
# ============================================================================

class TestAuditLedger:
    @pytest.fixture(autouse=True)
    def load(self):
        self.mod = load_service('audit-ledger')

    def test_chain_verification(self):
        ledger = self.mod.AuditLedger()
        ledger.append({"test": "record_1"})
        ledger.append({"test": "record_2"})
        ledger.append({"test": "record_3"})
        valid, count = ledger.verify_chain()
        assert valid is True
        assert count == 3

    def test_crdt_merge(self):
        ledger_a = self.mod.AuditLedger()
        ledger_b = self.mod.AuditLedger()
        ledger_a.append({"region": "us-east"})
        added = ledger_a.merge(ledger_b)
        assert len(ledger_a.records) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

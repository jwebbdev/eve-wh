"""Tests for wormhole rolling calculator."""
import pytest

from eve_wh.calculator import (
    add_passage,
    get_mass_status,
    undo_last_passage,
)
from eve_wh.models import (
    MassEstimate,
    RiskLevel,
    WHState,
    WormholeTracker,
    WormholeType,
)


# --- Fixtures ---

@pytest.fixture
def c2_static():
    """Typical C2 static — 2B total, 300M max jump."""
    return WormholeType(
        id="D382", destination="C2",
        total_mass=2_000_000_000, max_jump_mass=300_000_000,
        max_stable_hours=16, size_class="large",
    )


@pytest.fixture
def c5_static():
    """C5 static — 3B total, 1.35B max jump (capital)."""
    return WormholeType(
        id="H296", destination="C5",
        total_mass=3_000_000_000, max_jump_mass=1_350_000_000,
        max_stable_hours=24, size_class="capital",
    )


@pytest.fixture
def frigate_hole():
    """Frigate wormhole — 500M total, 5M max jump."""
    return WormholeType(
        id="E004", destination="C1",
        total_mass=500_000_000, max_jump_mass=5_000_000,
        max_stable_hours=16, size_class="frigate",
    )


@pytest.fixture
def tracker_2b(c2_static):
    return WormholeTracker(name="ABC-123", wh_type=c2_static)


# --- Basic Mass Tracking ---

class TestBasicTracking:
    def test_initial_state(self, tracker_2b):
        status = get_mass_status(tracker_2b)
        assert status.total_mass_passed == 0
        assert status.est_total_min == 1_800_000_000  # 2B * 0.9
        assert status.est_total_max == 2_200_000_000  # 2B * 1.1
        assert status.min_remaining == 1_800_000_000
        assert status.max_remaining == 2_200_000_000
        assert status.wh_state == WHState.STABLE

    def test_single_pass(self, tracker_2b):
        status = add_passage(tracker_2b, "Mega", 300_000_000, "out")
        assert status.total_mass_passed == 300_000_000
        assert status.min_remaining == 1_500_000_000
        assert status.max_remaining == 1_900_000_000

    def test_multiple_passes(self, tracker_2b):
        add_passage(tracker_2b, "Mega", 300_000_000, "out")
        add_passage(tracker_2b, "Mega", 200_000_000, "in")  # cold return
        status = add_passage(tracker_2b, "Mega", 300_000_000, "out")
        assert status.total_mass_passed == 800_000_000

    def test_remaining_cant_go_negative(self, tracker_2b):
        # Push way more than the hole can hold
        for _ in range(10):
            add_passage(tracker_2b, "Mega", 300_000_000, "out")
        status = get_mass_status(tracker_2b)
        assert status.min_remaining == 0
        assert status.max_remaining == 0


# --- State Observation Refinement ---

class TestStateRefinement:
    def test_shrunk_tightens_range(self, tracker_2b):
        """2B hole, push 1B through, observe shrunk → tightens estimate."""
        # Pass 1: 300M cold out, stable
        add_passage(tracker_2b, "Mega", 300_000_000, "out", "stable")
        # Pass 2: 200M cold in, stable
        add_passage(tracker_2b, "Mega", 200_000_000, "in", "stable")
        # Pass 3: 300M hot out, stable
        add_passage(tracker_2b, "Mega", 300_000_000, "out", "stable")
        # Pass 4: 200M cold in, shrunk!
        status = add_passage(tracker_2b, "Mega", 200_000_000, "in", "shrunk")

        # Total passed: 1B. Shrunk means real_total <= 2B (1B / 0.5)
        # Previous was stable at 800M, so real_total > 1.6B (800M / 0.5)
        assert tracker_2b.est_total_max <= 2_000_000_000
        assert tracker_2b.est_total_min >= 1_600_000_000
        assert status.wh_state == WHState.SHRUNK

    def test_stable_raises_minimum(self, tracker_2b):
        """If still stable after 600M passed, real total > 1.2B."""
        add_passage(tracker_2b, "Mega", 300_000_000, "out", "stable")
        add_passage(tracker_2b, "Mega", 300_000_000, "in", "stable")
        # 600M passed, still stable → real_total > 1.2B
        assert tracker_2b.est_total_min >= 1_200_000_000

    def test_critical_tightens_range(self, tracker_2b):
        """Push ~1.8B through 2B hole, observe critical."""
        for _ in range(6):
            add_passage(tracker_2b, "Mega", 300_000_000, "out")

        # 1.8B passed, mark as critical
        status = add_passage(tracker_2b, "Mega", 200_000_000, "in", "critical")
        # Total: 2.0B. Critical means real_total <= 2.0B / 0.9 ≈ 2.22B
        assert tracker_2b.est_total_max <= 2_222_222_223
        assert status.wh_state == WHState.CRITICAL

    def test_your_rolling_scenario(self, c2_static):
        """Your scenario: 2B hole, ships 200k cold / 300k hot.
        2 cold + 2 hot = 1B. Check if shrunk."""
        tracker = WormholeTracker(name="Static", wh_type=c2_static)

        add_passage(tracker, "Mega", 200_000_000, "out")  # cold out
        add_passage(tracker, "Mega", 200_000_000, "in")   # cold in
        add_passage(tracker, "Mega", 300_000_000, "out")  # hot out
        status = add_passage(tracker, "Mega", 300_000_000, "in", "shrunk")  # hot in, shrunk!

        # 1B passed, shrunk → real total ≤ 2B
        # Can close with 2 cold + 2 hot (another 1B)
        assert status.wh_state == WHState.SHRUNK
        assert status.max_remaining <= 1_000_000_000  # At most 1B left


# --- Prior Mass Detection ---

class TestPriorMass:
    def test_early_shrink_detects_prior_mass(self, c2_static):
        """If a 2B hole shrinks after only 200M passed, someone was here before."""
        tracker = WormholeTracker(name="Suspicious", wh_type=c2_static)
        status = add_passage(tracker, "Mega", 200_000_000, "out", "shrunk")

        # 200M shouldn't shrink a 2B hole (needs ~900M minimum)
        # Calculator should estimate prior mass
        assert tracker.prior_mass > 0
        assert status.est_prior_mass > 0

    def test_normal_shrink_no_prior_mass(self, c2_static):
        """Shrink at expected timing should not flag prior mass."""
        tracker = WormholeTracker(name="Normal", wh_type=c2_static)
        for _ in range(3):
            add_passage(tracker, "Mega", 300_000_000, "out")
        add_passage(tracker, "Mega", 200_000_000, "in", "shrunk")
        # 1.1B passed — reasonable for a 2B ±10% hole to shrink
        assert tracker.prior_mass == 0


# --- Risk Assessment ---

class TestRiskAssessment:
    def test_safe(self, tracker_2b):
        status = get_mass_status(tracker_2b, next_pass_mass=300_000_000)
        assert status.risk_level == RiskLevel.SAFE

    def test_danger(self, c2_static):
        tracker = WormholeTracker(name="Risky", wh_type=c2_static)
        # Push 1.7B through a 2B ±10% hole
        for _ in range(5):
            add_passage(tracker, "Mega", 300_000_000, "out")
        add_passage(tracker, "Mega", 200_000_000, "in")
        # 1.7B passed, min_remaining = 1.8B - 1.7B = 100M
        status = get_mass_status(tracker, next_pass_mass=200_000_000)
        assert status.risk_level == RiskLevel.DANGER

    def test_will_collapse(self, c2_static):
        tracker = WormholeTracker(name="Dead", wh_type=c2_static)
        # Push 2.1B through — even max total (2.2B) has only 100M left
        for _ in range(7):
            add_passage(tracker, "Mega", 300_000_000, "out")
        status = get_mass_status(tracker, next_pass_mass=300_000_000)
        assert status.risk_level == RiskLevel.WILL_COLLAPSE


# --- Undo ---

class TestUndo:
    def test_undo_passage(self, tracker_2b):
        add_passage(tracker_2b, "Mega", 300_000_000, "out")
        add_passage(tracker_2b, "Mega", 300_000_000, "in")

        status = undo_last_passage(tracker_2b)
        assert len(tracker_2b.passages) == 1
        assert status.total_mass_passed == 300_000_000

    def test_undo_recalculates_refinement(self, tracker_2b):
        add_passage(tracker_2b, "Mega", 300_000_000, "out", "stable")
        add_passage(tracker_2b, "Mega", 700_000_000, "in", "shrunk")

        # After shrunk, range is tightened
        assert tracker_2b.est_total_max <= 2_000_000_000

        # Undo the shrunk pass
        undo_last_passage(tracker_2b)

        # Range should be reset (only "stable" observation remains)
        assert tracker_2b.est_total_max == 2_200_000_000  # Back to ±10%

    def test_undo_empty(self, tracker_2b):
        result = undo_last_passage(tracker_2b)
        assert result is None

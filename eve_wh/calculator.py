"""Wormhole mass tracking and risk assessment calculator."""
from .models import (
    MassEstimate,
    Passage,
    RiskLevel,
    WHState,
    WormholeTracker,
)

# Thresholds for wormhole visual state changes
SHRUNK_THRESHOLD = 0.50   # Hole visually shrinks at 50% mass remaining
CRITICAL_THRESHOLD = 0.10  # Hole goes critical at 10% mass remaining


def add_passage(
    tracker: WormholeTracker,
    ship_name: str,
    mass: int,
    direction: str,
    state_after: str | None = None,
) -> MassEstimate:
    """Record a ship passage and return updated mass estimate.

    Args:
        tracker: The wormhole being tracked.
        ship_name: Name/label of the ship.
        mass: Mass of the ship for this jump (hot or cold).
        direction: "out" or "in".
        state_after: Visual state observed after this pass:
                     "stable", "shrunk", "critical", or None if not checked.

    Returns:
        Updated MassEstimate with refined ranges.
    """
    passage = Passage(
        ship_name=ship_name,
        mass=mass,
        direction=direction,
        state_after=state_after,
    )
    tracker.passages.append(passage)

    # Refine estimates based on state observation
    if state_after:
        _refine_estimate(tracker, state_after)

    return get_mass_status(tracker)


def get_mass_status(tracker: WormholeTracker, next_pass_mass: int = 0) -> MassEstimate:
    """Calculate current mass status for a wormhole.

    Args:
        tracker: The wormhole being tracked.
        next_pass_mass: Optional mass of the next planned pass (for risk assessment).

    Returns:
        MassEstimate with remaining mass range and risk level.
    """
    total_passed = sum(p.mass for p in tracker.passages)

    min_remaining = max(0, tracker.est_total_min - total_passed - tracker.prior_mass)
    max_remaining = max(0, tracker.est_total_max - total_passed - tracker.prior_mass)

    # Determine current visual state from observations
    wh_state = _current_state(tracker)

    # Risk assessment
    risk = _assess_risk(min_remaining, max_remaining, next_pass_mass)

    return MassEstimate(
        est_total_min=tracker.est_total_min,
        est_total_max=tracker.est_total_max,
        total_mass_passed=total_passed,
        est_prior_mass=tracker.prior_mass,
        min_remaining=min_remaining,
        max_remaining=max_remaining,
        wh_state=wh_state,
        risk_level=risk,
    )


def _refine_estimate(tracker: WormholeTracker, state_after: str):
    """Refine the estimated total mass range based on a state observation.

    When a player reports the hole's visual state after a pass, we can
    tighten the estimated range of the actual spawned total mass.
    """
    total_passed = sum(p.mass for p in tracker.passages) + tracker.prior_mass
    # Mass passed BEFORE this passage (the previous cumulative)
    prev_passed = total_passed - tracker.passages[-1].mass

    if state_after == "shrunk":
        # This pass pushed it past 50%. So:
        #   real_total * 0.50 <= total_passed  →  real_total <= total_passed / 0.50
        #   real_total * 0.50 > prev_passed    →  real_total > prev_passed / 0.50
        new_max = int(total_passed / SHRUNK_THRESHOLD)
        new_min = int(prev_passed / SHRUNK_THRESHOLD) if prev_passed > 0 else tracker.est_total_min

        tracker.est_total_max = min(tracker.est_total_max, new_max)
        tracker.est_total_min = max(tracker.est_total_min, new_min)

        # Check for anomaly: if the refined range is below the ±10% window,
        # there was likely prior mass we didn't track
        listed_min = int(tracker.wh_type.total_mass * 0.9)
        if tracker.est_total_max < listed_min and tracker.prior_mass == 0:
            # Estimate prior mass: how much extra mass explains this early shrink
            _estimate_prior_mass(tracker, total_passed, SHRUNK_THRESHOLD)

    elif state_after == "critical":
        # This pass pushed it past 90% consumed (10% remaining). So:
        #   real_total * 0.10 >= real_total - total_passed
        #   real_total * 0.90 <= total_passed  →  real_total <= total_passed / 0.90
        #   real_total * 0.90 > prev_passed    →  real_total > prev_passed / 0.90
        new_max = int(total_passed / (1 - CRITICAL_THRESHOLD))
        new_min = int(prev_passed / (1 - CRITICAL_THRESHOLD)) if prev_passed > 0 else tracker.est_total_min

        tracker.est_total_max = min(tracker.est_total_max, new_max)
        tracker.est_total_min = max(tracker.est_total_min, new_min)

        if tracker.est_total_max < int(tracker.wh_type.total_mass * 0.9) and tracker.prior_mass == 0:
            _estimate_prior_mass(tracker, total_passed, 1 - CRITICAL_THRESHOLD)

    elif state_after == "stable":
        # No state change — we haven't crossed any threshold yet.
        # Determine which threshold we're checking against.
        current_state = _current_state_before_latest(tracker)

        if current_state == WHState.STABLE:
            # Still stable means >50% remains → real_total > 2 * total_passed
            new_min = int(total_passed / SHRUNK_THRESHOLD)
            tracker.est_total_min = max(tracker.est_total_min, new_min)

        elif current_state == WHState.SHRUNK:
            # Still shrunk (not critical) means >10% remains
            # → real_total > total_passed / 0.90
            new_min = int(total_passed / (1 - CRITICAL_THRESHOLD))
            tracker.est_total_min = max(tracker.est_total_min, new_min)

    # Ensure min <= max
    if tracker.est_total_min > tracker.est_total_max:
        tracker.est_total_min = tracker.est_total_max


def _estimate_prior_mass(tracker: WormholeTracker, total_passed: int, threshold: float):
    """Estimate prior mass when a state transition happens too early.

    If the hole shrinks/crits earlier than the ±10% variance allows,
    someone else must have passed mass through before we started tracking.
    """
    # Reset estimate range to the standard ±10%
    listed = tracker.wh_type.total_mass
    tracker.est_total_min = int(listed * 0.9)
    tracker.est_total_max = int(listed * 1.1)

    # The prior mass is what makes our observed transition make sense
    # At worst case (max total), prior mass is:
    our_mass = sum(p.mass for p in tracker.passages)
    # threshold of real_total was reached at total_passed = our_mass + prior
    # real_total * threshold <= our_mass + prior → prior >= real_total * threshold - our_mass
    # Using min total for worst-case prior estimate:
    min_prior = int(tracker.est_total_min * threshold - our_mass)
    tracker.prior_mass = max(0, min_prior)


def _current_state(tracker: WormholeTracker) -> WHState:
    """Determine current visual state from passage observations."""
    state = WHState.STABLE
    for p in tracker.passages:
        if p.state_after == "critical":
            state = WHState.CRITICAL
        elif p.state_after == "shrunk" and state == WHState.STABLE:
            state = WHState.SHRUNK
    return state


def _current_state_before_latest(tracker: WormholeTracker) -> WHState:
    """Get the state before the most recent passage."""
    state = WHState.STABLE
    for p in tracker.passages[:-1]:
        if p.state_after == "critical":
            state = WHState.CRITICAL
        elif p.state_after == "shrunk" and state == WHState.STABLE:
            state = WHState.SHRUNK
    return state


def _assess_risk(min_remaining: int, max_remaining: int, next_mass: int) -> RiskLevel:
    """Assess the risk of the next pass collapsing the hole."""
    if next_mass <= 0:
        return RiskLevel.SAFE

    if max_remaining <= next_mass:
        return RiskLevel.WILL_COLLAPSE
    elif min_remaining <= next_mass:
        return RiskLevel.DANGER
    elif min_remaining <= next_mass * 2:
        return RiskLevel.CAUTION
    else:
        return RiskLevel.SAFE


def undo_last_passage(tracker: WormholeTracker) -> MassEstimate | None:
    """Remove the last passage and recalculate from scratch.

    Note: This recalculates all state refinements from the remaining passages,
    since we can't simply "unreverse" a refinement.
    """
    if not tracker.passages:
        return None

    tracker.passages.pop()

    # Reset estimates and replay all observations
    tracker.est_total_min = int(tracker.wh_type.total_mass * 0.9)
    tracker.est_total_max = int(tracker.wh_type.total_mass * 1.1)
    tracker.prior_mass = 0

    for i, p in enumerate(tracker.passages):
        if p.state_after:
            _refine_estimate(tracker, p.state_after)

    return get_mass_status(tracker)

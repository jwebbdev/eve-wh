"""Data models for wormhole rolling calculator."""
from dataclasses import dataclass, field
from enum import Enum


class WHState(str, Enum):
    """Visual state of a wormhole as seen in-game."""
    STABLE = "stable"      # Not yet disrupted (>50% mass remains)
    SHRUNK = "shrunk"      # Reduced/disrupted (10-50% remains)
    CRITICAL = "critical"  # Verge of collapse (<10% remains)


class RiskLevel(str, Enum):
    SAFE = "safe"                # min_remaining > ship_mass * 2
    CAUTION = "caution"          # min_remaining > ship_mass
    DANGER = "danger"            # min_remaining < ship_mass (could collapse)
    WILL_COLLAPSE = "will_collapse"  # max_remaining < ship_mass


@dataclass
class WormholeType:
    """A wormhole type definition from the database."""
    id: str                  # e.g., "C140", "B274"
    origin: str = ""         # e.g., "C2", "C5/C6", "K-space" — where this WH spawns
    destination: str = ""    # e.g., "Highsec", "C3", "Nullsec" — where it leads
    total_mass: int = 0      # Listed total mass in kg
    max_jump_mass: int = 0   # Max mass per single jump in kg
    max_stable_hours: int = 0  # Lifetime in hours
    size_class: str = ""     # "frigate", "medium", "large", "very_large", "capital"


@dataclass
class RollingShip:
    """A ship used for rolling wormholes."""
    name: str
    cold_mass: int       # Base mass in kg (no prop mod)
    hot_mass: int        # Mass with MWD/AB active
    zpm_mass: int | None = None  # Mass with Zero-Point Mass Entangler (HICs only, None = N/A)


@dataclass
class Passage:
    """A single ship pass through a wormhole."""
    ship_name: str
    mass: int            # Actual mass of this pass (hot or cold)
    direction: str       # "out" or "in"
    state_after: str | None = None  # "stable", "shrunk", "critical", or None


@dataclass
class MassEstimate:
    """Estimated mass state of a wormhole being rolled."""
    # Estimated range of the hole's actual spawned total mass
    est_total_min: int
    est_total_max: int
    # How much mass has been pushed through
    total_mass_passed: int
    # Estimated prior mass (from other players before we started tracking)
    est_prior_mass: int = 0
    # Remaining mass range
    min_remaining: int = 0
    max_remaining: int = 0
    # Current visual state
    wh_state: WHState = WHState.STABLE
    # Risk assessment for a given next-pass mass
    risk_level: RiskLevel = RiskLevel.SAFE


@dataclass
class WormholeTracker:
    """Tracks the rolling state of a single wormhole."""
    name: str                    # Player label or sig ID (e.g., "ABC-123")
    wh_type: WormholeType
    passages: list[Passage] = field(default_factory=list)
    # Refined mass estimates (updated by state observations)
    est_total_min: int = 0       # Lower bound on actual spawned total
    est_total_max: int = 0       # Upper bound on actual spawned total
    prior_mass: int = 0          # Estimated mass from before we started tracking

    def __post_init__(self):
        if self.est_total_min == 0:
            self.est_total_min = int(self.wh_type.total_mass * 0.9)
        if self.est_total_max == 0:
            self.est_total_max = int(self.wh_type.total_mass * 1.1)

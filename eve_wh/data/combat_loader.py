"""Load combat site data from YAML."""
from pathlib import Path
from dataclasses import dataclass, field

import yaml

DATA_DIR = Path(__file__).parent


@dataclass
class CombatSite:
    """A wormhole combat site."""
    slug: str
    name: str
    type: str  # anomaly, data, relic
    classes: list[int]
    blue_loot: int
    salvage_est: int
    waves: int
    threats: list[str]
    notes: str = ""

    @property
    def total_est(self) -> int:
        return self.blue_loot + self.salvage_est


def load_combat_sites() -> list[CombatSite]:
    """Load all combat site definitions."""
    path = DATA_DIR / "combat_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        CombatSite(
            slug=s["slug"],
            name=s["name"],
            type=s["type"],
            classes=s["classes"],
            blue_loot=s["blue_loot"],
            salvage_est=s["salvage_est"],
            waves=s["waves"],
            threats=s.get("threats", []),
            notes=s.get("notes", ""),
        )
        for s in data["sites"]
    ]

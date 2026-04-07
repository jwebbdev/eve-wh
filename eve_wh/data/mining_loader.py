"""Load mining/ore site data from YAML."""
from pathlib import Path
from dataclasses import dataclass, field

import yaml

DATA_DIR = Path(__file__).parent


@dataclass
class OreSite:
    """A wormhole ore mining site."""
    name: str
    classes: list[int]
    tier: str  # ordinary, common, uncommon, average, infrequent, unusual, exceptional, rarified
    ores: list[str]
    sleeper_difficulty: str  # low, medium, high, very_high

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "-")


# Tier order for sorting (index = sort priority)
TIER_ORDER = ["ordinary", "common", "uncommon", "average", "infrequent", "unusual", "exceptional", "rarified"]


def load_ore_sites() -> list[OreSite]:
    """Load all ore site definitions."""
    path = DATA_DIR / "mining_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        OreSite(
            name=s["name"],
            classes=s["classes"],
            tier=s["tier"],
            ores=s["ores"],
            sleeper_difficulty=s["sleeper_difficulty"],
        )
        for s in data["ore_sites"]
    ]

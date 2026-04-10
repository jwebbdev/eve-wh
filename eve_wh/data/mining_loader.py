"""Load mining/ore site data from YAML."""
from pathlib import Path
from dataclasses import dataclass, field

import yaml

DATA_DIR = Path(__file__).parent


@dataclass
class OreEntry:
    """A single ore type within a mining site."""
    type: str           # Ore name (e.g., "Arkonor", "Prime Arkonor")
    asteroids: int
    units: int
    volume: int         # Total m3
    size: int = 0       # m3 per asteroid (0 if unknown)
    size_range: list = field(default_factory=list)  # [min, max] if variable


@dataclass
class SleeperSpawn:
    """A Sleeper NPC spawn in a mining site."""
    name: str
    ship_class: str     # frigate, cruiser, battleship
    count: int
    dps: int
    ehp: int
    threats: list[str]  # web, scram, neut


@dataclass
class OreSite:
    """A wormhole ore/ice mining site with detailed composition."""
    name: str
    classes: list       # WH classes [1,2,3] or ["shattered"]
    ores: list[OreEntry]
    sleepers: list[SleeperSpawn]
    blue_loot: int = 0  # Fixed ISK blue loot drop

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "-")

    @property
    def total_units(self) -> int:
        return sum(o.units for o in self.ores)

    @property
    def total_volume(self) -> int:
        return sum(o.volume for o in self.ores)

    @property
    def total_asteroids(self) -> int:
        return sum(o.asteroids for o in self.ores)


def load_ore_sites() -> list[OreSite]:
    """Load all ore site definitions."""
    path = DATA_DIR / "mining_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sites = []
    for s in data.get("ore_sites", []):
        ores = []
        for o in s.get("ores", []):
            ores.append(OreEntry(
                type=o["type"],
                asteroids=o.get("asteroids", 0),
                units=o.get("units", 0),
                volume=o.get("volume", 0),
                size=o.get("size", 0),
                size_range=o.get("size_range", []),
            ))
        sleepers = []
        for sl in s.get("sleepers", []):
            sleepers.append(SleeperSpawn(
                name=sl["name"],
                ship_class=sl.get("class", ""),
                count=sl.get("count", 1),
                dps=sl.get("dps", 0),
                ehp=sl.get("ehp", 0),
                threats=sl.get("threats", []),
            ))
        sites.append(OreSite(
            name=s["name"],
            classes=s.get("classes", []),
            ores=ores,
            sleepers=sleepers,
            blue_loot=s.get("blue_loot", 0),
        ))
    return sites


def load_ice_sites() -> list[OreSite]:
    """Load ice site definitions (same structure as ore sites)."""
    path = DATA_DIR / "mining_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sites = []
    for s in data.get("ice_sites", []):
        ores = []
        for o in s.get("ices", []):
            ores.append(OreEntry(
                type=o["type"],
                asteroids=o.get("asteroids", 0),
                units=o.get("units", 0),
                volume=o.get("volume", 0),
                size=o.get("size", 0),
                size_range=o.get("size_range", []),
            ))
        sleepers = []
        for sl in s.get("sleepers", []):
            sleepers.append(SleeperSpawn(
                name=sl["name"],
                ship_class=sl.get("class", ""),
                count=sl.get("count", 1),
                dps=sl.get("dps", 0),
                ehp=sl.get("ehp", 0),
                threats=sl.get("threats", []),
            ))
        sites.append(OreSite(
            name=s["name"],
            classes=s.get("classes", []),
            ores=ores,
            sleepers=sleepers,
            blue_loot=s.get("blue_loot", 0),
        ))
    return sites

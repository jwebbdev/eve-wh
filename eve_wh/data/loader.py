"""Load wormhole type and ship data from YAML."""
from pathlib import Path

import yaml

from ..models import RollingShip, WormholeType

DATA_DIR = Path(__file__).parent


def load_wormhole_types() -> dict[str, WormholeType]:
    """Load all wormhole type definitions. Returns dict keyed by type ID."""
    path = DATA_DIR / "wormhole_types.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    types = {}
    for wh in data["wormhole_types"]:
        wht = WormholeType(
            id=wh["id"],
            destination=wh["destination"],
            total_mass=wh["total_mass"],
            max_jump_mass=wh["max_jump_mass"],
            max_stable_hours=wh["max_stable_hours"],
            size_class=wh.get("size_class", ""),
        )
        types[wht.id] = wht
    return types


def load_common_ships() -> list[RollingShip]:
    """Load common rolling ship presets."""
    path = DATA_DIR / "common_ships.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [
        RollingShip(
            name=s["name"],
            cold_mass=s["cold_mass"],
            hot_mass=s["hot_mass"],
            zpm_mass=s.get("zpm_mass"),
        )
        for s in data["ships"]
    ]

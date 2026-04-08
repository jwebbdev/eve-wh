"""Load combat site data from YAML."""
from pathlib import Path
from dataclasses import dataclass, field

import yaml

DATA_DIR = Path(__file__).parent


@dataclass
class WaveNpc:
    """An NPC entry within a wave."""
    name: str
    ship_class: str  # frigate, cruiser, battleship, sentry
    count: int
    dps: int
    threats: list[str]


@dataclass
class Wave:
    """A single wave within a combat site."""
    name: str
    trigger: str | None  # NPC name that triggers next wave, null for last wave
    npcs: list[WaveNpc]
    total_dps: int


@dataclass
class CapitalEscalation:
    """A capital escalation wave."""
    wave: int
    npcs: list[WaveNpc]
    total_dps: int


@dataclass
class NpcReference:
    """Reference data for an NPC type."""
    name: str
    ship_class: str
    dps: int
    threats: list[str]


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
    wave_data: list[Wave] = field(default_factory=list)
    capital_escalation: list[CapitalEscalation] = field(default_factory=list)

    @property
    def total_est(self) -> int:
        return self.blue_loot + self.salvage_est

    @property
    def max_wave_dps(self) -> int:
        """Highest single-wave DPS across all waves."""
        if not self.wave_data:
            return 0
        return max(w.total_dps for w in self.wave_data)


def _parse_npc(npc_dict: dict) -> WaveNpc:
    return WaveNpc(
        name=npc_dict["name"],
        ship_class=npc_dict["class"],
        count=npc_dict["count"],
        dps=npc_dict["dps"],
        threats=npc_dict.get("threats", []),
    )


def _parse_wave(wave_dict: dict) -> Wave:
    return Wave(
        name=wave_dict["name"],
        trigger=wave_dict.get("trigger"),
        npcs=[_parse_npc(n) for n in wave_dict.get("npcs", [])],
        total_dps=wave_dict.get("total_dps", 0),
    )


def _parse_escalation(esc_dict: dict) -> CapitalEscalation:
    return CapitalEscalation(
        wave=esc_dict["wave"],
        npcs=[_parse_npc(n) for n in esc_dict.get("npcs", [])],
        total_dps=esc_dict.get("total_dps", 0),
    )


def load_npc_reference() -> dict[str, NpcReference]:
    """Load the NPC reference table."""
    path = DATA_DIR / "combat_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ref = data.get("npc_reference", {})
    return {
        name: NpcReference(
            name=name,
            ship_class=info["class"],
            dps=info["dps"],
            threats=info.get("threats", []),
        )
        for name, info in ref.items()
    }


def load_combat_sites() -> list[CombatSite]:
    """Load all combat site definitions."""
    path = DATA_DIR / "combat_sites.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sites = []
    for s in data["sites"]:
        wave_data_raw = s.get("wave_data", [])
        wave_data = [_parse_wave(w) for w in wave_data_raw]
        cap_esc_raw = s.get("capital_escalation", [])
        cap_esc = [_parse_escalation(e) for e in cap_esc_raw]

        sites.append(CombatSite(
            slug=s["slug"],
            name=s["name"],
            type=s["type"],
            classes=s["classes"],
            blue_loot=s["blue_loot"],
            salvage_est=s["salvage_est"],
            waves=len(wave_data),
            threats=s.get("threats", []),
            notes=s.get("notes", ""),
            wave_data=wave_data,
            capital_escalation=cap_esc,
        ))

    return sites

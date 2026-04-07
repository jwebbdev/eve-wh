"""Valuate parsed probe scanner signatures against known site databases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .parser import ScannedSig


@dataclass
class SiteValuation:
    """Value estimate for a single scanned signature."""
    sig: ScannedSig
    category: str               # "gas", "combat", "relic", "data", "ore", "wormhole", "unknown"
    blue_loot: int | None = None      # Fixed ISK for combat/relic/data sites
    salvage_est: int | None = None    # Estimated salvage ISK
    gas_value: int | None = None      # Total gas cloud value for gas sites
    ninja_value_min: int | None = None  # 15-min ninja harvest value
    ninja_value_max: int | None = None  # 20-min ninja harvest value
    total_est: int | None = None      # Best estimate of total site value
    link: str | None = None           # Cross-tool link URL


# Map probe scanner group names to our categories
_GROUP_TO_CATEGORY = {
    "Gas Site": "gas",
    "Combat Site": "combat",
    "Relic Site": "relic",
    "Data Site": "data",
    "Ore Site": "ore",
    "Wormhole": "wormhole",
}


def _match_combat_site(name: str, combat_sites: list[dict]) -> dict | None:
    """Find a combat site by name (case-insensitive, handles trailing ...)."""
    if not name:
        return None
    # Scanner truncates long names with "..."
    clean = name.rstrip(".")
    for site in combat_sites:
        site_name = site.get("name", "")
        if site_name.lower() == name.lower():
            return site
        if clean and site_name.lower().startswith(clean.lower()):
            return site
    return None


def _match_gas_site(name: str, gas_sites: list[dict]) -> dict | None:
    """Find a gas site by name (case-insensitive, handles trailing ...)."""
    if not name:
        return None
    clean = name.rstrip(".")
    for site in gas_sites:
        site_name = site.get("name", "")
        if site_name.lower() == name.lower():
            return site
        if clean and site_name.lower().startswith(clean.lower()):
            return site
    return None


def valuate_system(
    sigs: list[ScannedSig],
    combat_sites: list[dict[str, Any]],
    gas_sites: list[dict[str, Any]],
) -> list[SiteValuation]:
    """Match parsed sigs to known sites and calculate values.

    Args:
        sigs: Parsed signatures from the probe scanner.
        combat_sites: List of dicts from combat_sites.yaml (each has name, blue_loot, salvage_est, type).
            The type field distinguishes anomaly/relic/data combat sites.
        gas_sites: List of dicts from gas sites.yaml (each has name, gas_value, ninja_value_min, ninja_value_max).
            Gas values should be pre-computed from gas cloud composition and market prices.

    Returns:
        List of SiteValuation sorted by total_est descending (None values sort last).
    """
    valuations: list[SiteValuation] = []

    for sig in sigs:
        category = _GROUP_TO_CATEGORY.get(sig.group, "unknown")

        val = SiteValuation(sig=sig, category=category)

        if category == "wormhole":
            val.link = "/eve/wh"

        elif category == "gas":
            matched = _match_gas_site(sig.name, gas_sites)
            if matched:
                val.gas_value = matched.get("gas_value")
                val.ninja_value_min = matched.get("ninja_value_min")
                val.ninja_value_max = matched.get("ninja_value_max")
                val.total_est = val.gas_value

        elif category in ("combat", "relic", "data"):
            matched = _match_combat_site(sig.name, combat_sites)
            if matched:
                val.blue_loot = matched.get("blue_loot")
                val.salvage_est = matched.get("salvage_est")
                bl = val.blue_loot or 0
                sv = val.salvage_est or 0
                val.total_est = bl + sv if (bl or sv) else None

        valuations.append(val)

    # Sort by total_est descending, None values last
    valuations.sort(key=lambda v: (v.total_est is None, -(v.total_est or 0)))
    return valuations

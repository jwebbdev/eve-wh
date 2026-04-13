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
    total_m3: int | None = None       # Total m3 volume for gas/ore sites
    total_ehp: int | None = None      # Total EHP for combat sites
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


def _attr(obj, key, default=None):
    """Get attribute from object or dict."""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    if hasattr(obj, 'get'):
        return obj.get(key, default)
    return default


# Pirate exploration site name prefixes (non-Sleeper data/relic in C1-C3 WHs)
_PIRATE_RELIC_PREFIXES = ("crumbling", "decayed", "ruined")
_PIRATE_DATA_PREFIXES = ("local", "regional", "central")
# Known factions that spawn pirate sites
_PIRATE_FACTIONS = ("angel", "blood", "guristas", "sansha", "serpentis")


def _is_pirate_exploration_site(name: str) -> bool:
    """Check if a site name matches pirate relic/data naming patterns."""
    lower = name.lower()
    # Pirate sites follow: "[Prefix] [Faction] [Site Name]"
    for prefix in (*_PIRATE_RELIC_PREFIXES, *_PIRATE_DATA_PREFIXES):
        if lower.startswith(prefix):
            for faction in _PIRATE_FACTIONS:
                if faction in lower:
                    return True
    return False


def _match_combat_site(name: str, combat_sites) -> object | None:
    """Find a combat site by name (case-insensitive, handles trailing ...)."""
    if not name:
        return None
    # Scanner truncates long names with "..."
    clean = name.rstrip(".")
    for site in combat_sites:
        site_name = site.name if hasattr(site, 'name') else site.get("name", "")
        if site_name.lower() == name.lower():
            return site
        if clean and site_name.lower().startswith(clean.lower()):
            return site
    return None


def _match_gas_site(name: str, gas_sites) -> object | None:
    """Find a gas site by name (case-insensitive, handles trailing ...)."""
    if not name:
        return None
    clean = name.rstrip(".")
    for site in gas_sites:
        site_name = site.name if hasattr(site, 'name') else site.get("name", "")
        if site_name.lower() == name.lower():
            return site
        if clean and site_name.lower().startswith(clean.lower()):
            return site
    return None


def valuate_system(
    sigs: list[ScannedSig],
    combat_sites: list[dict[str, Any]],
    gas_sites: list[dict[str, Any]],
    ore_sites: list[dict[str, Any]] | None = None,
) -> list[SiteValuation]:
    """Match parsed sigs to known sites and calculate values.

    Args:
        sigs: Parsed signatures from the probe scanner.
        combat_sites: List of dicts from combat_sites.yaml (each has name, blue_loot, salvage_est, type).
            The type field distinguishes anomaly/relic/data combat sites.
        gas_sites: List of dicts from gas sites.yaml (each has name, gas_value, ninja_value_min, ninja_value_max).
            Gas values should be pre-computed from gas cloud composition and market prices.
        ore_sites: List of dicts with name and total_est, pre-computed from ore composition and market prices.

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
                val.gas_value = _attr(matched, "gas_value")
                val.ninja_value_min = _attr(matched, "ninja_value_min")
                val.ninja_value_max = _attr(matched, "ninja_value_max")
                val.total_est = val.gas_value
                val.total_m3 = _attr(matched, "total_m3")
            val.link = "/eve/gas"

        elif category == "ore":
            if ore_sites and sig.name:
                matched = _match_gas_site(sig.name, ore_sites)  # reuse name matcher
                if matched:
                    val.total_est = _attr(matched, "total_est")
                    val.total_m3 = _attr(matched, "total_m3")
            val.link = "/eve/wh/mining"

        elif category in ("combat", "relic", "data"):
            matched = _match_combat_site(sig.name, combat_sites)
            if matched:
                val.blue_loot = _attr(matched, "blue_loot")
                val.salvage_est = _attr(matched, "salvage_est")
                bl = val.blue_loot or 0
                sv = val.salvage_est or 0
                val.total_est = bl + sv if (bl or sv) else None
                val.total_ehp = _attr(matched, "total_ehp")
                val.link = "/eve/wh/sites"
            elif sig.name and _is_pirate_exploration_site(sig.name):
                # Pirate relic/data sites in C1-C3 WHs — rough average estimates
                # Relic sites average ~15M (T2 salvage, highly variable)
                # Data sites average ~8M (decryptors, datacores, lower value)
                if category == "relic":
                    val.total_est = 15000000  # ~15M average
                else:
                    val.total_est = 8000000   # ~8M average

        valuations.append(val)

    # Sort by total_est descending, None values last
    valuations.sort(key=lambda v: (v.total_est is None, -(v.total_est or 0)))
    return valuations

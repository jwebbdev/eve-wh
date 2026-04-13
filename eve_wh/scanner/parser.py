"""Parse EVE Online probe scanner clipboard output."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ScannedSig:
    """A single signature from the probe scanner."""
    sig_id: str            # e.g., "ABC-123"
    scan_group: str        # "Cosmic Signature" or "Cosmic Anomaly"
    group: str             # "Gas Site", "Combat Site", "Wormhole", "Relic Site", "Data Site", "Ore Site", or ""
    name: str              # Site name or "" if not fully scanned
    signal_strength: float  # 0-100
    distance_au: float     # Distance in AU


@dataclass
class ParseResult:
    """Result of parsing probe scanner output."""
    signatures: list[ScannedSig] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Header detection: the first column is "ID" in the header row
_HEADER_PATTERN = re.compile(r"^ID\t", re.IGNORECASE)

# Signal strength: number with optional decimal (dot or comma) + % suffix
_STRENGTH_PATTERN = re.compile(r"^([\d.,]+)%$")

# Distance: number with optional decimal (dot or comma) + space + AU/km/m
_DISTANCE_PATTERN = re.compile(r"^([\d.,]+)\s*(AU|km|m)$", re.IGNORECASE)

VALID_SCAN_GROUPS = {"Cosmic Signature", "Cosmic Anomaly"}
VALID_GROUPS = {"Gas Site", "Combat Site", "Wormhole", "Relic Site", "Data Site", "Ore Site"}


def parse_scan(text: str) -> ParseResult:
    """Parse probe scanner clipboard text into structured signatures.

    Args:
        text: Tab-separated probe scanner output, one signature per line.

    Returns:
        ParseResult with parsed signatures and any warnings.
    """
    result = ParseResult()

    if not text or not text.strip():
        return result

    lines = text.strip().splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip header row
        if _HEADER_PATTERN.match(stripped):
            continue

        cols = stripped.split("\t")
        if len(cols) != 6:
            result.warnings.append(
                f"Line {i + 1}: expected 6 tab-separated columns, got {len(cols)}"
            )
            continue

        sig_id, scan_group, group, name, strength_str, distance_str = cols

        # Validate sig_id
        sig_id = sig_id.strip()
        if not sig_id:
            result.warnings.append(f"Line {i + 1}: empty signature ID")
            continue

        # Validate scan_group
        scan_group = scan_group.strip()
        if scan_group not in VALID_SCAN_GROUPS:
            result.warnings.append(
                f"Line {i + 1}: unknown scan group '{scan_group}'"
            )
            continue

        # Group and name may be empty for partially scanned sigs
        group = group.strip()
        name = name.strip()

        if group and group not in VALID_GROUPS:
            result.warnings.append(
                f"Line {i + 1}: unknown group '{group}'"
            )
            continue

        # Parse signal strength
        strength_str = strength_str.strip()
        m = _STRENGTH_PATTERN.match(strength_str)
        if not m:
            result.warnings.append(
                f"Line {i + 1}: invalid signal strength '{strength_str}'"
            )
            continue
        signal_strength = float(m.group(1).replace(",", "."))

        # Parse distance
        distance_str = distance_str.strip()
        m = _DISTANCE_PATTERN.match(distance_str)
        if not m:
            result.warnings.append(
                f"Line {i + 1}: invalid distance '{distance_str}'"
            )
            continue
        dist_val = float(m.group(1).replace(",", "."))
        dist_unit = m.group(2).lower()
        if dist_unit == "km":
            distance_au = dist_val / 149597870.7  # km to AU
        elif dist_unit == "m":
            distance_au = dist_val / 149597870700.0  # m to AU
        else:
            distance_au = dist_val

        result.signatures.append(ScannedSig(
            sig_id=sig_id,
            scan_group=scan_group,
            group=group,
            name=name,
            signal_strength=signal_strength,
            distance_au=distance_au,
        ))

    return result

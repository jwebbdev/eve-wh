"""Tests for probe scanner parser and valuator."""
import pytest

from eve_wh.scanner.parser import ParseResult, ScannedSig, parse_scan
from eve_wh.scanner.valuator import SiteValuation, valuate_system


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

FULL_SCAN = (
    "ABC-123\tCosmic Signature\tGas Site\tBarren Perimeter Reservoir\t100.0%\t4.2 AU\n"
    "DEF-456\tCosmic Signature\tCombat Site\tForgotten Perimeter Habitation Coils\t100.0%\t2.3 AU\n"
    "GHI-789\tCosmic Signature\tWormhole\tWormhole\t100.0%\t1.2 AU\n"
    "JKL-012\tCosmic Anomaly\tCombat Site\tPerimeter Ambush Point\t100.0%\t3.1 AU\n"
    "MNO-345\tCosmic Signature\tRelic Site\tRuined Sansha Monument\t62.3%\t7.8 AU\n"
    "PQR-678\tCosmic Signature\t\t\t15.0%\t9.1 AU\n"
)

SCAN_WITH_HEADER = (
    "ID\tScan Group\tGroup\tName\tSignal Strength\tDistance\n"
    "ABC-123\tCosmic Signature\tGas Site\tBarren Perimeter Reservoir\t100.0%\t4.2 AU\n"
)

COMBAT_SITES = [
    {
        "name": "Perimeter Ambush Point",
        "type": "anomaly",
        "blue_loot": 8600000,
        "salvage_est": 3000000,
    },
    {
        "name": "Forgotten Perimeter Habitation Coils",
        "type": "relic",
        "blue_loot": 25400000,
        "salvage_est": 9000000,
    },
]

GAS_SITES = [
    {
        "name": "Barren Perimeter Reservoir",
        "gas_value": 45000000,
        "ninja_value_min": 8000000,
        "ninja_value_max": 12000000,
    },
    {
        "name": "Vital Core Reservoir",
        "gas_value": 500000000,
        "ninja_value_min": 80000000,
        "ninja_value_max": 110000000,
    },
]


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_full_scan(self):
        result = parse_scan(FULL_SCAN)
        assert isinstance(result, ParseResult)
        assert len(result.signatures) == 6
        assert result.warnings == []

        # Check gas site
        gas = result.signatures[0]
        assert gas.sig_id == "ABC-123"
        assert gas.scan_group == "Cosmic Signature"
        assert gas.group == "Gas Site"
        assert gas.name == "Barren Perimeter Reservoir"
        assert gas.signal_strength == 100.0
        assert gas.distance_au == 4.2

        # Check wormhole
        wh = result.signatures[2]
        assert wh.group == "Wormhole"
        assert wh.name == "Wormhole"

        # Check anomaly
        anom = result.signatures[3]
        assert anom.scan_group == "Cosmic Anomaly"

    def test_partially_scanned_sigs(self):
        result = parse_scan(FULL_SCAN)
        partial = result.signatures[5]
        assert partial.sig_id == "PQR-678"
        assert partial.group == ""
        assert partial.name == ""
        assert partial.signal_strength == 15.0

    def test_header_row_skipped(self):
        result = parse_scan(SCAN_WITH_HEADER)
        assert len(result.signatures) == 1
        assert result.signatures[0].sig_id == "ABC-123"
        assert result.warnings == []

    def test_no_header_row(self):
        # Same data without header — should parse identically
        result = parse_scan("ABC-123\tCosmic Signature\tGas Site\tBarren Perimeter Reservoir\t100.0%\t4.2 AU\n")
        assert len(result.signatures) == 1
        assert result.warnings == []

    def test_empty_input(self):
        assert parse_scan("").signatures == []
        assert parse_scan("   ").signatures == []
        assert parse_scan("\n\n").signatures == []

    def test_wrong_column_count(self):
        result = parse_scan("ABC-123\tCosmic Signature\tGas Site\n")
        assert len(result.signatures) == 0
        assert len(result.warnings) == 1
        assert "expected 6" in result.warnings[0]

    def test_invalid_signal_strength(self):
        result = parse_scan("ABC-123\tCosmic Signature\tGas Site\tFoo\tbad\t4.2 AU\n")
        assert len(result.signatures) == 0
        assert len(result.warnings) == 1
        assert "signal strength" in result.warnings[0].lower()

    def test_truncated_name_with_ellipsis(self):
        """Scanner truncates long names with ..., parser should accept as-is."""
        line = "DEF-456\tCosmic Signature\tCombat Site\tForgotten Perimeter Habitation...\t100.0%\t2.3 AU\n"
        result = parse_scan(line)
        assert len(result.signatures) == 1
        assert result.signatures[0].name == "Forgotten Perimeter Habitation..."


# ---------------------------------------------------------------------------
# Valuator tests
# ---------------------------------------------------------------------------

class TestValuator:
    def test_valuate_gas_site(self):
        sig = ScannedSig("ABC-123", "Cosmic Signature", "Gas Site", "Barren Perimeter Reservoir", 100.0, 4.2)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        assert len(results) == 1
        v = results[0]
        assert v.category == "gas"
        assert v.gas_value == 45000000
        assert v.ninja_value_min == 8000000
        assert v.ninja_value_max == 12000000
        assert v.total_est == 45000000

    def test_valuate_combat_site(self):
        sig = ScannedSig("JKL-012", "Cosmic Anomaly", "Combat Site", "Perimeter Ambush Point", 100.0, 3.1)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        assert len(results) == 1
        v = results[0]
        assert v.category == "combat"
        assert v.blue_loot == 8600000
        assert v.salvage_est == 3000000
        assert v.total_est == 8600000 + 3000000

    def test_valuate_combat_relic_site(self):
        """Combat sites with type=relic still match via combat_sites DB."""
        sig = ScannedSig("DEF-456", "Cosmic Signature", "Combat Site", "Forgotten Perimeter Habitation Coils", 100.0, 2.3)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        v = results[0]
        assert v.category == "combat"
        assert v.blue_loot == 25400000

    def test_valuate_wormhole(self):
        sig = ScannedSig("GHI-789", "Cosmic Signature", "Wormhole", "Wormhole", 100.0, 1.2)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        v = results[0]
        assert v.category == "wormhole"
        assert v.total_est is None
        assert v.link == "/eve/wh"

    def test_valuate_unknown_partial_sig(self):
        sig = ScannedSig("PQR-678", "Cosmic Signature", "", "", 15.0, 9.1)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        v = results[0]
        assert v.category == "unknown"
        assert v.total_est is None

    def test_sort_by_value_descending(self):
        sigs = [
            ScannedSig("A", "Cosmic Signature", "Wormhole", "Wormhole", 100.0, 1.0),
            ScannedSig("B", "Cosmic Anomaly", "Combat Site", "Perimeter Ambush Point", 100.0, 2.0),
            ScannedSig("C", "Cosmic Signature", "Gas Site", "Barren Perimeter Reservoir", 100.0, 3.0),
            ScannedSig("D", "Cosmic Signature", "", "", 15.0, 4.0),
        ]
        results = valuate_system(sigs, COMBAT_SITES, GAS_SITES)
        # Gas (45M) > Combat (11.6M) > Wormhole (None) > Unknown (None)
        assert results[0].sig.sig_id == "C"  # gas, 45M
        assert results[1].sig.sig_id == "B"  # combat, 11.6M
        # Wormhole and unknown both have None — order among them is stable
        none_ids = {results[2].sig.sig_id, results[3].sig.sig_id}
        assert none_ids == {"A", "D"}

    def test_truncated_name_matches(self):
        """Valuator matches scanner-truncated names (trailing ...) to full site names."""
        sig = ScannedSig("DEF-456", "Cosmic Signature", "Combat Site", "Forgotten Perimeter Habitation...", 100.0, 2.3)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        v = results[0]
        assert v.blue_loot == 25400000

    def test_unmatched_site_name(self):
        sig = ScannedSig("X", "Cosmic Signature", "Gas Site", "Nonexistent Gas Cloud", 100.0, 1.0)
        results = valuate_system([sig], COMBAT_SITES, GAS_SITES)
        v = results[0]
        assert v.category == "gas"
        assert v.gas_value is None
        assert v.total_est is None

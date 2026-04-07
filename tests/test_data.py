"""Tests for wormhole data loading."""
from eve_wh.data.loader import load_common_ships, load_wormhole_types


class TestWormholeTypes:
    def test_load_types(self):
        types = load_wormhole_types()
        assert len(types) >= 30

    def test_known_types(self):
        types = load_wormhole_types()
        assert "B274" in types
        assert "H296" in types
        assert "E004" in types

    def test_b274_properties(self):
        types = load_wormhole_types()
        b274 = types["B274"]
        assert b274.destination == "Highsec"
        assert b274.total_mass == 2_000_000_000
        assert b274.max_jump_mass == 300_000_000
        assert b274.size_class == "large"

    def test_capital_hole(self):
        types = load_wormhole_types()
        h296 = types["H296"]
        assert h296.max_jump_mass == 1_350_000_000
        assert h296.size_class == "capital"

    def test_frigate_hole(self):
        types = load_wormhole_types()
        e004 = types["E004"]
        assert e004.max_jump_mass == 5_000_000
        assert e004.size_class == "frigate"

    def test_all_have_required_fields(self):
        types = load_wormhole_types()
        for wh_id, wh in types.items():
            assert wh.total_mass > 0, f"{wh_id} missing total_mass"
            assert wh.max_jump_mass > 0, f"{wh_id} missing max_jump_mass"
            assert wh.max_stable_hours > 0, f"{wh_id} missing max_stable_hours"


class TestCommonShips:
    def test_load_ships(self):
        ships = load_common_ships()
        assert len(ships) >= 15

    def test_megathron(self):
        ships = load_common_ships()
        mega = next(s for s in ships if s.name == "Megathron")
        assert mega.cold_mass == 101_000_000
        assert mega.hot_mass > mega.cold_mass

    def test_sigil(self):
        ships = load_common_ships()
        sigil = next(s for s in ships if s.name == "Sigil")
        assert sigil.cold_mass < 20_000_000  # Small enough for medium holes

    def test_hot_always_greater(self):
        ships = load_common_ships()
        for s in ships:
            assert s.hot_mass > s.cold_mass, f"{s.name}: hot should be > cold"

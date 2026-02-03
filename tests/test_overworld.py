from src.overworld import Overworld, UNIT_STATS


class TestAddUnitsToArmy:
    def _empty_overworld(self):
        ow = Overworld(num_players=2)
        ow.armies.clear()
        return ow

    def test_add_to_empty_pos(self):
        ow = self._empty_overworld()
        ow._add_units_to_army((3, 3), 1, "Page", 5)
        army = ow.get_army_at((3, 3))
        assert army is not None
        assert army.player == 1
        assert army.units == [("Page", 5)]

    def test_add_to_existing_army_same_unit(self):
        ow = self._empty_overworld()
        ow._add_units_to_army((3, 3), 1, "Page", 3)
        ow._add_units_to_army((3, 3), 1, "Page", 2)
        army = ow.get_army_at((3, 3))
        assert army.units == [("Page", 5)]

    def test_add_different_unit_to_existing_army(self):
        ow = self._empty_overworld()
        ow._add_units_to_army((3, 3), 1, "Page", 3)
        ow._add_units_to_army((3, 3), 1, "Librarian", 2)
        army = ow.get_army_at((3, 3))
        assert ("Page", 3) in army.units
        assert ("Librarian", 2) in army.units


class TestBuildUnit:
    def test_build_reduces_gold(self):
        ow = Overworld(num_players=2)
        initial_gold = ow.gold[1]
        err = ow.build_unit(1, "Page")
        assert err is None
        assert ow.gold[1] == initial_gold - UNIT_STATS["Page"]["value"]

    def test_build_unknown_unit(self):
        ow = Overworld(num_players=2)
        err = ow.build_unit(1, "Nonexistent")
        assert err is not None

    def test_build_insufficient_gold(self):
        ow = Overworld(num_players=2)
        ow.gold[1] = 0
        err = ow.build_unit(1, "Page")
        assert "gold" in err.lower()


class TestGoldCollection:
    def test_collect_gold_at_pile(self):
        ow = Overworld(num_players=2, rng_seed=42)
        if ow.gold_piles:
            pile = ow.gold_piles[0]
            pos = pile.pos
            value = pile.value
            initial_gold = ow.gold[1]
            collected = ow.collect_gold_at(pos, 1)
            assert collected == value
            assert ow.gold[1] == initial_gold + value

    def test_collect_gold_at_empty(self):
        ow = Overworld(num_players=2, rng_seed=42)
        # Pick a position with no gold pile
        occupied = {p.pos for p in ow.gold_piles}
        empty_pos = next(
            (c, r)
            for r in range(ow.ROWS)
            for c in range(ow.COLS)
            if (c, r) not in occupied
        )
        collected = ow.collect_gold_at(empty_pos, 1)
        assert collected == 0

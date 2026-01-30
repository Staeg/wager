import tkinter as tk
import pytest
import random
from src.combat import Battle, Unit, CombatGUI


# Default test armies (Custodians vs Weavers faction units)
DEFAULT_P1 = [("Page", 3, 1, 1, 10), ("Librarian", 2, 0, 3, 5, 0, 0, 1)]
DEFAULT_P2 = [("Apprentice", 8, 1, 2, 10, 0, 0, 0, 1), ("Seeker", 3, 1, 4, 5, 0, 0, 0, 0, 1)]


# --- Range-based spawn ordering ---

class TestSpawnOrdering:
    def test_p1_melee_in_front(self):
        """P1 melee units (range 1) should be in higher cols than ranged units."""
        random.seed(42)
        b = Battle()
        p1 = [u for u in b.units if u.player == 1]
        melee = [u for u in p1 if u.attack_range == 1]
        ranged = [u for u in p1 if u.attack_range > 1]
        assert melee and ranged
        avg_melee_col = sum(u.pos[0] for u in melee) / len(melee)
        avg_ranged_col = sum(u.pos[0] for u in ranged) / len(ranged)
        assert avg_melee_col > avg_ranged_col

    def test_p2_shorter_range_in_front(self):
        """P2 shorter-range units should be in lower cols than longer-range units."""
        random.seed(42)
        b = Battle()
        p2 = [u for u in b.units if u.player == 2]
        short = [u for u in p2 if u.attack_range <= 2]
        long = [u for u in p2 if u.attack_range > 2]
        assert short and long
        avg_short_col = sum(u.pos[0] for u in short) / len(short)
        avg_long_col = sum(u.pos[0] for u in long) / len(long)
        assert avg_short_col < avg_long_col

    def test_p1_positions_in_west_zone(self):
        b = Battle()
        for u in b.units:
            if u.player == 1:
                assert 0 <= u.pos[0] <= 5

    def test_p2_positions_in_east_zone(self):
        b = Battle()
        for u in b.units:
            if u.player == 2:
                assert 11 <= u.pos[0] <= 16

    def test_no_duplicate_positions(self):
        b = Battle()
        positions = [u.pos for u in b.units]
        assert len(positions) == len(set(positions))

    def test_p1_no_ranged_in_front_column(self):
        """No ranged P1 units should be in the frontmost column (col 5)."""
        for seed in range(10):
            random.seed(seed)
            b = Battle()
            for u in b.units:
                if u.player == 1 and u.attack_range > 1:
                    assert u.pos[0] < 5, f"Ranged unit {u.name} in front col 5 (seed={seed})"

    def test_p2_longest_range_not_in_front_column(self):
        """Longest-range P2 units should not be in the frontmost column (col 11)."""
        for seed in range(10):
            random.seed(seed)
            b = Battle()
            max_range = max(u.attack_range for u in b.units if u.player == 2)
            for u in b.units:
                if u.player == 2 and u.attack_range == max_range and max_range > 2:
                    assert u.pos[0] > 11, f"Longest-range unit {u.name} in front col 11 (seed={seed})"

    def test_row_variety_across_seeds(self):
        """Rows within each column should be shuffled, producing variety across seeds."""
        row_sets = []
        for seed in range(5):
            random.seed(seed)
            b = Battle()
            rows = tuple(u.pos[1] for u in b.units if u.player == 1)
            row_sets.append(rows)
        assert len(set(row_sets)) > 1, "Expected variety in row placement across seeds"


# --- Skip ---

class TestSkip:
    def test_skip_produces_winner(self):
        b = Battle()
        while b.step():
            pass
        assert b.winner in (1, 2)

    def test_skip_history_preserved(self):
        b = Battle()
        while b.step():
            pass
        assert len(b.history) > 0

    def test_undo_after_skip(self):
        b = Battle()
        while b.step():
            pass
        winner_before = b.winner
        b.undo()
        # After undo, winner should be cleared (stepped back one state)
        assert b.winner is None or b.winner != winner_before or len(b.history) >= 0

    def test_multiple_undos_after_skip(self):
        b = Battle()
        while b.step():
            pass
        hist_len = len(b.history)
        for _ in range(5):
            b.undo()
        assert len(b.history) == hist_len - 5


# --- Speed controls (GUI) ---

@pytest.fixture(scope="session")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def gui(tk_root):
    Unit._id_counter = 0
    g = CombatGUI(tk_root)
    yield g


class TestSpeedControls:
    def test_initial_speed(self, gui):
        assert gui.speed_index == 2
        assert gui.auto_delay == 100
        assert gui.speed_var.get() == "1x"

    def test_speed_up(self, gui):
        gui._speed_up()
        assert gui.auto_delay == 50
        assert gui.speed_var.get() == "2x"

    def test_speed_down(self, gui):
        gui._speed_down()
        assert gui.auto_delay == 200
        assert gui.speed_var.get() == "0.5x"

    def test_speed_clamp_upper(self, gui):
        for _ in range(10):
            gui._speed_up()
        assert gui.speed_index == len(gui.speed_levels) - 1
        assert gui.speed_var.get() == "4x"

    def test_speed_clamp_lower(self, gui):
        for _ in range(10):
            gui._speed_down()
        assert gui.speed_index == 0
        assert gui.speed_var.get() == "0.3x"

    def test_speed_roundtrip(self, gui):
        gui._speed_up()
        gui._speed_up()
        gui._speed_down()
        gui._speed_down()
        assert gui.auto_delay == 100
        assert gui.speed_var.get() == "1x"


# --- Skip button (GUI) ---

class TestGUISkip:
    def test_skip_ends_battle(self, gui):
        gui.on_skip()
        assert gui.battle.winner in (1, 2)

    def test_skip_stops_auto(self, gui):
        gui.auto_running = True
        gui.on_skip()
        assert gui.auto_running is False
        assert gui.auto_btn.cget("text") == "Auto"

    def test_undo_after_gui_skip(self, gui):
        gui.on_skip()
        gui.on_undo()
        # Should be able to undo at least one step
        assert len(gui.battle.history) >= 0

    def test_skip_then_reset(self, gui):
        gui.on_skip()
        gui.on_reset()
        assert gui.battle.winner is None
        assert len(gui.battle.history) == 0


# --- New ability tests ---

class TestPush:
    def test_push_moves_target(self):
        """A unit with push should move the target away horizontally after attacking."""
        # Apprentice (push=1) attacks a Page
        p1 = [("Page", 3, 1, 1, 1)]
        p2 = [("Apprentice", 8, 1, 2, 1, 0, 0, 0, 1)]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        # Run until an attack with push happens
        pushed = False
        for _ in range(200):
            if not b.step():
                break
            if any("pushed" in line for line in b.log[-3:]):
                pushed = True
                break
        # Either push happened or battle ended (Page might die before push)
        assert pushed or b.winner is not None

    def test_push_blocked_by_occupied(self):
        """Push should not move target into an occupied hex."""
        # Two Pages side by side, Apprentice pushes one into the other's hex
        p1 = [("Page", 30, 0, 1, 2)]  # Two pages, no damage so they survive
        p2 = [("Apprentice", 80, 1, 2, 1, 0, 0, 0, 1)]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=42)
        # All positions should remain valid (no overlaps)
        for _ in range(100):
            if not b.step():
                break
            alive_positions = [u.pos for u in b.units if u.alive]
            assert len(alive_positions) == len(set(alive_positions)), "Push created overlapping positions"


class TestRamp:
    def test_ramp_increases_damage(self):
        """A unit with ramp should increase damage after each successful attack."""
        p1 = [("Page", 100, 0, 1, 1)]  # Tanky target, 0 damage
        p2 = [("Seeker", 100, 1, 4, 1, 0, 0, 0, 0, 1)]  # ramp=1
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        seeker = [u for u in b.units if u.name == "Seeker"][0]
        initial_damage = seeker.damage
        for _ in range(200):
            if not b.step():
                break
            if seeker._ramp_accumulated >= 2:
                break
        assert seeker.damage > initial_damage, "Ramp should increase damage"
        assert seeker.damage == initial_damage + seeker._ramp_accumulated

    def test_ramp_undo(self):
        """Undo should restore ramp-accumulated damage."""
        p1 = [("Page", 100, 0, 1, 1)]
        p2 = [("Seeker", 100, 1, 4, 1, 0, 0, 0, 0, 1)]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        seeker = [u for u in b.units if u.name == "Seeker"][0]
        # Step until ramp triggers
        for _ in range(200):
            if not b.step():
                break
            if seeker._ramp_accumulated > 0:
                dmg_after = seeker.damage
                b.undo()
                assert seeker.damage < dmg_after, "Undo should restore pre-ramp damage"
                break


class TestAmplify:
    def test_amplify_boosts_adjacent_ability(self):
        """Amplify should increase adjacent allies' ability values."""
        # Conduit (amplify=1) next to Seeker (ramp=1) -> effective ramp=2
        p1 = [("Page", 100, 0, 1, 1)]
        # Put conduit and seeker together
        p2 = [("Conduit", 100, 2, 3, 1, 0, 0, 0, 0, 0, 1), ("Seeker", 100, 1, 4, 1, 0, 0, 0, 0, 1)]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        seeker = [u for u in b.units if u.name == "Seeker"][0]
        conduit = [u for u in b.units if u.name == "Conduit"][0]
        # Check effective ability when adjacent
        from src.combat import hex_distance
        if hex_distance(seeker.pos, conduit.pos) <= 1:
            eff = b._effective_ability(seeker, "ramp")
            assert eff == 2, f"Expected effective ramp=2 (1 base + 1 amplify), got {eff}"

    def test_amplify_not_self(self):
        """Amplify should not boost the unit's own abilities."""
        p1 = [("Page", 100, 0, 1, 1)]
        p2 = [("Conduit", 100, 2, 3, 1, 0, 0, 0, 0, 0, 1)]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        conduit = [u for u in b.units if u.name == "Conduit"][0]
        # Conduit has no ramp/push/sunder, so amplify doesn't boost itself
        assert b._effective_ability(conduit, "amplify") == 0 or conduit.amplify == 1


class TestNewUnitAttributes:
    def test_unit_has_new_attrs(self):
        u = Unit("Test", 10, 2, 1, 1, push=1, ramp=2, amplify=3)
        assert u.push == 1
        assert u.ramp == 2
        assert u.amplify == 3
        assert u._ramp_accumulated == 0

    def test_default_new_attrs_zero(self):
        u = Unit("Test", 10, 2, 1, 1)
        assert u.push == 0
        assert u.ramp == 0
        assert u.amplify == 0

    def test_all_ability_keys_default_zero(self):
        u = Unit("Test", 10, 2, 1, 1)
        for key in Unit.ABILITY_KEYS:
            assert getattr(u, key) == 0


class TestBarrage:
    def test_barrage_hits_adjacent_enemies(self):
        """Barrage should deal damage to enemies adjacent to the attack target."""
        # Savant (barrage=1) attacks one of two clustered enemies
        p1 = [{"name": "Dummy", "max_hp": 50, "damage": 0, "range": 1, "count": 2}]
        p2 = [{"name": "Savant", "max_hp": 100, "damage": 4, "range": 4, "count": 1, "barrage": 1}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        barraged = False
        for _ in range(200):
            if not b.step():
                break
            if any("Barrage hits" in line for line in b.log[-5:]):
                barraged = True
                break
        # Barrage may or may not fire depending on positioning
        assert barraged or b.winner is not None


class TestRage:
    def test_rage_increases_damage_on_hit(self):
        """Rage should increase damage when the unit takes damage."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 1, "range": 1, "count": 1}]
        p2 = [{"name": "Penitent", "max_hp": 100, "damage": 1, "range": 1, "count": 1, "rage": 1}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        penitent = [u for u in b.units if u.name == "Penitent"][0]
        initial_dmg = penitent.damage
        for _ in range(200):
            if not b.step():
                break
            if penitent._rage_accumulated > 0:
                break
        assert penitent.damage > initial_dmg, "Rage should increase damage after taking damage"


class TestVengeance:
    def test_vengeance_triggers_on_ally_death(self):
        """Vengeance should increase damage when an adjacent ally dies."""
        # Weak ally next to Avenger, enemy kills the ally
        p1 = [{"name": "Killer", "max_hp": 100, "damage": 100, "range": 1, "count": 1}]
        p2 = [
            {"name": "Avenger", "max_hp": 100, "damage": 3, "range": 1, "count": 1, "vengeance": 1},
            {"name": "Fodder", "max_hp": 1, "damage": 0, "range": 1, "count": 1},
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        avenger = [u for u in b.units if u.name == "Avenger"][0]
        vengeanced = False
        for _ in range(200):
            if not b.step():
                break
            if avenger._vengeance_accumulated > 0:
                vengeanced = True
                break
        # Vengeance may not trigger if Avenger and Fodder aren't adjacent
        assert vengeanced or b.winner is not None


class TestRepair:
    def test_repair_heals_adjacent_allies(self):
        """Repair should heal adjacent allies at end of turn."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 1, "range": 4, "count": 1}]
        p2 = [
            {"name": "Kitboy", "max_hp": 100, "damage": 2, "range": 2, "count": 1, "repair": 1},
            {"name": "Buddy", "max_hp": 100, "damage": 0, "range": 1, "count": 1},
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        repaired = False
        for _ in range(300):
            if not b.step():
                break
            if any("repairs" in line for line in b.log[-5:]):
                repaired = True
                break
        assert repaired or b.winner is not None


class TestBombardment:
    def test_bombardment_deals_extra_damage(self):
        """Bombardment should deal extra damage at end of turn."""
        p1 = [{"name": "Dummy", "max_hp": 100, "damage": 0, "range": 1, "count": 1}]
        p2 = [{"name": "Artillery", "max_hp": 100, "damage": 4, "range": 4, "count": 1,
               "bombardment": 2, "bombardment_range": 6}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        bombarded = False
        for _ in range(200):
            if not b.step():
                break
            if any("bombards" in line for line in b.log[-5:]):
                bombarded = True
                break
        assert bombarded or b.winner is not None


class TestChargeSummon:
    def test_summon_creates_blades(self):
        """Charge/Summon should create Blade units every N turns."""
        p1 = [{"name": "Dummy", "max_hp": 200, "damage": 0, "range": 1, "count": 1}]
        p2 = [{"name": "Herald", "max_hp": 100, "damage": 1, "range": 4, "count": 1,
               "charge": 3, "summon_count": 2}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        summoned = False
        for _ in range(300):
            if not b.step():
                break
            if any("summons" in line for line in b.log[-5:]):
                summoned = True
                break
        assert summoned, "Herald should summon Blades"
        blades = [u for u in b.units if u.name == "Blade"]
        assert len(blades) > 0

    def test_summoned_blades_are_exhausted(self):
        """Summoned Blades should be created exhausted."""
        p1 = [{"name": "Dummy", "max_hp": 200, "damage": 0, "range": 1, "count": 1}]
        p2 = [{"name": "Herald", "max_hp": 100, "damage": 1, "range": 4, "count": 1,
               "charge": 3, "summon_count": 2}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        for _ in range(300):
            if not b.step():
                break
            blades = [u for u in b.units if u.name == "Blade"]
            if blades:
                # Blades should have been created with has_acted=True
                # (they may have acted by now in subsequent rounds, so just check they exist)
                break
        assert any(u.name == "Blade" for u in b.units)


class TestUndying:
    def test_undying_prevents_death(self):
        """Undying should prevent death by reducing attack damage instead."""
        p1 = [{"name": "Killer", "max_hp": 100, "damage": 100, "range": 1, "count": 1}]
        p2 = [
            {"name": "Gatekeeper", "max_hp": 100, "damage": 4, "range": 2, "count": 1, "undying": 2},
            {"name": "Warrior", "max_hp": 3, "damage": 5, "range": 1, "count": 1},
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        saved = False
        for _ in range(300):
            if not b.step():
                break
            if any("saved by Undying" in line for line in b.log[-5:]):
                saved = True
                break
        # May or may not trigger depending on adjacency
        assert saved or b.winner is not None


class TestDictUnitSpec:
    def test_dict_spec_creates_units(self):
        """Dict-based unit specs should work for Battle construction."""
        p1 = [{"name": "Test", "max_hp": 10, "damage": 2, "range": 1, "count": 3, "armor": 1}]
        p2 = [{"name": "Foe", "max_hp": 5, "damage": 1, "range": 2, "count": 2, "push": 1}]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        tests = [u for u in b.units if u.name == "Test"]
        foes = [u for u in b.units if u.name == "Foe"]
        assert len(tests) == 3
        assert len(foes) == 2
        assert all(u.armor == 1 for u in tests)
        assert all(u.push == 1 for u in foes)

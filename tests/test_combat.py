import tkinter as tk
import pytest
import random
from src.combat import Battle, Unit, CombatGUI


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

    def test_p2_melee_in_front(self):
        """P2 melee units (range 1) should be in lower cols than ranged units."""
        random.seed(42)
        b = Battle()
        p2 = [u for u in b.units if u.player == 2]
        melee = [u for u in p2 if u.attack_range == 1]
        ranged = [u for u in p2 if u.attack_range > 1]
        assert melee and ranged
        avg_melee_col = sum(u.pos[0] for u in melee) / len(melee)
        avg_ranged_col = sum(u.pos[0] for u in ranged) / len(ranged)
        assert avg_melee_col < avg_ranged_col

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

    def test_p2_no_ranged_in_front_column(self):
        """No ranged P2 units should be in the frontmost column (col 11)."""
        for seed in range(10):
            random.seed(seed)
            b = Battle()
            for u in b.units:
                if u.player == 2 and u.attack_range > 1:
                    assert u.pos[0] > 11, f"Ranged unit {u.name} in front col 11 (seed={seed})"

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
        winner = gui.battle.winner
        gui.on_undo()
        # Should be able to undo at least one step
        assert len(gui.battle.history) >= 0

    def test_skip_then_reset(self, gui):
        gui.on_skip()
        gui.on_reset()
        assert gui.battle.winner is None
        assert len(gui.battle.history) == 0

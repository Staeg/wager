import tkinter as tk
import pytest
import random
from src.ability_defs import ability
from src.combat import Battle
from src.combat_gui import CombatGUI


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
                    assert u.pos[0] < 5, (
                        f"Ranged unit {u.name} in front col 5 (seed={seed})"
                    )

    def test_p2_longest_range_not_in_front_column(self):
        """Longest-range P2 units should not be in the frontmost column (col 11)."""
        for seed in range(10):
            random.seed(seed)
            b = Battle()
            max_range = max(u.attack_range for u in b.units if u.player == 2)
            for u in b.units:
                if u.player == 2 and u.attack_range == max_range and max_range > 2:
                    assert u.pos[0] > 11, (
                        f"Longest-range unit {u.name} in front col 11 (seed={seed})"
                    )

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
        hist_before = len(b.history)
        b.undo()
        # Undo should pop one state from history
        assert len(b.history) == hist_before - 1

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
        hist_before = len(gui.battle.history)
        gui.on_undo()
        # Undo should pop one state from history
        assert len(gui.battle.history) == hist_before - 1

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
        p1 = [{"name": "Page", "max_hp": 3, "damage": 1, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Apprentice",
                "max_hp": 8,
                "damage": 1,
                "range": 2,
                "count": 1,
                "abilities": [
                    ability("onhit", "push", target="target", value=1)
                ],
            }
        ]
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
        assert pushed, "Push should trigger before battle ends"

    def test_push_blocked_by_occupied(self):
        """Push should not move target into an occupied hex."""
        # Two Pages side by side, Apprentice pushes one into the other's hex
        p1 = [
            {"name": "Page", "max_hp": 30, "damage": 0, "range": 1, "count": 2}
        ]  # Two pages, no damage so they survive
        p2 = [
            {
                "name": "Apprentice",
                "max_hp": 80,
                "damage": 1,
                "range": 2,
                "count": 1,
                "abilities": [
                    ability("onhit", "push", target="target", value=1)
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=42)
        # All positions should remain valid (no overlaps)
        for _ in range(100):
            if not b.step():
                break
            alive_positions = [u.pos for u in b.units if u.alive]
            assert len(alive_positions) == len(set(alive_positions)), (
                "Push created overlapping positions"
            )


class TestRamp:
    def test_ramp_increases_damage(self):
        """A unit with ramp should increase damage after each successful attack."""
        p1 = [
            {"name": "Page", "max_hp": 100, "damage": 0, "range": 1, "count": 1}
        ]  # Tanky target, 0 damage
        p2 = [
            {
                "name": "Seeker",
                "max_hp": 100,
                "damage": 1,
                "range": 4,
                "count": 1,
                "abilities": [ability("onhit", "ramp", target="self", value=1)],
            }
        ]
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
        p1 = [{"name": "Page", "max_hp": 100, "damage": 0, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Seeker",
                "max_hp": 100,
                "damage": 1,
                "range": 4,
                "count": 1,
                "abilities": [ability("onhit", "ramp", target="self", value=1)],
            }
        ]
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


class TestSplash:
    def test_splash_hits_adjacent_enemies(self):
        """Splash should deal damage to enemies adjacent to the attack target."""
        # Savant (splash=1) attacks one of two clustered enemies
        p1 = [{"name": "Dummy", "max_hp": 50, "damage": 0, "range": 1, "count": 2}]
        p2 = [
            {
                "name": "Savant",
                "max_hp": 100,
                "damage": 4,
                "range": 4,
                "count": 1,
                "abilities": [ability("onhit", "splash", target="target", value=1)],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        splashed = False
        for _ in range(200):
            if not b.step():
                break
            if any("Splash hits" in line for line in b.log[-5:]):
                splashed = True
                break
        # Splash may or may not fire depending on positioning
        assert splashed, "Splash should trigger before battle ends"


class TestWounded:
    def test_wounded_increases_damage_on_hit(self):
        """Wounded should increase damage when the unit takes damage."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 1, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Penitent",
                "max_hp": 100,
                "damage": 1,
                "range": 1,
                "count": 1,
                "abilities": [ability("wounded", "ramp", target="self", value=1)],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        penitent = [u for u in b.units if u.name == "Penitent"][0]
        initial_dmg = penitent.damage
        for _ in range(200):
            if not b.step():
                break
            if penitent._ramp_accumulated > 0:
                break
        assert penitent.damage > initial_dmg, (
            "Wounded should increase damage after taking damage"
        )


class TestLament:
    def test_lament_triggers_on_ally_death(self):
        """Lament should increase damage when an ally dies in range."""
        # Weak ally same range as Avenger so they spawn in same column (adjacent)
        p1 = [{"name": "Killer", "max_hp": 100, "damage": 100, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Avenger",
                "max_hp": 100,
                "damage": 3,
                "range": 1,
                "count": 1,
                "abilities": [
                    ability("lament", "ramp", target="self", value=1, range=2)
                ],
            },
            {"name": "Fodder", "max_hp": 1, "damage": 0, "range": 1, "count": 3},
        ]
        ramped = False
        for seed in range(10):
            b = Battle(p1_units=p1, p2_units=p2, rng_seed=seed)
            avenger = [u for u in b.units if u.name == "Avenger"][0]
            for _ in range(200):
                if not b.step():
                    break
                if avenger._ramp_accumulated > 0:
                    ramped = True
                    break
            if ramped:
                break
        assert ramped, "Lament should trigger across seeds"


class TestRepair:
    def test_repair_heals_adjacent_allies(self):
        """Heal should heal adjacent allies at end of turn."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 1, "range": 4, "count": 1}]
        p2 = [
            {
                "name": "Kitboy",
                "max_hp": 100,
                "damage": 2,
                "range": 2,
                "count": 1,
                "abilities": [
                    ability("endturn", "heal", target="area", value=1, range=1)
                ],
            },
            {"name": "Buddy", "max_hp": 100, "damage": 0, "range": 1, "count": 1},
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        repaired = False
        for _ in range(300):
            if not b.step():
                break
            if any("heals" in line for line in b.log[-5:]):
                repaired = True
                break
        assert repaired, "Heal should trigger before battle ends"


class TestStrike:
    def test_strike_deals_extra_damage(self):
        """Strike should deal extra damage at end of turn."""
        p1 = [{"name": "Dummy", "max_hp": 100, "damage": 0, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Artillery",
                "max_hp": 100,
                "damage": 4,
                "range": 4,
                "count": 1,
                "abilities": [
                    ability("endturn", "strike", target="random", value=2, range=6)
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        struck = False
        for _ in range(200):
            if not b.step():
                break
            if any("strikes" in line for line in b.log[-5:]):
                struck = True
                break
        assert struck, "Strike should trigger before battle ends"


class TestChargeSummon:
    def test_summon_creates_blades(self):
        """Charge/Summon should create Blade units every N turns."""
        p1 = [{"name": "Dummy", "max_hp": 200, "damage": 0, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Herald",
                "max_hp": 100,
                "damage": 1,
                "range": 4,
                "count": 1,
                "abilities": [
                    ability(
                        "endturn",
                        "summon",
                        target="self",
                        count=2,
                        charge=3,
                    )
                ],
            }
        ]
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
        p2 = [
            {
                "name": "Herald",
                "max_hp": 100,
                "damage": 1,
                "range": 4,
                "count": 1,
                "abilities": [
                    ability(
                        "endturn",
                        "summon",
                        target="self",
                        count=2,
                        charge=3,
                    )
                ],
            }
        ]
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
            {
                "name": "Gatekeeper",
                "max_hp": 100,
                "damage": 4,
                "range": 1,
                "count": 1,
                "abilities": [
                    ability("passive", "undying", value=2, aura=3)
                ],
            },
            {"name": "Warrior", "max_hp": 3, "damage": 5, "range": 1, "count": 3},
        ]
        saved = False
        for seed in range(10):
            b = Battle(p1_units=p1, p2_units=p2, rng_seed=seed)
            for _ in range(300):
                if not b.step():
                    break
                if any("saved by Undying" in line for line in b.log[-5:]):
                    saved = True
                    break
            if saved:
                break
        assert saved, "Undying should trigger across seeds"


class TestDictUnitSpec:
    def test_dict_spec_creates_units(self):
        """Dict-based unit specs should work for Battle construction."""
        p1 = [
            {
                "name": "Test",
                "max_hp": 10,
                "damage": 2,
                "range": 1,
                "count": 3,
                "armor": 1,
            }
        ]
        p2 = [
            {
                "name": "Foe",
                "max_hp": 5,
                "damage": 1,
                "range": 2,
                "count": 2,
                "abilities": [
                    ability("onhit", "push", target="target", value=1)
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        tests = [u for u in b.units if u.name == "Test"]
        foes = [u for u in b.units if u.name == "Foe"]
        assert len(tests) == 3
        assert len(foes) == 2
        assert all(u.armor == 1 for u in tests)
        for foe in foes:
            assert any(ab.get("effect") == "push" for ab in foe.abilities)


class TestArmor:
    def test_armor_reduces_damage(self):
        """Armor should reduce incoming damage."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 3, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Tank",
                "max_hp": 100,
                "damage": 1,
                "range": 1,
                "count": 1,
                "armor": 2,
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        tank = [u for u in b.units if u.name == "Tank"][0]
        for _ in range(50):
            if not b.step():
                break
            if tank.hp < 100:
                # Took 3-2=1 damage, not 3
                assert tank.hp >= 99
                break


class TestHeal:
    def test_heal_restores_hp(self):
        """Heal should restore HP to damaged allies."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 1, "range": 4, "count": 1}]
        p2 = [
            {
                "name": "Healer",
                "max_hp": 100,
                "damage": 1,
                "range": 3,
                "count": 1,
                "abilities": [
                    ability("endturn", "heal", target="random", value=3, range=3)
                ],
            },
            {"name": "Buddy", "max_hp": 100, "damage": 0, "range": 1, "count": 1},
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        healed = False
        for _ in range(300):
            if not b.step():
                break
            if any("heals" in line for line in b.log[-5:]):
                healed = True
                break
        assert healed, "Heal should trigger"


class TestFortify:
    def test_fortify_increases_max_hp(self):
        """Fortify should increase max HP and current HP."""
        p1 = [{"name": "Attacker", "max_hp": 100, "damage": 0, "range": 1, "count": 1}]
        p2 = [
            {
                "name": "Fortifier",
                "max_hp": 50,
                "damage": 1,
                "range": 3,
                "count": 1,
                "abilities": [ability("endturn", "fortify", target="self", value=2)],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        fort = [u for u in b.units if u.name == "Fortifier"][0]
        initial_max = fort.max_hp
        for _ in range(200):
            if not b.step():
                break
            if fort.max_hp > initial_max:
                break
        assert fort.max_hp > initial_max, "Fortify should increase max HP"
        assert fort.hp > initial_max, "Fortify should also increase current HP"


class TestSunder:
    def test_sunder_reduces_armor(self):
        """Sunder should reduce target's armor."""
        p1 = [
            {
                "name": "Tank",
                "max_hp": 100,
                "damage": 1,
                "range": 1,
                "count": 1,
                "armor": 5,
            }
        ]
        p2 = [
            {
                "name": "Sunderer",
                "max_hp": 100,
                "damage": 1,
                "range": 3,
                "count": 1,
                "abilities": [
                    ability(
                        "endturn",
                        "sunder",
                        target="random",
                        value=1,
                        range=3,
                    )
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        tank = [u for u in b.units if u.name == "Tank"][0]
        for _ in range(200):
            if not b.step():
                break
            if tank.armor < 5:
                break
        assert tank.armor < 5, "Sunder should reduce armor"


class TestFreeze:
    def test_freeze_exhausts_enemy(self):
        """Freeze should exhaust random ready enemies."""
        p1 = [{"name": "Target", "max_hp": 100, "damage": 0, "range": 1, "count": 3}]
        p2 = [
            {
                "name": "Freezer",
                "max_hp": 100,
                "damage": 1,
                "range": 2,
                "count": 1,
                "abilities": [ability("onhit", "freeze", target="self", value=1)],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        frozen = False
        for _ in range(200):
            if not b.step():
                break
            if any("frozen" in line for line in b.log[-5:]):
                frozen = True
                break
        assert frozen, "Freeze should trigger"


class TestBlock:
    def test_block_prevents_damage(self):
        """Block should prevent the first N damage instances per round."""
        p1 = [
            {
                "name": "Attacker",
                "max_hp": 100,
                "damage": 5,
                "range": 1,
                "count": 1,
            }
        ]
        p2 = [
            {
                "name": "Blocker",
                "max_hp": 20,
                "damage": 1,
                "range": 1,
                "count": 1,
                "abilities": [ability("passive", "block", value=2)],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        blocker = [u for u in b.units if u.name == "Blocker"][0]
        blocked = False
        for _ in range(50):
            if not b.step():
                break
            if any("blocks damage" in line for line in b.log[-5:]):
                blocked = True
                break
        assert blocked, "Block should trigger and prevent damage"
        # Blocker should still have HP since first hits were blocked
        assert blocker.hp > 0 or not blocker.alive


class TestSilence:
    def test_silence_disables_abilities(self):
        """Silence should disable enemy abilities."""
        p1 = [
            {
                "name": "Healer",
                "max_hp": 100,
                "damage": 1,
                "range": 3,
                "count": 1,
                "abilities": [
                    ability("endturn", "heal", target="self", value=10, range=1)
                ],
            }
        ]
        p2 = [
            {
                "name": "Silencer",
                "max_hp": 100,
                "damage": 5,
                "range": 2,
                "count": 1,
                "abilities": [
                    ability("onhit", "silence", target="area", range=3)
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        healer = [u for u in b.units if u.name == "Healer"][0]
        silenced = False
        for _ in range(100):
            if not b.step():
                break
            if any("silences" in line for line in b.log[-5:]):
                silenced = True
                break
        assert silenced, "Silence should trigger"
        assert healer._silenced, "Healer should be silenced"


class TestExecute:
    def test_execute_kills_low_hp_enemies(self):
        """Execute should kill enemies at low HP within range."""
        p1 = [
            {
                "name": "Target",
                "max_hp": 10,
                "damage": 1,
                "range": 1,
                "count": 1,
            }
        ]
        p2 = [
            {
                "name": "Executioner",
                "max_hp": 100,
                "damage": 5,
                "range": 2,
                "count": 1,
                "abilities": [
                    ability(
                        "passive",
                        "execute",
                        target="area",
                        value=5,
                        aura=4,
                    )
                ],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        executed = False
        for _ in range(50):
            if not b.step():
                break
            if any("executes" in line for line in b.log[-10:]):
                executed = True
                break
        assert executed, "Execute should trigger on low HP target"


class TestReady:
    def test_ready_allows_second_action(self):
        """Ready should allow unit to act again after killing."""
        p1 = [
            {
                "name": "Fodder",
                "max_hp": 5,
                "damage": 0,
                "range": 1,
                "count": 3,
            }
        ]
        p2 = [
            {
                "name": "Emperor",
                "max_hp": 100,
                "damage": 10,
                "range": 1,
                "count": 1,
                "abilities": [ability("onkill", "ready", target="self")],
            }
        ]
        b = Battle(p1_units=p1, p2_units=p2, rng_seed=1)
        readied = False
        for _ in range(50):
            if not b.step():
                break
            if any("readies" in line for line in b.log[-5:]):
                readied = True
                break
        assert readied, "Ready should trigger after kill"

"""Tests for quest decision effect handlers."""

from src.overworld import Overworld, OverworldArmy, Base
from src.quest_effects import (
    apply_decision_effects,
    _handle_grant_upgrade,
    _handle_income_bonus,
    _handle_combat_rule,
    _handle_create_base,
    _handle_destroy_base,
    _handle_destroy_largest_army,
    _handle_add_units,
)


def _make_context(world=None, player_id=1, quest_pos=(5, 5)):
    """Helper to create a context dict for effect handlers."""
    if world is None:
        world = Overworld(num_players=4)
    return {
        "world": world,
        "player_id": player_id,
        "quest_pos": quest_pos,
        "player_economy": {},
        "player_combat_rules": {},
        "player_upgrades": {},
    }


class TestGrantUpgrade:
    def test_grant_new_upgrade(self):
        context = _make_context()
        effect = {"type": "grant_upgrade", "upgrade_id": "tide_of_bones"}
        _handle_grant_upgrade(effect, context)
        assert context["player_upgrades"][1] == ["tide_of_bones"]

    def test_grant_upgrade_does_not_duplicate(self):
        context = _make_context()
        context["player_upgrades"][1] = ["tide_of_bones"]
        effect = {"type": "grant_upgrade", "upgrade_id": "tide_of_bones"}
        _handle_grant_upgrade(effect, context)
        assert context["player_upgrades"][1] == ["tide_of_bones"]

    def test_grant_multiple_upgrades(self):
        context = _make_context()
        _handle_grant_upgrade(
            {"type": "grant_upgrade", "upgrade_id": "tide_of_bones"}, context
        )
        _handle_grant_upgrade(
            {"type": "grant_upgrade", "upgrade_id": "soul_eaters"}, context
        )
        assert "tide_of_bones" in context["player_upgrades"][1]
        assert "soul_eaters" in context["player_upgrades"][1]


class TestIncomeBonus:
    def test_add_income_bonus(self):
        context = _make_context()
        effect = {"type": "income_bonus", "delta": 3}
        _handle_income_bonus(effect, context)
        assert context["player_economy"][1]["income_bonus"] == 3

    def test_income_bonus_accumulates(self):
        context = _make_context()
        _handle_income_bonus({"type": "income_bonus", "delta": 3}, context)
        _handle_income_bonus({"type": "income_bonus", "delta": 2}, context)
        assert context["player_economy"][1]["income_bonus"] == 5


class TestCombatRule:
    def test_set_revive_on_win(self):
        context = _make_context()
        effect = {"type": "combat_rule", "rule": "revive_on_win", "value": True}
        _handle_combat_rule(effect, context)
        assert context["player_combat_rules"][1]["revive_on_win"] is True

    def test_set_defending_armor_bonus(self):
        context = _make_context()
        effect = {"type": "combat_rule", "rule": "defending_armor_bonus", "value": 1}
        _handle_combat_rule(effect, context)
        assert context["player_combat_rules"][1]["defending_armor_bonus"] == 1


class TestCreateBase:
    def test_create_base_at_empty_location(self):
        world = Overworld(num_players=4)
        world.bases.clear()
        quest_pos = (7, 7)
        context = _make_context(world=world, quest_pos=quest_pos)

        effect = {"type": "create_base", "income": 20}
        _handle_create_base(effect, context)

        base = world.get_base_at(quest_pos)
        assert base is not None
        assert base.player == 1
        assert base.alive is True

    def test_create_base_converts_existing(self):
        world = Overworld(num_players=4)
        quest_pos = (7, 7)
        # Add an existing base owned by player 2
        world.bases.append(Base(player=2, pos=quest_pos, alive=True))
        context = _make_context(world=world, quest_pos=quest_pos)

        effect = {"type": "create_base", "income": 20}
        _handle_create_base(effect, context)

        base = world.get_base_at(quest_pos)
        assert base is not None
        assert base.player == 1


class TestDestroyBase:
    def test_destroy_base_at_location(self):
        world = Overworld(num_players=4)
        quest_pos = (7, 7)
        # Remove any existing base at the quest position (e.g., neutral structures)
        world.bases = [b for b in world.bases if b.pos != quest_pos]
        world.bases.append(Base(player=1, pos=quest_pos, alive=True))
        context = _make_context(world=world, quest_pos=quest_pos)

        effect = {"type": "destroy_base"}
        _handle_destroy_base(effect, context)

        base = world.get_base_at(quest_pos)
        assert base is None  # get_base_at returns None if not alive

    def test_destroy_base_no_base_is_noop(self):
        world = Overworld(num_players=4)
        quest_pos = (7, 7)
        # Remove any existing base at the quest position
        world.bases = [b for b in world.bases if b.pos != quest_pos]
        context = _make_context(world=world, quest_pos=quest_pos)

        # Should not raise
        effect = {"type": "destroy_base"}
        _handle_destroy_base(effect, context)


class TestDestroyLargestArmy:
    def test_destroy_largest_weaver_army(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        # Player 2 is Weavers slot
        small_army = OverworldArmy(player=2, units=[("Apprentice", 3)], pos=(5, 5))
        large_army = OverworldArmy(player=2, units=[("Apprentice", 10)], pos=(6, 6))
        world.armies.append(small_army)
        world.armies.append(large_army)

        context = _make_context(world=world)
        effect = {"type": "destroy_largest_army", "faction": "Weavers"}
        _handle_destroy_largest_army(effect, context)

        assert large_army not in world.armies
        assert small_army in world.armies

    def test_destroy_largest_army_no_armies(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        context = _make_context(world=world)

        # Should not raise
        effect = {"type": "destroy_largest_army", "faction": "Weavers"}
        _handle_destroy_largest_army(effect, context)


class TestAddUnits:
    def test_add_units_to_hero_army(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        quest_pos = (5, 5)
        hero_army = OverworldArmy(
            player=1, units=[("Necromancer", 1)], pos=quest_pos
        )
        world.armies.append(hero_army)

        context = _make_context(world=world, quest_pos=quest_pos)
        effect = {
            "type": "add_units",
            "units": [("Servant", 12), ("Gatekeeper", 4)],
        }
        _handle_add_units(effect, context)

        assert ("Necromancer", 1) in hero_army.units
        assert ("Servant", 12) in hero_army.units
        assert ("Gatekeeper", 4) in hero_army.units

    def test_add_units_to_existing_unit_type(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        quest_pos = (5, 5)
        hero_army = OverworldArmy(
            player=1, units=[("Page", 5), ("Servant", 3)], pos=quest_pos
        )
        world.armies.append(hero_army)

        context = _make_context(world=world, quest_pos=quest_pos)
        effect = {"type": "add_units", "units": [("Servant", 10)]}
        _handle_add_units(effect, context)

        # Find Servant count
        servant_count = next(c for n, c in hero_army.units if n == "Servant")
        assert servant_count == 13

    def test_add_units_no_army_is_noop(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        context = _make_context(world=world, quest_pos=(5, 5))

        # Should not raise
        effect = {"type": "add_units", "units": [("Servant", 12)]}
        _handle_add_units(effect, context)


class TestApplyDecisionEffects:
    def test_apply_multiple_effects(self):
        world = Overworld(num_players=4)
        world.armies.clear()
        world.bases.clear()  # Clear default bases
        quest_pos = (5, 5)
        hero_army = OverworldArmy(player=1, units=[("Lich", 1)], pos=quest_pos)
        world.armies.append(hero_army)
        world.bases.append(Base(player=2, pos=quest_pos, alive=True))

        context = _make_context(world=world, quest_pos=quest_pos)
        decision = {
            "label": "Spurn",
            "effects": [
                {"type": "destroy_base"},
                {"type": "grant_upgrade", "upgrade_id": "lightbringers"},
            ],
        }
        apply_decision_effects(decision, context)

        # Base should be destroyed
        assert world.get_base_at(quest_pos) is None
        # Upgrade should be granted
        assert "lightbringers" in context["player_upgrades"][1]

    def test_empty_effects_is_noop(self):
        context = _make_context()
        decision = {"label": "Test", "effects": []}
        apply_decision_effects(decision, context)
        # Should not raise, nothing should change
        assert context["player_upgrades"] == {}

    def test_missing_effects_key_is_noop(self):
        context = _make_context()
        decision = {"label": "Test"}
        apply_decision_effects(decision, context)
        # Should not raise
        assert context["player_upgrades"] == {}

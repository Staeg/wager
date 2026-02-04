"""Quest decision effect handlers."""

from .overworld import Structure


def _handle_grant_upgrade(effect, context):
    """Grant an upgrade to the player."""
    upgrade_id = effect["upgrade_id"]
    player_upgrades = context["player_upgrades"]
    player_id = context["player_id"]
    upgrades = player_upgrades.setdefault(player_id, [])
    if upgrade_id not in upgrades:
        upgrades.append(upgrade_id)


def _handle_income_bonus(effect, context):
    """Add to the player's permanent income bonus."""
    delta = effect.get("delta", 0)
    player_economy = context["player_economy"]
    player_id = context["player_id"]
    economy = player_economy.setdefault(player_id, {"income_bonus": 0})
    economy["income_bonus"] = economy.get("income_bonus", 0) + delta


def _handle_combat_rule(effect, context):
    """Set a combat rule for the player."""
    rule = effect["rule"]
    value = effect["value"]
    player_combat_rules = context["player_combat_rules"]
    player_id = context["player_id"]
    rules = player_combat_rules.setdefault(player_id, {})
    rules[rule] = value


def _handle_create_base(effect, context):
    """Create a structure at the quest location."""
    world = context["world"]
    player_id = context["player_id"]
    quest_pos = tuple(context["quest_pos"])  # Ensure tuple for position comparisons
    income = effect.get("income", 5)
    allows_recruitment = effect.get("allows_recruitment", True)
    # Check if there's already a base at this position
    existing = world.get_base_at(quest_pos)
    if existing:
        # Convert ownership if different player
        existing.player = player_id
        existing.income = income
        existing.allows_recruitment = allows_recruitment
    else:
        world.bases.append(
            Structure(
                player=player_id,
                pos=quest_pos,
                alive=True,
                income=income,
                allows_recruitment=allows_recruitment,
            )
        )


def _handle_destroy_base(effect, context):
    """Destroy the base at the quest location."""
    world = context["world"]
    quest_pos = tuple(context["quest_pos"])  # Ensure tuple for position comparisons
    base = world.get_base_at(quest_pos)
    if base:
        base.alive = False


def _handle_destroy_largest_army(effect, context):
    """Destroy the largest army belonging to the specified faction's player slot."""
    from .quests import _FACTION_SLOT

    world = context["world"]
    faction = effect.get("faction")
    if not faction:
        return
    target_player = _FACTION_SLOT.get(faction)
    if not target_player:
        return

    # Find all armies for this player
    target_armies = [a for a in world.armies if a.player == target_player]
    if not target_armies:
        return

    # Find the one with the most total units
    largest = max(target_armies, key=lambda a: a.total_count)
    world.armies.remove(largest)


def _handle_add_units(effect, context):
    """Add units to the hero's army at the quest position."""
    world = context["world"]
    player_id = context["player_id"]
    quest_pos = tuple(context["quest_pos"])  # Ensure tuple for position comparisons
    units_to_add = effect.get("units", [])

    # Find player's army at quest position
    hero_army = None
    for army in world.get_armies_at(quest_pos):
        if army.player == player_id:
            hero_army = army
            break

    if not hero_army:
        return

    for unit_name, count in units_to_add:
        # Check if unit type already exists in army
        found = False
        for i, (name, existing_count) in enumerate(hero_army.units):
            if name == unit_name:
                hero_army.units[i] = (name, existing_count + count)
                found = True
                break
        if not found:
            hero_army.units.append((unit_name, count))


EFFECT_HANDLERS = {
    "grant_upgrade": _handle_grant_upgrade,
    "income_bonus": _handle_income_bonus,
    "combat_rule": _handle_combat_rule,
    "create_base": _handle_create_base,
    "destroy_base": _handle_destroy_base,
    "destroy_largest_army": _handle_destroy_largest_army,
    "add_units": _handle_add_units,
}


def apply_decision_effects(decision, context):
    """Apply all effects from a quest decision.

    Args:
        decision: the decision dict with "effects" array
        context: dict with world, player_id, quest_pos, player_economy,
                 player_combat_rules, player_upgrades
    """
    for effect in decision.get("effects", []):
        handler = EFFECT_HANDLERS.get(effect["type"])
        if handler:
            handler(effect, context)

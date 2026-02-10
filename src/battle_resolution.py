"""Shared battle resolution helpers for overworld and server."""


def make_battle_units(army, effective_stats, display_name_fn=None, armor_bonus=0):
    """Convert an OverworldArmy's unit list into Battle-compatible dicts.

    Args:
        army: OverworldArmy instance
        effective_stats: dict of unit stats with upgrades/evolutions applied
        display_name_fn: optional callable(unit_name) -> display_name
        armor_bonus: additional armor to add to all units (e.g., for defending)
    """
    result = []
    for name, count in army.units:
        s = effective_stats[name]
        display_name = display_name_fn(name) if display_name_fn else name
        spec = {
            "name": name,
            "display_name": display_name,
            "max_hp": s["max_hp"],
            "damage": s["damage"],
            "range": s["range"],
            "count": count,
            "abilities": s.get("abilities", []),
            "armor": s.get("armor", 0) + armor_bonus,
            "speed": s.get("speed", 1.0),
            "actions": s.get("actions", 2),
        }
        result.append(spec)
    return result


def update_survivors(army, battle, battle_player):
    """Update an OverworldArmy's unit list to reflect battle survivors."""
    survivor_counts = {}
    for u in battle.units:
        if u.alive and u.player == battle_player:
            survivor_counts[u.name] = survivor_counts.get(u.name, 0) + 1
    army.units = [
        (name, survivor_counts.get(name, 0))
        for name, _ in army.units
        if survivor_counts.get(name, 0) > 0
    ]


def _revive_army(army, original_units):
    """Restore army units to their original counts."""
    army.units = list(original_units)


def resolve_battle(
    world,
    attacker,
    defender,
    battle,
    battle_winner,
    p1_survivors,
    p2_survivors,
    attacker_combat_rules=None,
    defender_combat_rules=None,
    original_attacker_units=None,
    original_defender_units=None,
):
    """Resolve a battle and apply overworld state changes.

    Args:
        world: Overworld instance
        attacker: attacking army (battle P1)
        defender: defending army (battle P2)
        battle: Battle instance
        battle_winner: 1 for attacker, 2 for defender, 0 for draw
        p1_survivors: count of surviving attacker units
        p2_survivors: count of surviving defender units
        attacker_combat_rules: optional dict with combat rules for attacker
        defender_combat_rules: optional dict with combat rules for defender
        original_attacker_units: list of (name, count) tuples before battle
        original_defender_units: list of (name, count) tuples before battle

    Returns a dict with winner, summary, gained_gold, and moved_to.
    """
    ow_p1, ow_p2 = attacker, defender
    if battle_winner == 1:
        ow_winner = ow_p1.player
    elif battle_winner == 2:
        ow_winner = ow_p2.player
    else:
        ow_winner = 0

    moved_to = None
    gained_gold = 0

    if battle_winner == 0:
        update_survivors(ow_p1, battle, 1)
        update_survivors(ow_p2, battle, 2)
        attacker.exhausted = True
    elif ow_winner == attacker.player:
        update_survivors(attacker, battle, 1)
        # Apply revive_on_win if attacker has the rule
        if (
            attacker_combat_rules
            and attacker_combat_rules.get("revive_on_win")
            and original_attacker_units
        ):
            _revive_army(attacker, original_attacker_units)
        if defender in world.armies:
            world.armies.remove(defender)
        world.move_army(attacker, defender.pos)
        moved_to = defender.pos
        attacker.exhausted = True
        gained_gold = world.collect_gold_at(defender.pos, attacker.player)
    else:
        update_survivors(defender, battle, 2)
        # Apply revive_on_win if defender has the rule
        if (
            defender_combat_rules
            and defender_combat_rules.get("revive_on_win")
            and original_defender_units
        ):
            _revive_army(defender, original_defender_units)
        if attacker in world.armies:
            world.armies.remove(attacker)

    summary = (
        f"P{ow_p1.player} vs P{ow_p2.player}: "
        f"P{ow_winner} wins ({p1_survivors} vs {p2_survivors} survivors)"
    )
    if battle_winner == 0:
        summary = f"P{ow_p1.player} vs P{ow_p2.player}: Draw"

    return {
        "winner": ow_winner,
        "summary": summary,
        "gained_gold": gained_gold,
        "moved_to": moved_to,
    }

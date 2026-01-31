"""Shared battle resolution helpers for overworld and server."""


def make_battle_units(army, effective_stats):
    """Convert an OverworldArmy's unit list into Battle-compatible dicts."""
    result = []
    for name, count in army.units:
        s = effective_stats[name]
        spec = {
            "name": name,
            "max_hp": s["max_hp"],
            "damage": s["damage"],
            "range": s["range"],
            "count": count,
            "abilities": s.get("abilities", []),
            "armor": s.get("armor", 0),
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


def resolve_battle(
    world,
    attacker,
    defender,
    battle,
    battle_winner,
    p1_survivors,
    p2_survivors,
):
    """Resolve a battle and apply overworld state changes.

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
        if defender in world.armies:
            world.armies.remove(defender)
        world.move_army(attacker, defender.pos)
        moved_to = defender.pos
        attacker.exhausted = True
        gained_gold = world.collect_gold_at(defender.pos, attacker.player)
    else:
        update_survivors(defender, battle, 2)
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

"""Shared game logic used by both server and client."""

from .constants import NEUTRAL_PLAYER
from .heroes import HEROES_BY_FACTION, apply_hero_evolutions_to_stats
from .upgrades import apply_upgrades_to_unit_stats


def get_effective_unit_stats(
    faction,
    upgrade_ids,
    all_unit_stats,
    base_unit_stats,
    factions,
    hero_evolutions=None,
):
    """Compute unit stats with upgrades and hero evolutions applied.

    Args:
        faction: faction name (or None).
        upgrade_ids: list of upgrade id strings.
        all_unit_stats: combined dict of all unit stats (units + heroes).
        base_unit_stats: dict of base (non-hero) unit stats keys.
        factions: dict mapping faction name to list of unit names.
        hero_evolutions: optional dict mapping base_hero -> list of evolved forms.

    Returns:
        A dict of unit stats with upgrades and evolutions applied.
    """
    if not faction:
        return all_unit_stats
    if not isinstance(upgrade_ids, list):
        upgrade_ids = [upgrade_ids]

    # Apply hero evolutions first
    stats = all_unit_stats
    if hero_evolutions:
        stats = apply_hero_evolutions_to_stats(stats, hero_evolutions)

    faction_units = factions.get(
        faction, list(base_unit_stats.keys())
    ) + HEROES_BY_FACTION.get(faction, [])
    return apply_upgrades_to_unit_stats(stats, upgrade_ids, faction_units)


def is_hidden_objective_guard(army, my_faction, get_objective_fn):
    """Check if an army is a hidden objective guard for the given faction.

    Args:
        army: an OverworldArmy.
        my_faction: the player's faction name.
        get_objective_fn: callable(pos) -> Objective or None.

    Returns:
        True if the army is a neutral guard on an objective belonging to another faction.
    """
    if army.player != NEUTRAL_PLAYER:
        return False
    objective = get_objective_fn(army.pos)
    if not objective:
        return False
    return objective.faction != my_faction

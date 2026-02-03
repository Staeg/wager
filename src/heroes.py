"""Hero definitions and helpers."""

from copy import deepcopy

from .ability_defs import ability

HERO_STATS = {
    # Custodians
    "Watcher": {
        "max_hp": 30,
        "damage": 8,
        "range": 1,
        "value": 20,
        "abilities": [
            ability("passive", "armor", value=3, amplify=False),
        ],
    },
    "Neophyte": {
        "max_hp": 12,
        "damage": 6,
        "range": 4,
        "value": 20,
        "abilities": [
            ability("harvest", "fortify", target="area", value=1),
        ],
    },
    "Accursed": {
        "max_hp": 16,
        "damage": 8,
        "range": 1,
        "value": 20,
        "abilities": [
            ability("onkill", "heal", target="self", value=8),
        ],
    },
    # Weavers
    "Enchantress": {
        "max_hp": 12,
        "damage": 3,
        "range": 5,
        "value": 20,
        "abilities": [
            ability("onhit", "freeze", target="random", value=3, amplify=False),
        ],
    },
    "Prodigy": {
        "max_hp": 8,
        "damage": 8,
        "range": 4,
        "value": 20,
        "abilities": [
            ability("onhit", "splash", target="target", value=3),
        ],
    },
    "Scholar": {
        "max_hp": 16,
        "damage": 3,
        "range": 5,
        "value": 20,
        "abilities": [
            ability("endturn", "strike", target="area", value=1),
        ],
    },
    # Artificers
    "Outcast": {
        "max_hp": 16,
        "damage": 6,
        "range": 2,
        "value": 20,
        "abilities": [
            ability("turnstart", "shadowstep", charge=4, amplify=False),
        ],
    },
    "Mercenary": {
        "max_hp": 32,
        "damage": 3,
        "range": 2,
        "value": 20,
        "abilities": [
            ability("endturn", "strike", target="random", value=3),
            ability("endturn", "strike", target="random", value=3),
        ],
    },
    "Tactician": {
        "max_hp": 10,
        "damage": 4,
        "range": 4,
        "value": 20,
        "abilities": [
            ability("passive", "boost", target="global", value=1, amplify=False),
        ],
    },
    # Purifiers
    "Maiden": {
        "max_hp": 8,
        "damage": 3,
        "range": 5,
        "value": 20,
        "abilities": [
            ability("lament", "strike", target="area", value=1, charge=2),
        ],
    },
    "Aspirant": {
        "max_hp": 32,
        "damage": 4,
        "range": 1,
        "value": 20,
        "abilities": [
            ability("onhit", "splash", target="target", value=4),
            ability("passive", "armor", value=1, amplify=False),
        ],
    },
    "Apostle": {
        "max_hp": 12,
        "damage": 2,
        "range": 3,
        "value": 20,
        "abilities": [
            ability(
                "passive", "lament_aura", target="self", value=1, range=1, aura="R"
            ),
        ],
    },
}

HEROES_BY_FACTION = {
    "Custodians": ["Watcher", "Neophyte", "Accursed"],
    "Weavers": ["Enchantress", "Prodigy", "Scholar"],
    "Artificers": ["Outcast", "Mercenary", "Tactician"],
    "Purifiers": ["Maiden", "Aspirant", "Apostle"],
}


def get_heroes_for_faction(faction_name):
    return list(HEROES_BY_FACTION.get(faction_name, []))


# Hero evolutions: maps base_hero -> evolved_form -> evolution data
# Each evolution includes stat_changes (deltas), new abilities, and display_name
HERO_EVOLUTIONS = {
    # Custodian tier-1 evolutions
    "Accursed": {
        "Wraith": {
            "display_name": "Wraith",
            "stat_changes": {"max_hp": 8},
            "abilities": [
                ability("passive", "block", value=2, amplify=False),
            ],
        },
        "Abolisher": {
            "display_name": "Abolisher",
            "stat_changes": {"damage": 4, "range": 1},
            "abilities": [
                ability("onhit", "silence", target="area", value=2, amplify=False),
            ],
        },
    },
    "Neophyte": {
        "Scribe": {
            "display_name": "Scribe",
            "stat_changes": {"range": 1},
            "abilities": [
                ability(
                    "passive",
                    "amplify",
                    target="global",
                    value=1,
                    aura="area",
                    amplify=False,
                ),
            ],
        },
        "Judge": {
            "display_name": "Judge",
            "stat_changes": {"damage": 4},
            "abilities": [
                ability(
                    "passive", "execute", target="area", value=2, aura=4, amplify=False
                ),
            ],
        },
    },
    "Watcher": {
        "Revenant": {
            "display_name": "Revenant",
            "stat_changes": {"damage": 4},
            "abilities": [
                ability("wounded", "strike", target="area", value=4, range=1),
            ],
        },
        "Guardian": {
            "display_name": "Guardian",
            "stat_changes": {"max_hp": 8},
            "abilities": [
                ability("wounded", "heal", target="area", value=2, range=4),
            ],
        },
    },
    # Custodian tier-2 evolutions (from tier-1 forms)
    "Wraith": {
        "Nightmare": {
            "display_name": "Nightmare",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("turnstart", "shadowstep", amplify=False),
            ],
        },
        "Reaper": {
            "display_name": "Reaper",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability("endturn", "strike", target="global", value=1),
            ],
        },
    },
    "Abolisher": {
        "Nightmare": {
            "display_name": "Nightmare",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("turnstart", "shadowstep", amplify=False),
            ],
        },
        "Reaper": {
            "display_name": "Reaper",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability("endturn", "strike", target="global", value=1),
            ],
        },
    },
    "Scribe": {
        "Necromancer": {
            "display_name": "Necromancer",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability("harvest", "summon", target="area", value=3, range=6, count=1),
            ],
        },
        "Lich": {
            "display_name": "Lich",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("onkill", "splash", target="target", value=14),
            ],
        },
    },
    "Judge": {
        "Necromancer": {
            "display_name": "Necromancer",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability("harvest", "summon", target="area", value=3, range=6, count=1),
            ],
        },
        "Lich": {
            "display_name": "Lich",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("onkill", "splash", target="target", value=14),
            ],
        },
    },
    "Revenant": {
        "Emperor": {
            "display_name": "Emperor",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("onkill", "ready", target="self", amplify=False),
            ],
        },
        "Regent": {
            "display_name": "Regent",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability(
                    "passive", "armor", target="global", value=3, aura=3, amplify=False
                ),
            ],
        },
    },
    "Guardian": {
        "Emperor": {
            "display_name": "Emperor",
            "stat_changes": {"damage": 8},
            "abilities": [
                ability("onkill", "ready", target="self", amplify=False),
            ],
        },
        "Regent": {
            "display_name": "Regent",
            "stat_changes": {"max_hp": 16},
            "abilities": [
                ability(
                    "passive", "armor", target="global", value=3, aura=3, amplify=False
                ),
            ],
        },
    },
}


def get_hero_evolution_path(base_hero, evolutions):
    """Get the evolution path list for a base hero.

    Args:
        base_hero: The original hero name (e.g., "Accursed")
        evolutions: Dict mapping base_hero -> list of evolved form names
                   e.g., {"Accursed": ["Wraith", "Nightmare"]}

    Returns:
        List of evolution names in order, or empty list if no evolutions.
    """
    return evolutions.get(base_hero, [])


def get_hero_display_name(base_hero, evolutions):
    """Get the display name for a hero based on its evolutions.

    Args:
        base_hero: The original hero name (e.g., "Accursed")
        evolutions: Dict mapping base_hero -> list of evolved form names

    Returns:
        The display name (final evolved form, or base_hero if no evolutions).
    """
    path = get_hero_evolution_path(base_hero, evolutions)
    if path:
        return path[-1]  # Return the final evolved form name
    return base_hero


def get_evolved_hero_stats(base_hero, evolutions, base_stats=None):
    """Compute stats for a hero with evolutions applied cumulatively.

    Args:
        base_hero: The original hero name (e.g., "Accursed")
        evolutions: Dict mapping base_hero -> list of evolved form names
        base_stats: Optional dict of base hero stats. If None, uses HERO_STATS.

    Returns:
        Dict of computed stats with all evolutions applied.
    """
    if base_stats is None:
        base_stats = HERO_STATS

    if base_hero not in base_stats:
        return None

    stats = deepcopy(base_stats[base_hero])
    path = get_hero_evolution_path(base_hero, evolutions)

    # Track the current form to look up evolutions
    current_form = base_hero

    for evolved_form in path:
        evolution_data = HERO_EVOLUTIONS.get(current_form, {}).get(evolved_form)
        if not evolution_data:
            break

        # Apply stat changes (additive)
        for stat, delta in evolution_data.get("stat_changes", {}).items():
            stats[stat] = stats.get(stat, 0) + delta

        # Add new abilities
        for new_ability in evolution_data.get("abilities", []):
            stats.setdefault("abilities", []).append(new_ability)

        current_form = evolved_form

    return stats


def apply_hero_evolutions_to_stats(all_stats, hero_evolutions):
    """Apply hero evolutions to a stats dict, returning modified copy.

    Args:
        all_stats: Dict of all unit stats (units + heroes)
        hero_evolutions: Dict mapping base_hero -> list of evolved form names

    Returns:
        New stats dict with hero evolutions applied.
    """
    if not hero_evolutions:
        return all_stats

    result = deepcopy(all_stats)

    for base_hero, evolution_path in hero_evolutions.items():
        if base_hero not in result:
            continue

        evolved_stats = get_evolved_hero_stats(base_hero, hero_evolutions, all_stats)
        if evolved_stats:
            result[base_hero] = evolved_stats

    return result

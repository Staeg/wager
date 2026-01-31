"""Hero definitions and helpers."""

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
            ability("harvest", "fortify", target="area", value=1, range=4),
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
            ability("periodic", "strike", target="area", value=1, range=5),
        ],
    },
    # Artificers
    "Outcast": {
        "max_hp": 16,
        "damage": 6,
        "range": 2,
        "value": 20,
        "abilities": [
            ability("periodic", "shadowstep", charge=4, amplify=False),
        ],
    },
    "Mercenary": {
        "max_hp": 32,
        "damage": 3,
        "range": 2,
        "value": 20,
        "abilities": [
            ability("periodic", "strike", target="random", value=3, range=2),
            ability("periodic", "strike", target="random", value=3, range=2),
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
            ability("lament", "strike", target="area", value=1, range=5, charge=2),
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
            ability("passive", "lament_aura", target="self", value=1, range=1, aura=3),
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

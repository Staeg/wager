"""Hero definitions and helpers."""

HERO_STATS = {
    # Custodians
    "Watcher":   {"max_hp": 30, "damage": 8, "range": 1, "value": 20, "armor": 3},
    "Neophyte":  {"max_hp": 12, "damage": 6, "range": 4, "value": 20, "harvest": 1, "harvest_range": 4},
    "Accursed":  {"max_hp": 16, "damage": 8, "range": 1, "value": 20, "lifesteal": 4},
    # Weavers
    "Enchantress": {"max_hp": 12, "damage": 3, "range": 5, "value": 20, "freeze": 3},
    "Prodigy":     {"max_hp": 8, "damage": 8, "range": 4, "value": 20, "splash": 3},
    "Scholar":     {"max_hp": 16, "damage": 3, "range": 5, "value": 20,
                    "bombardment": 1, "bombardment_range": 5, "bombardment_all": True,
                    "bombardment_requires_attack": True},
    # Artificers
    "Outcast":    {"max_hp": 16, "damage": 6, "range": 2, "value": 20, "shadowstep_charge": 4},
    "Mercenary":  {"max_hp": 32, "damage": 3, "range": 2, "value": 20,
                   "followup_damage": 3, "followup_range": 2, "followup_count": 2},
    "Tactician":  {"max_hp": 10, "damage": 4, "range": 4, "value": 20, "global_boost": 1},
    # Purifiers
    "Maiden":    {"max_hp": 8, "damage": 3, "range": 5, "value": 20,
                  "lament_threshold": 2, "lament_range": 5, "lament_damage": 1},
    "Aspirant":  {"max_hp": 32, "damage": 4, "range": 1, "value": 20, "splash": 4, "armor": 1},
    "Apostle":   {"max_hp": 12, "damage": 2, "range": 3, "value": 20,
                  "aura_vengeance": 1, "aura_vengeance_range": 3},
}

HEROES_BY_FACTION = {
    "Custodians": ["Watcher", "Neophyte", "Accursed"],
    "Weavers": ["Enchantress", "Prodigy", "Scholar"],
    "Artificers": ["Outcast", "Mercenary", "Tactician"],
    "Purifiers": ["Maiden", "Aspirant", "Apostle"],
}


def get_heroes_for_faction(faction_name):
    return list(HEROES_BY_FACTION.get(faction_name, []))

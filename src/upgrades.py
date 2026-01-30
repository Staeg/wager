"""Faction upgrades and helpers for applying them to unit stats."""

from copy import deepcopy


UPGRADE_DEFS = {
    "Custodians": [
        {
            "id": "custodian_frenzy",
            "name": "Frenzy",
            "tier": 1,
            "description": "Pages gain Ramp 1.",
            "effects": [
                {"type": "add_ability", "unit": "Page", "ability": "ramp", "value": 1},
            ],
        },
        {
            "id": "custodian_sweeping_sands",
            "name": "Sweeping Sands",
            "tier": 2,
            "description": "Sunder abilities hit all enemies in range instead of randomly.",
            "effects": [
                {"type": "flag_if_ability", "ability": "sunder", "flag": "sunder_all"},
            ],
        },
        {
            "id": "custodian_trespassers",
            "name": "Trespassers",
            "tier": 3,
            "description": "Stewards gain Rage 1.",
            "effects": [
                {"type": "add_ability", "unit": "Steward", "ability": "rage", "value": 1},
            ],
        },
    ],
    "Weavers": [
        {
            "id": "weaver_skirmish_tactics",
            "name": "Skirmish Tactics",
            "tier": 1,
            "description": "Apprentices gain the Retreat ability.",
            "effects": [
                {"type": "add_ability", "unit": "Apprentice", "ability": "retreat", "value": 1},
            ],
        },
        {
            "id": "weaver_arcane_reach",
            "name": "Arcane Reach",
            "tier": 2,
            "description": "Conduit Amplify aura range becomes 2.",
            "effects": [
                {"type": "set_ability", "unit": "Conduit", "ability": "amplify_range", "value": 2},
            ],
        },
        {
            "id": "weaver_farcasting",
            "name": "Farcasting",
            "tier": 3,
            "description": "Apprentices +1 range, Conduits/Seekers +2 range, Savants +3 range.",
            "effects": [
                {"type": "add_stat", "unit": "Apprentice", "stat": "range", "delta": 1},
                {"type": "add_stat", "unit": "Conduit", "stat": "range", "delta": 2},
                {"type": "add_stat", "unit": "Seeker", "stat": "range", "delta": 2},
                {"type": "add_stat", "unit": "Savant", "stat": "range", "delta": 3},
            ],
        },
    ],
    "Artificers": [
        {
            "id": "artificer_corrosion",
            "name": "Corrosion",
            "tier": 1,
            "description": "Tincans gain Sunder 1.",
            "effects": [
                {"type": "add_ability", "unit": "Tincan", "ability": "sunder", "value": 1},
            ],
        },
        {
            "id": "artificer_armor_kits",
            "name": "Armor Kits",
            "tier": 2,
            "description": "Kitboys gain Aura 1 - Armor 1.",
            "effects": [
                {"type": "set_ability", "unit": "Kitboy", "ability": "aura_armor", "value": 1},
                {"type": "set_ability", "unit": "Kitboy", "ability": "aura_armor_range", "value": 1},
            ],
        },
        {
            "id": "artificer_carpet_bombing",
            "name": "Carpet Bombing",
            "tier": 3,
            "description": "Bombardment becomes Charge 2 and hits all enemies in range after attacking.",
            "effects": [
                {
                    "type": "set_for_ability",
                    "ability": "bombardment",
                    "set": {
                        "bombardment_charge": 2,
                        "bombardment_all": True,
                        "bombardment_requires_attack": True,
                    },
                },
            ],
        },
    ],
    "Purifiers": [
        {
            "id": "purifier_alacrity",
            "name": "Alacrity",
            "tier": 1,
            "description": "Blades spawn adjacent to the highest-health ally in range and are ready.",
            "effects": [
                {"type": "set_flag", "unit": "Herald", "flag": "summon_target_highest", "value": True},
                {"type": "set_flag", "unit": "Herald", "flag": "summon_ready", "value": True},
            ],
        },
        {
            "id": "purifier_salvation",
            "name": "Salvation",
            "tier": 2,
            "description": "Heal abilities target all allies in range instead of randomly.",
            "effects": [
                {"type": "flag_if_ability", "ability": "heal", "flag": "heal_all"},
            ],
        },
        {
            "id": "purifier_bladestorm",
            "name": "Bladestorm",
            "tier": 3,
            "description": "Summon Blades every turn instead of every 3 turns.",
            "effects": [
                {"type": "set_ability", "unit": "Herald", "ability": "charge", "value": 1},
            ],
        },
    ],
}

UPGRADE_BY_ID = {
    upgrade["id"]: upgrade
    for upgrades in UPGRADE_DEFS.values()
    for upgrade in upgrades
}


def get_upgrades_for_faction(faction_name):
    return list(UPGRADE_DEFS.get(faction_name, []))


def get_upgrade_by_id(upgrade_id):
    return UPGRADE_BY_ID.get(upgrade_id)


def apply_upgrade_to_unit_stats(base_stats, upgrade_def, faction_units):
    """Return a deep-copied unit stats dict with the upgrade applied."""
    stats = deepcopy(base_stats)
    if not upgrade_def:
        return stats

    for effect in upgrade_def.get("effects", []):
        etype = effect.get("type")
        if etype == "add_ability":
            unit = effect["unit"]
            ability = effect["ability"]
            value = effect.get("value", 0)
            stats[unit][ability] = stats[unit].get(ability, 0) + value
        elif etype == "set_ability":
            unit = effect["unit"]
            ability = effect["ability"]
            stats[unit][ability] = effect.get("value")
        elif etype == "add_stat":
            unit = effect["unit"]
            stat = effect["stat"]
            stats[unit][stat] = stats[unit].get(stat, 0) + effect.get("delta", 0)
        elif etype == "set_flag":
            unit = effect["unit"]
            stats[unit][effect["flag"]] = effect.get("value", True)
        elif etype == "flag_if_ability":
            ability = effect["ability"]
            flag = effect["flag"]
            for unit in faction_units:
                if stats[unit].get(ability, 0):
                    stats[unit][flag] = True
        elif etype == "set_for_ability":
            ability = effect["ability"]
            for unit in faction_units:
                if stats[unit].get(ability, 0):
                    for key, value in effect.get("set", {}).items():
                        stats[unit][key] = value

    return stats

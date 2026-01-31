"""Faction upgrades and helpers for applying them to unit stats."""

from copy import deepcopy
from .ability_defs import ability


UPGRADE_DEFS = {
    "Custodians": [
        {
            "id": "custodian_frenzy",
            "name": "Frenzy",
            "tier": 1,
            "description": "Pages gain Onhit Self Ramp 1.",
            "effects": [
                {"type": "append_ability", "unit": "Page",
                 "ability": ability("onhit", "ramp", target="self", value=1)},
            ],
        },
        {
            "id": "custodian_sweeping_sands",
            "name": "Sweeping Sands",
            "tier": 2,
            "description": "Random Sunder abilities become Area Sunder.",
            "effects": [
                {"type": "modify_abilities",
                 "match": {"effect": "sunder", "target": "random"},
                 "set": {"target": "area"}},
            ],
        },
        {
            "id": "custodian_trespassers",
            "name": "Trespassers",
            "tier": 3,
            "description": "Stewards gain Wounded Self Ramp 1.",
            "effects": [
                {"type": "append_ability", "unit": "Steward",
                 "ability": ability("wounded", "ramp", target="self", value=1)},
            ],
        },
    ],
    "Weavers": [
        {
            "id": "weaver_skirmish_tactics",
            "name": "Skirmish Tactics",
            "tier": 1,
            "description": "Apprentices gain Onhit Retreat 1.",
            "effects": [
                {"type": "append_ability", "unit": "Apprentice",
                 "ability": ability("onhit", "retreat", target="self", value=1, amplify=False)},
            ],
        },
        {
            "id": "weaver_arcane_reach",
            "name": "Arcane Reach",
            "tier": 2,
            "description": "Conduit Amplify aura range becomes 2.",
            "effects": [
                {"type": "modify_abilities",
                 "unit": "Conduit",
                 "match": {"effect": "amplify"},
                 "set": {"aura": 2}},
            ],
        },
        {
            "id": "weaver_farcasting",
            "name": "Farcasting",
            "tier": 3,
            "description": "All units gain +1 range.",
            "effects": [
                {"type": "add_stat", "unit": "__all__", "stat": "range", "delta": 1},
            ],
        },
    ],
    "Artificers": [
        {
            "id": "artificer_corrosion",
            "name": "Corrosion",
            "tier": 1,
            "description": "Tincans gain Onhit Target Sunder 1.",
            "effects": [
                {"type": "append_ability", "unit": "Tincan",
                 "ability": ability("onhit", "sunder", target="target", value=1, amplify=False)},
            ],
        },
        {
            "id": "artificer_armor_kits",
            "name": "Armor Kits",
            "tier": 2,
            "description": "Kitboys gain Passive Aura 1 - Armor 1.",
            "effects": [
                {"type": "append_ability", "unit": "Kitboy",
                 "ability": ability("passive", "armor", value=1, aura=1, amplify=False)},
            ],
        },
        {
            "id": "artificer_carpet_bombing",
            "name": "Carpet Bombing",
            "tier": 3,
            "description": "Random Followup abilities become Charge 2 Area Followup abilities.",
            "effects": [
                {
                    "type": "modify_abilities",
                    "match": {"effect": "strike", "target": "random", "trigger": "periodic"},
                    "set": {"target": "area", "charge": 2},
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
                {"type": "modify_abilities",
                 "unit": "Herald",
                 "match": {"effect": "summon"},
                 "set": {"summon_target": "highest", "summon_ready": True}},
            ],
        },
        {
            "id": "purifier_salvation",
            "name": "Salvation",
            "tier": 2,
            "description": "Random Heal abilities become Area Heal abilities.",
            "effects": [
                {"type": "modify_abilities",
                 "match": {"effect": "heal", "target": "random"},
                 "set": {"target": "area"}},
            ],
        },
        {
            "id": "purifier_bladestorm",
            "name": "Bladestorm",
            "tier": 3,
            "description": "Summon Blades every turn instead of every 3 turns.",
            "effects": [
                {"type": "modify_abilities",
                 "unit": "Herald",
                 "match": {"effect": "summon"},
                 "set": {"charge": None}},
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

    def _match(ab, match):
        for k, v in match.items():
            if ab.get(k) != v:
                return False
        return True

    for effect in upgrade_def.get("effects", []):
        etype = effect.get("type")
        if etype == "append_ability":
            unit = effect["unit"]
            stats[unit].setdefault("abilities", []).append(effect["ability"])
        elif etype == "modify_abilities":
            match = effect.get("match", {})
            for unit in faction_units:
                if effect.get("unit") and unit != effect["unit"]:
                    continue
                for ab in stats[unit].get("abilities", []):
                    if _match(ab, match):
                        for key, value in effect.get("set", {}).items():
                            if value is None and key in ab:
                                del ab[key]
                            else:
                                ab[key] = value
        elif etype == "add_stat":
            unit = effect["unit"]
            if unit == "__all__":
                for uname in faction_units:
                    stat = effect["stat"]
                    stats[uname][stat] = stats[uname].get(stat, 0) + effect.get("delta", 0)
            else:
                stat = effect["stat"]
                stats[unit][stat] = stats[unit].get(stat, 0) + effect.get("delta", 0)

    return stats

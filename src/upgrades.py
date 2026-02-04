"""Faction upgrades and helpers for applying them to unit stats."""

from copy import deepcopy
from .ability_defs import ability
from .combat_gui import format_ability
from .quests import QUEST_UPGRADE_DEFS


UPGRADE_DEFS = {
    "Custodians": [
        {
            "id": "custodian_frenzy",
            "name": "Frenzy",
            "tier": 1,
            "description": "Pages gain Onhit Self Ramp 1.",
            "effects": [
                {
                    "type": "append_ability",
                    "unit": "Page",
                    "ability": ability("onhit", "ramp", target="self", value=1),
                },
            ],
        },
        {
            "id": "custodian_sweeping_sands",
            "name": "Sweeping Sands",
            "tier": 2,
            "description": "Random Sunder abilities become Area Sunder.",
            "effects": [
                {
                    "type": "modify_abilities",
                    "match": {"effect": "sunder", "target": "random"},
                    "set": {"target": "area"},
                },
            ],
        },
        {
            "id": "custodian_trespassers",
            "name": "Trespassers",
            "tier": 3,
            "description": "Stewards gain Wounded Self Ramp 1.",
            "effects": [
                {
                    "type": "append_ability",
                    "unit": "Steward",
                    "ability": ability("wounded", "ramp", target="self", value=1),
                },
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
                {
                    "type": "append_ability",
                    "unit": "Apprentice",
                    "ability": ability(
                        "onhit", "retreat", target="self", value=1
                    ),
                },
            ],
        },
        {
            "id": "weaver_deep_freeze",
            "name": "Deep Freeze",
            "tier": 2,
            "description": "Whenever an enemy is frozen, deal 5 damage to them.",
            "effects": [
                {"type": "combat_rule", "rule": "deep_freeze", "value": 5},
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
                {
                    "type": "append_ability",
                    "unit": "Tincan",
                    "ability": ability(
                        "onhit", "sunder", target="target", value=1
                    ),
                },
            ],
        },
        {
            "id": "artificer_armor_kits",
            "name": "Armor Kits",
            "tier": 2,
            "description": "Kitboys gain Passive Aura 1 - Armor 1.",
            "effects": [
                {
                    "type": "append_ability",
                    "unit": "Kitboy",
                    "ability": ability(
                        "passive", "armor", value=1, aura=1
                    ),
                },
            ],
        },
        {
            "id": "artificer_carpet_bombing",
            "name": "Carpet Bombing",
            "tier": 3,
            "description": "Random Strike abilities become Charge 2 Area Strike abilities.",
            "effects": [
                {
                    "type": "modify_abilities",
                    "match": {
                        "effect": "strike",
                        "target": "random",
                        "trigger": "endturn",
                    },
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
                {
                    "type": "modify_abilities",
                    "unit": "Herald",
                    "match": {"effect": "summon"},
                    "set": {"summon_target": "highest", "summon_ready": True},
                },
            ],
        },
        {
            "id": "purifier_salvation",
            "name": "Salvation",
            "tier": 2,
            "description": "Random Heal abilities become Area Heal abilities.",
            "effects": [
                {
                    "type": "modify_abilities",
                    "match": {"effect": "heal", "target": "random"},
                    "set": {"target": "area"},
                },
            ],
        },
        {
            "id": "purifier_bladestorm",
            "name": "Bladestorm",
            "tier": 3,
            "description": "Summon Blades every turn instead of every 3 turns.",
            "effects": [
                {
                    "type": "modify_abilities",
                    "unit": "Herald",
                    "match": {"effect": "summon"},
                    "set": {"charge": None},
                },
            ],
        },
    ],
}

UPGRADE_BY_ID = {
    upgrade["id"]: upgrade for upgrades in UPGRADE_DEFS.values() for upgrade in upgrades
}
# Merge in quest-triggered upgrades
UPGRADE_BY_ID.update(QUEST_UPGRADE_DEFS)


def get_upgrades_for_faction(faction_name):
    return list(UPGRADE_DEFS.get(faction_name, []))


def get_upgrade_by_id(upgrade_id):
    return UPGRADE_BY_ID.get(upgrade_id)


def _apply_upgrade_effects(stats, upgrade_def, faction_units):
    if not upgrade_def:
        return

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
                    stats[uname][stat] = stats[uname].get(stat, 0) + effect.get(
                        "delta", 0
                    )
            else:
                stat = effect["stat"]
                stats[unit][stat] = stats[unit].get(stat, 0) + effect.get("delta", 0)


def apply_upgrade_to_unit_stats(base_stats, upgrade_def, faction_units):
    """Return a deep-copied unit stats dict with the upgrade applied."""
    stats = deepcopy(base_stats)
    _apply_upgrade_effects(stats, upgrade_def, faction_units)
    return stats


def apply_upgrades_to_unit_stats(base_stats, upgrade_ids, faction_units):
    """Return a deep-copied unit stats dict with multiple upgrades applied."""
    stats = deepcopy(base_stats)
    for upgrade_id in upgrade_ids or []:
        _apply_upgrade_effects(stats, get_upgrade_by_id(upgrade_id), faction_units)
    return stats


def get_combat_rules_from_upgrades(upgrade_ids):
    """Extract combat rules from upgrade effects.

    Returns a dict of rule_name -> value for any combat_rule effects.
    """
    rules = {}
    for upgrade_id in upgrade_ids or []:
        upgrade_def = get_upgrade_by_id(upgrade_id)
        if not upgrade_def:
            continue
        for effect in upgrade_def.get("effects", []):
            if effect.get("type") == "combat_rule":
                rules[effect["rule"]] = effect["value"]
    return rules


def _find_matching_ability(base_stats, faction_units, match):
    if not base_stats or not faction_units or not match:
        return None
    for unit in faction_units:
        stats = base_stats.get(unit, {})
        for ability_def in stats.get("abilities", []):
            if all(ability_def.get(k) == v for k, v in match.items()):
                return ability_def
    return None


def upgrade_effect_keywords(upgrade_def, base_stats=None, faction_units=None):
    keywords = []
    for effect in upgrade_def.get("effects", []):
        etype = effect.get("type")
        if etype == "append_ability":
            text = format_ability(effect["ability"], include_self_target=True)
            if text:
                keywords.append((text, effect["ability"]))
        elif etype == "modify_abilities":
            match = dict(effect.get("match", {}))
            sample = _find_matching_ability(base_stats, faction_units, match)
            base_ability = sample or match
            base = format_ability(base_ability, include_self_target=True)
            if base:
                keywords.append((base, base_ability))
            merged = dict(base_ability)
            for key, value in effect.get("set", {}).items():
                if value is None:
                    merged.pop(key, None)
                else:
                    merged[key] = value
            updated = format_ability(merged, include_self_target=True)
            if updated and updated != base:
                keywords.append((updated, merged))
    return keywords


def upgrade_effect_summaries(upgrade_def, base_stats=None, faction_units=None):
    summaries = []
    for effect in upgrade_def.get("effects", []):
        etype = effect.get("type")
        unit = effect.get("unit")
        unit_prefix = ""
        if unit and unit != "__all__":
            unit_prefix = f"{unit} "
        elif unit == "__all__":
            unit_prefix = "All units "

        if etype == "append_ability":
            ability_text = format_ability(effect["ability"], include_self_target=True)
            if ability_text:
                summaries.append(f"{unit_prefix}gain {ability_text}.")
        elif etype == "add_stat":
            stat = effect.get("stat")
            delta = effect.get("delta", 0)
            sign = "+" if delta >= 0 else ""
            if stat:
                summaries.append(f"{unit_prefix}gain {sign}{delta} {stat}.")
        elif etype == "modify_abilities":
            match = dict(effect.get("match", {}))
            sample = _find_matching_ability(base_stats, faction_units, match)
            base_ability = sample or match
            base = format_ability(base_ability, include_self_target=True)
            merged = dict(base_ability)
            for key, value in effect.get("set", {}).items():
                if value is None:
                    merged.pop(key, None)
                else:
                    merged[key] = value
            updated = format_ability(merged, include_self_target=True)
            if base and updated and base != updated:
                if unit_prefix:
                    summaries.append(f"{unit_prefix}{base} abilities become {updated}.")
                else:
                    summaries.append(f"{base} abilities become {updated}.")
            elif updated:
                if unit_prefix:
                    summaries.append(f"{unit_prefix}abilities become {updated}.")
                else:
                    summaries.append(f"Abilities become {updated}.")
    return summaries

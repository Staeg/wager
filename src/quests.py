"""Quest definitions and helpers for the Custodian faction."""

from .ability_defs import ability
from .hex import hex_distance


# Quest-triggered upgrades that can't be obtained via objectives
QUEST_UPGRADE_DEFS = {
    "what_remains_of_the_mighty": {
        "id": "what_remains_of_the_mighty",
        "name": "What remains of the mighty",
        "description": "Librarian Sunder becomes 3. Gatekeeper Undying aura becomes 3.",
        "effects": [
            {
                "type": "modify_abilities",
                "unit": "Librarian",
                "match": {"effect": "sunder"},
                "set": {"value": 3},
            },
            {
                "type": "modify_abilities",
                "unit": "Gatekeeper",
                "match": {"effect": "undying"},
                "set": {"aura": 3},
            },
        ],
    },
    "tide_of_bones": {
        "id": "tide_of_bones",
        "name": "Tide of bones",
        "description": "All units gain +0.4 speed.",
        "effects": [
            {"type": "add_stat", "unit": "__all__", "stat": "speed", "delta": 0.4},
        ],
    },
    "soul_eaters": {
        "id": "soul_eaters",
        "name": "Soul eaters",
        "description": "All units gain Harvest 3 - Self Heal 2.",
        "effects": [
            {
                "type": "append_ability",
                "unit": "__all__",
                "ability": ability(
                    "harvest", "heal", target="self", value=2, range=3
                ),
            },
        ],
    },
    "lightbringers": {
        "id": "lightbringers",
        "name": "Lightbringers",
        "description": "All units gain Periodic Area Strike 1.",
        "effects": [
            {
                "type": "append_ability",
                "unit": "__all__",
                "ability": ability(
                    "endturn", "strike", target="area", value=1, range="R"
                ),
            },
        ],
    },
    "pages_freeze": {
        "id": "pages_freeze",
        "name": "Gunpowder tactics",
        "description": "Pages gain Onhit Freeze 1/1 and +0.4 speed.",
        "effects": [
            {
                "type": "append_ability",
                "unit": "Page",
                "ability": ability(
                    "onhit", "freeze", target="random", value=1, range=1
                ),
            },
            {"type": "add_stat", "unit": "Page", "stat": "speed", "delta": 0.4},
        ],
    },
}

CUSTODIAN_QUESTS = {
    "curiosity_1": {
        "name": "The First Archive",
        "questline": "Curiosity",
        "tier": 1,
        "requires": [],
        "intro": (
            "Records found in a dusty corner reveal that these fortifications we awoke in "
            "are the second, third and fourth greatest citadels our creators entombed us in. "
            "What of the mightiest of our kind? We must find out what happened."
        ),
        "objective": "Bring the Accursed and 100 gold.",
        "completion_text": (
            "They did not fail to awaken as we thought, though they never stepped outside "
            "the boundaries of the Archive. Inside we found signs of recent movement and "
            "tunnels leading ever deeper underground and some tomes written in an unknown language."
        ),
        "required_hero": ["Accursed"],
        "gold_cost": 100,
        "location_rule": "between_bases",
        "decisions": [
            {
                "label": "Delve",
                "description": "We must investigate.",
                "hero_evolution": {"from": "Accursed", "to": "Wraith"},
                "hero_outcome": (
                    "Accursed turns into Wraith, gains +8 HP and the "
                    '"Passive Block 2" ability, which reduces the first 2 '
                    "instances of damage taken on any turn to 0."
                ),
                "other_outcome": (
                    'Gain the "What remains of the mighty" upgrade, which turns '
                    "the Librarian Sunder 1 ability into Sunder 3 and the "
                    "Gatekeeper Aura 2 - Undying 2 into Aura 3 - Undying 2."
                ),
                "outcome_text": "Bodies found.",
                "effects": [
                    {"type": "grant_upgrade", "upgrade_id": "what_remains_of_the_mighty"},
                ],
            },
            {
                "label": "Seal",
                "description": "Collapse the passages. Establish a citadel.",
                "hero_evolution": {"from": "Accursed", "to": "Abolisher"},
                "hero_outcome": (
                    "Accursed turns into Abolisher; gains +4 DMG, +1 Range and "
                    'the "Onhit Area 2 Silence" ability, which removes all '
                    "abilities from enemies within 2 hexes after attacking."
                ),
                "other_outcome": (
                    "Turns the hex of the quest into a Base that gives 20 income."
                ),
                "outcome_text": "We'll never know.",
                "effects": [
                    {"type": "create_base", "income": 20},
                ],
            },
        ],
    },
    "curiosity_2": {
        "name": "Tracing the trail",
        "questline": "Curiosity",
        "tier": 2,
        "requires": ["curiosity_1", "intent_1"],
        "intro": "Same magic found in the First Archive emanating.",
        "objective": "Bring Scribe/Judge and take control of the base.",
        "completion_text": "Ton of tomes here.",
        "required_hero": ["Scribe", "Judge"],
        "gold_cost": 0,
        "location_rule": "enemy_base_weaver",
        "capture_base": True,
        "decisions": [
            {
                "label": "Embrace",
                "description": "Read them.",
                "hero_evolution": {"from": ["Scribe", "Judge"], "to": "Necromancer"},
                "hero_outcome": (
                    "Scribe/Judge turns into Necromancer; gains +16 HP and the "
                    '"Harvest 3 - Area 6 Summon Servant" ability, which summons '
                    "a Servant for every 3 enemies that die within 6 range."
                ),
                "other_outcome": (
                    "Destroy the biggest Weaver army if one exists, then add "
                    "12 Servants and 4 Gatekeepers to the Necromancer's army."
                ),
                "outcome_text": (
                    "Forbidden knowledge found. No global consequences\u2026 yet."
                ),
                "effects": [
                    {"type": "destroy_largest_army", "faction": "Weavers"},
                    {
                        "type": "add_units",
                        "units": [("Servant", 12), ("Gatekeeper", 4)],
                    },
                ],
            },
            {
                "label": "Spurn",
                "description": "Torch them.",
                "hero_evolution": {"from": ["Scribe", "Judge"], "to": "Lich"},
                "hero_outcome": (
                    "Scribe/Judge turns into Lich; gains +8 DMG and the "
                    '"Onkill Target Splash 14" ability, which deals 14 damage '
                    "to all enemies adjacent to whoever this unit kills."
                ),
                "other_outcome": (
                    'Destroy the base. Gain the "Lightbringers" upgrade, which '
                    'gives all your units "Periodic Area [Range] Strike 1".'
                ),
                "outcome_text": "Gone for good.",
                "effects": [
                    {"type": "destroy_base"},
                    {"type": "grant_upgrade", "upgrade_id": "lightbringers"},
                ],
            },
        ],
    },
    "intent_1": {
        "name": "Seeking scope",
        "questline": "Intent",
        "tier": 1,
        "requires": [],
        "intro": (
            "What is our purpose, given that we do not even remember all our "
            "creators wanted of us?"
        ),
        "objective": "Bring the Neophyte and do not move him for 2 turns.",
        "completion_text": "",
        "required_hero": ["Neophyte"],
        "gold_cost": 0,
        "location_rule": "center",
        "wait_turns": 2,
        "decisions": [
            {
                "label": "Hypothesize",
                "description": "Extrapolate in reasonable directions.",
                "hero_evolution": {"from": "Neophyte", "to": "Scribe"},
                "hero_outcome": (
                    "Neophyte turns into Scribe; gains +1 Range and the "
                    '"Endturn Global Heal 1" ability, which heals all allied '
                    "units by 1 at the end of its turn."
                ),
                "other_outcome": "",
                "outcome_text": "Can't go wrong with more knowledge.",
                "effects": [],
            },
            {
                "label": "Focus",
                "description": "Do what you're certain you're supposed to.",
                "hero_evolution": {"from": "Neophyte", "to": "Judge"},
                "hero_outcome": (
                    "Neophyte turns into Judge; gains +4 DMG and the "
                    '"Passive Aura 4 - Execute 2" ability, which causes this '
                    "unit to kill any enemy within 4 range who falls to 2 "
                    "health or lower but doesn't die."
                ),
                "other_outcome": "",
                "outcome_text": "Can't go wrong with more power.",
                "effects": [],
            },
        ],
    },
    "intent_2": {
        "name": "Our role",
        "questline": "Intent",
        "tier": 2,
        "requires": ["intent_1", "doctrine_1"],
        "intro": (
            "We must make a decision. What ought we be? The Purifiers are "
            "strong of conviction."
        ),
        "objective": "Bring Revenant/Guardian and take control of the base.",
        "completion_text": "Their ways, unfortunately, will not work for us. Instead\u2026",
        "required_hero": ["Revenant", "Guardian"],
        "gold_cost": 0,
        "location_rule": "enemy_base_purifier",
        "capture_base": True,
        "decisions": [
            {
                "label": "Dominion",
                "description": "We must rule.",
                "hero_evolution": {"from": ["Revenant", "Guardian"], "to": "Emperor"},
                "hero_outcome": (
                    "Revenant/Guardian turns into Emperor, gains +8 DMG and "
                    'the "Onkill Self Ready" ability, which allows it to '
                    "become readied again after killing a unit."
                ),
                "other_outcome": (
                    'Gain the "Soul eaters" upgrade, which grants all units '
                    'the "Harvest 3 - Self Heal 2" ability, which lets them '
                    "heal 1 health whenever an enemy within 3 hexes dies."
                ),
                "outcome_text": "They are gone.",
                "effects": [
                    {"type": "grant_upgrade", "upgrade_id": "soul_eaters"},
                ],
            },
            {
                "label": "Protectorate",
                "description": "We must bide our time.",
                "hero_evolution": {"from": ["Revenant", "Guardian"], "to": "Regent"},
                "hero_outcome": (
                    "Revenant/Guardian turns into Regent, gains +16 HP and "
                    'the "Global Aura 3 - Armor 3" ability, which increases '
                    "the Armor of all allies in combat by 3."
                ),
                "other_outcome": (
                    'Gain the "Until the end" upgrade, which increases your '
                    "income by 3 every turn."
                ),
                "outcome_text": "They will return.",
                "effects": [
                    {"type": "income_bonus", "delta": 3},
                ],
            },
        ],
    },
    "doctrine_1": {
        "name": "Border control",
        "questline": "Doctrine",
        "tier": 1,
        "requires": [],
        "intro": "Clear the surroundings.",
        "objective": "Bring Watcher after clearing all gold piles within 5 hexes of that base.",
        "completion_text": "Now that the local area is safe, what ought we do next?",
        "required_hero": ["Watcher"],
        "gold_cost": 0,
        "location_rule": "own_base",
        "clear_gold_radius": 5,
        "decisions": [
            {
                "label": "Hunger",
                "description": "Spew forth.",
                "hero_evolution": {"from": "Watcher", "to": "Revenant"},
                "hero_outcome": (
                    "Watcher turns into Revenant; gains +4 Damage and the "
                    '"Wounded Area 1 Strike 4" ability, which lets him deal '
                    "4 damage to all enemies within 1 range whenever he takes damage."
                ),
                "other_outcome": (
                    'Gain the "Tide of bones" upgrade, which increases the '
                    "Speed of all friendly units by 0.4."
                ),
                "outcome_text": "Wash over them.",
                "effects": [
                    {"type": "grant_upgrade", "upgrade_id": "tide_of_bones"},
                ],
            },
            {
                "label": "Entrench",
                "description": "Stay protected.",
                "hero_evolution": {"from": "Watcher", "to": "Guardian"},
                "hero_outcome": (
                    "Watcher turns into Guardian; gains +8 HP and the "
                    '"Wounded Area 4 Heal 2" ability, which lets him heal '
                    "2 health to all allies within 4 range whenever he takes damage."
                ),
                "other_outcome": (
                    'Gain the "Mobile fortifications" upgrade, which increases '
                    "the Armor of all friendly units by 1 when defending."
                ),
                "outcome_text": "Defense, though not amazing as offense, is still good.",
                "effects": [
                    {"type": "combat_rule", "rule": "defending_armor_bonus", "value": 1},
                ],
            },
        ],
    },
    "doctrine_2": {
        "name": "Stratagems",
        "questline": "Doctrine",
        "tier": 2,
        "requires": ["doctrine_1", "curiosity_1"],
        "intro": "How ought we approach battles?",
        "objective": "Bring Wraith/Abolisher and take control of the base.",
        "completion_text": "These metal contraptions seem specialized.",
        "required_hero": ["Wraith", "Abolisher"],
        "gold_cost": 0,
        "location_rule": "enemy_base_artificer",
        "capture_base": True,
        "decisions": [
            {
                "label": "Gunpowder",
                "description": "",
                "hero_evolution": {"from": ["Wraith", "Abolisher"], "to": "Nightmare"},
                "hero_outcome": (
                    "Wraith/Abolisher turns into Nightmare, gains +8 Damage "
                    'and "Turnstart Shadowstep", which lets it move to a hex '
                    "adjacent to the furthest enemy unit instead of moving "
                    "normally every turn."
                ),
                "other_outcome": (
                    'Your Pages gain the "Onhit Freeze 1/1" ability, which '
                    "exhausts a random ready enemy within attack range after "
                    "attacking and their Speed increases by 0.4."
                ),
                "outcome_text": (
                    "Take after their designs of gunpowder. Do not give our "
                    "foes a chance to respond."
                ),
                "effects": [
                    {"type": "grant_upgrade", "upgrade_id": "pages_freeze"},
                ],
            },
            {
                "label": "Metal",
                "description": "",
                "hero_evolution": {"from": ["Wraith", "Abolisher"], "to": "Reaper"},
                "hero_outcome": (
                    "Wraith/Abolisher turns into Reaper, gains +16 HP and "
                    '"Turnend Global Strike 1", which lets it deal 1 damage '
                    "to all enemies at the end of every turn."
                ),
                "other_outcome": (
                    'Gain the "Eternal servitude" upgrade, which makes it so '
                    "that winning a combat brings all your units that died in "
                    "the combat back to life on the overworld."
                ),
                "outcome_text": "Take after their designs of metal. Outlast our foes.",
                "effects": [
                    {"type": "combat_rule", "rule": "revive_on_win", "value": True},
                ],
            },
        ],
    },
}

QUESTS_BY_FACTION = {
    "Custodians": CUSTODIAN_QUESTS,
}

# Map faction names to player quadrant slots (matches Overworld._spawn_bases order)
_FACTION_SLOT = {
    "Custodians": 1,
    "Weavers": 2,
    "Artificers": 3,
    "Purifiers": 4,
}


def generate_quest_location(quest, overworld, player):
    """Pick a hex for a quest based on its location_rule. Returns (col, row)."""
    rule = quest["location_rule"]
    rng = overworld.rng

    if rule == "between_bases":
        bases = overworld.get_player_bases(player)
        if not bases:
            return (overworld.COLS // 2, overworld.ROWS // 2)
        avg_c = sum(b.pos[0] for b in bases) / len(bases)
        avg_r = sum(b.pos[1] for b in bases) / len(bases)
        mid_c = overworld.COLS / 2
        mid_r = overworld.ROWS / 2
        target_c = (avg_c + mid_c) / 2
        target_r = (avg_r + mid_r) / 2
        best = None
        best_dist = float("inf")
        for r in range(overworld.ROWS):
            for c in range(overworld.COLS):
                d = abs(c - target_c) + abs(r - target_r)
                if d < best_dist:
                    best_dist = d
                    best = (c, r)
        return best

    if rule == "center":
        center = (overworld.COLS // 2, overworld.ROWS // 2)
        candidates = [
            (c, r)
            for r in range(overworld.ROWS)
            for c in range(overworld.COLS)
            if hex_distance((c, r), center) <= 3
        ]
        return rng.choice(candidates) if candidates else center

    if rule == "own_base":
        bases = overworld.get_player_bases(player)
        if bases:
            return rng.choice(bases).pos
        return (overworld.COLS // 2, overworld.ROWS // 2)

    # enemy_base_<faction>
    faction_map = {
        "enemy_base_weaver": "Weavers",
        "enemy_base_purifier": "Purifiers",
        "enemy_base_artificer": "Artificers",
    }
    target_faction = faction_map.get(rule)
    if target_faction:
        slot = _FACTION_SLOT.get(target_faction, 1)
        bases = overworld.get_player_bases(slot)
        if bases:
            return rng.choice(bases).pos
        # Fallback: pick a hex in that quadrant
        mid_c = overworld.COLS // 2
        mid_r = overworld.ROWS // 2
        quadrants = {
            1: (range(0, mid_c), range(0, mid_r)),
            2: (range(mid_c, overworld.COLS), range(0, mid_r)),
            3: (range(0, mid_c), range(mid_r, overworld.ROWS)),
            4: (range(mid_c, overworld.COLS), range(mid_r, overworld.ROWS)),
        }
        cols, rows = quadrants.get(slot, quadrants[1])
        candidates = [(c, r) for r in rows for c in cols]
        return rng.choice(candidates) if candidates else (mid_c, mid_r)

    return (overworld.COLS // 2, overworld.ROWS // 2)


def check_quest_completable(quest, quest_state, overworld, player):
    """Check whether a quest can be completed right now. Returns True/False."""
    pos = quest_state["pos"]

    # Required hero must be at the quest location
    required_heroes = quest["required_hero"]
    hero_present = False
    for army in overworld.get_armies_at(pos):
        if army.player == player:
            for unit_name, count in army.units:
                if unit_name in required_heroes and count > 0:
                    hero_present = True
                    break
        if hero_present:
            break
    if not hero_present:
        return False

    # Gold cost
    gold_cost = quest.get("gold_cost", 0)
    if gold_cost > 0 and overworld.gold.get(player, 0) < gold_cost:
        return False

    # Wait turns
    wait_needed = quest.get("wait_turns", 0)
    if wait_needed > 0 and quest_state.get("wait_counter", 0) < wait_needed:
        return False

    # Clear gold radius
    clear_radius = quest.get("clear_gold_radius", 0)
    if clear_radius > 0:
        for pile in overworld.gold_piles:
            if hex_distance(pile.pos, pos) <= clear_radius:
                return False

    # Capture base
    if quest.get("capture_base"):
        base = overworld.get_base_at(pos)
        if not base or base.player != player:
            return False

    return True


def get_unlockable_quests(completed_ids, faction_quests):
    """Return list of quest_ids from faction_quests whose prerequisites are all completed
    and that aren't already active or completed."""
    result = []
    for qid, quest in faction_quests.items():
        if quest["tier"] <= 1:
            continue
        if all(req in completed_ids for req in quest.get("requires", [])):
            result.append(qid)
    return result

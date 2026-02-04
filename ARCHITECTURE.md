# Architecture Overview

This document describes how the major systems connect to help with navigation and debugging.

## File Structure

| File | Purpose |
|------|---------|
| `src/overworld.py` | Game state, armies, map data, unit/hero stats (UNIT_STATS, HERO_STATS, FACTIONS) |
| `src/overworld_gui.py` | Overworld UI, army management, quest tracking, hero evolution tracking |
| `src/combat.py` | Battle simulation engine, ability execution, damage resolution |
| `src/combat_gui.py` | Battle UI, ability tooltips, unit display |
| `src/heroes.py` | Hero definitions, evolution trees (HERO_EVOLUTIONS), stat computation |
| `src/quests.py` | Quest definitions including hero_evolution triggers |
| `src/game_state.py` | Shared logic for computing effective unit stats with upgrades/evolutions |
| `src/battle_resolution.py` | Helpers for converting armies to battle format |

## System Connections

### Quest → Hero Evolution → Combat Stats

```
Quest decision selected (overworld_gui._choose_quest_decision)
    ↓
If decision has "hero_evolution" field:
    ↓
_apply_hero_evolution() updates player_hero_evolutions dict
    Format: {player_id: {base_hero: [evolution_path]}}
    Example: {1: {"Accursed": ["Abolisher"]}}
    ↓
Stats cache invalidated
    ↓
When entering combat, _make_battle_units() calls:
    ↓
_get_effective_unit_stats() → game_state.get_effective_unit_stats()
    ↓
heroes.apply_hero_evolutions_to_stats() computes evolved stats
    - Starts with base hero stats (e.g., Accursed)
    - Applies each evolution in path cumulatively
    - Base abilities preserved, evolution abilities added
    ↓
battle_resolution.make_battle_units() creates unit specs with abilities
    ↓
combat.Battle._parse_unit_spec() creates Unit instances
```

### Combat Flow

```
Battle.step() - one unit takes its turn
    ↓
If enemy in range: attack
    ↓
_apply_damage(target, amount, source_unit)
    - Checks Block (passive ability)
    - Applies armor reduction
    - Checks Undying saves
    - Reduces target HP
    ↓
If target.hp <= 0:
    ↓
_handle_unit_death(dead_unit, source_unit)
    - Triggers "onkill" abilities on source_unit
    - Triggers "lament" abilities on dead unit's allies
    - Triggers "harvest" abilities on enemies
    ↓
Back in step(): set self.last_action dict
    ↓
_trigger_abilities(unit, "onhit", context)
    ↓
End of turn: _trigger_abilities(unit, "endturn", context)
```

### Ability Execution Flow

```
_trigger_abilities(unit, trigger, context)
    - Skips if unit._silenced
    - For each ability matching trigger:
        ↓
    _execute_ability(unit, ability, context)
        ↓
    _ABILITY_DISPATCH[effect](unit, ability, context, value)
        e.g., _exec_heal_or_fortify, _exec_silence, _exec_strike
        ↓
    _queue_event() adds to self.last_action["{effect}_events"]
        ↓
    If apply_events_immediately: _apply_queued_events()
        ↓
    apply_effect_event() → _EVENT_DISPATCH[type]()
        e.g., _event_heal, _event_strike
```

### Ability Triggers

| Trigger | When it fires |
|---------|---------------|
| `passive` | Checked continuously (armor, block, execute, boost) |
| `onhit` | After attacking (even if target survives) |
| `onkill` | After killing an enemy |
| `wounded` | When this unit takes damage |
| `turnstart` | Before unit's action (used for shadowstep) |
| `endturn` | After unit's action |
| `lament` | When an ally dies within range |
| `harvest` | When an enemy dies within range |

### Display Names vs Unit IDs

Heroes keep their base ID (e.g., "Accursed") in army.units for game logic, but display a different name (e.g., "Abolisher") in UI:

- `_get_unit_display_name(unit_id, player_id)` returns evolved name
- `Unit.display_name` set during battle creation
- Tooltips and labels use display_name
- Game logic uses unit.name (base ID)

## Key Data Structures

### Hero Evolution Tracking

```python
# In overworld_gui.py
self.player_hero_evolutions = {
    1: {  # player_id
        "Accursed": ["Abolisher", "Nightmare"],  # base_hero: [evolution_path]
    }
}
```

### Unit Spec (battle creation)

```python
{
    "name": "Accursed",           # Base ID for game logic
    "display_name": "Abolisher",  # Shown in UI
    "max_hp": 16,
    "damage": 12,
    "range": 2,
    "count": 1,
    "abilities": [...],           # Combined base + evolution abilities
    "armor": 0,
    "speed": 1.0,
}
```

### Ability Definition

```python
{
    "trigger": "onkill",      # When ability activates
    "effect": "heal",         # What it does
    "target": "self",         # Who it affects (self/target/area/random/global)
    "value": 8,               # Effect magnitude
    "range": 2,               # Optional: range for area effects
    "charge": 3,              # Optional: activates every N triggers
}
```

## Known Issues

- Abolisher onkill self-heal not triggering in actual gameplay (isolated tests pass)

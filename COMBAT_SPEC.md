# Combat System Specification

This document describes how battles work in the game.

## Overview

Battles are turn-based engagements on a hex grid. Two armies (Player 1 and Player 2) fight until one side is eliminated or a stalemate is detected.

## Map

- **Grid**: 17 columns x 5-15 rows (rows scale based on army size)
- **Hex coordinates**: (column, row) where column 0 is west, column 16 is east
- **Deployment zones**:
  - Player 1 (west): columns 0-5
  - Player 2 (east): columns 11-16
  - Neutral zone: columns 6-10

## Units

### Base Stats

| Stat | Description |
|------|-------------|
| `max_hp` | Maximum hit points |
| `hp` | Current hit points (unit dies when <= 0) |
| `damage` | Base attack damage |
| `attack_range` | How far the unit can attack (hex distance) |
| `armor` | Damage reduction (can go negative from Sunder) |
| `speed` | Movement bonus chance (1.0 = normal, 1.5 = 50% chance of extra move) |
| `abilities` | List of ability definitions |

### Temporary State

| State | Description |
|-------|-------------|
| `_frozen_turns` | Turns remaining where unit skips its action |
| `_silenced` | If true, unit cannot trigger any abilities |
| `_block_used` | Damage instances blocked this round (resets each round) |
| `_ramp_accumulated` | Total damage gained from all sources (ramp, lament aura, etc.) |
| `has_acted` | Whether unit has taken its turn this round |
| `_ready_triggered` | If true, unit doesn't mark `has_acted` after its turn |

## Rounds and Turn Order

1. At round start:
   - All living units are shuffled randomly into turn order
   - All units have `has_acted` set to False
   - All units have `_block_used` reset to 0
   - Stalemate check runs (3 identical consecutive rounds = draw)

2. Units take turns in order:
   - Skip dead units
   - Frozen units decrement `_frozen_turns`, skip their turn
   - Active units perform their action

3. When all units have acted, a new round begins

## Unit Turn Sequence

```
1. turnstart abilities trigger
2. Find enemies in attack range
3. If enemies in range:
   → Attack random enemy in range
   → onhit abilities trigger
4. Else:
   → Move toward closest enemy (by path length)
   → If shadowstep ability ready, teleport instead
   → If speed bonus triggers, move extra hex
   → If now in range, attack
   → onhit abilities trigger (if attacked)
5. endturn abilities trigger
6. If _ready_triggered: don't mark has_acted (can act again)
7. Advance to next unit
```

## Movement

- Units move one hex per turn toward the closest enemy (by BFS path length)
- Movement uses pathfinding around occupied hexes
- **Speed bonus**: If `speed > 1.0`, roll `random() < (speed - 1.0)` for extra movement
- **Shadowstep**: Teleport to hex adjacent to the furthest enemy instead of normal movement

## Attacking

- Target selection: Random enemy within attack range
- Attack is **ranged** if `attack_range > 1`
- Damage formula: `base_damage + global_boost_bonus`

### Global Boost

Units with `passive boost` ability add their value to all allies' attacks:
```
total_boost = sum(ability_value for each ally with passive boost)
```

## Damage Resolution

When damage is dealt to a target:

```
1. Check Block (passive ability)
   - If target has Block and _block_used < block_value:
     → Increment _block_used, deal 0 damage, stop

2. Calculate effective armor
   - base_armor + self_armor_abilities + aura_armor_from_allies

3. Calculate actual damage
   - actual = max(0, incoming_damage - effective_armor)
   - If actual <= 0, stop

4. Check Undying (ally passive ability)
   - If damage would kill and target has damage stat > 0:
     → Check allies with Undying aura in range
     → If found and target.damage >= undying_value:
       → Reduce target.damage by undying_value
       → Deal 0 damage, stop

5. Apply damage
   - target.hp -= actual

6. If target still alive:
   → Trigger "wounded" abilities on target
   → Check Execute (see below)

7. If target dead:
   → Call _handle_unit_death
```

### Execute Check

After a unit takes damage but survives:
```
For each enemy with passive Execute ability:
  If target within aura range AND target.hp <= execute_threshold:
    → Kill target instantly
    → Credit kill to Execute unit
```

## Death Handling

When a unit dies:

```
1. Trigger "onkill" abilities on the killer (if any)

2. For each living unit:
   - Trigger "lament" abilities (ally deaths within range)
   - Trigger "harvest" abilities (enemy deaths within range)
   - Apply "lament_aura" damage bonuses to nearby allies
```

## Ability System

### Ability Definition

```python
{
    "trigger": "onkill",      # When ability activates
    "effect": "heal",         # What it does
    "target": "self",         # Who it affects
    "value": 8,               # Effect magnitude
    "range": 2,               # Range for area effects
    "charge": 3,              # Activates every N triggers
    "aura": 3,                # Aura range (for passive auras)
}
```

### Triggers

| Trigger | When |
|---------|------|
| `passive` | Always active (checked continuously) |
| `turnstart` | Before unit's action |
| `onhit` | After attacking (even if target survives) |
| `onkill` | After killing an enemy |
| `wounded` | When this unit takes damage |
| `endturn` | After unit's action completes |
| `lament` | When an ally dies within range |
| `harvest` | When an enemy dies within range |

### Targets

| Target | Selection |
|--------|-----------|
| `self` | The ability user |
| `target` | The attack target (from context) |
| `random` | Random valid target in range |
| `area` | All valid targets in range |
| `global` | All allies (for buffs) or all enemies (for damage) |

For heal/fortify: targets are allies within range (heal excludes full HP units)
For damage effects: targets are enemies within range

### Effects

| Effect | Description |
|--------|-------------|
| `heal` | Restore HP (up to max_hp) |
| `fortify` | Increase max_hp and current HP |
| `strike` | Deal damage to targets |
| `splash` | Deal damage to enemies adjacent to target |
| `sunder` | Reduce target's armor |
| `ramp` | Permanently increase own damage (tracked in `_ramp_accumulated`) |
| `push` | Push target N hexes away horizontally |
| `retreat` | Move self away from target after attacking |
| `freeze` | Skip target's next turn |
| `summon` | Create Blade units adjacent to self |
| `shadowstep` | Teleport to furthest enemy (handled in movement) |
| `silence` | Disable all abilities on enemies in range |
| `ready` | Allow acting again this round |
| `block` | Negate first N damage instances per round |
| `execute` | Kill enemies that fall below HP threshold |
| `armor` | Add to effective armor (self or aura) |
| `boost` | Add to all allies' attack damage |
| `undying` | Prevent ally death by sacrificing their damage |
| `lament_aura` | Grant damage to allies when nearby ally dies (tracked in `_ramp_accumulated`) |

### Charge System

Abilities with `charge: N` only activate every Nth trigger:
- Counter increments each time trigger condition is met
- When counter reaches N, ability fires and counter resets to 0


## Event Queue

Some effects are queued and applied after the triggering action:

**Queued events**: heal, fortify, sunder, splash, strike

**Immediate effects**: ramp, push, retreat, freeze, summon, silence, ready

When `apply_events_immediately` is True (default), queued events process immediately after each ability trigger. Events can chain (e.g., splash damage can trigger more deaths).

## Win Conditions

- **Victory**: All enemy units dead
- **Defeat**: All your units dead
- **Draw**: 3 consecutive rounds with no change in game state (stalemate)

## Stalemate Detection

Each round, a snapshot of game state is taken:
- Unit IDs, HP, positions, armor, damage, unit count

If snapshot matches previous round, increment stalemate counter.
If counter reaches 3, battle ends in a draw (winner = 0).

## Special Mechanics

### Frozen Units

- `_frozen_turns` decrements at turn start
- While frozen > 0, unit skips its turn entirely
- Set by Freeze ability

### Silenced Units

- `_silenced = True` prevents all ability triggers
- Does not prevent basic attacks or movement
- Currently set by Silence ability (persists until... ?)

### Summoned Units (Blades)

- Created by Summon ability
- Stats: 1 HP, 2 damage, 1 range, no abilities
- Placed in empty hexes adjacent to summoner
- `summoner_id` tracks which unit created them
- May or may not act immediately based on `summon_ready` flag

### Ready Ability

- Sets `_ready_triggered = True`
- At end of turn, if flag is set, `has_acted` stays False
- Unit can take another turn this round when reached again in turn order
- Flag is cleared after being checked

---

## Implementation Details

This section describes code-level details of how `combat.py` executes battles.

### Battle.step() - Single Step Execution

Each call to `step()` executes one unit's turn. Returns `True` if battle continues, `False` if battle ended.

```python
def step(self):
    # 1. Save state for undo
    self._save_state()
    self.last_action = None

    # 2. Check if battle already over
    if self.winner is not None:
        return False

    # 3. Check win conditions
    p1_alive = [u for u in self.units if u.alive and u.player == 1]
    p2_alive = [u for u in self.units if u.alive and u.player == 2]
    if not p1_alive: self.winner = 2; return False
    if not p2_alive: self.winner = 1; return False

    # 4. Find next unit to act
    while self.current_index < len(self.turn_order):
        unit = self.turn_order[self.current_index]
        if not unit.alive:
            self.current_index += 1
            continue
        if unit._frozen_turns > 0:
            unit._frozen_turns -= 1
            unit.has_acted = True
            self.current_index += 1
            continue
        break
    else:
        # All units acted, start new round
        self._new_round()
        return self.step()  # Recursive call for new round

    # 5. Execute unit's turn (see Unit Turn Sequence above)
    # ... turnstart, attack/move, onhit, endturn ...

    # 6. Handle ready ability
    if unit._ready_triggered:
        unit._ready_triggered = False
        # Don't mark has_acted - unit can act again
    else:
        unit.has_acted = True

    self.current_index += 1
    return True
```

### last_action Dictionary

After each `step()`, `self.last_action` contains details about what happened. The GUI uses this for animations and visual feedback.

**Attack (no movement):**
```python
{
    "type": "attack",
    "attacker_pos": (col, row),
    "target_pos": (col, row),
    "ranged": bool,          # True if attack_range > 1
    "killed": bool,          # True if target died
    # Plus any event lists from abilities (see below)
}
```

**Move only:**
```python
{
    "type": "move",
    "from": (col, row),
    "to": (col, row),
}
```

**Move then attack:**
```python
{
    "type": "move_attack",
    "from": (col, row),
    "to": (col, row),
    "target_pos": (col, row),
    "ranged": bool,
    "killed": bool,
    # Plus any event lists from abilities
}
```

**Additional fields added by abilities:**

| Field | Added by | Description |
|-------|----------|-------------|
| `heal_events` | heal ability | List of heal event dicts |
| `fortify_events` | fortify ability | List of fortify event dicts |
| `sunder_events` | sunder ability | List of sunder event dicts |
| `splash_events` | splash ability | List of splash damage event dicts |
| `strike_events` | strike ability | List of strike damage event dicts |
| `ramp_pos` | ramp ability | Position of unit that ramped |
| `push_from` | push ability | Original position before push |
| `push_to` | push ability | Position after push |
| `undying_saves` | undying ability | List of `{target, source}` positions |
| `vengeance_positions` | lament_aura | List of positions that gained damage |

### Event Dictionary Format

Events queued via `_queue_event()`:
```python
{
    "type": "heal",           # Event type
    "target_id": int,         # Unit ID of target
    "source_id": int,         # Unit ID of source
    "amount": int,            # Effect value
    "pos": (col, row),        # Target position
    # Optional extra fields depending on event type:
    "source_pos": (col, row), # For sunder/strike
}
```

### Ability Execution Flow

```
_trigger_abilities(unit, trigger, context)
    │
    ├─ If unit._silenced: return (no abilities fire)
    │
    └─ For each ability with matching trigger:
        │
        ├─ Check _charge_ready() - skip if charge not met
        │
        └─ _execute_ability(unit, ability, context)
            │
            ├─ Get value via _ability_value()
            │
            └─ Call handler from _ABILITY_DISPATCH[effect]
                │
                ├─ Immediate effects: modify state directly
                │
                └─ Queued effects: call _queue_event()
        │
        └─ If apply_events_immediately: _apply_queued_events()
```

### _apply_damage() Flow

```
_apply_damage(target, amount, source_unit)
    │
    ├─ Check Block ability (if not silenced)
    │   └─ If _block_used < block_value: return 0
    │
    ├─ Calculate effective armor
    │
    ├─ actual = max(0, amount - armor)
    │   └─ If actual <= 0: return 0
    │
    ├─ Check Undying (ally aura)
    │   └─ If would die and can sacrifice damage: return 0
    │
    ├─ target.hp -= actual
    │
    ├─ If target still alive:
    │   ├─ _trigger_abilities(target, "wounded", ...)
    │   └─ _check_execute(target, source_unit)
    │
    └─ If target dead:
        └─ _handle_unit_death(target, source_unit)
```

### _handle_unit_death() Flow

```
_handle_unit_death(dead_unit, source_unit)
    │
    ├─ If source_unit alive:
    │   └─ _trigger_abilities(source_unit, "onkill", {target: dead_unit})
    │
    └─ For each living unit:
        ├─ Check "lament" abilities (ally died within range)
        ├─ Check "harvest" abilities (enemy died within range)
        └─ Check "lament_aura" passive (grant damage to nearby allies)
```

### State Management

**History for undo:**
- `_save_state()` called at start of each `step()`
- Saves: unit states, turn order, current index, round number, log, winner, RNG state, stalemate count
- `undo()` restores previous state

**RNG determinism:**
- Battle initialized with `rng_seed`
- All random choices use `self.rng` (seeded Random instance)
- Allows replay and multiplayer synchronization

### Army Setup

Units are positioned by range tier:
1. Sort units by `attack_range`
2. Shortest range units go in frontmost column
3. When range tier changes, skip to next column
4. Within each column, units are center-packed and shuffled

P1 deploys in columns 0-5 (front at col 5, back at col 0)
P2 deploys in columns 11-16 (front at col 11, back at col 16)

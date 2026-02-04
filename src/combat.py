import random
from dataclasses import dataclass
from typing import Optional
from .constants import (
    COMBAT_P1_ZONE_END,
    COMBAT_P2_ZONE_START,
)
from .hex import (
    hex_distance,
    hex_neighbors,
    bfs_next_step,
    bfs_path_length,
    bfs_speed_move,
)


# Event types for queued effects
EVENT_HEAL = "heal"
EVENT_FORTIFY = "fortify"
EVENT_SUNDER = "sunder"
EVENT_SPLASH = "splash"
EVENT_BOMBARDMENT = "bombardment"
EVENT_STRIKE = "strike"

# Event queue keys for ability effects
_EVENT_KEYS = (
    f"{EVENT_HEAL}_events",
    f"{EVENT_FORTIFY}_events",
    f"{EVENT_SUNDER}_events",
    f"{EVENT_SPLASH}_events",
    f"{EVENT_BOMBARDMENT}_events",
    f"{EVENT_STRIKE}_events",
)


@dataclass
class BattleSnapshot:
    """Immutable snapshot of battle state for undo functionality."""

    unit_states: dict
    turn_ids: list
    unit_ids: list
    current_index: int
    round_num: int
    log: list
    winner: Optional[int]
    rng_state: tuple
    stalemate_count: int
    prev_round_state: Optional[frozenset]


# --- Setup helpers ---


class BattleSetup:
    """Static methods for army setup and positioning."""

    MIN_ROWS = 5
    MAX_ROWS = 15

    @staticmethod
    def compute_rows(p1_units, p2_units):
        """Compute map rows so the army with the most frontline units fits in one column."""

        def frontline_count(specs):
            if not specs:
                return 0
            parsed = []
            for spec in specs:
                if isinstance(spec, dict):
                    rng = spec["range"]
                    cnt = spec["count"]
                else:
                    rng = spec[3]
                    cnt = spec[4]
                parsed.append((rng, cnt))
            min_range = min(r for r, _ in parsed)
            return sum(c for r, c in parsed if r == min_range)

        p1_front = frontline_count(
            p1_units
            or [
                {"name": "Page", "range": 1, "count": 10},
                {"name": "Librarian", "range": 3, "count": 5},
            ]
        )
        p2_front = frontline_count(
            p2_units
            or [
                {"name": "Apprentice", "range": 2, "count": 10},
                {"name": "Seeker", "range": 4, "count": 5},
            ]
        )
        needed = max(p1_front, p2_front)
        return max(BattleSetup.MIN_ROWS, min(BattleSetup.MAX_ROWS, needed))

    @staticmethod
    def assign_positions(positions, unit_list, descending_col, rng):
        """Assign positions to units front-to-back, skipping columns on range tier changes.

        Args:
            positions: List of (col, row) tuples available for placement
            unit_list: List of Unit objects to position (will be sorted in place)
            descending_col: True for P1 (high cols first), False for P2
            rng: Random instance for shuffling
        """
        from collections import defaultdict
        from itertools import groupby

        by_col = defaultdict(list)
        for c, r in positions:
            by_col[c].append((c, r))
        sorted_cols = sorted(by_col.keys(), reverse=descending_col)
        num_rows = len(by_col[sorted_cols[0]])

        unit_list.sort(key=lambda u: u.attack_range)
        # Shuffle within each range tier
        shuffled = []
        for _, group in groupby(unit_list, key=lambda u: u.attack_range):
            tier = list(group)
            rng.shuffle(tier)
            shuffled.extend(tier)
        unit_list[:] = shuffled

        # First pass: count units per column
        col_boundaries = [i * num_rows for i in range(len(sorted_cols))]
        units_per_col = defaultdict(int)
        pos_i = 0
        prev_range = None
        for u in unit_list:
            if prev_range is not None and u.attack_range != prev_range:
                for b in col_boundaries:
                    if b >= pos_i:
                        pos_i = b
                        break
            col_idx = pos_i // num_rows
            units_per_col[col_idx] += 1
            pos_i += 1
            prev_range = u.attack_range

        # Second pass: build positions for each column
        flat_positions = []
        for ci, col in enumerate(sorted_cols):
            k = units_per_col.get(ci, 0)
            if k == 0:
                continue
            rows_in_col = sorted(r for _, r in by_col[col])
            mid = num_rows // 2
            selected = sorted(rows_in_col, key=lambda r: abs(r - rows_in_col[mid]))[:k]
            selected.sort()
            col_positions = [(col, r) for r in selected]
            rng.shuffle(col_positions)
            flat_positions.extend(col_positions)

        # Assign positions to units
        for i, u in enumerate(unit_list):
            u.pos = flat_positions[i]

    @staticmethod
    def default_p1_units():
        """Default army for player 1."""
        return [
            {"name": "Page", "max_hp": 3, "damage": 1, "range": 1, "count": 10},
            {
                "name": "Librarian",
                "max_hp": 2,
                "damage": 0,
                "range": 3,
                "count": 5,
                "sunder": 1,
            },
        ]

    @staticmethod
    def default_p2_units():
        """Default army for player 2."""
        return [
            {
                "name": "Apprentice",
                "max_hp": 8,
                "damage": 1,
                "range": 2,
                "count": 10,
                "push": 1,
            },
            {
                "name": "Seeker",
                "max_hp": 3,
                "damage": 1,
                "range": 4,
                "count": 5,
                "ramp": 1,
            },
        ]


# --- Game classes ---


class Unit:
    def __init__(
        self,
        name,
        max_hp,
        damage,
        attack_range,
        player,
        abilities=None,
        armor=0,
        speed=1.0,
        *,
        unit_id,
        display_name=None,
    ):
        self.id = unit_id
        self.name = name
        self.display_name = display_name or name  # Use display_name for UI, name for ID
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.attack_range = attack_range
        self.player = player
        self.abilities = abilities or []
        self.armor = armor
        self.speed = speed
        self._ramp_accumulated = 0  # Tracks all damage gained (ramp, lament aura, etc.)
        self._frozen_turns = 0
        self._ability_counters = {}
        self._block_used = 0  # Track damage instances blocked this round
        self._silenced = False  # Whether abilities are silenced
        self._ready_triggered = False  # Whether ready ability triggered this turn
        self.pos = None
        self.has_acted = False
        # For summoned units tracking
        self.summoner_id = None

    @property
    def alive(self):
        return self.hp > 0

    def __repr__(self):
        return f"{self.display_name}(P{self.player} HP:{self.hp}/{self.max_hp})"


class Battle:
    COLS = 17
    MIN_ROWS = 5
    MAX_ROWS = 15

    def __init__(
        self,
        p1_units=None,
        p2_units=None,
        rng_seed=None,
        apply_events_immediately=True,
        record_history=True,
    ):
        """Initialize battle.

        p1_units/p2_units: optional list of unit specs (tuples or dicts).
        If None, uses default hardcoded armies.
        rng_seed: optional int seed for deterministic battles.
        """
        if rng_seed is None:
            rng_seed = random.SystemRandom().randint(0, 2**31 - 1)
        self._init_p1_units = p1_units
        self._init_p2_units = p2_units
        self.rng_seed = rng_seed
        self.rng = random.Random(rng_seed)
        self._init_rng_state = self.rng.getstate()
        self._unit_id_counter = 0
        self.apply_events_immediately = apply_events_immediately
        self._record_history = record_history
        self.ROWS = BattleSetup.compute_rows(p1_units, p2_units)
        self.units = []
        self.turn_order = []
        self.current_index = 0
        self.round_num = 0
        self.log = []
        self.winner = None
        self.history = []
        self._prev_round_state = None
        self._stalemate_count = 0
        self._setup_armies(p1_units, p2_units)
        self._new_round()

    def _next_unit_id(self):
        self._unit_id_counter += 1
        return self._unit_id_counter

    def _save_state(self):
        if not self._record_history:
            return
        unit_states = {}
        for u in self.units:
            state = {
                "pos": u.pos,
                "hp": u.hp,
                "has_acted": u.has_acted,
                "damage": u.damage,
                "_ramp_accumulated": u._ramp_accumulated,
                "_frozen_turns": u._frozen_turns,
                "_ability_counters": dict(u._ability_counters),
                "armor": u.armor,
            }
            unit_states[u.id] = state
        snapshot = BattleSnapshot(
            unit_states=unit_states,
            turn_ids=[u.id for u in self.turn_order],
            unit_ids=[u.id for u in self.units],
            current_index=self.current_index,
            round_num=self.round_num,
            log=list(self.log),
            winner=self.winner,
            rng_state=self.rng.getstate(),
            stalemate_count=self._stalemate_count,
            prev_round_state=self._prev_round_state,
        )
        self.history.append(snapshot)

    def undo(self):
        if not self.history:
            return
        snapshot = self.history.pop()
        self.current_index = snapshot.current_index
        self.round_num = snapshot.round_num
        self.log = snapshot.log
        self.winner = snapshot.winner
        self._stalemate_count = snapshot.stalemate_count
        self._prev_round_state = snapshot.prev_round_state
        self.rng.setstate(snapshot.rng_state)
        id_to_unit = {u.id: u for u in self.units}
        # Remove units that didn't exist in the saved state (summoned units)
        self.units = [id_to_unit[uid] for uid in snapshot.unit_ids if uid in id_to_unit]
        for uid, state in snapshot.unit_states.items():
            u = id_to_unit.get(uid)
            if u is None:
                continue
            u.pos = state["pos"]
            u.hp = state["hp"]
            u.has_acted = state["has_acted"]
            u.damage = state["damage"]
            u._ramp_accumulated = state["_ramp_accumulated"]
            u._frozen_turns = state.get("_frozen_turns", 0)
            u._ability_counters = dict(state.get("_ability_counters", {}))
            u.armor = state.get("armor", u.armor)
        self.turn_order = [
            id_to_unit[uid] for uid in snapshot.turn_ids if uid in id_to_unit
        ]

    @staticmethod
    def _aura_range(unit, ab):
        """Resolve aura range, treating 'R' as the unit's attack range."""
        val = ab.get("aura")
        if val == "R":
            return unit.attack_range
        return val

    def _ability_value(self, unit, ability):
        base = ability.get("value", 0)
        if base == 0:
            return 0
        if ability.get("amplify", True) is False:
            return base
        bonus = sum(
            val
            for _, _, val in self._iter_passive_effects(
                "amplify", unit.pos, unit.player, source="allies"
            )
        )
        return base + bonus

    def _iter_passive_effects(
        self, effect_type, target_pos, target_player, source="allies"
    ):
        """Iterate over passive effects affecting a position.

        Yields (source_unit, ability, value) tuples for matching passive abilities.

        Args:
            effect_type: Effect type to find (e.g., "armor", "boost", "amplify")
            target_pos: Position being affected (used for aura range checks)
            target_player: Player of the unit at target position
            source: Which units to check:
                - "self": Only the unit at target_pos (if any)
                - "allies": Allied units (same player, excludes self)
                - "allies_and_self": Allied units including self
                - "enemies": Enemy units (different player)
                - "all": All living units
        """
        for unit in self.units:
            if not unit.alive:
                continue

            # Filter by source type
            is_self = unit.pos == target_pos
            is_ally = unit.player == target_player
            if source == "self" and not is_self:
                continue
            if source == "allies" and (not is_ally or is_self):
                continue
            if source == "allies_and_self" and not is_ally:
                continue
            if source == "enemies" and is_ally:
                continue

            for ab in unit.abilities:
                if ab.get("trigger") != "passive" or ab.get("effect") != effect_type:
                    continue

                # Check aura range if ability has aura
                aura_range = self._aura_range(unit, ab)
                if aura_range is not None:
                    if hex_distance(unit.pos, target_pos) > aura_range:
                        continue

                value = ab.get("value", 0)
                yield unit, ab, value

    def _sum_passive_effect(
        self, effect_type, target_pos, target_player, source="allies"
    ):
        """Sum all passive effects of a type affecting a position."""
        total = 0
        for unit, ab, base_value in self._iter_passive_effects(
            effect_type, target_pos, target_player, source
        ):
            # Apply amplify bonus to the value
            if ab.get("amplify", True) is not False and base_value > 0:
                amplify_bonus = sum(
                    val
                    for _, _, val in self._iter_passive_effects(
                        "amplify", unit.pos, unit.player, source="allies"
                    )
                )
                total += base_value + amplify_bonus
            else:
                total += base_value
        return total

    def _effective_armor(self, unit):
        """Return base armor + passive armor on self + aura armor from allies."""
        # Self armor (non-aura abilities on this unit)
        self_bonus = 0
        for ab in unit.abilities:
            if (
                ab.get("trigger") == "passive"
                and ab.get("effect") == "armor"
                and not ab.get("aura")
            ):
                self_bonus += self._ability_value(unit, ab)

        # Aura armor from allies
        aura_bonus = self._sum_passive_effect(
            "armor", unit.pos, unit.player, source="allies"
        )
        return unit.armor + self_bonus + aura_bonus

    def _global_boost_bonus(self, player):
        """Sum boost bonuses from all allies (global effect, no range check)."""
        # Boost is global - use a dummy position, allies_and_self includes all team members
        # We need a position to call the method, use (0,0) since boost has no aura range
        bonus = 0
        for unit in self.units:
            if unit.alive and unit.player == player:
                for ab in unit.abilities:
                    if ab.get("trigger") == "passive" and ab.get("effect") == "boost":
                        bonus += self._ability_value(unit, ab)
        return bonus

    def _charge_ready(self, unit, idx, ability):
        charge = ability.get("charge")
        if not charge:
            return True
        key = f"{idx}:{ability.get('trigger')}"
        unit._ability_counters[key] = unit._ability_counters.get(key, 0) + 1
        if unit._ability_counters[key] < charge:
            return False
        unit._ability_counters[key] = 0
        return True

    def _targets_for_ability(self, unit, ability, context):
        target = ability.get("target", "self")
        rng = ability.get("range", unit.attack_range)
        effect = ability.get("effect")
        if target == "self":
            return [unit]
        if target == "target":
            tgt = context.get("target")
            return [tgt] if tgt and tgt.alive else []
        if target == "global":
            return [u for u in self.units if u.alive and u.player == unit.player]
        if effect in (EVENT_HEAL, EVENT_FORTIFY):
            pool = [
                u
                for u in self.units
                if u.alive
                and u.player == unit.player
                and hex_distance(unit.pos, u.pos) <= rng
                and (effect != EVENT_HEAL or u.hp < u.max_hp)
            ]
        else:
            pool = [
                u
                for u in self.units
                if u.alive
                and u.player != unit.player
                and hex_distance(unit.pos, u.pos) <= rng
            ]
        if target == "random":
            return [self.rng.choice(pool)] if pool else []
        if target == "area":
            return pool
        return []

    def _queue_event(self, event_type, unit, target, amount, extra=None):
        if self.last_action is None:
            self.last_action = {}
        event = {
            "type": event_type,
            "target_id": target.id,
            "amount": amount,
            "pos": target.pos,
            "source_id": unit.id,
        }
        if extra:
            event.update(extra)
        key = f"{event_type}_events"
        self.last_action.setdefault(key, []).append(event)

    def _exec_ramp(self, unit, ability, context, value):
        unit.damage += value
        unit._ramp_accumulated += value
        if self.last_action is not None:
            self.last_action["ramp_pos"] = unit.pos

    def _exec_push(self, unit, ability, context, value):
        targets = self._targets_for_ability(unit, ability, context)
        if targets:
            self._apply_push_value(unit, targets[0], value)

    def _exec_retreat(self, unit, ability, context, value):
        tgt = context.get("target")
        if tgt:
            self._apply_retreat(unit, tgt)

    def _exec_freeze(self, unit, ability, context, value):
        self._apply_freeze_value(unit, value)

    def _exec_summon(self, unit, ability, context, value):
        count = ability.get("count", 1)
        self._apply_summon(unit, count, ability)

    def _exec_shadowstep(self, unit, ability, context, value):
        pass  # handled during movement

    def _exec_splash(self, unit, ability, context, value):
        tgt = context.get("target")
        if tgt:
            self._queue_splash_events(unit, tgt, value)

    def _exec_heal_or_fortify(self, unit, ability, context, value):
        effect = ability.get("effect")
        targets = self._targets_for_ability(unit, ability, context)
        for t in targets:
            etype = EVENT_FORTIFY if effect == EVENT_FORTIFY else EVENT_HEAL
            self._queue_event(etype, unit, t, value)

    def _exec_sunder(self, unit, ability, context, value):
        targets = self._targets_for_ability(unit, ability, context)
        for t in targets:
            self._queue_event(EVENT_SUNDER, unit, t, value, {"source_pos": unit.pos})

    def _exec_strike(self, unit, ability, context, value):
        targets = self._targets_for_ability(unit, ability, context)
        for t in targets:
            self._queue_event(EVENT_STRIKE, unit, t, value, {"source_pos": unit.pos})

    def _exec_silence(self, unit, ability, context, value):
        """Silence enemies within range, disabling their abilities."""
        silence_range = ability.get("range", unit.attack_range)
        for enemy in self.units:
            if enemy.alive and enemy.player != unit.player:
                if hex_distance(unit.pos, enemy.pos) <= silence_range:
                    if not enemy._silenced:
                        enemy._silenced = True
                        self.log.append(f"  {unit} silences {enemy}!")

    def _exec_ready(self, unit, ability, context, value):
        """Ready the unit, allowing it to act again this round."""
        unit._ready_triggered = True
        self.log.append(f"  {unit} readies for another action!")

    _ABILITY_DISPATCH = {
        "ramp": _exec_ramp,
        "push": _exec_push,
        "retreat": _exec_retreat,
        "freeze": _exec_freeze,
        "summon": _exec_summon,
        "shadowstep": _exec_shadowstep,
        "splash": _exec_splash,
        "heal": _exec_heal_or_fortify,
        "fortify": _exec_heal_or_fortify,
        "sunder": _exec_sunder,
        "strike": _exec_strike,
        "silence": _exec_silence,
        "ready": _exec_ready,
    }

    def _execute_ability(self, unit, ability, context):
        effect = ability.get("effect")
        value = self._ability_value(unit, ability)
        handler = self._ABILITY_DISPATCH.get(effect)
        if handler:
            handler(self, unit, ability, context, value)

    def _trigger_abilities(self, unit, trigger, context):
        if unit._silenced:
            return  # Silenced units can't trigger abilities
        for idx, ability in enumerate(unit.abilities):
            if ability.get("trigger") != trigger:
                continue
            if not self._charge_ready(unit, idx, ability):
                continue
            self._execute_ability(unit, ability, context)
        if self.apply_events_immediately:
            self._apply_queued_events()

    def _parse_unit_spec(self, spec, player):
        """Parse a unit spec dict into Unit instances.

        Dict format: {"name": str, "max_hp": int, "damage": int, "range": int, "count": int, ...}
        Optional: "display_name" for evolved heroes (defaults to name if not provided)
        """
        units = []
        name = spec["name"]
        display_name = spec.get("display_name", name)
        max_hp = spec["max_hp"]
        damage = spec["damage"]
        atk_range = spec["range"]
        count = spec["count"]
        abilities = spec.get("abilities", [])
        armor = spec.get("armor", 0)
        speed = spec.get("speed", 1.0)
        for _ in range(count):
            units.append(
                Unit(
                    name,
                    max_hp,
                    damage,
                    atk_range,
                    player,
                    abilities=abilities,
                    armor=armor,
                    speed=speed,
                    unit_id=self._next_unit_id(),
                    display_name=display_name,
                )
            )
        return units

    def _setup_armies(self, p1_units=None, p2_units=None):
        if p1_units is None:
            p1_units = BattleSetup.default_p1_units()
        if p2_units is None:
            p2_units = BattleSetup.default_p2_units()

        # P1 western zone: cols 0..5, P2 eastern zone: cols 11..16
        west = [(c, r) for c in range(COMBAT_P1_ZONE_END) for r in range(self.ROWS)]
        east = [
            (c, r)
            for c in range(COMBAT_P2_ZONE_START, self.COLS)
            for r in range(self.ROWS)
        ]

        p1_unit_list = []
        for spec in p1_units:
            p1_unit_list.extend(self._parse_unit_spec(spec, 1))
        BattleSetup.assign_positions(
            west, p1_unit_list, descending_col=True, rng=self.rng
        )
        self.units.extend(p1_unit_list)

        p2_unit_list = []
        for spec in p2_units:
            p2_unit_list.extend(self._parse_unit_spec(spec, 2))
        BattleSetup.assign_positions(
            east, p2_unit_list, descending_col=False, rng=self.rng
        )
        self.units.extend(p2_unit_list)

    def _snapshot(self):
        return frozenset(
            (u.id, u.hp, u.pos, u.armor, u.damage, len(self.units))
            for u in self.units
            if u.alive
        )

    def _new_round(self):
        # Stalemate detection: require 3 consecutive identical rounds
        snap = self._snapshot()
        if self._prev_round_state is not None and snap == self._prev_round_state:
            self._stalemate_count += 1
            if self._stalemate_count >= 3:
                self.winner = 0  # draw
                self.log.append("Stalemate - no progress possible. Battle is a draw!")
                return
        else:
            self._stalemate_count = 0
        self._prev_round_state = snap

        alive = [u for u in self.units if u.alive]
        self.rng.shuffle(alive)
        self.turn_order = alive
        self.current_index = 0
        self.round_num += 1
        for u in alive:
            u.has_acted = False
            u._block_used = 0  # Reset block counter each round
        self.log.append(f"--- Round {self.round_num} ---")

    def _occupied(self):
        return {u.pos for u in self.units if u.alive}

    def _get_block_ability(self, unit):
        """Find block ability on unit, if any. Returns (ability, block_value) or None."""
        if unit._silenced:
            return None
        for ab in unit.abilities:
            if ab.get("trigger") == "passive" and ab.get("effect") == "block":
                return ab, ab.get("value", 0)
        return None

    def _find_undying_save(self, target):
        """Find an ally that can save target with undying. Returns (ally, value) or None."""
        for ally, ab, value in self._iter_passive_effects(
            "undying", target.pos, target.player, source="allies"
        ):
            amplified_value = self._ability_value(ally, ab)
            if target.damage >= amplified_value:
                return ally, amplified_value
        return None

    def _find_executioner(self, target):
        """Find an enemy that can execute target. Returns (enemy, threshold) or None."""
        if not target.alive:
            return None
        for enemy, ab, threshold in self._iter_passive_effects(
            "execute", target.pos, target.player, source="enemies"
        ):
            if enemy._silenced:
                continue
            if target.hp <= threshold:
                return enemy, threshold
        return None

    def _apply_damage(self, target, amount, source_unit=None):
        """Apply damage to target, handling Block, Armor, Undying. Returns actual damage dealt."""
        # Check for passive Block ability
        block_info = self._get_block_ability(target)
        if block_info:
            _, block_value = block_info
            if target._block_used < block_value:
                target._block_used += 1
                self.log.append(
                    f"  {target} blocks damage! ({target._block_used}/{block_value} blocks used)"
                )
                return 0

        eff_armor = self._effective_armor(target)
        actual = max(0, amount - eff_armor)
        if actual <= 0:
            return 0

        # Check Undying save
        would_die = target.hp - actual <= 0
        if would_die and target.damage > 0:
            save = self._find_undying_save(target)
            if save:
                ally, undying_val = save
                target.damage -= undying_val
                self.log.append(
                    f"  {target} saved by Undying! Loses {undying_val} dmg (now {target.damage})"
                )
                if self.last_action is not None:
                    self.last_action.setdefault("undying_saves", []).append(
                        {"target": target.pos, "source": ally.pos}
                    )
                return 0

        target.hp -= actual
        if target.alive and actual > 0:
            self._trigger_abilities(target, "wounded", {"source": source_unit})
            self._check_execute(target, source_unit)
        if not target.alive:
            self._handle_unit_death(target, source_unit)
        return actual

    def _check_execute(self, target, source_unit):
        """Check if any enemy with Execute can kill this low-HP target."""
        result = self._find_executioner(target)
        if result:
            enemy, threshold = result
            self.log.append(
                f"  {enemy} executes {target}! (HP {target.hp} <= {threshold})"
            )
            target.hp = 0
            self._handle_unit_death(target, enemy)

    def _trigger_death_reaction(self, unit, trigger, dead_unit, player_match):
        """Trigger death-related abilities (lament or harvest) on a unit.

        Args:
            unit: The unit that may react to the death
            trigger: "lament" or "harvest"
            dead_unit: The unit that died
            player_match: True if we want same-player (lament), False for different (harvest)
        """
        is_same_player = unit.player == dead_unit.player
        if player_match != is_same_player:
            return
        if trigger == "lament" and unit.id == dead_unit.id:
            return  # Don't trigger lament on self

        for idx, ab in enumerate(unit.abilities):
            if ab.get("trigger") != trigger:
                continue
            rng = ab.get("range", unit.attack_range)
            if hex_distance(unit.pos, dead_unit.pos) <= rng:
                if self._charge_ready(unit, idx, ab):
                    self._execute_ability(unit, ab, {"dead": dead_unit})

    def _apply_lament_aura(self, unit, dead_unit):
        """Apply lament_aura passive effects when an ally dies."""
        for ab in unit.abilities:
            if ab.get("trigger") != "passive" or ab.get("effect") != "lament_aura":
                continue
            aura_range = self._aura_range(unit, ab) or 0
            inner_range = ab.get("range", 1)
            for ally in self.units:
                if (
                    ally.alive
                    and ally.player == unit.player
                    and ally.id != dead_unit.id
                    and hex_distance(ally.pos, unit.pos) <= aura_range
                    and hex_distance(ally.pos, dead_unit.pos) <= inner_range
                ):
                    value = self._ability_value(unit, ab)
                    ally.damage += value
                    ally._ramp_accumulated += value
                    self.log.append(
                        f"  {ally} gains {value} dmg from Aura Lament (now {ally.damage})"
                    )
                    if self.last_action is not None:
                        self.last_action.setdefault("vengeance_positions", []).append(
                            ally.pos
                        )

    def _handle_unit_death(self, dead_unit, source_unit=None):
        if source_unit and source_unit.alive:
            self._trigger_abilities(source_unit, "onkill", {"target": dead_unit})
        for unit in self.units:
            if not unit.alive:
                continue
            self._trigger_death_reaction(unit, "lament", dead_unit, player_match=True)
            self._trigger_death_reaction(unit, "harvest", dead_unit, player_match=False)
            self._apply_lament_aura(unit, dead_unit)

    def _apply_push_value(self, attacker, target, push_val):
        """Push target N hexes horizontally away from attacker after attacking."""
        if push_val <= 0 or not target.alive:
            return
        direction = 1 if target.pos[0] >= attacker.pos[0] else -1
        occupied = self._occupied()
        col, row = target.pos
        for _ in range(push_val):
            new_col = col + direction
            if new_col < 0 or new_col >= self.COLS:
                break
            if (new_col, row) in occupied and (new_col, row) != target.pos:
                break
            col = new_col
        if (col, row) != target.pos:
            old_pos = target.pos
            target.pos = (col, row)
            self.log.append(f"  {target} pushed {old_pos}->{target.pos}")
            if self.last_action is not None:
                self.last_action["push_from"] = old_pos
                self.last_action["push_to"] = target.pos

    def _apply_retreat(self, unit, target):
        """Move unit one hex away from target after a successful attack."""
        if not target:
            return
        occupied = self._occupied() - {unit.pos}
        current_dist = hex_distance(unit.pos, target.pos)
        candidates = []
        for nb in hex_neighbors(unit.pos[0], unit.pos[1], self.COLS, self.ROWS):
            if nb in occupied:
                continue
            dist = hex_distance(nb, target.pos)
            if dist > current_dist:
                candidates.append((dist, nb))
        if not candidates:
            return
        candidates.sort(reverse=True)
        _, best = candidates[0]
        unit.pos = best
        self.log.append(f"  {unit} retreats to {best}")

    def _apply_freeze_value(self, unit, freeze_count):
        """Exhaust random ready enemies within attack range after attacking."""
        if freeze_count <= 0:
            return
        candidates = [
            e
            for e in self.units
            if e.alive
            and e.player != unit.player
            and e._frozen_turns == 0
            and not e.has_acted
            and hex_distance(unit.pos, e.pos) <= unit.attack_range
        ]
        if not candidates:
            return
        count = min(freeze_count, len(candidates))
        chosen = self.rng.sample(candidates, count)
        for enemy in chosen:
            enemy._frozen_turns = 1
            self.log.append(f"  {enemy} is frozen")

    def _apply_summon(self, unit, count, ability):
        """Summon units adjacent to the summoner or another target."""
        if count <= 0 or not unit.alive:
            return
        occupied = self._occupied()
        anchor = unit.pos
        if ability.get("summon_target") == "highest":
            allies = [
                a
                for a in self.units
                if a.alive
                and a.player == unit.player
                and hex_distance(unit.pos, a.pos) <= unit.attack_range
            ]
            if allies:
                max_hp = max(a.hp for a in allies)
                candidates = [a for a in allies if a.hp == max_hp]
                anchor = self.rng.choice(candidates).pos
        adj = hex_neighbors(anchor[0], anchor[1], self.COLS, self.ROWS)
        empty = [pos for pos in adj if pos not in occupied]
        summoned = 0
        for _ in range(count):
            if not empty:
                break
            pos = empty.pop(0)
            blade = Unit(
                "Blade",
                1,
                2,
                1,
                unit.player,
                abilities=[],
                unit_id=self._next_unit_id(),
            )
            blade.pos = pos
            blade.has_acted = not ability.get("summon_ready", False)
            blade.summoner_id = unit.id
            self.units.append(blade)
            summoned += 1
        if summoned > 0:
            self.log.append(f"  {unit} summons {summoned} Blade(s)!")

    def _queue_splash_events(self, attacker, target, amount):
        for enemy in list(self.units):
            if (
                enemy.alive
                and enemy.player != attacker.player
                and enemy.id != target.id
                and hex_distance(enemy.pos, target.pos) <= 1
            ):
                self._queue_event(EVENT_SPLASH, attacker, enemy, amount)

    def _shadowstep_destination(self, unit, enemies, occupied):
        """Find a hex adjacent to the furthest enemy unit."""
        if not enemies:
            return None
        distances = [
            (bfs_path_length(unit.pos, e.pos, occupied, self.COLS, self.ROWS), e)
            for e in enemies
        ]
        furthest_dist = max(d for d, _ in distances)
        furthest = [e for d, e in distances if d == furthest_dist]
        target_enemy = self.rng.choice(furthest)
        adj = hex_neighbors(
            target_enemy.pos[0], target_enemy.pos[1], self.COLS, self.ROWS
        )
        empty = [pos for pos in adj if pos not in occupied]
        if not empty:
            return None
        return self.rng.choice(empty)

    def _event_heal(self, target, source, amount):
        healed = min(amount, target.max_hp - target.hp)
        if healed <= 0:
            return
        target.hp += healed
        if source:
            self.log.append(f"  {source} heals {target} for {healed} HP")

    def _event_fortify(self, target, source, amount):
        target.max_hp += amount
        target.hp += amount
        if source:
            self.log.append(f"  {source} fortifies {target} for +{amount} HP")

    def _event_sunder(self, target, source, amount):
        target.armor -= amount
        if source:
            self.log.append(
                f"  {source} sunders {target}'s armor by {amount} (now {target.armor})"
            )

    def _event_splash(self, target, source, amount):
        actual = self._apply_damage(target, amount, source_unit=source)
        if actual > 0:
            self.log.append(f"  Splash hits {target} for {actual} dmg")
            if not target.alive:
                self.log.append(f"  {target.name}(P{target.player}) dies from splash!")

    def _event_bombardment(self, target, source, amount):
        actual = self._apply_damage(target, amount, source_unit=source)
        if actual > 0 and source:
            self.log.append(f"  {source} bombards {target} for {actual} dmg")
            if not target.alive:
                self.log.append(
                    f"  {target.name}(P{target.player}) dies from bombardment!"
                )

    def _event_strike(self, target, source, amount):
        actual = self._apply_damage(target, amount, source_unit=source)
        if actual > 0 and source:
            self.log.append(f"  {source} strikes {target} for {actual} dmg")

    _EVENT_DISPATCH = {
        EVENT_HEAL: _event_heal,
        EVENT_FORTIFY: _event_fortify,
        EVENT_SUNDER: _event_sunder,
        EVENT_SPLASH: _event_splash,
        EVENT_BOMBARDMENT: _event_bombardment,
        EVENT_STRIKE: _event_strike,
    }

    def apply_effect_event(self, event):
        etype = event.get("type")
        target_id = event.get("target_id")
        source_id = event.get("source_id")
        target = next((u for u in self.units if u.id == target_id), None)
        source = next((u for u in self.units if u.id == source_id), None)
        if not target or not target.alive:
            return
        handler = self._EVENT_DISPATCH.get(etype)
        if handler:
            handler(self, target, source, event.get("amount", 0))

    def _apply_queued_events(self):
        if not self.last_action:
            return
        while True:
            for key in _EVENT_KEYS:
                events = self.last_action.get(key, [])
                idx = 0
                while idx < len(events):
                    self.apply_effect_event(events[idx])
                    idx += 1
                if events:
                    self.last_action[key] = []
            if not any(self.last_action.get(key) for key in _EVENT_KEYS):
                break

    def apply_all_events(self, action):
        if not action:
            return
        while True:
            applied_any = False
            for key in _EVENT_KEYS:
                events = action.get(key, [])
                idx = 0
                while idx < len(events):
                    event = events[idx]
                    if not event.get("_applied"):
                        self.apply_effect_event(event)
                        event["_applied"] = True
                        applied_any = True
                    idx += 1
            if not applied_any:
                break

    def _perform_attack(self, unit, enemies_in_range, log_indent=""):
        """Execute an attack against a random enemy in range.

        Args:
            unit: The attacking unit
            enemies_in_range: List of valid targets
            log_indent: Prefix for log messages (e.g., "  " for after-move attacks)

        Returns:
            dict with keys: target, target_pos, ranged, killed, actual_damage
        """
        target = self.rng.choice(enemies_in_range)
        ranged = unit.attack_range > 1
        unit._attacked_this_turn = True

        eff_armor = self._effective_armor(target)
        attack_damage = unit.damage + self._global_boost_bonus(unit.player)
        actual = self._apply_damage(target, attack_damage, source_unit=unit)

        # Log the attack with armor info
        if eff_armor > 0 and actual < attack_damage:
            self.log.append(
                f"{log_indent}{unit} attacks {target} for {actual} dmg "
                f"({eff_armor} blocked by armor)"
            )
        elif eff_armor < 0:
            self.log.append(
                f"{log_indent}{unit} attacks {target} for {actual} dmg "
                f"({-eff_armor} extra from sundered armor)"
            )
        else:
            self.log.append(f"{log_indent}{unit} attacks {target} for {actual} dmg")

        killed = not target.alive
        if killed:
            self.log.append(f"{log_indent}  {target.name}(P{target.player}) dies!")

        # Trigger onhit abilities
        self._trigger_abilities(unit, "onhit", {"target": target, "damage": actual})

        return {
            "target": target,
            "target_pos": target.pos,
            "ranged": ranged,
            "killed": killed,
            "actual_damage": actual,
        }

    def _perform_move(self, unit, enemies):
        """Move unit toward closest enemy, handling speed bonus and shadowstep.

        Args:
            unit: The moving unit
            enemies: List of enemy units

        Returns:
            dict with keys: from_pos, to_pos
        """
        occupied = self._occupied() - {unit.pos}
        old_pos = unit.pos

        # Find closest enemy by path length
        enemy_dists = [
            (bfs_path_length(unit.pos, e.pos, occupied, self.COLS, self.ROWS), e)
            for e in enemies
        ]
        closest_dist = min(d for d, _ in enemy_dists)
        closest = [e for d, e in enemy_dists if d == closest_dist]
        target_enemy = self.rng.choice(closest)

        # Speed bonus roll (consume rng deterministically)
        speed_triggered = unit.speed > 1.0 and self.rng.random() < (unit.speed - 1.0)

        # Calculate normal next step
        next_pos = bfs_next_step(
            unit.pos, target_enemy.pos, occupied, self.COLS, self.ROWS
        )

        # Check for shadowstep ability
        shadowstepped = False
        for idx, ab in enumerate(unit.abilities):
            if ab.get("trigger") == "turnstart" and ab.get("effect") == "shadowstep":
                if self._charge_ready(unit, idx, ab):
                    shadow_pos = self._shadowstep_destination(unit, enemies, occupied)
                    if shadow_pos:
                        unit.pos = shadow_pos
                        shadowstepped = True
                        self.log.append(f"{unit} shadowsteps {old_pos}->{shadow_pos}")
                    break

        if not shadowstepped:
            if speed_triggered:
                enemy_positions = {e.pos for e in enemies}
                all_occupied = self._occupied() - {unit.pos}
                landing, first_step = bfs_speed_move(
                    unit.pos,
                    target_enemy.pos,
                    enemy_positions,
                    all_occupied,
                    self.COLS,
                    self.ROWS,
                )
                unit.pos = first_step
                self.log.append(f"{unit} moves {old_pos}->{first_step}")
                if landing != first_step:
                    mid = first_step
                    unit.pos = landing
                    self.log.append(f"  Speed! {unit} moves extra {mid}->{landing}")
            else:
                unit.pos = next_pos
                self.log.append(f"{unit} moves {old_pos}->{next_pos}")

        return {"from_pos": old_pos, "to_pos": unit.pos}

    def step(self):
        """Execute one unit's turn. Returns True if battle continues.

        Also sets self.last_action to a dict describing what happened:
            {"type": "attack", "attacker_pos": (c,r), "target_pos": (c,r), "ranged": bool, "killed": bool}
            {"type": "move", "from": (c,r), "to": (c,r)}
            {"type": "move_attack", "from": (c,r), "to": (c,r), "target_pos": (c,r), "ranged": bool, "killed": bool}
            None if no action (battle over)
        """
        self._save_state()
        self.last_action = None
        if self.winner is not None:
            return False

        # check win condition
        p1_alive = [u for u in self.units if u.alive and u.player == 1]
        p2_alive = [u for u in self.units if u.alive and u.player == 2]
        if not p1_alive:
            self.winner = 2
            self.log.append("Player 2 wins!")
            return False
        if not p2_alive:
            self.winner = 1
            self.log.append("Player 1 wins!")
            return False

        # advance to next living unit
        while self.current_index < len(self.turn_order):
            unit = self.turn_order[self.current_index]
            if not unit.alive:
                self.current_index += 1
                continue
            if unit._frozen_turns > 0:
                unit._frozen_turns -= 1
                unit.has_acted = True
                self.log.append(f"{unit} is frozen and skips a turn")
                self.current_index += 1
                continue
            break
        else:
            self._new_round()
            return self.step()

        unit._attacked_this_turn = False
        # Start-of-turn abilities
        self._trigger_abilities(unit, "turnstart", {"target": None})
        enemies = [u for u in self.units if u.alive and u.player != unit.player]
        if not enemies:
            self.winner = unit.player
            self.log.append(f"Player {unit.player} wins!")
            return False

        # find enemies in range
        in_range = [
            e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range
        ]

        if in_range:
            result = self._perform_attack(unit, in_range)
            prev_action = self.last_action or {}
            self.last_action = {
                "type": "attack",
                "attacker_pos": unit.pos,
                "target_pos": result["target_pos"],
                "ranged": result["ranged"],
                "killed": result["killed"],
            }
            self.last_action.update(prev_action)
        else:
            move_result = self._perform_move(unit, enemies)
            old = move_result["from_pos"]
            moved_to = move_result["to_pos"]

            # Check if now in range after moving
            in_range = [
                e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range
            ]
            if in_range:
                result = self._perform_attack(unit, in_range, log_indent="  ")
                prev_action = self.last_action or {}
                self.last_action = {
                    "type": "move_attack",
                    "from": old,
                    "to": moved_to,
                    "target_pos": result["target_pos"],
                    "ranged": result["ranged"],
                    "killed": result["killed"],
                }
                self.last_action.update(prev_action)
            else:
                self.last_action = {"type": "move", "from": old, "to": moved_to}

        # End-of-turn abilities
        self._trigger_abilities(unit, "endturn", {"target": None})

        # Check if ready was triggered (allows acting again)
        if unit._ready_triggered:
            unit._ready_triggered = False
            # Don't mark as acted, allowing another turn this round
        else:
            unit.has_acted = True
        self.current_index += 1
        return True

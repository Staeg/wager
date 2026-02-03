import random
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
        self._ramp_accumulated = 0
        self._rage_accumulated = 0
        self._vengeance_accumulated = 0
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
        self.ROWS = self._compute_rows(p1_units, p2_units)
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

    def _compute_rows(self, p1_units, p2_units):
        """Compute map rows so the army with the most frontline units fits them in one column."""

        def _frontline_count(specs):
            if not specs:
                return 0
            # Parse specs to find the minimum range tier and count those units
            parsed = []
            for spec in specs:
                if isinstance(spec, dict):
                    rng = spec["range"]
                    cnt = spec["count"]
                else:
                    # Tuple format: (name, max_hp, damage, range, count, ...)
                    rng = spec[3]
                    cnt = spec[4]
                parsed.append((rng, cnt))
            min_range = min(r for r, _ in parsed)
            return sum(c for r, c in parsed if r == min_range)

        p1_front = _frontline_count(
            p1_units
            or [
                {"name": "Page", "range": 1, "count": 10},
                {"name": "Librarian", "range": 3, "count": 5},
            ]
        )
        p2_front = _frontline_count(
            p2_units
            or [
                {"name": "Apprentice", "range": 2, "count": 10},
                {"name": "Seeker", "range": 4, "count": 5},
            ]
        )
        needed = max(p1_front, p2_front)
        return max(self.MIN_ROWS, min(self.MAX_ROWS, needed))

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
                "_rage_accumulated": u._rage_accumulated,
                "_vengeance_accumulated": u._vengeance_accumulated,
                "_frozen_turns": u._frozen_turns,
                "_ability_counters": dict(u._ability_counters),
                "armor": u.armor,
            }
            unit_states[u.id] = state
        turn_ids = [u.id for u in self.turn_order]
        unit_ids = [u.id for u in self.units]
        rng_state = self.rng.getstate()
        self.history.append(
            (
                unit_states,
                turn_ids,
                unit_ids,
                self.current_index,
                self.round_num,
                list(self.log),
                self.winner,
                rng_state,
                self._stalemate_count,
                self._prev_round_state,
            )
        )

    def undo(self):
        if not self.history:
            return
        (
            unit_states,
            turn_ids,
            unit_ids,
            self.current_index,
            self.round_num,
            self.log,
            self.winner,
            rng_state,
            self._stalemate_count,
            self._prev_round_state,
        ) = self.history.pop()
        self.rng.setstate(rng_state)
        id_to_unit = {u.id: u for u in self.units}
        # Remove units that didn't exist in the saved state (summoned units)
        self.units = [id_to_unit[uid] for uid in unit_ids if uid in id_to_unit]
        for uid, state in unit_states.items():
            u = id_to_unit.get(uid)
            if u is None:
                continue
            u.pos = state["pos"]
            u.hp = state["hp"]
            u.has_acted = state["has_acted"]
            u.damage = state["damage"]
            u._ramp_accumulated = state["_ramp_accumulated"]
            u._rage_accumulated = state["_rage_accumulated"]
            u._vengeance_accumulated = state["_vengeance_accumulated"]
            u._frozen_turns = state.get("_frozen_turns", 0)
            u._ability_counters = dict(state.get("_ability_counters", {}))
            u.armor = state.get("armor", u.armor)
        self.turn_order = [id_to_unit[uid] for uid in turn_ids if uid in id_to_unit]

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
        bonus = 0
        for ally in self.units:
            if not ally.alive or ally.player != unit.player or ally.id == unit.id:
                continue
            for a in ally.abilities:
                if a.get("trigger") == "passive" and a.get("effect") == "amplify":
                    aura_range = self._aura_range(ally, a)
                    if hex_distance(unit.pos, ally.pos) <= aura_range:
                        bonus += a.get("value", 0)
        return base + bonus

    def _effective_armor(self, unit):
        """Return base armor + passive armor on self + aura armor from allies."""
        bonus = 0
        for ab in unit.abilities:
            if (
                ab.get("trigger") == "passive"
                and ab.get("effect") == "armor"
                and not ab.get("aura")
            ):
                bonus += self._ability_value(unit, ab)
        for ally in self.units:
            if ally.alive and ally.player == unit.player and ally.id != unit.id:
                for ab in ally.abilities:
                    if (
                        ab.get("trigger") == "passive"
                        and ab.get("effect") == "armor"
                        and ab.get("aura")
                    ):
                        aura_range = self._aura_range(ally, ab)
                        if hex_distance(unit.pos, ally.pos) <= aura_range:
                            bonus += self._ability_value(ally, ab)
        return unit.armor + bonus

    def _global_boost_bonus(self, player):
        bonus = 0
        for ally in self.units:
            if ally.alive and ally.player == player:
                for ab in ally.abilities:
                    if ab.get("trigger") == "passive" and ab.get("effect") == "boost":
                        bonus += self._ability_value(ally, ab)
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
        if effect in ("heal", "fortify"):
            pool = [
                u
                for u in self.units
                if u.alive
                and u.player == unit.player
                and hex_distance(unit.pos, u.pos) <= rng
                and (effect != "heal" or u.hp < u.max_hp)
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
            etype = "fortify" if effect == "fortify" else "heal"
            self._queue_event(etype, unit, t, value)

    def _exec_sunder(self, unit, ability, context, value):
        targets = self._targets_for_ability(unit, ability, context)
        for t in targets:
            self._queue_event("sunder", unit, t, value, {"source_pos": unit.pos})

    def _exec_strike(self, unit, ability, context, value):
        targets = self._targets_for_ability(unit, ability, context)
        for t in targets:
            self._queue_event("strike", unit, t, value, {"source_pos": unit.pos})

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
            p1_units = [
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
        if p2_units is None:
            p2_units = [
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

        # P1 western zone: cols 0..5, P2 eastern zone: cols 11..16
        west = [(c, r) for c in range(COMBAT_P1_ZONE_END) for r in range(self.ROWS)]
        east = [
            (c, r)
            for c in range(COMBAT_P2_ZONE_START, self.COLS)
            for r in range(self.ROWS)
        ]

        def _assign_with_range_ordering(positions, unit_list, descending_col):
            """Assign positions front-to-back, skipping to next column when range tier changes."""
            from collections import defaultdict
            from itertools import groupby

            by_col = defaultdict(list)
            for c, r in positions:
                by_col[c].append((c, r))
            sorted_cols = sorted(by_col.keys(), reverse=descending_col)
            num_rows = len(by_col[sorted_cols[0]])  # rows per column

            unit_list.sort(key=lambda u: u.attack_range)
            # Shuffle within each range tier to interleave different unit types
            shuffled = []
            for _, group in groupby(unit_list, key=lambda u: u.attack_range):
                tier = list(group)
                self.rng.shuffle(tier)
                shuffled.extend(tier)
            unit_list[:] = shuffled

            # First pass: figure out column boundaries and count units per column
            col_boundaries = []
            for col in sorted_cols:
                col_boundaries.append(len(col_boundaries) * num_rows)

            # Determine which column each unit lands in
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
                is_frontline = ci == 0 or units_per_col.get(ci - 1, 0) == 0
                if is_frontline or k >= num_rows:
                    # Frontline or overflow: center-pack
                    mid = num_rows // 2
                    selected = sorted(
                        rows_in_col, key=lambda r: abs(r - rows_in_col[mid])
                    )[:k]
                else:
                    # Backline: tighter center-pack to reduce spread
                    mid = num_rows // 2
                    selected = sorted(
                        rows_in_col, key=lambda r: abs(r - rows_in_col[mid])
                    )[:k]
                selected.sort()
                col_positions = [(col, r) for r in selected]
                self.rng.shuffle(col_positions)
                flat_positions.extend(col_positions)

            # Assign positions to units
            for i, u in enumerate(unit_list):
                u.pos = flat_positions[i]

        p1_unit_list = []
        for spec in p1_units:
            p1_unit_list.extend(self._parse_unit_spec(spec, 1))
        _assign_with_range_ordering(west, p1_unit_list, descending_col=True)
        self.units.extend(p1_unit_list)

        p2_unit_list = []
        for spec in p2_units:
            p2_unit_list.extend(self._parse_unit_spec(spec, 2))
        _assign_with_range_ordering(east, p2_unit_list, descending_col=False)
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

    def _apply_damage(self, target, amount, source_unit=None):
        """Apply damage to target, handling Block, Armor, Undying, and Rage. Returns actual damage dealt."""
        # Check for passive Block ability
        if not target._silenced:
            for ab in target.abilities:
                if ab.get("trigger") == "passive" and ab.get("effect") == "block":
                    block_value = ab.get("value", 0)
                    if target._block_used < block_value:
                        target._block_used += 1
                        self.log.append(
                            f"  {target} blocks damage! ({target._block_used}/{block_value} blocks used)"
                        )
                        return 0
                    break  # Only one block ability matters

        eff_armor = self._effective_armor(target)
        actual = max(0, amount - eff_armor)
        if actual <= 0:
            return 0
        would_die = target.hp - actual <= 0
        if would_die and target.damage > 0:
            for ally in self.units:
                if ally.alive and ally.player == target.player and ally.id != target.id:
                    for ab in ally.abilities:
                        if (
                            ab.get("trigger") == "passive"
                            and ab.get("effect") == "undying"
                        ):
                            aura_range = self._aura_range(ally, ab)
                            if hex_distance(target.pos, ally.pos) <= aura_range:
                                undying_val = self._ability_value(ally, ab)
                                if target.damage >= undying_val:
                                    target.damage -= undying_val
                                    self.log.append(
                                        f"  {target} saved by Undying! Loses {undying_val} dmg (now {target.damage})"
                                    )
                                    if self.last_action is not None:
                                        self.last_action.setdefault(
                                            "undying_saves", []
                                        ).append(
                                            {"target": target.pos, "source": ally.pos}
                                        )
                                    return 0
        target.hp -= actual
        if target.alive and actual > 0:
            self._trigger_abilities(target, "wounded", {"source": source_unit})
            # Check for Execute: enemies with passive execute can kill low-HP targets
            self._check_execute(target, source_unit)
        if not target.alive:
            self._handle_unit_death(target, source_unit)
        return actual

    def _check_execute(self, target, source_unit):
        """Check if any enemy with Execute can kill this low-HP target."""
        if not target.alive:
            return
        for unit in self.units:
            if not unit.alive or unit.player == target.player:
                continue
            if unit._silenced:
                continue
            for ab in unit.abilities:
                if ab.get("trigger") == "passive" and ab.get("effect") == "execute":
                    aura_range = ab.get("aura", 0)
                    execute_threshold = ab.get("value", 0)
                    if hex_distance(unit.pos, target.pos) <= aura_range:
                        if target.hp <= execute_threshold:
                            self.log.append(
                                f"  {unit} executes {target}! (HP {target.hp} <= {execute_threshold})"
                            )
                            target.hp = 0
                            self._handle_unit_death(target, unit)
                            return  # Target is dead, stop checking

    def _handle_unit_death(self, dead_unit, source_unit=None):
        if source_unit and source_unit.alive:
            self._trigger_abilities(source_unit, "onkill", {"target": dead_unit})
        for unit in self.units:
            if not unit.alive:
                continue
            # Lament: ally deaths within range
            for idx, ab in enumerate(unit.abilities):
                if (
                    ab.get("trigger") == "lament"
                    and unit.player == dead_unit.player
                    and unit.id != dead_unit.id
                ):
                    rng = ab.get("range", unit.attack_range)
                    if hex_distance(unit.pos, dead_unit.pos) <= rng:
                        if self._charge_ready(unit, idx, ab):
                            self._execute_ability(unit, ab, {"dead": dead_unit})
            # Harvest: enemy deaths within range
            for idx, ab in enumerate(unit.abilities):
                if ab.get("trigger") == "harvest" and unit.player != dead_unit.player:
                    rng = ab.get("range", unit.attack_range)
                    if hex_distance(unit.pos, dead_unit.pos) <= rng:
                        if self._charge_ready(unit, idx, ab):
                            self._execute_ability(unit, ab, {"dead": dead_unit})
            # Lament aura: allies within aura range gain ramp when nearby ally dies
            for ab in unit.abilities:
                if ab.get("trigger") == "passive" and ab.get("effect") == "lament_aura":
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
                            ally._vengeance_accumulated += value
                            self.log.append(
                                f"  {ally} gains {value} dmg from Aura Lament (now {ally.damage})"
                            )
                            if self.last_action is not None:
                                self.last_action.setdefault(
                                    "vengeance_positions", []
                                ).append(ally.pos)

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
                self._queue_event("splash", attacker, enemy, amount)

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
        "heal": _event_heal,
        "fortify": _event_fortify,
        "sunder": _event_sunder,
        "splash": _event_splash,
        "bombardment": _event_bombardment,
        "strike": _event_strike,
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
        keys = (
            "heal_events",
            "fortify_events",
            "sunder_events",
            "splash_events",
            "bombardment_events",
            "strike_events",
        )
        while True:
            for key in keys:
                events = self.last_action.get(key, [])
                idx = 0
                while idx < len(events):
                    self.apply_effect_event(events[idx])
                    idx += 1
                if events:
                    self.last_action[key] = []
            if not any(self.last_action.get(key) for key in keys):
                break

    def apply_all_events(self, action):
        if not action:
            return
        keys = (
            "heal_events",
            "fortify_events",
            "sunder_events",
            "splash_events",
            "bombardment_events",
            "strike_events",
        )
        while True:
            applied_any = False
            for key in keys:
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
            target = self.rng.choice(in_range)
            ranged = unit.attack_range > 1
            unit._attacked_this_turn = True
            eff_armor = self._effective_armor(target)
            attack_damage = unit.damage + self._global_boost_bonus(unit.player)
            actual = self._apply_damage(target, attack_damage, source_unit=unit)
            if eff_armor > 0 and actual < attack_damage:
                self.log.append(
                    f"{unit} attacks {target} for {actual} dmg ({eff_armor} blocked by armor)"
                )
            elif eff_armor < 0:
                self.log.append(
                    f"{unit} attacks {target} for {actual} dmg ({-eff_armor} extra from sundered armor)"
                )
            else:
                self.log.append(f"{unit} attacks {target} for {actual} dmg")
            killed = not target.alive
            if killed:
                self.log.append(f"  {target.name}(P{target.player}) dies!")
            self.last_action = {
                "type": "attack",
                "attacker_pos": unit.pos,
                "target_pos": target.pos,
                "ranged": ranged,
                "killed": killed,
            }
            self._trigger_abilities(unit, "onhit", {"target": target, "damage": actual})
        else:
            # move toward closest enemy by actual path length
            occupied = self._occupied() - {unit.pos}
            enemy_dists = [
                (bfs_path_length(unit.pos, e.pos, occupied, self.COLS, self.ROWS), e)
                for e in enemies
            ]
            closest_dist = min(d for d, _ in enemy_dists)
            closest = [e for d, e in enemy_dists if d == closest_dist]
            target_enemy = self.rng.choice(closest)
            # Speed bonus roll (consume rng deterministically)
            speed_triggered = unit.speed > 1.0 and self.rng.random() < (
                unit.speed - 1.0
            )
            next_pos = bfs_next_step(
                unit.pos, target_enemy.pos, occupied, self.COLS, self.ROWS
            )
            old = unit.pos
            shadowstepped = False
            for idx, ab in enumerate(unit.abilities):
                if (
                    ab.get("trigger") == "turnstart"
                    and ab.get("effect") == "shadowstep"
                ):
                    if self._charge_ready(unit, idx, ab):
                        shadow_pos = self._shadowstep_destination(
                            unit, enemies, occupied
                        )
                        if shadow_pos:
                            unit.pos = shadow_pos
                            shadowstepped = True
                            self.log.append(f"{unit} shadowsteps {old}->{shadow_pos}")
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
                    self.log.append(f"{unit} moves {old}->{first_step}")
                    if landing != first_step:
                        mid = first_step
                        unit.pos = landing
                        self.log.append(f"  Speed! {unit} moves extra {mid}->{landing}")
                else:
                    unit.pos = next_pos
                    self.log.append(f"{unit} moves {old}->{next_pos}")
            moved_to = unit.pos

            # check if now in range
            in_range = [
                e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range
            ]
            if in_range:
                target = self.rng.choice(in_range)
                ranged = unit.attack_range > 1
                unit._attacked_this_turn = True
                eff_armor = self._effective_armor(target)
                attack_damage = unit.damage + self._global_boost_bonus(unit.player)
                actual = self._apply_damage(target, attack_damage, source_unit=unit)
                if eff_armor > 0 and actual < attack_damage:
                    self.log.append(
                        f"  {unit} attacks {target} for {actual} dmg ({eff_armor} blocked by armor)"
                    )
                elif eff_armor < 0:
                    self.log.append(
                        f"  {unit} attacks {target} for {actual} dmg ({-eff_armor} extra from sundered armor)"
                    )
                else:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg")
                killed = not target.alive
                if killed:
                    self.log.append(f"  {target.name}(P{target.player}) dies!")
                self.last_action = {
                    "type": "move_attack",
                    "from": old,
                    "to": moved_to,
                    "target_pos": target.pos,
                    "ranged": ranged,
                    "killed": killed,
                }
                self._trigger_abilities(
                    unit, "onhit", {"target": target, "damage": actual}
                )
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

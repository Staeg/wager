import tkinter as tk
import math
import random
import os
import sys
from PIL import Image, ImageTk, ImageEnhance

# --- Hex grid utilities (offset coordinates, even-r) ---

def offset_to_cube(col, row):
    x = col - (row - (row % 2)) // 2
    z = row
    y = -x - z
    return x, y, z

def cube_distance(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]), abs(a[2]-b[2]))

def hex_distance(c1, c2):
    return cube_distance(offset_to_cube(*c1), offset_to_cube(*c2))

def hex_neighbors(col, row, cols, rows):
    parity = row % 2
    if parity == 0:
        dirs = [(1,0),(-1,0),(0,-1),(0,1),(-1,-1),(-1,1)]
    else:
        dirs = [(1,0),(-1,0),(0,-1),(0,1),(1,-1),(1,1)]
    results = []
    for dc, dr in dirs:
        nc, nr = col+dc, row+dr
        if 0 <= nc < cols and 0 <= nr < rows:
            results.append((nc, nr))
    return results


# --- Pathfinding (BFS on hex grid, avoiding occupied hexes) ---

def bfs_next_step(start, goal, occupied, cols, rows):
    """Return the next hex to move to from start toward goal, avoiding occupied hexes.
    If no full path exists, moves to the unoccupied neighbor closest to goal by hex distance."""
    from collections import deque
    if start == goal:
        return start
    queue = deque()
    queue.append((start, [start]))
    visited = {start}
    while queue:
        current, path = queue.popleft()
        for nb in hex_neighbors(current[0], current[1], cols, rows):
            if nb in visited:
                continue
            visited.add(nb)
            new_path = path + [nb]
            if nb == goal:
                return new_path[1]
            if nb not in occupied:
                queue.append((nb, new_path))
    # No full path found — move to the adjacent unoccupied hex closest to goal
    best = start
    best_dist = hex_distance(start, goal)
    for nb in hex_neighbors(start[0], start[1], cols, rows):
        if nb not in occupied:
            d = hex_distance(nb, goal)
            if d < best_dist:
                best_dist = d
                best = nb
    return best


def bfs_path_length(start, goal, occupied, cols, rows):
    """Return the BFS path length from start to goal, avoiding occupied hexes.
    The goal itself is allowed even if occupied. Returns a large number if no path."""
    from collections import deque
    if start == goal:
        return 0
    queue = deque()
    queue.append((start, 0))
    visited = {start}
    while queue:
        current, dist = queue.popleft()
        for nb in hex_neighbors(current[0], current[1], cols, rows):
            if nb in visited:
                continue
            visited.add(nb)
            if nb == goal:
                return dist + 1
            if nb not in occupied:
                queue.append((nb, dist + 1))
    return 9999


# --- Game classes ---

class Unit:
    _id_counter = 0

    # All known ability keys (for save/restore)
    ABILITY_KEYS = ("armor", "heal", "sunder", "push", "ramp", "amplify",
                    "undying", "splash", "repair", "bombardment", "bombardment_range",
                    "rage", "vengeance", "charge", "summon_count")

    def __init__(self, name, max_hp, damage, attack_range, player, **abilities):
        Unit._id_counter += 1
        self.id = Unit._id_counter
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.attack_range = attack_range
        self.player = player
        # Abilities — all default to 0
        for key in Unit.ABILITY_KEYS:
            setattr(self, key, abilities.get(key, 0))
        self._ramp_accumulated = 0
        self._rage_accumulated = 0
        self._vengeance_accumulated = 0
        self._charge_counter = 0
        self.pos = None
        self.has_acted = False
        # For summoned units tracking
        self.summoner_id = None

    @property
    def alive(self):
        return self.hp > 0

    def __repr__(self):
        return f"{self.name}(P{self.player} HP:{self.hp}/{self.max_hp})"


class Battle:
    COLS = 17
    MIN_ROWS = 5
    MAX_ROWS = 15

    def __init__(self, p1_units=None, p2_units=None, rng_seed=None):
        """Initialize battle.

        p1_units/p2_units: optional list of unit specs (tuples or dicts).
        If None, uses default hardcoded armies.
        rng_seed: optional int seed for deterministic battles.
        """
        self._init_p1_units = p1_units
        self._init_p2_units = p2_units
        self.rng_seed = rng_seed
        if rng_seed is not None:
            random.seed(rng_seed)
        self._init_rng_state = random.getstate()
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

    def _compute_rows(self, p1_units, p2_units):
        """Compute map rows so the army with the most frontline units fits them in one column."""
        def _frontline_count(specs):
            if not specs:
                return 0
            # Parse specs to find the minimum range tier and count those units
            parsed = []
            for spec in specs:
                if isinstance(spec, dict):
                    parsed.append((spec["range"], spec["count"]))
                else:
                    parsed.append((spec[3], spec[4]))
            min_range = min(r for r, _ in parsed)
            return sum(c for r, c in parsed if r == min_range)

        p1_front = _frontline_count(p1_units or [
            {"name": "Page", "range": 1, "count": 10},
            {"name": "Librarian", "range": 3, "count": 5},
        ])
        p2_front = _frontline_count(p2_units or [
            {"name": "Apprentice", "range": 2, "count": 10},
            {"name": "Seeker", "range": 4, "count": 5},
        ])
        needed = max(p1_front, p2_front)
        return max(self.MIN_ROWS, min(self.MAX_ROWS, needed))

    def _save_state(self):
        unit_states = {}
        for u in self.units:
            state = {
                "pos": u.pos, "hp": u.hp, "has_acted": u.has_acted,
                "damage": u.damage, "_ramp_accumulated": u._ramp_accumulated,
                "_rage_accumulated": u._rage_accumulated,
                "_vengeance_accumulated": u._vengeance_accumulated,
                "_charge_counter": u._charge_counter,
            }
            for key in Unit.ABILITY_KEYS:
                state[key] = getattr(u, key)
            unit_states[u.id] = state
        turn_ids = [u.id for u in self.turn_order]
        unit_ids = [u.id for u in self.units]
        rng_state = random.getstate()
        self.history.append((unit_states, turn_ids, unit_ids, self.current_index,
                             self.round_num, list(self.log), self.winner, rng_state,
                             self._stalemate_count, self._prev_round_state))

    def undo(self):
        if not self.history:
            return
        unit_states, turn_ids, unit_ids, self.current_index, self.round_num, self.log, self.winner, rng_state, self._stalemate_count, self._prev_round_state = self.history.pop()
        random.setstate(rng_state)
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
            u._charge_counter = state["_charge_counter"]
            for key in Unit.ABILITY_KEYS:
                setattr(u, key, state[key])
        self.turn_order = [id_to_unit[uid] for uid in turn_ids if uid in id_to_unit]

    def _effective_ability(self, unit, ability_name):
        """Return base ability value + sum of amplify from adjacent alive allies."""
        base = getattr(unit, ability_name, 0)
        if base == 0:
            return 0
        bonus = 0
        for ally in self.units:
            if ally.alive and ally.player == unit.player and ally.id != unit.id and ally.amplify > 0:
                if hex_distance(unit.pos, ally.pos) <= 1:
                    bonus += ally.amplify
        return base + bonus

    @staticmethod
    def _parse_unit_spec(spec, player):
        """Parse a unit spec (tuple or dict) into Unit instances.

        Tuple format (legacy): (name, max_hp, damage, range, count, ...)
        Dict format: {"name": str, "max_hp": int, "damage": int, "range": int, "count": int, ...abilities}
        """
        units = []
        if isinstance(spec, dict):
            name = spec["name"]
            max_hp = spec["max_hp"]
            damage = spec["damage"]
            atk_range = spec["range"]
            count = spec["count"]
            abilities = {k: v for k, v in spec.items()
                         if k not in ("name", "max_hp", "damage", "range", "count", "value")}
            for _ in range(count):
                units.append(Unit(name, max_hp, damage, atk_range, player, **abilities))
        else:
            tup = spec
            name, max_hp, damage, atk_range, count = tup[:5]
            # Legacy positional: armor, heal, sunder, push, ramp, amplify
            legacy_keys = ("armor", "heal", "sunder", "push", "ramp", "amplify")
            abilities = {}
            for i, key in enumerate(legacy_keys):
                if len(tup) > 5 + i:
                    abilities[key] = tup[5 + i]
            for _ in range(count):
                units.append(Unit(name, max_hp, damage, atk_range, player, **abilities))
        return units

    def _setup_armies(self, p1_units=None, p2_units=None):
        if p1_units is None:
            p1_units = [
                {"name": "Page", "max_hp": 3, "damage": 1, "range": 1, "count": 10},
                {"name": "Librarian", "max_hp": 2, "damage": 0, "range": 3, "count": 5, "sunder": 1},
            ]
        if p2_units is None:
            p2_units = [
                {"name": "Apprentice", "max_hp": 8, "damage": 1, "range": 2, "count": 10, "push": 1},
                {"name": "Seeker", "max_hp": 3, "damage": 1, "range": 4, "count": 5, "ramp": 1},
            ]

        # P1 western zone: cols 0..5, P2 eastern zone: cols 11..16
        west = [(c, r) for c in range(6) for r in range(self.ROWS)]
        east = [(c, r) for c in range(11, self.COLS) for r in range(self.ROWS)]

        def _assign_with_range_ordering(positions, unit_list, descending_col):
            """Assign positions front-to-back, skipping to next column when range tier changes."""
            from collections import defaultdict
            by_col = defaultdict(list)
            for c, r in positions:
                by_col[c].append((c, r))
            for col_positions in by_col.values():
                random.shuffle(col_positions)
            sorted_cols = sorted(by_col.keys(), reverse=descending_col)

            flat_positions = []
            col_boundaries = []
            for col in sorted_cols:
                col_boundaries.append(len(flat_positions))
                flat_positions.extend(by_col[col])

            unit_list.sort(key=lambda u: u.attack_range)
            # Shuffle within each range tier to interleave different unit types
            from itertools import groupby
            shuffled = []
            for _, group in groupby(unit_list, key=lambda u: u.attack_range):
                tier = list(group)
                random.shuffle(tier)
                shuffled.extend(tier)
            unit_list[:] = shuffled
            pos_i = 0
            prev_range = None
            for u in unit_list:
                if prev_range is not None and u.attack_range != prev_range:
                    for b in col_boundaries:
                        if b > pos_i:
                            pos_i = b
                            break
                u.pos = flat_positions[pos_i]
                pos_i += 1
                prev_range = u.attack_range

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
        return frozenset((u.id, u.hp, u.pos, u.armor, u.damage, len(self.units)) for u in self.units if u.alive)

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
        random.shuffle(alive)
        self.turn_order = alive
        self.current_index = 0
        self.round_num += 1
        for u in alive:
            u.has_acted = False
        self.log.append(f"--- Round {self.round_num} ---")

    def _occupied(self):
        return {u.pos for u in self.units if u.alive}

    def _apply_damage(self, target, amount, source_unit=None):
        """Apply damage to target, handling Armor, Undying, and Rage. Returns actual damage dealt."""
        actual = max(0, amount - target.armor)
        if actual <= 0:
            return 0
        would_die = target.hp - actual <= 0
        if would_die and target.damage > 0:
            # Check for Undying aura from allies
            for ally in self.units:
                if (ally.alive and ally.player == target.player and ally.id != target.id
                        and ally.undying > 0):
                    dist = hex_distance(target.pos, ally.pos)
                    # Undying has an aura range (stored as undying_range via the aura range)
                    # The doc says "Aura 2 - Undying 2": aura range is 2
                    # We use the Gatekeeper's attack_range or a fixed 2 for the aura
                    # Actually the doc says "ally within 2 hexes", so undying value is the
                    # damage reduction, and aura range is always 2 for Gatekeeper
                    aura_range = 2  # Undying aura range
                    if dist <= aura_range and target.damage >= 2:
                        # Instead of dying, lose 2 attack damage
                        target.damage -= 2
                        self.log.append(f"  {target} saved by Undying! Loses 2 dmg (now {target.damage})")
                        if self.last_action is not None:
                            self.last_action.setdefault("undying_saves", []).append(
                                {"target": target.pos, "source": ally.pos})
                        return 0
        target.hp -= actual
        # Rage: gain damage when taking damage
        if target.alive and target.rage > 0 and actual > 0:
            eff_rage = self._effective_ability(target, "rage")
            target.damage += eff_rage
            target._rage_accumulated += eff_rage
            self.log.append(f"  {target} rages! +{eff_rage} dmg (now {target.damage})")
            if self.last_action is not None:
                self.last_action.setdefault("rage_positions", []).append(target.pos)
        return actual

    def _check_vengeance(self, dead_unit):
        """When a unit dies, adjacent allies with vengeance gain damage."""
        if not dead_unit.pos:
            return
        for ally in self.units:
            if (ally.alive and ally.player == dead_unit.player and ally.id != dead_unit.id
                    and ally.vengeance > 0 and hex_distance(ally.pos, dead_unit.pos) <= 1):
                eff = self._effective_ability(ally, "vengeance")
                ally.damage += eff
                ally._vengeance_accumulated += eff
                self.log.append(f"  {ally} gains {eff} dmg from Vengeance (now {ally.damage})")
                if self.last_action is not None:
                    self.last_action.setdefault("vengeance_positions", []).append(ally.pos)

    def _apply_push(self, attacker, target):
        """Push target N hexes horizontally away from attacker after attacking."""
        push_val = self._effective_ability(attacker, "push")
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

    def _apply_ramp(self, unit, damage_dealt):
        """Increase unit's damage after a successful attack."""
        ramp_val = self._effective_ability(unit, "ramp")
        if ramp_val <= 0 or damage_dealt <= 0:
            return
        unit.damage += ramp_val
        unit._ramp_accumulated += ramp_val
        self.log.append(f"  {unit} ramps damage by {ramp_val} (now {unit.damage})")
        if self.last_action is not None:
            self.last_action["ramp_pos"] = unit.pos

    def _apply_splash(self, attacker, target):
        """Deal splash damage to all enemies adjacent to the attack target."""
        splash_val = self._effective_ability(attacker, "splash")
        if splash_val <= 0:
            return
        for enemy in list(self.units):
            if (enemy.alive and enemy.player != attacker.player
                    and enemy.id != target.id
                    and hex_distance(enemy.pos, target.pos) <= 1):
                actual = self._apply_damage(enemy, splash_val)
                if actual > 0:
                    self.log.append(f"  Splash hits {enemy} for {actual} dmg")
                    if self.last_action is not None:
                        self.last_action.setdefault("splash_positions", []).append(enemy.pos)
                    if not enemy.alive:
                        self.log.append(f"  {enemy.name}(P{enemy.player}) dies from splash!")
                        self._check_vengeance(enemy)

    def _apply_repair(self, unit):
        """Heal all adjacent allies by repair value."""
        repair_val = self._effective_ability(unit, "repair")
        if repair_val <= 0 or not unit.alive:
            return
        for ally in self.units:
            if (ally.alive and ally.player == unit.player and ally.id != unit.id
                    and ally.hp < ally.max_hp and hex_distance(unit.pos, ally.pos) <= 1):
                healed = min(repair_val, ally.max_hp - ally.hp)
                ally.hp += healed
                self.log.append(f"  {unit} repairs {ally} for {healed} HP")
                if self.last_action is not None:
                    self.last_action.setdefault("repair_positions", []).append(ally.pos)

    def _apply_bombardment(self, unit):
        """Deal bombardment damage to a random enemy within bombardment_range."""
        bomb_val = self._effective_ability(unit, "bombardment")
        if bomb_val <= 0 or not unit.alive:
            return
        bomb_range = unit.bombardment_range if unit.bombardment_range > 0 else 6
        enemies_in_range = [e for e in self.units if e.alive and e.player != unit.player
                            and hex_distance(unit.pos, e.pos) <= bomb_range]
        if enemies_in_range:
            bomb_target = random.choice(enemies_in_range)
            actual = self._apply_damage(bomb_target, bomb_val)
            if actual > 0:
                self.log.append(f"  {unit} bombards {bomb_target} for {actual} dmg")
                if not bomb_target.alive:
                    self.log.append(f"  {bomb_target.name}(P{bomb_target.player}) dies from bombardment!")
                    self._check_vengeance(bomb_target)
                if self.last_action is None:
                    self.last_action = {}
                self.last_action["bombardment_pos"] = bomb_target.pos
                self.last_action["bombardment_src"] = unit.pos

    def _apply_charge_summon(self, unit):
        """Every N turns, summon units adjacent to the summoner."""
        if unit.charge <= 0 or unit.summon_count <= 0 or not unit.alive:
            return
        unit._charge_counter += 1
        if unit._charge_counter < unit.charge:
            return
        unit._charge_counter = 0
        # Find empty adjacent hexes
        occupied = self._occupied()
        adj = hex_neighbors(unit.pos[0], unit.pos[1], self.COLS, self.ROWS)
        empty = [pos for pos in adj if pos not in occupied]
        summoned = 0
        for _ in range(unit.summon_count):
            if not empty:
                break
            pos = empty.pop(0)
            blade = Unit("Blade", 1, 2, 1, unit.player)
            blade.pos = pos
            blade.has_acted = True  # summoned exhausted
            blade.summoner_id = unit.id
            self.units.append(blade)
            summoned += 1
        if summoned > 0:
            self.log.append(f"  {unit} summons {summoned} Blade(s)!")

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
            if unit.alive:
                break
            self.current_index += 1
        else:
            self._new_round()
            return self.step()

        enemies = [u for u in self.units if u.alive and u.player != unit.player]
        if not enemies:
            self.winner = unit.player
            self.log.append(f"Player {unit.player} wins!")
            return False

        # find enemies in range
        in_range = [e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range]

        if in_range:
            target = random.choice(in_range)
            ranged = unit.attack_range > 1
            actual = self._apply_damage(target, unit.damage)
            if target.armor > 0 and actual < unit.damage:
                self.log.append(f"{unit} attacks {target} for {actual} dmg ({target.armor} blocked by armor)")
            elif target.armor < 0:
                self.log.append(f"{unit} attacks {target} for {actual} dmg ({-target.armor} extra from sundered armor)")
            else:
                self.log.append(f"{unit} attacks {target} for {actual} dmg")
            killed = not target.alive
            if killed:
                self.log.append(f"  {target.name}(P{target.player}) dies!")
                self._check_vengeance(target)
            self.last_action = {
                "type": "attack", "attacker_pos": unit.pos, "target_pos": target.pos,
                "ranged": ranged, "killed": killed,
            }
            self._apply_push(unit, target)
            self._apply_ramp(unit, actual)
            self._apply_splash(unit, target)
        else:
            # move toward closest enemy by actual path length
            occupied = self._occupied() - {unit.pos}
            enemy_dists = [(bfs_path_length(unit.pos, e.pos, occupied, self.COLS, self.ROWS), e) for e in enemies]
            closest_dist = min(d for d, _ in enemy_dists)
            closest = [e for d, e in enemy_dists if d == closest_dist]
            target_enemy = random.choice(closest)
            next_pos = bfs_next_step(unit.pos, target_enemy.pos, occupied, self.COLS, self.ROWS)
            old = unit.pos
            unit.pos = next_pos
            self.log.append(f"{unit} moves {old}->{next_pos}")

            # check if now in range
            in_range = [e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range]
            if in_range:
                target = random.choice(in_range)
                ranged = unit.attack_range > 1
                actual = self._apply_damage(target, unit.damage)
                if target.armor > 0 and actual < unit.damage:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg ({target.armor} blocked by armor)")
                elif target.armor < 0:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg ({-target.armor} extra from sundered armor)")
                else:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg")
                killed = not target.alive
                if killed:
                    self.log.append(f"  {target.name}(P{target.player}) dies!")
                    self._check_vengeance(target)
                self.last_action = {
                    "type": "move_attack", "from": old, "to": next_pos,
                    "target_pos": target.pos, "ranged": ranged, "killed": killed,
                }
                self._apply_push(unit, target)
                self._apply_ramp(unit, actual)
                self._apply_splash(unit, target)
            else:
                self.last_action = {"type": "move", "from": old, "to": next_pos}

        # Heal ability
        if unit.heal > 0 and unit.alive:
            allies = [a for a in self.units if a.alive and a.player == unit.player
                      and a.hp < a.max_hp and hex_distance(unit.pos, a.pos) <= unit.attack_range]
            if allies:
                heal_target = random.choice(allies)
                healed = min(unit.heal, heal_target.max_hp - heal_target.hp)
                heal_target.hp += healed
                self.log.append(f"  {unit} heals {heal_target} for {healed} HP")
                if self.last_action is None:
                    self.last_action = {}
                self.last_action["heal_pos"] = heal_target.pos

        # Sunder ability (reduce target armor)
        if unit.sunder > 0 and unit.alive:
            enemies_in_range = [e for e in self.units if e.alive and e.player != unit.player
                                and hex_distance(unit.pos, e.pos) <= unit.attack_range]
            if enemies_in_range:
                sunder_target = random.choice(enemies_in_range)
                sunder_target.armor -= unit.sunder
                self.log.append(f"  {unit} sunders {sunder_target}'s armor by {unit.sunder} (now {sunder_target.armor})")
                if self.last_action is None:
                    self.last_action = {}
                self.last_action["sunder_pos"] = sunder_target.pos
                self.last_action["sunder_src"] = unit.pos

        # Repair ability (heal all adjacent allies)
        self._apply_repair(unit)

        # Bombardment ability (extra ranged damage)
        self._apply_bombardment(unit)

        # Charge / Summon ability
        self._apply_charge_summon(unit)

        unit.has_acted = True
        self.current_index += 1
        return True



# --- GUI ---

ABILITY_DESCRIPTIONS = {
    "armor": "Reduces incoming damage by {value}",
    "heal": "Heals a random ally in range for {value} HP per turn",
    "sunder": "Reduces a random enemy's armor in range by {value} after attacking",
    "push": "Pushes the target {value} hex(es) away horizontally after attacking",
    "ramp": "Increases damage by {value} after each successful attack",
    "amplify": "Increases adjacent allies' ability values by {value}",
    "undying": "Allies within 2 hexes lose {value} attack instead of dying",
    "splash": "Deals {value} damage to all enemies adjacent to the target after attacking",
    "repair": "Heals all adjacent allies by {value} at end of turn",
    "bombardment": "Deals {value} damage to a random enemy in range at end of turn",
    "rage": "Gains {value} attack damage after taking damage",
    "vengeance": "Gains {value} attack damage when an adjacent ally dies",
    "charge": "Every {value} turns, summons Blades adjacent to this unit",
}


class CombatGUI:
    HEX_SIZE = 32

    def __init__(self, root, battle=None, on_complete=None):
        self.root = root
        try:
            root.title("Wager of War v3 - Combat")
        except AttributeError:
            pass
        self.battle = battle if battle is not None else Battle()
        self.on_complete = on_complete

        # layout
        top = tk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.step_btn = tk.Button(top, text="Step", command=self.on_step, font=("Arial", 12))
        self.step_btn.pack(side=tk.LEFT)

        self.auto_btn = tk.Button(top, text="Auto", command=self.toggle_auto, font=("Arial", 12))
        self.auto_btn.pack(side=tk.LEFT, padx=5)

        # Speed controls
        self.speed_levels = [(300, "0.3x"), (200, "0.5x"), (100, "1x"), (50, "2x"), (25, "4x")]
        self.speed_index = 2
        self.auto_delay = self.speed_levels[self.speed_index][0]

        self.speed_down_btn = tk.Button(top, text="-", command=self._speed_down, font=("Arial", 12), width=2)
        self.speed_down_btn.pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value=self.speed_levels[self.speed_index][1])
        tk.Label(top, textvariable=self.speed_var, font=("Arial", 11), width=4).pack(side=tk.LEFT)
        self.speed_up_btn = tk.Button(top, text="+", command=self._speed_up, font=("Arial", 12), width=2)
        self.speed_up_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.undo_btn = tk.Button(top, text="Undo", command=self.on_undo, font=("Arial", 12))
        self.undo_btn.pack(side=tk.LEFT, padx=5)

        self.skip_btn = tk.Button(top, text="Skip", command=self.on_skip, font=("Arial", 12))
        self.skip_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = tk.Button(top, text="Reset", command=self.on_reset, font=("Arial", 12))
        self.reset_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Round 1")
        tk.Label(top, textvariable=self.status_var, font=("Arial", 12)).pack(side=tk.LEFT, padx=15)

        self.score_var = tk.StringVar()
        tk.Label(top, textvariable=self.score_var, font=("Arial", 11)).pack(side=tk.RIGHT)

        canvas_w = self._hex_x(self.battle.COLS, 0) + self.HEX_SIZE + 20
        canvas_h = self._hex_y(0, self.battle.ROWS) + self.HEX_SIZE + 20
        self.canvas = tk.Canvas(root, width=canvas_w, height=canvas_h, bg="#2b2b2b")
        self.canvas.pack(padx=5, pady=5)

        self.log_btn = tk.Button(top, text="Log", command=self._toggle_log, font=("Arial", 12))
        self.log_btn.pack(side=tk.LEFT, padx=5)

        self._log_window = None
        self.log_text = None

        self.return_btn = None
        self.auto_running = False
        self._tooltip = None
        self._tooltip_unit = None
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        root.bind("<KeyRelease-Shift_L>", self._on_shift_release)
        root.bind("<KeyRelease-Shift_R>", self._on_shift_release)
        self._load_sprites()
        self._draw()

    def _load_sprites(self):
        if getattr(sys, 'frozen', False):
            asset_dir = os.path.join(sys._MEIPASS, "assets")
        else:
            asset_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        self._sprite_imgs = {}
        for name in ("footman", "archer", "priest", "knight", "mage",
                     "page", "librarian", "steward", "gatekeeper",
                     "apprentice", "conduit", "seeker", "savant",
                     "tincan", "golem", "kitboy", "artillery",
                     "penitent", "avenger", "herald", "blade"):
            img = Image.open(os.path.join(asset_dir, f"{name}.png")).convert("RGBA")
            bright = img
            faded = ImageEnhance.Brightness(img).enhance(0.5)
            self._sprite_imgs[name] = (bright, faded)
        self._sprite_cache = {}

    def _get_sprite(self, name, faded):
        key = (name, faded)
        if key not in self._sprite_cache:
            img = self._sprite_imgs[name][1 if faded else 0]
            self._sprite_cache[key] = ImageTk.PhotoImage(img)
        return self._sprite_cache[key]

    def _hex_x(self, col, row):
        x = self.HEX_SIZE * 1.75 * col + 30
        if row % 2 == 1:
            x += self.HEX_SIZE * 0.875
        return x

    def _hex_y(self, col, row):
        return self.HEX_SIZE * 1.5 * row + 30

    def _hex_polygon(self, cx, cy):
        points = []
        for i in range(6):
            angle = math.radians(60 * i + 30)
            points.append(cx + self.HEX_SIZE * 0.85 * math.cos(angle))
            points.append(cy + self.HEX_SIZE * 0.85 * math.sin(angle))
        return points

    def _draw(self):
        self.canvas.delete("all")
        b = self.battle

        # draw grid
        for r in range(b.ROWS):
            for c in range(b.COLS):
                cx = self._hex_x(c, r)
                cy = self._hex_y(c, r)
                if c < 6:
                    fill = "#3a3a5c"
                elif c >= 11:
                    fill = "#5c3a3a"
                else:
                    fill = "#3a3a3a"
                self.canvas.create_polygon(self._hex_polygon(cx, cy), fill=fill, outline="#555")

        # draw aura glows behind units
        for u in b.units:
            if not u.alive:
                continue
            aura_range = 0
            aura_color = ""
            if u.amplify > 0:
                aura_range = 1
                aura_color = "#8844cc"  # purple for amplify
            elif u.undying > 0:
                aura_range = 2
                aura_color = "#ccaa22"  # gold for undying
            if aura_range > 0:
                # Draw faint highlight on all hexes within aura range
                for r2 in range(b.ROWS):
                    for c2 in range(b.COLS):
                        if hex_distance(u.pos, (c2, r2)) <= aura_range and (c2, r2) != u.pos:
                            ax = self._hex_x(c2, r2)
                            ay = self._hex_y(c2, r2)
                            self.canvas.create_polygon(
                                self._hex_polygon(ax, ay),
                                fill="", outline=aura_color, width=2, stipple="gray25",
                            )

        # draw units
        self._sprite_refs = []  # prevent GC
        for u in b.units:
            if not u.alive:
                continue
            cx = self._hex_x(u.pos[0], u.pos[1])
            cy = self._hex_y(u.pos[0], u.pos[1])
            sprite_name = u.name.lower()
            sprite = self._get_sprite(sprite_name, u.has_acted)
            self._sprite_refs.append(sprite)
            self.canvas.create_image(cx, cy, image=sprite)

            # HP bar
            bar_w = self.HEX_SIZE * 0.7
            bar_h = 4
            hp_frac = u.hp / u.max_hp
            bx = cx - bar_w/2
            by = cy - 18
            self.canvas.create_rectangle(bx, by, bx+bar_w, by+bar_h, fill="#333", outline="")
            bar_color = "#44ff44" if hp_frac > 0.5 else "#ffaa00" if hp_frac > 0.25 else "#ff4444"
            self.canvas.create_rectangle(bx, by, bx+bar_w*hp_frac, by+bar_h, fill=bar_color, outline="")

        # update status
        p1_counts = {}
        p2_counts = {}
        for u in b.units:
            if not u.alive:
                continue
            d = p1_counts if u.player == 1 else p2_counts
            d[u.name] = d.get(u.name, 0) + 1
        p1_str = "  ".join(f"{n}:{c}" for n, c in p1_counts.items())
        p2_str = "  ".join(f"{n}:{c}" for n, c in p2_counts.items())
        self.score_var.set(f"P1 [{p1_str}]  |  P2 [{p2_str}]")
        if b.winner is not None:
            if b.winner == 0:
                self.status_var.set("Stalemate - Draw!")
            else:
                self.status_var.set(f"Player {b.winner} wins!")
            if self.on_complete and not self.return_btn:
                p1_survivors = sum(1 for u in b.units if u.alive and u.player == 1)
                p2_survivors = sum(1 for u in b.units if u.alive and u.player == 2)
                self.return_btn = tk.Button(
                    self.canvas, text="Return to Overworld", font=("Arial", 14),
                    command=lambda: self.on_complete(b.winner, p1_survivors, p2_survivors)
                )
                self.canvas.create_window(
                    self.canvas.winfo_reqwidth() // 2,
                    self.canvas.winfo_reqheight() // 2,
                    window=self.return_btn
                )
        else:
            self.status_var.set(f"Round {b.round_num}")

        # update log
        self._update_log_display()

    def _unit_at_pixel(self, px, py):
        """Return the unit closest to pixel coords, if within hex radius."""
        best_unit = None
        best_dist = float("inf")
        for u in self.battle.units:
            if not u.alive:
                continue
            cx = self._hex_x(u.pos[0], u.pos[1])
            cy = self._hex_y(u.pos[0], u.pos[1])
            d = math.hypot(px - cx, py - cy)
            if d < self.HEX_SIZE * 0.8 and d < best_dist:
                best_dist = d
                best_unit = u
        return best_unit

    def _on_hover(self, event):
        unit = self._unit_at_pixel(event.x, event.y)
        shift_held = event.state & 0x1
        if unit:
            if self._tooltip_unit is unit and self._tooltip is not None:
                if not shift_held:
                    self._tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
                return
            self._hide_tooltip()
            self._tooltip_unit = unit
            self._tooltip = tw = tk.Toplevel(self.root)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
            tw.configure(bg="#222")

            main_text = f"{unit.name} (P{unit.player})  HP: {unit.hp}/{unit.max_hp}  Dmg:{unit.damage}  Rng:{unit.attack_range}"
            tk.Label(tw, text=main_text, fg="white", bg="#222",
                     font=("Arial", 10, "bold"), padx=6, pady=2).pack(anchor="w")

            abilities = []
            for ab_key in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                           "undying", "splash", "repair", "bombardment",
                           "rage", "vengeance", "charge"):
                val = getattr(unit, ab_key, 0)
                if val > 0 and ab_key in ABILITY_DESCRIPTIONS:
                    abilities.append((ab_key, val))

            if abilities:
                row = tk.Frame(tw, bg="#222")
                row.pack(anchor="w", padx=4, pady=(0, 2))
                for ability_name, value in abilities:
                    lbl = tk.Label(row, text=f"{ability_name.capitalize()}:{value}",
                                   fg="#aaffaa", bg="#333", font=("Arial", 9),
                                   padx=4, pady=1, relief=tk.RAISED, borderwidth=1)
                    lbl.pack(side=tk.LEFT, padx=2)
                    desc = ABILITY_DESCRIPTIONS[ability_name].format(value=value)
                    self._bind_ability_hover(lbl, tw, desc)
        else:
            if not shift_held:
                self._hide_tooltip()

    def _bind_ability_hover(self, label, parent, description):
        sub_tip = [None]
        def on_enter(e):
            sub_tip[0] = st = tk.Toplevel(parent)
            st.wm_overrideredirect(True)
            st.wm_geometry(f"+{e.x_root + 10}+{e.y_root + 18}")
            tk.Label(st, text=description, fg="white", bg="#444",
                     font=("Arial", 9), padx=4, pady=2).pack()
        def on_leave(e):
            if sub_tip[0]:
                sub_tip[0].destroy()
                sub_tip[0] = None
        label.bind("<Enter>", on_enter)
        label.bind("<Leave>", on_leave)

    def _on_leave(self, event):
        shift_held = event.state & 0x1
        if not shift_held:
            self._hide_tooltip()

    def _on_shift_release(self, event):
        # Check if cursor is still over a unit
        try:
            mx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            my = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            if not self._unit_at_pixel(mx, my):
                self._hide_tooltip()
        except Exception:
            self._hide_tooltip()

    def _update_log_display(self):
        if self.log_text is None:
            return
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            for line in self.battle.log[-50:]:
                self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        except tk.TclError:
            pass  # window was closed

    def _toggle_log(self):
        """Toggle the battle log popout window."""
        if self._log_window and self._log_window.winfo_exists():
            self._log_window.destroy()
            self._log_window = None
            self.log_text = None
            return
        self._log_window = lw = tk.Toplevel(self.root)
        lw.title("Battle Log")
        lw.geometry("500x300")
        lw.transient(self.root)
        self.log_text = tk.Text(lw, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._update_log_display()

    def _close_log(self):
        """Close the log window if open."""
        if self._log_window and self._log_window.winfo_exists():
            self._log_window.destroy()
        self._log_window = None
        self.log_text = None

    def _hide_tooltip(self):
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None
            self._tooltip_unit = None

    def _anim_delay(self, base_ms):
        """Scale animation delay by current speed setting (1x = 100ms auto_delay)."""
        return max(1, int(base_ms * self.auto_delay / 100))

    def _animate_arrow(self, src, dst, on_done, frame=0):
        """Animate an arrow projectile from src to dst hex over several frames."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("anim")
            on_done()
            return

        t = frame / total_frames
        sx, sy = self._hex_x(src[0], src[1]), self._hex_y(src[0], src[1])
        dx, dy = self._hex_x(dst[0], dst[1]), self._hex_y(dst[0], dst[1])
        cx = sx + (dx - sx) * t
        cy = sy + (dy - sy) * t

        self.canvas.delete("anim")
        # Arrow: a line with a triangle head
        angle = math.atan2(dy - sy, dx - sx)
        tail_x = cx - 10 * math.cos(angle)
        tail_y = cy - 10 * math.sin(angle)
        self.canvas.create_line(tail_x, tail_y, cx, cy, fill="#ffff44", width=2, tags="anim")
        # Arrowhead
        ha1 = angle + math.radians(150)
        ha2 = angle - math.radians(150)
        self.canvas.create_polygon(
            cx, cy,
            cx + 6 * math.cos(ha1), cy + 6 * math.sin(ha1),
            cx + 6 * math.cos(ha2), cy + 6 * math.sin(ha2),
            fill="#ffff44", tags="anim",
        )
        self.root.after(self._anim_delay(30), lambda: self._animate_arrow(src, dst, on_done, frame + 1))

    def _animate_slash(self, target_pos, attacker_pos, on_done, frame=0):
        """Animate a slash effect offset 25% from target toward attacker."""
        total_frames = 6
        if frame > total_frames:
            self.canvas.delete("anim")
            on_done()
            return

        tx = self._hex_x(target_pos[0], target_pos[1])
        ty = self._hex_y(target_pos[0], target_pos[1])
        ax = self._hex_x(attacker_pos[0], attacker_pos[1])
        ay = self._hex_y(attacker_pos[0], attacker_pos[1])
        # Place slash 40% of the way from target toward attacker
        cx = tx + (ax - tx) * 0.4
        cy = ty + (ay - ty) * 0.4
        self.canvas.delete("anim")

        t = frame / total_frames
        r = self.HEX_SIZE * 0.4
        sweep = -60 + 120 * t
        angle = math.radians(sweep)
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx - r * math.cos(angle)
        y2 = cy - r * math.sin(angle)
        gb = int(255 * (1 - t))
        color = f"#ff{gb:02x}{gb:02x}"
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3, tags="anim")
        angle2 = math.radians(sweep + 30)
        x3 = cx + r * 0.7 * math.cos(angle2)
        y3 = cy + r * 0.7 * math.sin(angle2)
        x4 = cx - r * 0.7 * math.cos(angle2)
        y4 = cy - r * 0.7 * math.sin(angle2)
        self.canvas.create_line(x3, y3, x4, y4, fill=color, width=2, tags="anim")

        self.root.after(self._anim_delay(40), lambda: self._animate_slash(target_pos, attacker_pos, on_done, frame + 1))

    def _animate_heal(self, pos, on_done, frame=0):
        """Animate a green '+' that fades at the given hex position."""
        total_frames = 10
        if frame > total_frames:
            self.canvas.delete("heal_anim")
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1]) - t * 12  # float upward
        alpha = int(255 * (1 - t))
        green = f"#00{alpha:02x}00"
        self.canvas.delete("heal_anim")
        self.canvas.create_text(cx, cy, text="+", fill=green,
                                font=("Arial", 14, "bold"), tags="heal_anim")
        self.root.after(self._anim_delay(40), lambda: self._animate_heal(pos, on_done, frame + 1))

    def _animate_small_arrow(self, pos, color, direction, tag, on_done, frame=0):
        """Animate a small arrow (up or down) at the given hex position.
        direction: -1 for up, +1 for down."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete(tag)
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1]) + direction * t * 10
        alpha_frac = 1 - t
        self.canvas.delete(tag)
        # Arrow shaft
        y1 = cy - 6 * direction
        self.canvas.create_line(cx, cy, cx, y1, fill=color, width=2, tags=tag)
        # Arrowhead
        self.canvas.create_polygon(
            cx, y1,
            cx - 4, y1 + 5 * direction,
            cx + 4, y1 + 5 * direction,
            fill=color, tags=tag,
        )
        # Fade text label
        r_val = int(int(color[1:3], 16) * alpha_frac)
        g_val = int(int(color[3:5], 16) * alpha_frac)
        b_val = int(int(color[5:7], 16) * alpha_frac)
        faded = f"#{r_val:02x}{g_val:02x}{b_val:02x}"
        self.canvas.create_line(cx, cy, cx, y1, fill=faded, width=2, tags=tag)
        self.root.after(self._anim_delay(30), lambda: self._animate_small_arrow(pos, color, direction, tag, on_done, frame + 1))

    def _animate_splash_hit(self, pos, on_done, frame=0):
        """Animate a small red burst at the given position."""
        total_frames = 6
        if frame > total_frames:
            self.canvas.delete("splash_anim")
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1])
        self.canvas.delete("splash_anim")
        r = self.HEX_SIZE * 0.3 * (0.5 + t * 0.5)
        fade = int(255 * (1 - t))
        color = f"#ff{fade // 4:02x}{fade // 4:02x}"
        # Small expanding X
        for angle_deg in (45, 135):
            angle = math.radians(angle_deg)
            x1 = cx + r * math.cos(angle)
            y1 = cy + r * math.sin(angle)
            x2 = cx - r * math.cos(angle)
            y2 = cy - r * math.sin(angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2, tags="splash_anim")
        self.root.after(self._anim_delay(35), lambda: self._animate_splash_hit(pos, on_done, frame + 1))

    def _animate_repair_tick(self, pos, on_done, frame=0):
        """Animate a small green wrench/+ symbol at the given position."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("repair_anim")
            on_done()
            return
        t = frame / total_frames
        cx = self._hex_x(pos[0], pos[1])
        cy = self._hex_y(pos[0], pos[1]) - t * 8
        fade = int(200 * (1 - t))
        color = f"#00{max(80, fade):02x}00"
        self.canvas.delete("repair_anim")
        self.canvas.create_text(cx, cy, text="+", fill=color,
                                font=("Arial", 10, "bold"), tags="repair_anim")
        self.root.after(self._anim_delay(30), lambda: self._animate_repair_tick(pos, on_done, frame + 1))

    def _animate_sunder_arrow(self, target_pos, source_pos, on_done, frame=0):
        """Animate a small black down-arrow shifted toward source."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("sunder_anim")
            on_done()
            return
        t = frame / total_frames
        tx = self._hex_x(target_pos[0], target_pos[1])
        ty = self._hex_y(target_pos[0], target_pos[1])
        sx = self._hex_x(source_pos[0], source_pos[1])
        sy = self._hex_y(source_pos[0], source_pos[1])
        # Shift 30% toward source
        cx = tx + (sx - tx) * 0.3
        cy = ty + (sy - ty) * 0.3 + t * 8
        self.canvas.delete("sunder_anim")
        fade = int(200 * (1 - t))
        color = f"#{fade // 3:02x}{fade // 3:02x}{fade // 3:02x}"
        # Down arrow
        self.canvas.create_line(cx, cy - 8, cx, cy, fill=color, width=2, tags="sunder_anim")
        self.canvas.create_polygon(cx, cy + 2, cx - 4, cy - 3, cx + 4, cy - 3,
                                   fill=color, tags="sunder_anim")
        self.root.after(self._anim_delay(30), lambda: self._animate_sunder_arrow(target_pos, source_pos, on_done, frame + 1))

    def _animate_bombardment_arrow(self, src, dst, on_done, frame=0):
        """Animate a differently-colored arrow (orange) from src to dst."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete("bomb_anim")
            on_done()
            return
        t = frame / total_frames
        sx, sy = self._hex_x(src[0], src[1]), self._hex_y(src[0], src[1])
        dx, dy = self._hex_x(dst[0], dst[1]), self._hex_y(dst[0], dst[1])
        cx = sx + (dx - sx) * t
        cy = sy + (dy - sy) * t
        self.canvas.delete("bomb_anim")
        angle = math.atan2(dy - sy, dx - sx)
        tail_x = cx - 10 * math.cos(angle)
        tail_y = cy - 10 * math.sin(angle)
        self.canvas.create_line(tail_x, tail_y, cx, cy, fill="#ff8800", width=2, tags="bomb_anim")
        ha1 = angle + math.radians(150)
        ha2 = angle - math.radians(150)
        self.canvas.create_polygon(
            cx, cy,
            cx + 6 * math.cos(ha1), cy + 6 * math.sin(ha1),
            cx + 6 * math.cos(ha2), cy + 6 * math.sin(ha2),
            fill="#ff8800", tags="bomb_anim",
        )
        self.root.after(self._anim_delay(30), lambda: self._animate_bombardment_arrow(src, dst, on_done, frame + 1))

    def _animate_stat_arrow(self, pos, color, direction, tag, on_done, source_pos=None, frame=0):
        """Animate a small colored arrow at pos, optionally shifted toward source_pos.
        direction: -1 for up (buff), +1 for down (debuff)."""
        total_frames = 8
        if frame > total_frames:
            self.canvas.delete(tag)
            on_done()
            return
        t = frame / total_frames
        px = self._hex_x(pos[0], pos[1])
        py = self._hex_y(pos[0], pos[1])
        if source_pos:
            sx = self._hex_x(source_pos[0], source_pos[1])
            sy = self._hex_y(source_pos[0], source_pos[1])
            px = px + (sx - px) * 0.3
            py = py + (sy - py) * 0.3
        cy = py + direction * t * 10
        self.canvas.delete(tag)
        # Arrow shaft + head
        y_tip = cy + direction * (-8)
        fade = 1 - t
        r_c = int(int(color[1:3], 16) * fade)
        g_c = int(int(color[3:5], 16) * fade)
        b_c = int(int(color[5:7], 16) * fade)
        faded = f"#{max(0,r_c):02x}{max(0,g_c):02x}{max(0,b_c):02x}"
        self.canvas.create_line(px, cy, px, y_tip, fill=faded, width=2, tags=tag)
        self.canvas.create_polygon(
            px, y_tip + (-3 if direction == -1 else 3) * (-1),
            px - 4, y_tip + 5 * (-direction),
            px + 4, y_tip + 5 * (-direction),
            fill=faded, tags=tag,
        )
        self.root.after(self._anim_delay(30), lambda: self._animate_stat_arrow(pos, color, direction, tag, on_done, source_pos, frame + 1))

    def _chain_anims(self, anim_fns, final_done):
        """Run a list of animation functions in sequence. Each fn takes on_done callback."""
        if not anim_fns:
            final_done()
            return
        first = anim_fns[0]
        rest = anim_fns[1:]
        first(lambda: self._chain_anims(rest, final_done))

    def _play_ability_anims(self, action, on_done):
        """Play visual effects for all abilities that triggered this step."""
        if not action:
            on_done()
            return
        anims = []

        # Sunder — black down-arrow on target shifted toward source
        if action.get("sunder_pos") and action.get("sunder_src"):
            spos = action["sunder_pos"]
            ssrc = action["sunder_src"]
            anims.append(lambda done, s=spos, r=ssrc: self._animate_stat_arrow(s, "#444444", 1, "sunder_anim", done, source_pos=r))

        # Ramp — red up-arrow on unit
        if action.get("ramp_pos"):
            rpos = action["ramp_pos"]
            anims.append(lambda done, p=rpos: self._animate_stat_arrow(p, "#ff4444", -1, "ramp_anim", done))

        # Rage — red up-arrow on each raging unit
        for rpos in action.get("rage_positions", []):
            anims.append(lambda done, p=rpos: self._animate_stat_arrow(p, "#ff6644", -1, "rage_anim", done))

        # Vengeance — red up-arrow on each vengeance unit
        for vpos in action.get("vengeance_positions", []):
            anims.append(lambda done, p=vpos: self._animate_stat_arrow(p, "#ff2222", -1, "veng_anim", done))

        # Splash — red burst on each hit
        for bpos in action.get("splash_positions", []):
            anims.append(lambda done, p=bpos: self._animate_splash_hit(p, done))

        # Repair — green + on each healed ally
        for rpos in action.get("repair_positions", []):
            anims.append(lambda done, p=rpos: self._animate_repair_tick(p, done))

        # Bombardment — orange arrow from source to target
        if action.get("bombardment_pos") and action.get("bombardment_src"):
            bsrc = action["bombardment_src"]
            bdst = action["bombardment_pos"]
            anims.append(lambda done, s=bsrc, d=bdst: self._animate_bombardment_arrow(s, d, done))

        self._chain_anims(anims, on_done)

    def _play_attack_anim(self, action, on_done):
        """Play the appropriate animation for an attack action, then call on_done."""
        attacker_pos = action.get("attacker_pos", action.get("to"))
        if action["ranged"]:
            self._animate_arrow(attacker_pos, action["target_pos"], on_done)
        else:
            self._animate_slash(action["target_pos"], attacker_pos, on_done)

    def _play_heal_if_needed(self, action, on_done):
        """If action has a heal_pos, play heal animation then call on_done, else call on_done immediately."""
        if action and action.get("heal_pos"):
            self._animate_heal(action["heal_pos"], on_done)
        else:
            on_done()

    def _play_post_attack_anims(self, action, on_done):
        """Chain: heal -> ability effects."""
        self._play_heal_if_needed(action, lambda: self._play_ability_anims(action, on_done))

    def on_step(self):
        self.battle.step()
        action = self.battle.last_action
        self._draw()
        if action and action.get("type") in ("attack", "move_attack"):
            self._play_attack_anim(action, lambda: self._play_post_attack_anims(action, lambda: None))
        else:
            self._play_post_attack_anims(action, lambda: None)

    def on_undo(self):
        self.battle.undo()
        self._draw()

    def on_reset(self):
        self.auto_running = False
        self.auto_btn.config(text="Auto")
        if self.return_btn:
            self.return_btn.destroy()
            self.return_btn = None
        Unit._id_counter = 0
        random.setstate(self.battle._init_rng_state)
        self.battle = Battle(p1_units=self.battle._init_p1_units, p2_units=self.battle._init_p2_units)
        self._draw()

    def _speed_down(self):
        if self.speed_index > 0:
            self.speed_index -= 1
            self.auto_delay = self.speed_levels[self.speed_index][0]
            self.speed_var.set(self.speed_levels[self.speed_index][1])

    def _speed_up(self):
        if self.speed_index < len(self.speed_levels) - 1:
            self.speed_index += 1
            self.auto_delay = self.speed_levels[self.speed_index][0]
            self.speed_var.set(self.speed_levels[self.speed_index][1])

    def on_skip(self):
        self.auto_running = False
        self.auto_btn.config(text="Auto")
        while self.battle.step():
            pass
        self._draw()

    def toggle_auto(self):
        self.auto_running = not self.auto_running
        self.auto_btn.config(text="Stop" if self.auto_running else "Auto")
        if self.auto_running:
            self._auto_step()

    def _auto_step(self):
        if not self.auto_running:
            return
        cont = self.battle.step()
        self._draw()
        action = self.battle.last_action

        def schedule_next():
            if cont:
                self.root.after(self.auto_delay, self._auto_step)
            else:
                self.auto_running = False
                self.auto_btn.config(text="Auto")

        if action and action.get("type") in ("attack", "move_attack"):
            self._play_attack_anim(action, lambda: self._play_post_attack_anims(action, schedule_next))
        else:
            self._play_post_attack_anims(action, schedule_next)


def main():
    root = tk.Tk()
    CombatGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

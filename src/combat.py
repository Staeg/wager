import tkinter as tk
import math
import random
import os
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
    """Return the next hex to move to from start toward goal, avoiding occupied hexes."""
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
    return start  # no path found


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

    def __init__(self, name, max_hp, damage, attack_range, player, armor=0, heal=0):
        Unit._id_counter += 1
        self.id = Unit._id_counter
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.attack_range = attack_range
        self.player = player
        self.armor = armor
        self.heal = heal
        self.pos = None
        self.has_acted = False

    @property
    def alive(self):
        return self.hp > 0

    def __repr__(self):
        return f"{self.name}(P{self.player} HP:{self.hp}/{self.max_hp})"


class Battle:
    COLS = 17
    ROWS = 11

    def __init__(self, p1_units=None, p2_units=None):
        """Initialize battle.

        p1_units/p2_units: optional list of (name, max_hp, damage, range, count) tuples.
        If None, uses default hardcoded armies.
        """
        self.units = []
        self.turn_order = []
        self.current_index = 0
        self.round_num = 0
        self.log = []
        self.winner = None
        self.history = []
        self._setup_armies(p1_units, p2_units)
        self._new_round()

    def _save_state(self):
        unit_states = {u.id: (u.pos, u.hp, u.has_acted, u.armor, u.heal) for u in self.units}
        turn_ids = [u.id for u in self.turn_order]
        rng_state = random.getstate()
        self.history.append((unit_states, turn_ids, self.current_index,
                             self.round_num, list(self.log), self.winner, rng_state))

    def undo(self):
        if not self.history:
            return
        unit_states, turn_ids, self.current_index, self.round_num, self.log, self.winner, rng_state = self.history.pop()
        random.setstate(rng_state)
        id_to_unit = {u.id: u for u in self.units}
        for uid, (pos, hp, acted, armor, heal) in unit_states.items():
            u = id_to_unit[uid]
            u.pos = pos
            u.hp = hp
            u.has_acted = acted
            u.armor = armor
            u.heal = heal
        self.turn_order = [id_to_unit[uid] for uid in turn_ids]

    def _setup_armies(self, p1_units=None, p2_units=None):
        if p1_units is None:
            p1_units = [("Footman", 8, 2, 1, 10), ("Priest", 2, 1, 3, 5, 0, 1)]
        if p2_units is None:
            p2_units = [("Skirmisher", 6, 1, 3, 10), ("Knight", 12, 1, 1, 5, 1, 0)]

        # P1 western zone: cols 0..5, P2 eastern zone: cols 11..16
        west = [(c, r) for c in range(6) for r in range(self.ROWS)]
        east = [(c, r) for c in range(11, self.COLS) for r in range(self.ROWS)]

        def _sort_positions_front_to_back(positions, descending_col):
            """Group by column, shuffle rows within each group, flatten front-to-back."""
            from collections import defaultdict
            by_col = defaultdict(list)
            for c, r in positions:
                by_col[c].append((c, r))
            for col_positions in by_col.values():
                random.shuffle(col_positions)
            sorted_cols = sorted(by_col.keys(), reverse=descending_col)
            result = []
            for col in sorted_cols:
                result.extend(by_col[col])
            return result

        # P1: front = high cols (closer to enemy), melee (low range) gets front
        west = _sort_positions_front_to_back(west, descending_col=True)
        # P2: front = low cols (closer to enemy)
        east = _sort_positions_front_to_back(east, descending_col=False)

        # Build P1 units sorted by range ascending (melee first = front)
        p1_unit_list = []
        for tup in p1_units:
            name, max_hp, damage, atk_range, count = tup[:5]
            armor = tup[5] if len(tup) > 5 else 0
            heal = tup[6] if len(tup) > 6 else 0
            for _ in range(count):
                p1_unit_list.append(Unit(name, max_hp, damage, atk_range, 1, armor, heal))
        p1_unit_list.sort(key=lambda u: u.attack_range)
        for i, u in enumerate(p1_unit_list):
            u.pos = west[i]
            self.units.append(u)

        # Build P2 units sorted by range ascending (melee first = front)
        p2_unit_list = []
        for tup in p2_units:
            name, max_hp, damage, atk_range, count = tup[:5]
            armor = tup[5] if len(tup) > 5 else 0
            heal = tup[6] if len(tup) > 6 else 0
            for _ in range(count):
                p2_unit_list.append(Unit(name, max_hp, damage, atk_range, 2, armor, heal))
        p2_unit_list.sort(key=lambda u: u.attack_range)
        for i, u in enumerate(p2_unit_list):
            u.pos = east[i]
            self.units.append(u)

    def _new_round(self):
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
        if self.winner:
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
            actual = max(0, unit.damage - target.armor)
            target.hp -= actual
            if target.armor > 0 and actual < unit.damage:
                self.log.append(f"{unit} attacks {target} for {actual} dmg ({target.armor} blocked by armor)")
            else:
                self.log.append(f"{unit} attacks {target} for {actual} dmg")
            killed = not target.alive
            if killed:
                self.log.append(f"  {target.name}(P{target.player}) dies!")
            self.last_action = {
                "type": "attack", "attacker_pos": unit.pos, "target_pos": target.pos,
                "ranged": ranged, "killed": killed,
            }
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
                actual = max(0, unit.damage - target.armor)
                target.hp -= actual
                if target.armor > 0 and actual < unit.damage:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg ({target.armor} blocked by armor)")
                else:
                    self.log.append(f"  {unit} attacks {target} for {actual} dmg")
                killed = not target.alive
                if killed:
                    self.log.append(f"  {target.name}(P{target.player}) dies!")
                self.last_action = {
                    "type": "move_attack", "from": old, "to": next_pos,
                    "target_pos": target.pos, "ranged": ranged, "killed": killed,
                }
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

        unit.has_acted = True
        self.current_index += 1
        return True


# --- GUI ---

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

        canvas_w = self._hex_x(Battle.COLS, 0) + self.HEX_SIZE + 20
        canvas_h = self._hex_y(0, Battle.ROWS) + self.HEX_SIZE + 20
        self.canvas = tk.Canvas(root, width=canvas_w, height=canvas_h, bg="#2b2b2b")
        self.canvas.pack(padx=5, pady=5)

        self.log_text = tk.Text(root, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, padx=5, pady=5)

        self.return_btn = None
        self.auto_running = False
        self._tooltip = None
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        self._load_sprites()
        self._draw()

    def _load_sprites(self):
        asset_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        self._sprite_imgs = {}
        for name in ("footman", "skirmisher", "priest", "knight"):
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
        if b.winner:
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
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for line in b.log[-20:]:
            self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

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
        if unit:
            text = f"{unit.name} (P{unit.player})  HP: {unit.hp}/{unit.max_hp}  Dmg:{unit.damage}  Rng:{unit.attack_range}"
            if unit.armor > 0:
                text += f"  Armor:{unit.armor}"
            if unit.heal > 0:
                text += f"  Heal:{unit.heal}"
            if self._tooltip is None:
                self._tooltip = self.canvas.create_text(
                    event.x, event.y - 20, text=text,
                    fill="white", font=("Arial", 10, "bold"),
                    anchor="s", tags="tooltip",
                )
                self._tooltip_bg = self.canvas.create_rectangle(
                    0, 0, 0, 0, fill="#222", outline="#888", tags="tooltip_bg",
                )
            self.canvas.coords(self._tooltip, event.x, event.y - 20)
            self.canvas.itemconfigure(self._tooltip, text=text)
            bbox = self.canvas.bbox(self._tooltip)
            if bbox:
                self.canvas.coords(self._tooltip_bg,
                                   bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2)
                self.canvas.tag_raise("tooltip_bg")
                self.canvas.tag_raise("tooltip")
        else:
            self._hide_tooltip()

    def _on_leave(self, _event):
        self._hide_tooltip()

    def _hide_tooltip(self):
        if self._tooltip is not None:
            self.canvas.delete("tooltip")
            self.canvas.delete("tooltip_bg")
            self._tooltip = None

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
        self.root.after(30, lambda: self._animate_arrow(src, dst, on_done, frame + 1))

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

        self.root.after(40, lambda: self._animate_slash(target_pos, attacker_pos, on_done, frame + 1))

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
        self.root.after(40, lambda: self._animate_heal(pos, on_done, frame + 1))

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

    def on_step(self):
        cont = self.battle.step()
        action = self.battle.last_action
        self._draw()
        if action and action.get("type") in ("attack", "move_attack"):
            self._play_attack_anim(action, lambda: self._play_heal_if_needed(action, lambda: None))
        else:
            self._play_heal_if_needed(action, lambda: None)

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
        self.battle = Battle()
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
            self._play_attack_anim(action, lambda: self._play_heal_if_needed(action, schedule_next))
        else:
            self._play_heal_if_needed(action, schedule_next)


def main():
    root = tk.Tk()
    CombatGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

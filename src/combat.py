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


# --- Game classes ---

class Unit:
    _id_counter = 0

    def __init__(self, name, max_hp, damage, attack_range, player):
        Unit._id_counter += 1
        self.id = Unit._id_counter
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.damage = damage
        self.attack_range = attack_range
        self.player = player
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

    def __init__(self):
        self.units = []
        self.turn_order = []
        self.current_index = 0
        self.round_num = 0
        self.log = []
        self.winner = None
        self.history = []
        self._setup_armies()
        self._new_round()

    def _save_state(self):
        unit_states = {u.id: (u.pos, u.hp, u.has_acted) for u in self.units}
        turn_ids = [u.id for u in self.turn_order]
        self.history.append((unit_states, turn_ids, self.current_index,
                             self.round_num, list(self.log), self.winner))

    def undo(self):
        if not self.history:
            return
        unit_states, turn_ids, self.current_index, self.round_num, self.log, self.winner = self.history.pop()
        id_to_unit = {u.id: u for u in self.units}
        for uid, (pos, hp, acted) in unit_states.items():
            u = id_to_unit[uid]
            u.pos = pos
            u.hp = hp
            u.has_acted = acted
        self.turn_order = [id_to_unit[uid] for uid in turn_ids]

    def _setup_armies(self):
        # P1 western zone: cols 0..5, P2 eastern zone: cols 11..16
        west = [(c, r) for c in range(6) for r in range(self.ROWS)]
        east = [(c, r) for c in range(11, self.COLS) for r in range(self.ROWS)]
        random.shuffle(west)
        random.shuffle(east)

        for i in range(10):
            u = Unit("Footman", 8, 2, 1, 1)
            u.pos = west[i]
            self.units.append(u)
        for i in range(10):
            u = Unit("Skirmisher", 6, 1, 3, 2)
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
        """Execute one unit's turn. Returns True if battle continues."""
        self._save_state()
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
            target.hp -= unit.damage
            self.log.append(f"{unit} attacks {target} for {unit.damage} dmg")
            if not target.alive:
                self.log.append(f"  {target.name}(P{target.player}) dies!")
        else:
            # move toward closest enemy
            closest_dist = min(hex_distance(unit.pos, e.pos) for e in enemies)
            closest = [e for e in enemies if hex_distance(unit.pos, e.pos) == closest_dist]
            target_enemy = random.choice(closest)

            occupied = self._occupied() - {unit.pos}
            next_pos = bfs_next_step(unit.pos, target_enemy.pos, occupied, self.COLS, self.ROWS)
            old = unit.pos
            unit.pos = next_pos
            self.log.append(f"{unit} moves {old}->{next_pos}")

            # check if now in range
            in_range = [e for e in enemies if hex_distance(unit.pos, e.pos) <= unit.attack_range]
            if in_range:
                target = random.choice(in_range)
                target.hp -= unit.damage
                self.log.append(f"  {unit} attacks {target} for {unit.damage} dmg")
                if not target.alive:
                    self.log.append(f"  {target.name}(P{target.player}) dies!")

        unit.has_acted = True
        self.current_index += 1
        return True


# --- GUI ---

class CombatGUI:
    HEX_SIZE = 32

    def __init__(self, root):
        self.root = root
        root.title("Wager of War v3 - Combat")
        self.battle = Battle()

        # layout
        top = tk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.step_btn = tk.Button(top, text="Step", command=self.on_step, font=("Arial", 12))
        self.step_btn.pack(side=tk.LEFT)

        self.auto_btn = tk.Button(top, text="Auto", command=self.toggle_auto, font=("Arial", 12))
        self.auto_btn.pack(side=tk.LEFT, padx=5)

        self.undo_btn = tk.Button(top, text="Undo", command=self.on_undo, font=("Arial", 12))
        self.undo_btn.pack(side=tk.LEFT, padx=5)

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

        self.auto_running = False
        self._load_sprites()
        self._draw()

    def _load_sprites(self):
        asset_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        self._sprite_imgs = {}
        for name in ("footman", "skirmisher"):
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
            sprite_name = "footman" if u.name == "Footman" else "skirmisher"
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
        p1 = sum(1 for u in b.units if u.alive and u.player == 1)
        p2 = sum(1 for u in b.units if u.alive and u.player == 2)
        self.score_var.set(f"P1 Footmen: {p1}  |  P2 Skirmishers: {p2}")
        if b.winner:
            self.status_var.set(f"Player {b.winner} wins!")
        else:
            self.status_var.set(f"Round {b.round_num}")

        # update log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for line in b.log[-20:]:
            self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def on_step(self):
        self.battle.step()
        self._draw()

    def on_undo(self):
        self.battle.undo()
        self._draw()

    def on_reset(self):
        self.auto_running = False
        self.auto_btn.config(text="Auto")
        Unit._id_counter = 0
        self.battle = Battle()
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
        if cont:
            self.root.after(150, self._auto_step)
        else:
            self.auto_running = False
            self.auto_btn.config(text="Auto")


def main():
    root = tk.Tk()
    CombatGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

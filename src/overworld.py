import tkinter as tk
import math
from dataclasses import dataclass
from combat import Battle, CombatGUI, Unit, hex_neighbors, ABILITY_DESCRIPTIONS

# Canonical unit stats
UNIT_STATS = {
    # Custodians (yellow/orange)
    "Page":       {"max_hp": 3,  "damage": 1, "range": 1, "value": 2},
    "Librarian":  {"max_hp": 2,  "damage": 0, "range": 3, "sunder": 1, "value": 12},
    "Steward":    {"max_hp": 20, "damage": 3, "range": 1, "value": 10},
    "Gatekeeper": {"max_hp": 32, "damage": 4, "range": 2, "undying": 2, "value": 25},
    # Weavers (purple/blue)
    "Apprentice": {"max_hp": 8,  "damage": 1, "range": 2, "push": 1, "value": 5},
    "Conduit":    {"max_hp": 5,  "damage": 2, "range": 3, "amplify": 1, "value": 10},
    "Seeker":     {"max_hp": 3,  "damage": 1, "range": 4, "ramp": 1, "value": 10},
    "Savant":     {"max_hp": 6,  "damage": 4, "range": 4, "splash": 1, "value": 25},
    # Artificers (gray/black)
    "Tincan":     {"max_hp": 11, "damage": 2, "range": 1, "value": 6},
    "Golem":      {"max_hp": 16, "damage": 2, "range": 1, "armor": 2, "value": 14},
    "Kitboy":     {"max_hp": 6,  "damage": 2, "range": 2, "repair": 1, "value": 10},
    "Artillery":  {"max_hp": 8,  "damage": 4, "range": 4, "bombardment": 2, "bombardment_range": 6, "value": 25},
    # Purifiers (red/white)
    "Penitent":   {"max_hp": 5,  "damage": 1, "range": 1, "rage": 1, "value": 5},
    "Priest":     {"max_hp": 3,  "damage": 1, "range": 3, "heal": 1, "value": 10},
    "Avenger":    {"max_hp": 20, "damage": 3, "range": 1, "vengeance": 1, "value": 12},
    "Herald":     {"max_hp": 6,  "damage": 1, "range": 4, "charge": 3, "summon_count": 2, "value": 25},
}

FACTIONS = {
    "Custodians": ["Page", "Librarian", "Steward", "Gatekeeper"],
    "Weavers": ["Apprentice", "Conduit", "Seeker", "Savant"],
    "Artificers": ["Tincan", "Golem", "Kitboy", "Artillery"],
    "Purifiers": ["Penitent", "Priest", "Avenger", "Herald"],
}

ARMY_BUDGET = 100
STARTING_GOLD = 100

PLAYER_COLORS = {
    1: "#4488ff",
    2: "#ff4444",
    3: "#44cc44",
    4: "#cc44cc",
}

PLAYER_COLORS_EXHAUSTED = {
    1: "#223366",
    2: "#882222",
    3: "#226622",
    4: "#662266",
}

def unit_count(name):
    return ARMY_BUDGET // UNIT_STATS[name]["value"]


@dataclass
class OverworldArmy:
    player: int
    units: list  # list of (unit_type, count) tuples
    pos: tuple  # (col, row)
    exhausted: bool = False

    @property
    def label(self):
        return " + ".join(f"{count} {name}" for name, count in self.units)

    @property
    def total_count(self):
        return sum(count for _, count in self.units)


@dataclass
class Base:
    player: int
    pos: tuple  # (col, row)
    alive: bool = True


# Base positions: center of each player's side on a 10x8 grid
BASE_POSITIONS = {
    1: (1, 3),
    2: (5, 3),
    3: (1, 2),
    4: (5, 2),
}


class Overworld:
    COLS = 7
    ROWS = 7

    def __init__(self, num_players=2):
        self.armies = []
        self.gold = {p: STARTING_GOLD for p in range(1, num_players + 1)}
        self.bases = [Base(player=p, pos=BASE_POSITIONS[p]) for p in range(1, num_players + 1)]

    def get_base_at(self, pos):
        for b in self.bases:
            if b.pos == pos and b.alive:
                return b
        return None

    def get_player_base(self, player):
        for b in self.bases:
            if b.player == player and b.alive:
                return b
        return None

    def build_unit(self, player, unit_name):
        """Build a unit at the player's base. Returns error string or None on success."""
        if unit_name not in UNIT_STATS:
            return f"Unknown unit: {unit_name}"
        base = self.get_player_base(player)
        if not base:
            return "No base"
        cost = UNIT_STATS[unit_name]["value"]
        if self.gold.get(player, 0) < cost:
            return "Not enough gold"
        self.gold[player] -= cost
        # Find or create army at base position
        army = self.get_army_at(base.pos)
        if army and army.player == player:
            # Add to existing army
            for i, (name, count) in enumerate(army.units):
                if name == unit_name:
                    army.units[i] = (name, count + 1)
                    return None
            army.units.append((unit_name, 1))
        else:
            # Create new army at base
            self.armies.append(OverworldArmy(
                player=player,
                units=[(unit_name, 1)],
                pos=base.pos,
            ))
        return None

    def to_dict(self):
        """Serialize overworld state to a dict."""
        return {
            "armies": [
                {
                    "player": a.player,
                    "units": a.units,
                    "pos": list(a.pos),
                    "exhausted": a.exhausted,
                }
                for a in self.armies
            ],
            "gold": self.gold,
            "bases": [
                {"player": b.player, "pos": list(b.pos), "alive": b.alive}
                for b in self.bases
            ],
        }

    @classmethod
    def from_dict(cls, data):
        """Restore an Overworld from a serialized dict."""
        ow = cls.__new__(cls)
        ow.armies = [
            OverworldArmy(
                player=d["player"],
                units=[tuple(u) for u in d["units"]],
                pos=tuple(d["pos"]),
                exhausted=d["exhausted"],
            )
            for d in data["armies"]
        ]
        ow.gold = {int(k): v for k, v in data.get("gold", {}).items()}
        ow.bases = [
            Base(player=d["player"], pos=tuple(d["pos"]), alive=d["alive"])
            for d in data.get("bases", [])
        ]
        return ow

    def get_army_at(self, pos):
        for a in self.armies:
            if a.pos == pos:
                return a
        return None

    def move_army(self, army, new_pos):
        army.pos = new_pos


def _deserialize_armies(army_data):
    """Convert serialized army dicts to OverworldArmy objects."""
    return [
        OverworldArmy(
            player=d["player"],
            units=[tuple(u) for u in d["units"]],
            pos=tuple(d["pos"]),
            exhausted=d["exhausted"],
        )
        for d in army_data
    ]


def _deserialize_bases(base_data):
    """Convert serialized base dicts to Base objects."""
    return [
        Base(player=d["player"], pos=tuple(d["pos"]), alive=d["alive"])
        for d in base_data
    ]


ARMY_MOVE_RANGE = 3


def _reachable_hexes(start, steps, cols, rows, occupied):
    """Return set of hexes reachable from start within `steps` moves, avoiding occupied."""
    from collections import deque
    visited = {start: 0}
    queue = deque([(start, 0)])
    while queue:
        pos, dist = queue.popleft()
        if dist >= steps:
            continue
        for nb in hex_neighbors(pos[0], pos[1], cols, rows):
            if nb not in visited and nb not in occupied:
                visited[nb] = dist + 1
                queue.append((nb, dist + 1))
    # Remove start itself from reachable set
    result = set(visited.keys())
    result.discard(start)
    return result


def _bfs_path(start, goal, cols, rows, occupied):
    """Return the path from start to goal avoiding occupied hexes, or None."""
    from collections import deque
    if start == goal:
        return [start]
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        pos, path = queue.popleft()
        for nb in hex_neighbors(pos[0], pos[1], cols, rows):
            if nb in visited:
                continue
            visited.add(nb)
            new_path = path + [nb]
            if nb == goal:
                return new_path
            if nb not in occupied:
                queue.append((nb, new_path))
    return None


class OverworldGUI:
    HEX_SIZE = 40

    def __init__(self, root, client=None):
        """Initialize overworld GUI.

        Args:
            root: tkinter root or frame
            client: optional GameClient for multiplayer mode.
                    If None, runs in local single-player mode.
        """
        self.root = root
        self.client = client
        self.player_id = 1  # default for single-player
        self.current_player = 1
        self._multiplayer = client is not None
        self.faction = None

        root.title("Wager of War - Overworld")

        if self._multiplayer:
            self.world = Overworld.__new__(Overworld)
            self.world.armies = []
            self.world.bases = []
            self.world.gold = {}
        else:
            self.world = Overworld()
            # Show faction selection before building
            self._pick_faction()
            # Auto-build P2 armies since there's no AI
            self._auto_build_p2()

        self.selected_army = None
        self.build_panel = None  # track build popup

        # Main frame for overworld content
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        canvas_w = int(self.HEX_SIZE * 1.75 * Overworld.COLS + self.HEX_SIZE + 40)
        canvas_h = int(self.HEX_SIZE * 1.5 * Overworld.ROWS + self.HEX_SIZE + 40)

        left_frame = tk.Frame(self.main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.canvas = tk.Canvas(left_frame, width=canvas_w, height=canvas_h, bg="#2b3b2b")
        self.canvas.pack(padx=5, pady=5)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_hover)
        root.bind("<Escape>", self._on_escape)
        root.bind("<space>", lambda e: self._on_end_turn())
        root.bind("<KeyRelease-Shift_L>", self._on_shift_release)
        root.bind("<KeyRelease-Shift_R>", self._on_shift_release)

        self.status_var = tk.StringVar(value="Waiting for players..." if self._multiplayer else "Click your base to build units, or move armies.")
        tk.Label(left_frame, textvariable=self.status_var, font=("Arial", 12)).pack(pady=5)

        self.gold_var = tk.StringVar(value="")
        tk.Label(left_frame, textvariable=self.gold_var, font=("Arial", 11, "bold"), fg="#B8960F").pack(pady=2)
        self._update_gold_display()

        self.end_turn_btn = tk.Button(left_frame, text="End Turn", font=("Arial", 12), command=self._on_end_turn)
        self.end_turn_btn.pack(pady=5)

        # Battle log panel (right side)
        if self._multiplayer:
            right_frame = tk.Frame(self.main_frame, width=250)
            right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
            right_frame.pack_propagate(False)
            tk.Label(right_frame, text="Battle Log", font=("Arial", 11, "bold")).pack()
            self.battle_log = tk.Listbox(right_frame, font=("Consolas", 9), selectmode=tk.SINGLE)
            self.battle_log.pack(fill=tk.BOTH, expand=True)
            self.battle_log.bind("<Double-Button-1>", self._on_replay_click)
            self._battle_log_ids = []  # parallel list of battle_ids
        else:
            self.battle_log = None
            self._battle_log_ids = []

        self.tooltip = None
        self._hovered_army = None
        self.combat_frame = None

        if self._multiplayer:
            self.client.on_message = self._on_server_message
        else:
            self._draw()

    def _pick_faction(self):
        """Show a modal dialog for the player to pick a faction."""
        import random as rng
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Your Faction")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Faction", font=("Arial", 14, "bold")).pack(pady=10)

        for faction_name, unit_names in FACTIONS.items():
            frame = tk.Frame(dialog, relief=tk.RIDGE, borderwidth=2, padx=10, pady=5)
            frame.pack(fill=tk.X, padx=15, pady=5)
            tk.Label(frame, text=faction_name, font=("Arial", 12, "bold")).pack(anchor="w")
            for uname in unit_names:
                s = UNIT_STATS[uname]
                desc = f"  {uname} — HP:{s['max_hp']} Dmg:{s['damage']} Rng:{s['range']} Cost:{s['value']}"
                for ab in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                           "undying", "splash", "repair", "bombardment",
                           "rage", "vengeance", "charge"):
                    if s.get(ab, 0):
                        desc += f" {ab.capitalize()}:{s[ab]}"
                tk.Label(frame, text=desc, font=("Arial", 9), anchor="w").pack(anchor="w")
            tk.Button(frame, text=f"Play {faction_name}", font=("Arial", 11),
                      command=lambda fn=faction_name: self._select_faction(fn, dialog)).pack(pady=5)

        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.root.wait_window(dialog)

        # Default if somehow closed without picking
        if self.faction is None:
            self.faction = rng.choice(list(FACTIONS.keys()))

    def _select_faction(self, faction_name, dialog):
        self.faction = faction_name
        dialog.destroy()

    def _pick_faction_multiplayer(self, taken):
        """Show faction picker for multiplayer, excluding already-taken factions."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Your Faction")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Faction", font=("Arial", 14, "bold")).pack(pady=10)

        for faction_name, unit_names in FACTIONS.items():
            is_taken = faction_name in taken
            frame = tk.Frame(dialog, relief=tk.RIDGE, borderwidth=2, padx=10, pady=5)
            frame.pack(fill=tk.X, padx=15, pady=5)
            label_text = faction_name + (" (taken)" if is_taken else "")
            tk.Label(frame, text=label_text, font=("Arial", 12, "bold"),
                     fg="gray" if is_taken else "black").pack(anchor="w")
            for uname in unit_names:
                s = UNIT_STATS[uname]
                desc = f"  {uname} — HP:{s['max_hp']} Dmg:{s['damage']} Rng:{s['range']} Cost:{s['value']}"
                for ab in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                           "undying", "splash", "repair", "bombardment",
                           "rage", "vengeance", "charge"):
                    if s.get(ab, 0):
                        desc += f" {ab.capitalize()}:{s[ab]}"
                tk.Label(frame, text=desc, font=("Arial", 9), anchor="w",
                         fg="gray" if is_taken else "black").pack(anchor="w")
            btn = tk.Button(frame, text=f"Play {faction_name}", font=("Arial", 11),
                            state=tk.DISABLED if is_taken else tk.NORMAL,
                            command=lambda fn=faction_name, d=dialog: self._select_faction_mp(fn, d))
            btn.pack(pady=5)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _select_faction_mp(self, faction_name, dialog):
        """Send faction selection to server in multiplayer."""
        self.client.send({"type": "select_faction", "faction": faction_name})
        dialog.destroy()

    def _auto_build_p2(self):
        """Auto-spend P2's gold to create armies in single-player mode.
        Distributes gold roughly equally across all faction unit types."""
        import random as rng
        # P2 gets a random faction different from player's if possible
        other_factions = [f for f in FACTIONS if f != self.faction]
        p2_faction = rng.choice(other_factions) if other_factions else rng.choice(list(FACTIONS.keys()))
        names = FACTIONS[p2_faction]
        spent = {n: 0 for n in names}
        while self.world.gold.get(2, 0) > 0:
            affordable = [n for n in names if UNIT_STATS[n]["value"] <= self.world.gold[2]]
            if not affordable:
                break
            # Pick the affordable unit with the least gold spent so far
            min_spent = min(spent[n] for n in affordable)
            candidates = [n for n in affordable if spent[n] == min_spent]
            name = rng.choice(candidates)
            spent[name] += UNIT_STATS[name]["value"]
            self.world.build_unit(2, name)

    def _update_gold_display(self):
        my_player = self.player_id if self._multiplayer else 1
        gold = self.world.gold.get(my_player, 0)
        self.gold_var.set(f"Gold: {gold}")

    def _show_build_panel(self):
        """Show a popup panel for building units at the player's base."""
        if self.build_panel:
            self.build_panel.destroy()

        self.build_panel = tw = tk.Toplevel(self.root)
        tw.title("Build Unit")
        tw.resizable(False, False)
        tw.transient(self.root)

        self._build_gold_label = tk.Label(tw, text="", font=("Arial", 12, "bold"), fg="#B8960F")
        self._build_gold_label.pack(pady=5)

        self._build_buttons = {}
        faction_units = FACTIONS.get(self.faction, list(UNIT_STATS.keys())) if self.faction else list(UNIT_STATS.keys())
        for name in faction_units:
            stats = UNIT_STATS[name]
            cost = stats["value"]
            text = f"{name} (Cost: {cost}) - HP:{stats['max_hp']} Dmg:{stats['damage']} Rng:{stats['range']}"
            for ab in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                       "undying", "splash", "repair", "bombardment",
                       "rage", "vengeance", "charge"):
                if stats.get(ab, 0):
                    text += f" {ab.capitalize()}:{stats[ab]}"
            btn = tk.Button(tw, text=text, font=("Arial", 10),
                            command=lambda n=name: self._do_build(n))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self._build_buttons[name] = btn

            # Ability hover tooltip for build buttons
            ability_lines = []
            for ab in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                       "undying", "splash", "repair", "bombardment",
                       "rage", "vengeance", "charge"):
                if stats.get(ab, 0):
                    ability_lines.append(f"{ab.capitalize()}: {ABILITY_DESCRIPTIONS[ab].format(value=stats[ab])}")
            if ability_lines:
                self._bind_build_ability_hover(btn, "\n".join(ability_lines))

        tk.Button(tw, text="Close", command=tw.destroy).pack(pady=5)
        self._refresh_build_panel()

    def _bind_build_ability_hover(self, widget, description):
        tip = [None]
        def on_enter(e):
            tip[0] = tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root + 10}+{e.y_root + 20}")
            tk.Label(tw, text=description, fg="white", bg="#444",
                     font=("Arial", 9), padx=6, pady=4, justify=tk.LEFT).pack()
        def on_leave(e):
            if tip[0]:
                tip[0].destroy()
                tip[0] = None
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _refresh_build_panel(self):
        """Update gold display and button states in the build panel."""
        if not self.build_panel or not self.build_panel.winfo_exists():
            return
        my_player = self.player_id if self._multiplayer else 1
        gold = self.world.gold.get(my_player, 0)
        self._build_gold_label.config(text=f"Gold: {gold}")
        for name, btn in self._build_buttons.items():
            cost = UNIT_STATS[name]["value"]
            btn.config(state=tk.NORMAL if gold >= cost else tk.DISABLED)

    def _do_build(self, unit_name):
        """Execute a build action (panel stays open)."""
        if self._multiplayer:
            self.client.send({"type": "build_unit", "unit_name": unit_name})
        else:
            err = self.world.build_unit(1, unit_name)
            if err:
                self.status_var.set(f"Build failed: {err}")
            else:
                self.status_var.set(f"Built a {unit_name}.")
                self._update_gold_display()
                self._draw()
        self._refresh_build_panel()

    def _hex_center(self, col, row):
        x = self.HEX_SIZE * 1.75 * col + 50
        if row % 2 == 1:
            x += self.HEX_SIZE * 0.875
        y = self.HEX_SIZE * 1.5 * row + 50
        return x, y

    def _hex_polygon(self, cx, cy):
        points = []
        for i in range(6):
            angle = math.radians(60 * i + 30)
            points.append(cx + self.HEX_SIZE * 0.85 * math.cos(angle))
            points.append(cy + self.HEX_SIZE * 0.85 * math.sin(angle))
        return points

    def _draw(self):
        self.canvas.delete("all")
        w = self.world

        # Determine reachable hexes for selected army
        neighbors = set()
        if self.selected_army:
            occupied = {a.pos for a in w.armies if a is not self.selected_army}
            neighbors = _reachable_hexes(
                self.selected_army.pos, ARMY_MOVE_RANGE, w.COLS, w.ROWS, occupied
            )
            # Also include hexes occupied by enemy armies (attack targets)
            for a in w.armies:
                if a.player != self.selected_army.player:
                    neighbors.add(a.pos)

        for r in range(w.ROWS):
            for c in range(w.COLS):
                cx, cy = self._hex_center(c, r)
                fill = "#4a5a3a"
                outline = "#666"
                outline_width = 1
                if (c, r) in neighbors:
                    fill = "#5a6a4a"
                if self.selected_army and (c, r) == self.selected_army.pos:
                    outline = "#ffff00"
                    outline_width = 3
                self.canvas.create_polygon(self._hex_polygon(cx, cy), fill=fill, outline=outline, width=outline_width)

        # Draw bases (behind armies, larger square)
        for base in getattr(w, 'bases', []):
            if not base.alive:
                continue
            cx, cy = self._hex_center(base.pos[0], base.pos[1])
            color = PLAYER_COLORS.get(base.player, "#888888")
            s = 22
            self.canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s,
                                         fill=color, outline="white", width=2)
            self.canvas.create_text(cx, cy - s + 8, text="B", fill="white", font=("Arial", 9, "bold"))

        # Draw armies
        for army in w.armies:
            cx, cy = self._hex_center(army.pos[0], army.pos[1])
            if army.exhausted:
                color = PLAYER_COLORS_EXHAUSTED.get(army.player, "#444444")
            else:
                color = PLAYER_COLORS.get(army.player, "#888888")
            self.canvas.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, fill=color, outline="white", width=2)
            self.canvas.create_text(cx, cy, text=str(army.total_count), fill="white", font=("Arial", 12, "bold"))

    def _pixel_to_hex(self, px, py):
        best = None
        best_dist = float("inf")
        for r in range(self.world.ROWS):
            for c in range(self.world.COLS):
                cx, cy = self._hex_center(c, r)
                d = (px - cx) ** 2 + (py - cy) ** 2
                if d < best_dist:
                    best_dist = d
                    best = (c, r)
        return best

    def _on_hover(self, event):
        hovered = self._pixel_to_hex(event.x, event.y)
        army = self.world.get_army_at(hovered) if hovered else None
        shift_held = event.state & 0x1

        if army is not self._hovered_army:
            if shift_held and self.tooltip:
                # Shift held — keep existing tooltip pinned
                pass
            else:
                self._hovered_army = army
                if self.tooltip:
                    self.tooltip.destroy()
                    self.tooltip = None
                if army:
                    self.tooltip = tw = tk.Toplevel(self.root)
                    tw.wm_overrideredirect(True)
                    tw.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
                    text = f"P{army.player} Army\n" + "\n".join(
                        f"  {count}x {name}" for name, count in army.units
                    )
                    if army.exhausted:
                        text += "\n  (Exhausted)"
                    tk.Label(tw, text=text, justify=tk.LEFT, bg="#ffffdd",
                             font=("Arial", 10), padx=6, pady=4, relief=tk.SOLID, borderwidth=1).pack()
        elif self.tooltip:
            if not shift_held:
                self.tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")

    def _on_shift_release(self, event):
        """Dismiss tooltip when Shift is released if cursor is no longer over the army."""
        if self.tooltip:
            try:
                mx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
                my = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
                hovered = self._pixel_to_hex(mx, my)
                army = self.world.get_army_at(hovered) if hovered else None
                if army is not self._hovered_army:
                    self.tooltip.destroy()
                    self.tooltip = None
                    self._hovered_army = None
            except Exception:
                self.tooltip.destroy()
                self.tooltip = None
                self._hovered_army = None

    def _is_my_turn(self):
        if not self._multiplayer:
            return True
        return self.current_player == self.player_id

    def _on_click(self, event):
        """Left-click: select/deselect armies, open build panel on own base."""
        clicked = self._pixel_to_hex(event.x, event.y)
        if not clicked:
            return

        my_player = self.player_id if self._multiplayer else 1
        clicked_army = self.world.get_army_at(clicked)

        if not self._is_my_turn():
            self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
            return

        # Click own base -> build panel only if no own army, or army already selected
        clicked_base = self.world.get_base_at(clicked) if hasattr(self.world, 'bases') else None
        if clicked_base and clicked_base.player == my_player:
            if clicked_army and clicked_army.player == my_player:
                if self.selected_army == clicked_army:
                    # Already selected this army, so open build panel
                    self._show_build_panel()
                    return
                # Army here but not selected yet — fall through to select it
            else:
                # No army on base, open build panel directly
                self._show_build_panel()
                return

        # No army selected yet
        if self.selected_army is None:
            if clicked_army and clicked_army.player == my_player:
                if clicked_army.exhausted:
                    self.status_var.set("That army is exhausted. End Turn to ready it.")
                    return
                self.selected_army = clicked_army
                self.status_var.set(f"Selected: {clicked_army.label}. Right-click to move.")
                self._draw()
            else:
                self.status_var.set(f"Click a P{my_player} army to select it.")
            return

        # Click the same army -> deselect
        if clicked == self.selected_army.pos:
            self.selected_army = None
            self.status_var.set("Selection cancelled.")
            self._draw()
            return

        # Click another own army -> switch selection
        if clicked_army and clicked_army.player == my_player:
            if clicked_army.exhausted:
                self.status_var.set("That army is exhausted. End Turn to ready it.")
                return
            self.selected_army = clicked_army
            self.status_var.set(f"Selected: {clicked_army.label}. Right-click to move.")
            self._draw()
            return

        # Left-click on non-own hex with selection: just deselect
        self.selected_army = None
        self.status_var.set("Selection cancelled.")
        self._draw()

    def _on_right_click(self, event):
        """Right-click: move/attack with the selected army."""
        if not self.selected_army:
            return
        clicked = self._pixel_to_hex(event.x, event.y)
        if not clicked:
            return

        my_player = self.player_id if self._multiplayer else 1

        if not self._is_my_turn():
            self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
            return

        clicked_army = self.world.get_army_at(clicked)

        # Cannot move onto own army
        if clicked_army and clicked_army.player == my_player:
            self.status_var.set("Cannot move onto your own army.")
            return

        # Check reachability within move range
        occupied = {a.pos for a in self.world.armies if a is not self.selected_army}
        reachable = _reachable_hexes(
            self.selected_army.pos, ARMY_MOVE_RANGE, self.world.COLS, self.world.ROWS, occupied
        )
        # Enemy army hexes are valid attack targets even if "occupied"
        is_enemy = clicked_army and clicked_army.player != my_player
        if clicked not in reachable and not is_enemy:
            self.status_var.set("Too far. Right-click a highlighted hex to move.")
            return
        # For enemy targets, check that we can reach an adjacent hex
        if is_enemy and clicked not in reachable:
            # Check if any neighbor of the enemy is reachable
            adj = hex_neighbors(clicked[0], clicked[1], self.world.COLS, self.world.ROWS)
            adj_reachable = [h for h in adj if h in reachable or h == self.selected_army.pos]
            if not adj_reachable:
                self.status_var.set("Too far. Right-click a highlighted hex to move.")
                return

        if self._multiplayer:
            self.client.send({
                "type": "move_army",
                "from": list(self.selected_army.pos),
                "to": list(clicked),
            })
            self.selected_army = None
            return

        # Local single-player mode
        # Enemy -> battle
        if is_enemy:
            army = self.selected_army
            self.selected_army = None
            self._start_battle(army, clicked_army)
            return

        # Empty hex -> move
        army = self.selected_army
        self.selected_army = None
        self.world.move_army(army, clicked)
        army.exhausted = True
        # Check for base destruction
        self._check_local_base_destruction(clicked, army.player)
        self.status_var.set(f"Army moved to {clicked}.")
        self._draw()

    def _check_local_base_destruction(self, pos, moving_player):
        """Destroy enemy base at pos in single-player mode."""
        for base in getattr(self.world, 'bases', []):
            if base.pos == pos and base.alive and base.player != moving_player:
                base.alive = False
                self.status_var.set(f"P{base.player}'s base destroyed!")

    def _on_escape(self, event):
        if self.selected_army:
            self.selected_army = None
            self.status_var.set("Selection cancelled.")
            self._draw()

    def _on_end_turn(self):
        if self._multiplayer:
            if not self._is_my_turn():
                return
            self.client.send({"type": "end_turn"})
            self.selected_army = None
            return

        # Local single-player
        for army in self.world.armies:
            if army.player == 1:
                army.exhausted = False
        self.selected_army = None
        self.status_var.set("New turn. Click a P1 army to select it.")
        self._draw()

    def _make_battle_units(self, army):
        """Convert an army's units list into Battle-compatible dicts."""
        result = []
        for name, count in army.units:
            s = UNIT_STATS[name]
            spec = {"name": name, "max_hp": s["max_hp"], "damage": s["damage"],
                    "range": s["range"], "count": count}
            # Copy all ability keys
            for key in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                        "undying", "splash", "repair", "bombardment", "bombardment_range",
                        "rage", "vengeance", "charge", "summon_count"):
                if s.get(key, 0):
                    spec[key] = s[key]
            result.append(spec)
        return result

    def _start_battle(self, army1, army2):
        """Start a local single-player battle."""
        p1_units = self._make_battle_units(army1)
        p2_units = self._make_battle_units(army2)

        battle = Battle(p1_units=p1_units, p2_units=p2_units)

        # Hide overworld UI
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.main_frame.pack_forget()
        self.status_var.set("Battle in progress!")

        self.combat_frame = tk.Frame(self.root)
        self.combat_frame.pack(fill=tk.BOTH, expand=True)

        def on_battle_complete(winner, p1_survivors, p2_survivors):
            if hasattr(self, '_combat_gui') and self._combat_gui:
                self._combat_gui._close_log()
                self._combat_gui = None
            self.combat_frame.destroy()
            self.combat_frame = None

            def _update_survivors(army, player):
                survivor_counts = {}
                for u in battle.units:
                    if u.alive and u.player == player:
                        survivor_counts[u.name] = survivor_counts.get(u.name, 0) + 1
                army.units = [
                    (name, survivor_counts.get(name, 0))
                    for name, _ in army.units
                    if survivor_counts.get(name, 0) > 0
                ]

            if winner == 0:
                _update_survivors(army1, 1)
                _update_survivors(army2, 2)
                army1.exhausted = True
            elif winner == 1:
                _update_survivors(army1, 1)
                self.world.armies.remove(army2)
                self.world.move_army(army1, army2.pos)
                army1.exhausted = True
                # Check base destruction at new position
                self._check_local_base_destruction(army2.pos, army1.player)
            else:
                _update_survivors(army2, 2)
                self.world.armies.remove(army1)

            self.main_frame.pack(fill=tk.BOTH, expand=True)
            p1_armies = [a for a in self.world.armies if a.player == 1]
            p2_armies = [a for a in self.world.armies if a.player == 2]
            p1_bases = [b for b in self.world.bases if b.player == 1 and b.alive]
            p2_bases = [b for b in self.world.bases if b.player == 2 and b.alive]
            if not p1_armies and not p1_bases:
                self.status_var.set("Player 2 wins the overworld!")
            elif not p2_armies and not p2_bases:
                self.status_var.set("Player 1 wins the overworld!")
            elif winner == 0:
                self.status_var.set("Battle ended in a stalemate. Both armies survive.")
            else:
                self.status_var.set(f"Battle over. P{winner} won with {p1_survivors if winner == 1 else p2_survivors} survivors.")
            self._draw()

        Unit._id_counter = 0
        self._combat_gui = CombatGUI(self.combat_frame, battle=battle, on_complete=on_battle_complete)

    # --- Multiplayer message handling ---

    def _on_server_message(self, msg):
        """Handle a message from the server (called from main thread via queue polling)."""
        msg_type = msg.get("type")

        if msg_type == "joined":
            self.player_id = msg["player_id"]
            self.status_var.set(f"You are P{self.player_id}. Waiting for players ({msg['player_count']}/{msg['needed']})...")

        elif msg_type == "faction_prompt":
            picking = msg["picking_player"]
            taken = msg.get("taken", [])
            if picking == self.player_id:
                self.status_var.set("Choose your faction!")
                self._pick_faction_multiplayer(taken)
            else:
                self.status_var.set(f"Waiting for P{picking} to choose a faction...")

        elif msg_type == "game_start":
            self.player_id = msg["player_id"]
            self.current_player = msg["current_player"]
            self.faction = msg.get("faction")
            self.world.armies = _deserialize_armies(msg["armies"])
            self.world.bases = _deserialize_bases(msg.get("bases", []))
            self.world.gold = {int(k): v for k, v in msg.get("gold", {}).items()}
            self._update_gold_display()
            if self._is_my_turn():
                self.status_var.set(f"Game started! Your turn (P{self.player_id}). Click your base to build units.")
            else:
                self.status_var.set(f"Game started! Waiting for P{self.current_player}.")
            self._draw()

        elif msg_type == "state_update":
            self.world.armies = _deserialize_armies(msg["armies"])
            self.world.bases = _deserialize_bases(msg.get("bases", []))
            self.world.gold = {int(k): v for k, v in msg.get("gold", {}).items()}
            self._update_gold_display()
            self.current_player = msg["current_player"]
            self.selected_army = None
            status = msg.get("message", "")
            if self._is_my_turn():
                status += f" Your turn (P{self.player_id})."
            else:
                status += f" Waiting for P{self.current_player}."
            self.status_var.set(status)
            self._draw()

        elif msg_type == "battle_end":
            if self.battle_log is not None:
                self.battle_log.insert(tk.END, msg["summary"])
                self._battle_log_ids.append(msg["battle_id"])

        elif msg_type == "replay_data":
            self._show_replay(msg)

        elif msg_type == "game_over":
            winner = msg["winner"]
            if winner == self.player_id:
                self.status_var.set("You win!")
            else:
                self.status_var.set(f"P{winner} wins the game!")

        elif msg_type == "error":
            self.status_var.set(f"Error: {msg['message']}")

    def _close_replay(self):
        """Close the replay viewer and return to overworld."""
        if self.combat_frame:
            self.combat_frame.destroy()
            self.combat_frame = None
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self._draw()

    def _on_replay_click(self, event):
        """Handle double-click on battle log to request replay."""
        if not self.battle_log or not self.client:
            return
        sel = self.battle_log.curselection()
        if sel:
            idx = sel[0]
            if idx < len(self._battle_log_ids):
                self.client.send({
                    "type": "request_replay",
                    "battle_id": self._battle_log_ids[idx],
                })

    def _show_replay(self, msg):
        """Show a battle replay by re-simulating locally with the server's seed."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.main_frame.pack_forget()

        self.combat_frame = tk.Frame(self.root)
        self.combat_frame.pack(fill=tk.BOTH, expand=True)

        Unit._id_counter = 0
        battle = Battle(
            p1_units=msg["p1_units"],
            p2_units=msg["p2_units"],
            rng_seed=msg["rng_seed"],
        )

        CombatGUI(
            self.combat_frame, battle=battle,
            on_complete=lambda w, p1, p2: self._close_replay(),
        )

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = OverworldGUI(root)
    app.run()


if __name__ == "__main__":
    main()

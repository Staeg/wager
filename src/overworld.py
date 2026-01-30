import tkinter as tk
import math
from dataclasses import dataclass, field
from combat import Battle, CombatGUI, Unit, hex_neighbors

# Canonical unit stats: (max_hp, damage, range, armor, heal, sunder, value)
UNIT_STATS = {
    "Footman": {"max_hp": 8,  "damage": 2, "range": 1, "armor": 0, "heal": 0, "sunder": 0, "value": 6},
    "Archer":  {"max_hp": 4,  "damage": 1, "range": 4, "armor": 0, "heal": 0, "sunder": 0, "value": 6},
    "Knight":  {"max_hp": 12, "damage": 1, "range": 1, "armor": 1, "heal": 0, "sunder": 0, "value": 12},
    "Priest":  {"max_hp": 2,  "damage": 1, "range": 3, "armor": 0, "heal": 1, "sunder": 0, "value": 10},
    "Mage":    {"max_hp": 2,  "damage": 0, "range": 3, "armor": 0, "heal": 0, "sunder": 1, "value": 20},
}

ARMY_BUDGET = 60

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


class Overworld:
    COLS = 10
    ROWS = 8

    def __init__(self):
        # All 10 two-unit combinations, 5 per player
        self.armies = [
            # P1: 5 of 10 three-unit combinations
            OverworldArmy(player=1, pos=(1, 0), units=[
                ("Footman", unit_count("Footman")),
                ("Archer", unit_count("Archer")),
                ("Knight", unit_count("Knight")),
            ]),
            OverworldArmy(player=1, pos=(0, 2), units=[
                ("Footman", unit_count("Footman")),
                ("Archer", unit_count("Archer")),
                ("Priest", unit_count("Priest")),
            ]),
            OverworldArmy(player=1, pos=(1, 4), units=[
                ("Footman", unit_count("Footman")),
                ("Archer", unit_count("Archer")),
                ("Mage", unit_count("Mage")),
            ]),
            OverworldArmy(player=1, pos=(0, 6), units=[
                ("Footman", unit_count("Footman")),
                ("Knight", unit_count("Knight")),
                ("Priest", unit_count("Priest")),
            ]),
            OverworldArmy(player=1, pos=(2, 3), units=[
                ("Footman", unit_count("Footman")),
                ("Knight", unit_count("Knight")),
                ("Mage", unit_count("Mage")),
            ]),
            # P2: other 5 three-unit combinations
            OverworldArmy(player=2, pos=(8, 0), units=[
                ("Footman", unit_count("Footman")),
                ("Priest", unit_count("Priest")),
                ("Mage", unit_count("Mage")),
            ]),
            OverworldArmy(player=2, pos=(9, 2), units=[
                ("Archer", unit_count("Archer")),
                ("Knight", unit_count("Knight")),
                ("Priest", unit_count("Priest")),
            ]),
            OverworldArmy(player=2, pos=(8, 4), units=[
                ("Archer", unit_count("Archer")),
                ("Knight", unit_count("Knight")),
                ("Mage", unit_count("Mage")),
            ]),
            OverworldArmy(player=2, pos=(9, 6), units=[
                ("Archer", unit_count("Archer")),
                ("Priest", unit_count("Priest")),
                ("Mage", unit_count("Mage")),
            ]),
            OverworldArmy(player=2, pos=(7, 3), units=[
                ("Knight", unit_count("Knight")),
                ("Priest", unit_count("Priest")),
                ("Mage", unit_count("Mage")),
            ]),
        ]

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
            ]
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

        root.title("Wager of War - Overworld")

        if self._multiplayer:
            self.world = Overworld.__new__(Overworld)
            self.world.armies = []
        else:
            self.world = Overworld()

        self.selected_army = None

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
        self.canvas.bind("<Motion>", self._on_hover)
        root.bind("<Escape>", self._on_escape)
        root.bind("<space>", lambda e: self._on_end_turn())

        self.status_var = tk.StringVar(value="Waiting for players..." if self._multiplayer else "Click a P1 army to select it.")
        tk.Label(left_frame, textvariable=self.status_var, font=("Arial", 12)).pack(pady=5)

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

        # Battle viewer state
        self._battle_steps = []
        self._battle_step_idx = 0
        self._viewing_battle = False

        if self._multiplayer:
            self.client.on_message = self._on_server_message
        else:
            self._draw()

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

        # Determine neighbors for selected army
        neighbors = set()
        if self.selected_army:
            neighbors = set(hex_neighbors(self.selected_army.pos[0], self.selected_army.pos[1], w.COLS, w.ROWS))

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

        if army is not self._hovered_army:
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
            self.tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")

    def _is_my_turn(self):
        if not self._multiplayer:
            return True
        return self.current_player == self.player_id

    def _on_click(self, event):
        if self._viewing_battle:
            return
        clicked = self._pixel_to_hex(event.x, event.y)
        if not clicked:
            return

        my_player = self.player_id if self._multiplayer else 1
        clicked_army = self.world.get_army_at(clicked)

        if not self._is_my_turn():
            self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
            return

        # No army selected yet
        if self.selected_army is None:
            if clicked_army and clicked_army.player == my_player:
                if clicked_army.exhausted:
                    self.status_var.set("That army is exhausted. End Turn to ready it.")
                    return
                self.selected_army = clicked_army
                self.status_var.set(f"Selected: {clicked_army.label}.")
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
            self.status_var.set(f"Selected: {clicked_army.label}.")
            self._draw()
            return

        # Check adjacency
        neighbors = hex_neighbors(self.selected_army.pos[0], self.selected_army.pos[1], self.world.COLS, self.world.ROWS)
        if clicked not in neighbors:
            self.status_var.set("Must click an adjacent hex.")
            return

        if self._multiplayer:
            # Send move to server
            self.client.send({
                "type": "move_army",
                "from": list(self.selected_army.pos),
                "to": list(clicked),
            })
            self.selected_army = None
            return

        # Local single-player mode
        # Adjacent enemy -> battle
        if clicked_army and clicked_army.player != self.selected_army.player:
            army = self.selected_army
            self.selected_army = None
            self._start_battle(army, clicked_army)
            return

        # Adjacent empty -> move
        army = self.selected_army
        self.selected_army = None
        self.world.move_army(army, clicked)
        army.exhausted = True
        self.status_var.set(f"Army moved to {clicked}.")
        self._draw()

    def _on_escape(self, event):
        if self.selected_army:
            self.selected_army = None
            self.status_var.set("Selection cancelled.")
            self._draw()

    def _on_end_turn(self):
        if self._viewing_battle:
            return

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
        """Convert an army's units list into Battle-compatible tuples."""
        result = []
        for name, count in army.units:
            s = UNIT_STATS[name]
            result.append((name, s["max_hp"], s["damage"], s["range"], count, s["armor"], s["heal"], s["sunder"]))
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
            else:
                _update_survivors(army2, 2)
                self.world.armies.remove(army1)

            self.main_frame.pack(fill=tk.BOTH, expand=True)
            remaining = [a for a in self.world.armies]
            p1_remaining = [a for a in remaining if a.player == 1]
            p2_remaining = [a for a in remaining if a.player == 2]
            if not p1_remaining:
                self.status_var.set("Player 2 wins the overworld!")
            elif not p2_remaining:
                self.status_var.set("Player 1 wins the overworld!")
            elif winner == 0:
                self.status_var.set("Battle ended in a stalemate. Both armies survive.")
            else:
                self.status_var.set(f"Battle over. P{winner} won with {p1_survivors if winner == 1 else p2_survivors} survivors.")
            self._draw()

        Unit._id_counter = 0
        CombatGUI(self.combat_frame, battle=battle, on_complete=on_battle_complete)

    # --- Multiplayer message handling ---

    def _on_server_message(self, msg):
        """Handle a message from the server (called from main thread via queue polling)."""
        msg_type = msg.get("type")

        if msg_type == "joined":
            self.player_id = msg["player_id"]
            self.status_var.set(f"You are P{self.player_id}. Waiting for players ({msg['player_count']}/{msg['needed']})...")

        elif msg_type == "game_start":
            self.player_id = msg["player_id"]
            self.current_player = msg["current_player"]
            self.world.armies = _deserialize_armies(msg["armies"])
            if self._is_my_turn():
                self.status_var.set(f"Game started! Your turn (P{self.player_id}).")
            else:
                self.status_var.set(f"Game started! Waiting for P{self.current_player}.")
            self._draw()

        elif msg_type == "state_update":
            self.world.armies = _deserialize_armies(msg["armies"])
            self.current_player = msg["current_player"]
            self.selected_army = None
            status = msg.get("message", "")
            if self._is_my_turn():
                status += f" Your turn (P{self.player_id})."
            else:
                status += f" Waiting for P{self.current_player}."
            self.status_var.set(status)
            if not self._viewing_battle:
                self._draw()

        elif msg_type == "battle_start":
            self._battle_steps = []
            self._viewing_battle = True
            self._current_battle_msg = msg
            # Show battle in viewer mode
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
            self._viewer_battle = battle
            self._viewer_gui = CombatGUI(
                self.combat_frame, battle=battle, viewer_mode=True
            )

        elif msg_type == "battle_step":
            if self._viewing_battle and hasattr(self, '_viewer_gui'):
                self._viewer_gui.receive_step(msg["step_data"])

        elif msg_type == "battle_end":
            if self.battle_log is not None:
                self.battle_log.insert(tk.END, msg["summary"])
                self._battle_log_ids.append(msg["battle_id"])
            # Wait for all queued steps to finish playing, then close
            if self._viewing_battle:
                self._wait_for_battle_done()

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

    def _wait_for_battle_done(self):
        """Poll until the viewer GUI has finished playing all queued steps."""
        if hasattr(self, '_viewer_gui') and (self._viewer_gui._step_queue or self._viewer_gui._playing_step):
            self.root.after(200, self._wait_for_battle_done)
            return
        self.root.after(1500, self._close_battle_viewer)

    def _close_battle_viewer(self):
        """Close the battle viewer and return to overworld."""
        if self.combat_frame:
            self.combat_frame.destroy()
            self.combat_frame = None
        self._viewing_battle = False
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
        """Show a battle replay from replay_data."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.main_frame.pack_forget()
        self._viewing_battle = True

        self.combat_frame = tk.Frame(self.root)
        self.combat_frame.pack(fill=tk.BOTH, expand=True)

        Unit._id_counter = 0
        battle = Battle(
            p1_units=msg["p1_units"],
            p2_units=msg["p2_units"],
            rng_seed=msg["rng_seed"],
        )

        def on_replay_done(winner, p1_s, p2_s):
            self._close_battle_viewer()

        gui = CombatGUI(self.combat_frame, battle=battle, on_complete=on_replay_done)
        # Auto-play the replay
        gui.toggle_auto()

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = OverworldGUI(root)
    app.run()


if __name__ == "__main__":
    main()

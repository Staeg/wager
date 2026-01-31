import tkinter as tk
import math
import os
import random
from dataclasses import dataclass
from PIL import Image, ImageTk
from .combat import (
    Battle,
    CombatGUI,
    format_ability,
    describe_ability,
    bind_keyword_hover,
)
from .battle_resolution import make_battle_units, resolve_battle
from .compat import get_asset_dir
from .hex import hex_neighbors, reachable_hexes, hex_distance
from .protocol import (
    deserialize_armies,
    deserialize_bases,
    deserialize_gold_piles,
    deserialize_objectives,
    serialize_armies,
    serialize_bases,
    serialize_gold_piles,
    serialize_objectives,
    SPLIT_MOVE,
    MOVE_ARMY,
    END_TURN,
    REQUEST_REPLAY,
    BUILD_UNIT,
    SELECT_FACTION,
    SELECT_UPGRADE,
    OBJECTIVE_REWARD_CHOICE,
    JOINED,
    FACTION_PROMPT,
    UPGRADE_PROMPT,
    GAME_START,
    STATE_UPDATE,
    BATTLE_END,
    REPLAY_DATA,
    GAME_OVER,
    ERROR,
    OBJECTIVE_REWARD_PROMPT,
)
from .ability_defs import ability
from .heroes import HERO_STATS, HEROES_BY_FACTION, get_heroes_for_faction
from .upgrades import (
    get_upgrades_for_faction,
    get_upgrade_by_id,
    apply_upgrades_to_unit_stats,
    upgrade_effect_keywords,
    upgrade_effect_summaries,
)

# Canonical unit stats
UNIT_STATS = {
    # Custodians (yellow/orange)
    "Page": {"max_hp": 3, "damage": 1, "range": 1, "value": 2, "abilities": []},
    "Librarian": {
        "max_hp": 2,
        "damage": 0,
        "range": 3,
        "value": 12,
        "abilities": [
            ability(
                "periodic", "sunder", target="random", value=1, range=3, amplify=False
            )
        ],
    },
    "Steward": {"max_hp": 20, "damage": 3, "range": 1, "value": 10, "abilities": []},
    "Gatekeeper": {
        "max_hp": 32,
        "damage": 4,
        "range": 2,
        "value": 25,
        "abilities": [ability("passive", "undying", value=2, aura=2, amplify=False)],
    },
    # Weavers (purple/blue)
    "Apprentice": {
        "max_hp": 8,
        "damage": 1,
        "range": 2,
        "value": 5,
        "abilities": [
            ability("onhit", "push", target="target", value=1, amplify=False)
        ],
    },
    "Conduit": {
        "max_hp": 5,
        "damage": 2,
        "range": 3,
        "value": 10,
        "abilities": [ability("passive", "amplify", value=1, aura=1, amplify=False)],
    },
    "Seeker": {
        "max_hp": 3,
        "damage": 1,
        "range": 4,
        "value": 10,
        "abilities": [ability("onhit", "ramp", target="self", value=1)],
    },
    "Savant": {
        "max_hp": 6,
        "damage": 4,
        "range": 4,
        "value": 25,
        "abilities": [ability("onhit", "splash", target="target", value=1)],
    },
    # Artificers (gray/black)
    "Tincan": {"max_hp": 11, "damage": 2, "range": 1, "value": 6, "abilities": []},
    "Golem": {
        "max_hp": 16,
        "damage": 2,
        "range": 1,
        "value": 14,
        "abilities": [ability("passive", "armor", value=2, amplify=False)],
    },
    "Kitboy": {
        "max_hp": 6,
        "damage": 2,
        "range": 2,
        "value": 10,
        "abilities": [ability("periodic", "repair", target="area", value=1, range=1)],
    },
    "Artillery": {
        "max_hp": 8,
        "damage": 4,
        "range": 4,
        "value": 25,
        "abilities": [ability("periodic", "strike", target="random", value=2, range=6)],
    },
    # Purifiers (red/white)
    "Penitent": {
        "max_hp": 5,
        "damage": 1,
        "range": 1,
        "value": 5,
        "abilities": [ability("wounded", "ramp", target="self", value=1)],
    },
    "Priest": {
        "max_hp": 3,
        "damage": 1,
        "range": 3,
        "value": 10,
        "abilities": [ability("periodic", "heal", target="random", value=3, range=3)],
    },
    "Avenger": {
        "max_hp": 20,
        "damage": 3,
        "range": 1,
        "value": 12,
        "abilities": [ability("lament", "ramp", target="self", value=1, range=1)],
    },
    "Herald": {
        "max_hp": 6,
        "damage": 1,
        "range": 4,
        "value": 25,
        "abilities": [
            ability(
                "periodic", "summon", target="self", count=2, charge=3, amplify=False
            )
        ],
    },
}

ALL_UNIT_STATS = {**UNIT_STATS, **HERO_STATS}

FACTIONS = {
    "Custodians": ["Page", "Librarian", "Steward", "Gatekeeper"],
    "Weavers": ["Apprentice", "Conduit", "Seeker", "Savant"],
    "Artificers": ["Tincan", "Golem", "Kitboy", "Artillery"],
    "Purifiers": ["Penitent", "Priest", "Avenger", "Herald"],
}

ARMY_BUDGET = 100
STARTING_GOLD = 100
GOLD_PILE_COUNT = 16
GOLD_PILE_MIN = 10
GOLD_PILE_MAX = 20
BASE_INCOME = 5
OBJECTIVE_GUARD_VALUE = 50
OBJECTIVE_NEAR_DISTANCE = 2

PLAYER_COLORS = {
    0: "#888888",
    1: "#4488ff",
    2: "#ff4444",
    3: "#44cc44",
    4: "#cc44cc",
}

PLAYER_COLORS_EXHAUSTED = {
    0: "#444444",
    1: "#223366",
    2: "#882222",
    3: "#226622",
    4: "#662266",
}


def unit_count(name):
    return ARMY_BUDGET // UNIT_STATS[name]["value"]


def _ability_texts(stats):
    return [format_ability(ab) for ab in stats.get("abilities", [])]


def _ability_descriptions(stats):
    return [describe_ability(ab) for ab in stats.get("abilities", [])]


def _unit_tooltip_text(name, stats):
    armor = stats.get("armor", 0)
    stats_line = (
        f"{name} - HP:{stats['max_hp']} Dmg:{stats['damage']} Rng:{stats['range']}"
    )
    if armor:
        stats_line += f" Armor:{armor}"
    ability_lines = _ability_descriptions(stats)
    if ability_lines:
        return "\n".join([stats_line, ""] + ability_lines)
    return stats_line


def _upgrade_referenced_units(upgrade, base_stats, faction_units):
    units = set()
    for effect in upgrade.get("effects", []):
        unit = effect.get("unit")
        if unit == "__all__":
            units.update(faction_units or [])
            continue
        if unit:
            units.add(unit)
            continue
        if effect.get("type") == "modify_abilities":
            match = effect.get("match", {})
            for fname in faction_units or []:
                stats = base_stats.get(fname, {})
                for ability in stats.get("abilities", []):
                    if all(ability.get(k) == v for k, v in match.items()):
                        units.add(fname)
                        break
    return sorted(units)


def _add_upgrade_hover_rows(
    parent, upgrade, effective_stats, faction_units, bind_unit_tooltip
):
    units = _upgrade_referenced_units(upgrade, effective_stats, faction_units)
    if units:
        row = tk.Frame(parent)
        row.pack(anchor="w", pady=(2, 0))
        tk.Label(row, text="Units:", font=("Arial", 9, "bold")).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        for unit_name in units:
            stats = effective_stats.get(unit_name)
            if not stats:
                continue
            lbl = tk.Label(
                row,
                text=unit_name,
                fg="#2244aa",
                bg=row.cget("bg"),
                font=("Arial", 9, "underline"),
                padx=3,
            )
            lbl.pack(side=tk.LEFT, padx=2)
            bind_unit_tooltip(lbl, _unit_tooltip_text(unit_name, stats))

    keywords = upgrade_effect_keywords(upgrade, effective_stats, faction_units)
    if keywords:
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(anchor="w", pady=(2, 0))
        tk.Label(row, text="Keywords:", font=("Arial", 9, "bold")).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        for text, ability in keywords:
            lbl = tk.Label(
                row,
                text=text,
                fg="#aaffaa",
                bg="#333",
                font=("Arial", 9),
                padx=4,
                pady=1,
                relief=tk.RAISED,
                borderwidth=1,
            )
            lbl.pack(side=tk.LEFT, padx=2)
            bind_keyword_hover(lbl, parent, describe_ability(ability))


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


@dataclass
class GoldPile:
    pos: tuple  # (col, row)
    value: int


@dataclass
class Objective:
    pos: tuple  # (col, row)
    faction: str

class Overworld:
    COLS = 14
    ROWS = 14

    def __init__(self, num_players=2, rng_seed=None):
        if rng_seed is None:
            rng_seed = random.SystemRandom().randint(0, 2**31 - 1)
        self.rng_seed = rng_seed
        self.rng = random.Random(rng_seed)
        self.armies = []
        self.gold = {p: STARTING_GOLD for p in range(1, num_players + 1)}
        self.bases = []
        self._spawn_bases(num_players)
        self.gold_piles = []
        self._spawn_gold_piles()
        self.objectives = []
        self._spawn_objectives()

    def _spawn_bases(self, num_players):
        mid_c = self.COLS // 2
        mid_r = self.ROWS // 2
        quadrants = {
            1: (range(0, mid_c), range(0, mid_r)),  # top-left
            2: (range(mid_c, self.COLS), range(0, mid_r)),  # top-right
            3: (range(0, mid_c), range(mid_r, self.ROWS)),  # bottom-left
            4: (range(mid_c, self.COLS), range(mid_r, self.ROWS)),  # bottom-right
        }
        occupied = set()
        for p in range(1, num_players + 1):
            cols, rows = quadrants.get(p, quadrants[1])
            candidates = [(c, r) for r in rows for c in cols if (c, r) not in occupied]
            if len(candidates) < 2:
                break
            picks = self.rng.sample(candidates, 2)
            for pos in picks:
                occupied.add(pos)
                self.bases.append(Base(player=p, pos=pos))

    def _spawn_gold_piles(self, count=GOLD_PILE_COUNT):
        excluded = {b.pos for b in self.bases if b.alive}
        mid_c = self.COLS // 2
        mid_r = self.ROWS // 2
        quadrants = [
            (range(0, mid_c), range(0, mid_r)),
            (range(mid_c, self.COLS), range(0, mid_r)),
            (range(0, mid_c), range(mid_r, self.ROWS)),
            (range(mid_c, self.COLS), range(mid_r, self.ROWS)),
        ]
        per_quad = max(1, count // 4)
        for cols, rows in quadrants:
            available = [
                (c, r)
                for r in rows
                for c in cols
                if (c, r) not in excluded
            ]
            for _ in range(per_quad):
                if not available:
                    break
                pos = self.rng.choice(available)
                available.remove(pos)
                excluded.add(pos)
                pile = GoldPile(
                    pos=pos,
                    value=self.rng.randint(GOLD_PILE_MIN, GOLD_PILE_MAX),
                )
                self.gold_piles.append(pile)
                name = self.rng.choice(list(UNIT_STATS.keys()))
                value = UNIT_STATS[name]["value"]
                guard_count = max(1, round(2 * pile.value / value))
                self.armies.append(
                    OverworldArmy(player=0, units=[(name, guard_count)], pos=pile.pos)
                )

    def _spawn_objectives(self):
        excluded = {b.pos for b in self.bases if b.alive}
        excluded |= {p.pos for p in self.gold_piles}
        excluded |= {a.pos for a in self.armies}
        available = [
            (c, r)
            for r in range(self.ROWS)
            for c in range(self.COLS)
            if (c, r) not in excluded
        ]

        faction_list = list(FACTIONS.keys())
        faction_slots = {faction: idx + 1 for idx, faction in enumerate(faction_list)}
        base_by_player = {p: [b.pos for b in self.bases if b.player == p] for p in range(1, 5)}

        for faction_name in faction_list:
            home_slot = faction_slots.get(faction_name)
            for enemy_slot in range(1, 5):
                if enemy_slot == home_slot:
                    continue
                pos = self._pick_objective_pos_near(
                    base_by_player.get(enemy_slot, []), available
                )
                if pos is None:
                    return
                self.objectives.append(Objective(pos=pos, faction=faction_name))
                self._spawn_objective_guards(pos)

    def _spawn_objective_guards(self, pos):
        unit_names = list(UNIT_STATS.keys())
        if len(unit_names) < 2:
            return
        choices = self.rng.sample(unit_names, 2)
        units = []
        for name in choices:
            value = UNIT_STATS[name]["value"]
            count = max(1, round(OBJECTIVE_GUARD_VALUE / value))
            units.append((name, count))
        self.armies.append(OverworldArmy(player=0, units=units, pos=pos))

    def _pick_objective_pos_near(self, base_positions, available):
        if not available:
            return None
        candidates = []
        for pos in available:
            if any(hex_distance(pos, bpos) <= OBJECTIVE_NEAR_DISTANCE for bpos in base_positions):
                candidates.append(pos)
        pool = candidates or list(available)
        pos = self.rng.choice(pool)
        available.remove(pos)
        return pos

    def get_gold_pile_at(self, pos):
        for pile in self.gold_piles:
            if pile.pos == pos:
                return pile
        return None

    def get_objective_at(self, pos):
        for objective in getattr(self, "objectives", []):
            if objective.pos == pos:
                return objective
        return None

    def collect_gold_at(self, pos, player):
        pile = self.get_gold_pile_at(pos)
        if not pile:
            return 0
        value = pile.value
        self.gold[player] = self.gold.get(player, 0) + value
        self.gold_piles.remove(pile)
        return value

    def grant_income(self, player):
        income = sum(1 for b in self.bases if b.alive and b.player == player) * BASE_INCOME
        if income:
            self.gold[player] = self.gold.get(player, 0) + income
        return income

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

    def get_player_bases(self, player):
        return [b for b in self.bases if b.player == player and b.alive]

    def _add_units_to_army(self, pos, player, unit_name, count):
        """Add units to an existing army at pos, or create a new one."""
        army = self.get_army_at(pos)
        if army and army.player == player:
            for i, (name, existing) in enumerate(army.units):
                if name == unit_name:
                    army.units[i] = (name, existing + count)
                    return
            army.units.append((unit_name, count))
        else:
            self.armies.append(
                OverworldArmy(
                    player=player,
                    units=[(unit_name, count)],
                    pos=pos,
                )
            )

    def build_unit(self, player, unit_name):
        """Build a unit at the player's base. Returns error string or None on success."""
        base = self.get_player_base(player)
        if not base:
            return "No base"
        return self.build_unit_at_pos(player, unit_name, base.pos)

    def build_unit_at_pos(self, player, unit_name, pos):
        """Build a unit at a specific base position. Returns error string or None on success."""
        if unit_name not in UNIT_STATS:
            return f"Unknown unit: {unit_name}"
        base = self.get_base_at(pos)
        if not base or base.player != player:
            return "Invalid base"
        cost = UNIT_STATS[unit_name]["value"]
        if self.gold.get(player, 0) < cost:
            return "Not enough gold"
        self.gold[player] -= cost
        self._add_units_to_army(base.pos, player, unit_name, 1)
        return None

    def add_unit_at_base(self, player, unit_name, count=1):
        """Add units at the player's base without cost."""
        if unit_name not in ALL_UNIT_STATS:
            return f"Unknown unit: {unit_name}"
        base = self.get_player_base(player)
        if not base:
            return "No base"
        self._add_units_to_army(base.pos, player, unit_name, count)
        return None

    def add_unit_at_pos(self, player, unit_name, pos, count=1):
        """Add units at a specific position without cost."""
        if unit_name not in ALL_UNIT_STATS:
            return f"Unknown unit: {unit_name}"
        self._add_units_to_army(pos, player, unit_name, count)
        return None

    def to_dict(self):
        """Serialize overworld state to a dict."""
        return {
            "armies": serialize_armies(self.armies),
            "gold": self.gold,
            "bases": serialize_bases(self.bases),
            "gold_piles": serialize_gold_piles(self.gold_piles),
            "objectives": serialize_objectives(getattr(self, "objectives", [])),
        }

    @classmethod
    def from_dict(cls, data):
        """Restore an Overworld from a serialized dict."""
        ow = cls.__new__(cls)
        ow.rng_seed = data.get("rng_seed", 0)
        ow.rng = random.Random(ow.rng_seed)
        ow.armies = deserialize_armies(data.get("armies", []))
        ow.gold = {int(k): v for k, v in data.get("gold", {}).items()}
        ow.bases = deserialize_bases(data.get("bases", []))
        ow.gold_piles = deserialize_gold_piles(data.get("gold_piles", []))
        ow.objectives = deserialize_objectives(data.get("objectives", []))
        return ow

    def get_army_at(self, pos):
        for a in self.armies:
            if a.pos == pos:
                return a
        return None

    def get_armies_at(self, pos):
        return [a for a in self.armies if a.pos == pos]

    def move_army(self, army, new_pos):
        army.pos = new_pos

    def merge_armies(self, target, source):
        if target is source:
            return
        counts = {name: count for name, count in target.units}
        for name, count in source.units:
            counts[name] = counts.get(name, 0) + count
        target.units = list(counts.items())
        if source in self.armies:
            self.armies.remove(source)


ARMY_MOVE_RANGE = 3


class OverworldGUI:
    HEX_SIZE = 40

    def __init__(self, root, client=None, upgrade_mode="none"):
        """Initialize overworld GUI.

        Args:
            root: tkinter root or frame
            client: optional GameClient for multiplayer mode.
                    If None, runs in local single-player mode.
        """
        self.root = root
        self.client = client
        self.upgrade_mode = upgrade_mode
        self.player_id = 1  # default for single-player
        self.current_player = 1
        self._multiplayer = client is not None
        self.faction = None
        self.player_factions = {}
        self.player_upgrades = {}
        self.player_heroes = {}
        self._effective_stats_cache = {}
        self.ai_factions = {}
        self.ai_upgrades = {}
        self.ai_heroes = {}

        root.title("Wager of War - Overworld")

        if self._multiplayer:
            self.world = Overworld.__new__(Overworld)
            self.world.armies = []
            self.world.bases = []
            self.world.gold = {}
            self.world.gold_piles = []
            self.world.objectives = []
        else:
            self.world = Overworld(num_players=4)
            # Show faction selection before building
            self._pick_faction()
            self.player_factions[1] = self.faction
            self._assign_ai_factions_singleplayer()
            # Spawn heroes after factions are picked, before upgrades
            self.player_heroes[1] = self._choose_random_heroes(self.faction)
            p1_bases = self.world.get_player_bases(1)
            for hero_name, base in zip(self.player_heroes[1], p1_bases):
                self.world.add_unit_at_pos(1, hero_name, base.pos)
            for pid, faction_name in self.ai_factions.items():
                heroes = self._choose_random_heroes(faction_name)
                self.ai_heroes[pid] = heroes
                self.player_heroes[pid] = heroes
                bases = self.world.get_player_bases(pid)
                for hero_name, base in zip(heroes, bases):
                    self.world.add_unit_at_pos(pid, hero_name, base.pos)
            # Choose upgrades after factions are set
            self._pick_upgrade_singleplayer()
            for pid, faction_name in self.ai_factions.items():
                upgrade = self._auto_pick_upgrade(faction_name)
                self.ai_upgrades[pid] = upgrade
                if upgrade:
                    self.player_upgrades[pid] = [upgrade]
            # Auto-build AI armies since there's no AI turns
            for pid, faction_name in self.ai_factions.items():
                self._auto_build_ai(pid, faction_name)
            self.world.grant_income(1)

        self.selected_army = None
        self.selected_armies = []
        self.build_panel = None  # track build popup
        self.build_base_pos = None
        self.view_offset = [0, 0]
        self._pan_anchor = None

        # Main frame for overworld content
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        canvas_w = int(self.HEX_SIZE * 1.75 * Overworld.COLS + self.HEX_SIZE + 40)
        canvas_h = int(self.HEX_SIZE * 1.5 * Overworld.ROWS + self.HEX_SIZE + 40)

        left_frame = tk.Frame(self.main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.canvas = tk.Canvas(
            left_frame, width=canvas_w, height=canvas_h, bg="#2b3b2b"
        )
        self.canvas.pack(padx=5, pady=5)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self.canvas.bind("<Motion>", self._on_hover)
        root.bind("<Escape>", self._on_escape)
        root.bind("<space>", lambda e: self._on_end_turn())
        root.bind("<KeyPress-w>", lambda e: self._pan_by(0, 30))
        root.bind("<KeyPress-s>", lambda e: self._pan_by(0, -30))
        root.bind("<KeyPress-a>", lambda e: self._pan_by(30, 0))
        root.bind("<KeyPress-d>", lambda e: self._pan_by(-30, 0))
        root.bind("<KeyRelease-Shift_L>", self._on_shift_release)
        root.bind("<KeyRelease-Shift_R>", self._on_shift_release)
        self._load_overworld_assets()

        self.status_var = tk.StringVar(
            value="Waiting for players..."
            if self._multiplayer
            else "Click your base to build units, or move armies."
        )
        tk.Label(left_frame, textvariable=self.status_var, font=("Arial", 12)).pack(
            pady=5
        )

        self.gold_var = tk.StringVar(value="")
        tk.Label(
            left_frame,
            textvariable=self.gold_var,
            font=("Arial", 11, "bold"),
            fg="#B8960F",
        ).pack(pady=2)
        self._update_gold_display()

        self.end_turn_btn = tk.Button(
            left_frame, text="End Turn", font=("Arial", 12), command=self._on_end_turn
        )
        self.end_turn_btn.pack(pady=5)

        self.army_info_title = tk.StringVar(value="No army selected.")
        self._army_info_key = None

        # Battle log panel (right side)
        right_frame = tk.Frame(self.main_frame, width=250)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_frame.pack_propagate(False)
        self.army_info_frame = tk.Frame(
            right_frame, relief=tk.GROOVE, borderwidth=2, padx=6, pady=6
        )
        self.army_info_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            self.army_info_frame, text="Army Info", font=("Arial", 11, "bold")
        ).pack(anchor="w")
        tk.Label(
            self.army_info_frame,
            textvariable=self.army_info_title,
            font=("Arial", 9),
            justify=tk.LEFT,
        ).pack(anchor="w")
        self.army_info_units_frame = tk.Frame(self.army_info_frame)
        self.army_info_units_frame.pack(fill=tk.X, pady=(4, 0))

        tk.Label(right_frame, text="Battle Log", font=("Arial", 11, "bold")).pack()
        self.battle_log = tk.Listbox(
            right_frame, font=("Consolas", 9), selectmode=tk.SINGLE
        )
        self.battle_log.pack(fill=tk.BOTH, expand=True)
        self.battle_log.bind("<Double-Button-1>", self._on_replay_click)
        self._battle_log_ids = []  # parallel list of battle_ids
        self._local_battle_history = {}
        self._next_local_battle_id = 1

        self.tooltip = None
        self._hovered_army = None
        self.combat_frame = None

        if self._multiplayer:
            self.client.on_message = self._on_server_message
        else:
            self._draw()

    def _load_overworld_assets(self):
        asset_dir = get_asset_dir()
        gold_path = os.path.join(asset_dir, "gold_pile.png")
        img = Image.open(gold_path).convert("RGBA")
        self._gold_sprite = ImageTk.PhotoImage(img)
        small = img.resize((16, 16), Image.LANCZOS)
        self._gold_sprite_small = ImageTk.PhotoImage(small)

    def _pick_faction(self):
        """Show a modal dialog for the player to pick a faction."""
        import random as rng

        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Your Faction")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Faction", font=("Arial", 14, "bold")).pack(
            pady=10
        )

        for faction_name, unit_names in FACTIONS.items():
            frame = tk.Frame(dialog, relief=tk.RIDGE, borderwidth=2, padx=10, pady=5)
            frame.pack(fill=tk.X, padx=15, pady=5)
            tk.Label(frame, text=faction_name, font=("Arial", 12, "bold")).pack(
                anchor="w"
            )
            for uname in unit_names:
                s = UNIT_STATS[uname]
                desc = f"  {uname} — HP:{s['max_hp']} Dmg:{s['damage']} Rng:{s['range']} Cost:{s['value']}"
                for ab_text in _ability_texts(s):
                    desc += f" {ab_text}"
                label = tk.Label(frame, text=desc, font=("Arial", 9), anchor="w")
                label.pack(anchor="w")
                ability_lines = _ability_descriptions(s)
                if ability_lines:
                    self._bind_ability_hover(label, "\n".join(ability_lines))
            tk.Button(
                frame,
                text=f"Play {faction_name}",
                font=("Arial", 11),
                command=lambda fn=faction_name: self._select_faction(fn, dialog),
            ).pack(pady=5)

        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - dialog.winfo_height()) // 2
        )
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.root.wait_window(dialog)

        # Default if somehow closed without picking
        if self.faction is None:
            self.faction = rng.choice(list(FACTIONS.keys()))

    def _select_faction(self, faction_name, dialog):
        self.faction = faction_name
        dialog.destroy()

    def _assign_ai_factions_singleplayer(self):
        """Assign remaining factions to AI players (P2-P4) in single-player."""
        remaining = [f for f in FACTIONS if f != self.faction]
        for pid, faction_name in zip(range(2, 5), remaining):
            self.ai_factions[pid] = faction_name
            self.player_factions[pid] = faction_name

    def _choose_random_heroes(self, faction_name, count=2):
        import random as rng

        heroes = list(get_heroes_for_faction(faction_name))
        if not heroes:
            return []
        rng.shuffle(heroes)
        return heroes[: min(count, len(heroes))]

    def _auto_pick_upgrade(self, faction_name):
        """Pick a random upgrade for an AI faction."""
        import random as rng

        upgrades = get_upgrades_for_faction(faction_name)
        if not upgrades:
            return None
        return rng.choice(upgrades)["id"]

    def _get_effective_unit_stats(self, player_id):
        """Return a unit stats dict with the player's upgrade applied."""
        faction = self.player_factions.get(player_id)
        if not faction:
            return ALL_UNIT_STATS
        upgrade_ids = self.player_upgrades.get(player_id) or []
        if not isinstance(upgrade_ids, list):
            upgrade_ids = [upgrade_ids]
        cache_key = (faction, tuple(upgrade_ids))
        cached = self._effective_stats_cache.get(player_id)
        if cached and cached.get("key") == cache_key:
            return cached["stats"]
        faction_units = FACTIONS.get(
            faction, list(UNIT_STATS.keys())
        ) + HEROES_BY_FACTION.get(faction, [])
        stats = apply_upgrades_to_unit_stats(
            ALL_UNIT_STATS, upgrade_ids, faction_units
        )
        self._effective_stats_cache[player_id] = {"key": cache_key, "stats": stats}
        return stats

    def _get_unlocked_upgrades(self, player_id):
        upgrades = self.player_upgrades.get(player_id) or []
        if not isinstance(upgrades, list):
            upgrades = [upgrades]
        return upgrades

    def _is_hidden_objective_guard(self, army, my_faction):
        if army.player != 0:
            return False
        objective = self.world.get_objective_at(army.pos)
        return objective is not None and objective.faction != my_faction

    def _visible_armies_at(self, pos, my_faction):
        armies = self.world.get_armies_at(pos)
        return [a for a in armies if not self._is_hidden_objective_guard(a, my_faction)]

    @staticmethod
    def _pick_target_army(armies, my_player):
        for a in armies:
            if a.player not in (0, my_player):
                return a
        for a in armies:
            if a.player == my_player:
                return a
        return armies[0] if armies else None

    def _grant_objective_reward_local(self, player_id, reward):
        if reward == "gold":
            self.world.gold[player_id] = self.world.gold.get(player_id, 0) + 50
            self.status_var.set("Objective reward: 50 gold.")
            self._update_gold_display()
            return
        upgrades = self._get_unlocked_upgrades(player_id)
        if reward not in upgrades:
            upgrades.append(reward)
            self.player_upgrades[player_id] = upgrades
        self.status_var.set("Objective reward: upgrade unlocked.")

    def _show_upgrade_dialog(
        self, faction_name, player_factions, player_heroes, on_select
    ):
        upgrades = get_upgrades_for_faction(faction_name)
        if not upgrades:
            on_select(None, None)
            return
        faction_units = FACTIONS.get(
            faction_name, list(UNIT_STATS.keys())
        ) + HEROES_BY_FACTION.get(faction_name, [])
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Your Upgrade")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Upgrade", font=("Arial", 14, "bold")).pack(
            pady=8
        )
        if player_factions:
            tk.Label(dialog, text="Factions:", font=("Arial", 11, "bold")).pack(
                anchor="w", padx=12
            )
            for pid in sorted(player_factions.keys()):
                tk.Label(
                    dialog, text=f"P{pid}: {player_factions[pid]}", font=("Arial", 10)
                ).pack(anchor="w", padx=20)
        if player_heroes:
            tk.Label(dialog, text="Heroes:", font=("Arial", 11, "bold")).pack(
                anchor="w", padx=12, pady=(6, 0)
            )
            for pid in sorted(player_heroes.keys()):
                hero_list = player_heroes[pid]
                if isinstance(hero_list, str):
                    hero_list = [hero_list]
                for hero_name in hero_list:
                    hero_label = tk.Label(
                        dialog, text=f"P{pid}: {hero_name}", font=("Arial", 10)
                    )
                    hero_label.pack(anchor="w", padx=20)
                    hero_stats = ALL_UNIT_STATS.get(hero_name)
                    if hero_stats:
                        self._bind_ability_hover(
                            hero_label, _unit_tooltip_text(hero_name, hero_stats)
                        )

        for upgrade in upgrades:
            frame = tk.Frame(dialog, relief=tk.RIDGE, borderwidth=2, padx=10, pady=6)
            frame.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(frame, text=upgrade["name"], font=("Arial", 12, "bold")).pack(
                anchor="w"
            )
            summary_lines = upgrade_effect_summaries(
                upgrade, ALL_UNIT_STATS, faction_units
            )
            summary_text = (
                "\n".join(summary_lines)
                if summary_lines
                else upgrade.get("description", "")
            )
            tk.Label(
                frame,
                text=summary_text,
                font=("Arial", 9),
                wraplength=360,
                justify=tk.LEFT,
            ).pack(anchor="w")
            _add_upgrade_hover_rows(
                frame, upgrade, ALL_UNIT_STATS, faction_units, self._bind_ability_hover
            )
            tk.Button(
                frame,
                text=f"Choose {upgrade['name']}",
                font=("Arial", 10),
                command=lambda u=upgrade: on_select(u["id"], dialog),
            ).pack(pady=4)

        dialog.focus_force()

    def _pick_upgrade_singleplayer(self):
        faction = self.faction
        if not faction:
            return
        if self.upgrade_mode == "none":
            return
        if self.upgrade_mode == "random":
            upgrade_id = self._auto_pick_upgrade(faction)
            if upgrade_id:
                self.player_upgrades[1] = [upgrade_id]
            return

        def on_select(upgrade_id, dialog):
            self.player_upgrades[1] = [upgrade_id]
            if dialog:
                dialog.destroy()
            if upgrade_id:
                if hasattr(self, "status_var"):
                    self.status_var.set(
                        f"Upgrade selected: {get_upgrade_by_id(upgrade_id)['name']}"
                    )

        self._show_upgrade_dialog(
            faction, self.player_factions, self.player_heroes, on_select
        )

    def _pick_upgrade_multiplayer(self, player_factions):
        faction = player_factions.get(self.player_id)
        if not faction:
            return
        if self.upgrade_mode == "none":
            return
        if self.upgrade_mode == "random":
            upgrade_id = self._auto_pick_upgrade(faction)
            if upgrade_id:
                self.client.send({"type": SELECT_UPGRADE, "upgrade_id": upgrade_id})
            return

        def on_select(upgrade_id, dialog):
            if dialog:
                dialog.destroy()
            if upgrade_id:
                self.client.send({"type": SELECT_UPGRADE, "upgrade_id": upgrade_id})

        self._show_upgrade_dialog(
            faction, player_factions, self.player_heroes, on_select
        )

    def _pick_faction_multiplayer(self, taken):
        """Show faction picker for multiplayer, excluding already-taken factions."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Your Faction")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Faction", font=("Arial", 14, "bold")).pack(
            pady=10
        )

        for faction_name, unit_names in FACTIONS.items():
            is_taken = faction_name in taken
            frame = tk.Frame(dialog, relief=tk.RIDGE, borderwidth=2, padx=10, pady=5)
            frame.pack(fill=tk.X, padx=15, pady=5)
            label_text = faction_name + (" (taken)" if is_taken else "")
            tk.Label(
                frame,
                text=label_text,
                font=("Arial", 12, "bold"),
                fg="gray" if is_taken else "black",
            ).pack(anchor="w")
            for uname in unit_names:
                s = UNIT_STATS[uname]
                desc = f"  {uname} — HP:{s['max_hp']} Dmg:{s['damage']} Rng:{s['range']} Cost:{s['value']}"
                for ab_text in _ability_texts(s):
                    desc += f" {ab_text}"
                label = tk.Label(
                    frame,
                    text=desc,
                    font=("Arial", 9),
                    anchor="w",
                    fg="gray" if is_taken else "black",
                )
                label.pack(anchor="w")
                ability_lines = _ability_descriptions(s)
                if ability_lines:
                    self._bind_ability_hover(label, "\n".join(ability_lines))
            btn = tk.Button(
                frame,
                text=f"Play {faction_name}",
                font=("Arial", 11),
                state=tk.DISABLED if is_taken else tk.NORMAL,
                command=lambda fn=faction_name, d=dialog: self._select_faction_mp(
                    fn, d
                ),
            )
            btn.pack(pady=5)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - dialog.winfo_height()) // 2
        )
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _select_faction_mp(self, faction_name, dialog):
        """Send faction selection to server in multiplayer."""
        self.client.send({"type": SELECT_FACTION, "faction": faction_name})
        dialog.destroy()

    def _show_objective_reward_dialog(self, faction_name, upgrade_ids, on_select):
        dialog = tk.Toplevel(self.root)
        dialog.title("Objective Reward")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="Choose Your Reward", font=("Arial", 14, "bold")).pack(
            pady=8
        )
        tk.Label(
            dialog,
            text=f"{faction_name} objective completed!",
            font=("Arial", 9),
        ).pack(pady=(0, 6))

        for upgrade_id in upgrade_ids:
            upgrade = get_upgrade_by_id(upgrade_id)
            if not upgrade:
                continue
            text = upgrade.get("name", upgrade_id)
            tk.Button(
                dialog,
                text=text,
                width=28,
                command=lambda uid=upgrade_id: (on_select(uid), dialog.destroy()),
            ).pack(pady=2)

        tk.Button(
            dialog,
            text="50 Gold",
            width=28,
            command=lambda: (on_select("gold"), dialog.destroy()),
        ).pack(pady=(6, 8))

    def _auto_build_ai(self, player_id, faction_name):
        """Auto-spend an AI player's gold to create armies in single-player mode.
        Distributes gold roughly equally across all faction unit types."""
        import random as rng

        names = FACTIONS[faction_name]
        spent = {n: 0 for n in names}
        bases = self.world.get_player_bases(player_id)
        base_spent = {b.pos: 0 for b in bases}
        while self.world.gold.get(player_id, 0) > 0:
            affordable = [
                n
                for n in names
                if UNIT_STATS[n]["value"] <= self.world.gold[player_id]
            ]
            if not affordable:
                break
            # Pick the affordable unit with the least gold spent so far
            min_spent = min(spent[n] for n in affordable)
            candidates = [n for n in affordable if spent[n] == min_spent]
            name = rng.choice(candidates)
            spent[name] += UNIT_STATS[name]["value"]
            if bases:
                pos = min(base_spent, key=base_spent.get)
                err = self.world.build_unit_at_pos(player_id, name, pos)
                if err:
                    break
                base_spent[pos] += UNIT_STATS[name]["value"]
            else:
                self.world.build_unit(player_id, name)

    def _update_gold_display(self):
        my_player = self.player_id if self._multiplayer else 1
        gold = self.world.gold.get(my_player, 0)
        self.gold_var.set(f"Gold: {gold}")

    def _show_build_panel(self, base_pos=None):
        """Show a popup panel for building units at the player's base."""
        if self.build_panel:
            self._close_build_panel()

        self.build_base_pos = base_pos
        self.build_panel = tw = tk.Toplevel(self.root)
        tw.title("Build Unit")
        tw.resizable(False, False)
        tw.transient(self.root)

        self._build_gold_label = tk.Label(
            tw, text="", font=("Arial", 12, "bold"), fg="#B8960F"
        )
        self._build_gold_label.pack(pady=5)
        if self.build_base_pos:
            tk.Label(
                tw,
                text=f"Building at {self.build_base_pos}",
                font=("Arial", 9),
                fg="#cccccc",
            ).pack()

        self._build_buttons = {}
        self._build_order = []  # ordered list of unit names for hotkeys
        my_player = self.player_id if self._multiplayer else 1
        faction_units = (
            FACTIONS.get(self.faction, list(UNIT_STATS.keys()))
            if self.faction
            else list(UNIT_STATS.keys())
        )
        effective_stats = self._get_effective_unit_stats(my_player)
        for idx, name in enumerate(faction_units):
            stats = effective_stats[name]
            cost = stats["value"]
            hotkey = idx + 1
            text = f"[{hotkey}] {name} (Cost: {cost}) - HP:{stats['max_hp']} Dmg:{stats['damage']} Rng:{stats['range']}"
            for ab_text in _ability_texts(stats):
                text += f" {ab_text}"
            btn = tk.Button(
                tw,
                text=text,
                font=("Arial", 10),
                command=lambda n=name: self._do_build(n),
            )
            btn.pack(fill=tk.X, padx=10, pady=2)
            self._build_buttons[name] = btn
            self._build_order.append(name)
            self._bind_ability_hover(btn, _unit_tooltip_text(name, stats))

        # Bind number hotkeys
        for i, uname in enumerate(self._build_order):
            tw.bind(str(i + 1), lambda e, n=uname: self._do_build(n))

        tk.Button(tw, text="Close", command=self._close_build_panel).pack(pady=5)
        self._refresh_build_panel()
        # Also bind hotkeys on the root so they work even without build panel focus
        self._build_hotkey_ids = []
        for i, uname in enumerate(self._build_order):
            bid = self.root.bind(str(i + 1), lambda e, n=uname: self._do_build(n))
            self._build_hotkey_ids.append((str(i + 1), bid))
        tw.protocol("WM_DELETE_WINDOW", self._close_build_panel)
        tw.focus_force()

    def _bind_ability_hover(self, widget, description):
        tip = [None]

        def on_enter(e):
            tip[0] = tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root + 10}+{e.y_root + 20}")
            tk.Label(
                tw,
                text=description,
                fg="white",
                bg="#444",
                font=("Arial", 9),
                padx=6,
                pady=4,
                justify=tk.LEFT,
            ).pack()

        def on_leave(e):
            if tip[0]:
                tip[0].destroy()
                tip[0] = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _refresh_army_info_panel(self, force=False):
        if self.selected_army and self.selected_army not in self.world.armies:
            self.selected_army = None
        if self.selected_army is None:
            self.selected_armies = []
        if self.selected_armies:
            self.selected_armies = [
                a for a in self.selected_armies if a in self.world.armies
            ]
        if not self.selected_armies and self.selected_army:
            self.selected_armies = [self.selected_army]
        if not self.selected_armies:
            key = None
        else:
            key = tuple(
                (a.player, a.pos, tuple(a.units)) for a in self.selected_armies
            )
        if not force and key == self._army_info_key:
            return
        self._army_info_key = key

        for child in self.army_info_units_frame.winfo_children():
            child.destroy()

        if not self.selected_armies:
            self.army_info_title.set("No army selected.")
            return

        if len(self.selected_armies) == 1:
            army = self.selected_armies[0]
            owner = "Neutral" if army.player == 0 else f"P{army.player}"
            self.army_info_title.set(f"{owner} Army - {army.total_count} units")
            effective_stats = self._get_effective_unit_stats(army.player)
            for name, count in army.units:
                label = tk.Label(
                    self.army_info_units_frame,
                    text=f"{count}x {name}",
                    font=("Arial", 9),
                    anchor="w",
                    justify=tk.LEFT,
                )
                label.pack(anchor="w")
                stats = effective_stats.get(name)
                if stats:
                    self._bind_ability_hover(label, _unit_tooltip_text(name, stats))
            return

        self.army_info_title.set("Armies at hex")
        for army in self.selected_armies:
            owner = "Neutral" if army.player == 0 else f"P{army.player}"
            header = tk.Label(
                self.army_info_units_frame,
                text=f"{owner} Army - {army.total_count} units",
                font=("Arial", 9, "bold"),
                anchor="w",
                justify=tk.LEFT,
            )
            header.pack(anchor="w", pady=(4, 0))
            effective_stats = self._get_effective_unit_stats(army.player)
            for name, count in army.units:
                label = tk.Label(
                    self.army_info_units_frame,
                    text=f"{count}x {name}",
                    font=("Arial", 9),
                    anchor="w",
                    justify=tk.LEFT,
                )
                label.pack(anchor="w")
                stats = effective_stats.get(name)
                if stats:
                    self._bind_ability_hover(label, _unit_tooltip_text(name, stats))

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

    def _close_build_panel(self):
        """Close the build panel and unbind root hotkeys."""
        for key, bid in getattr(self, "_build_hotkey_ids", []):
            self.root.unbind(key, bid)
        self._build_hotkey_ids = []
        if self.build_panel and self.build_panel.winfo_exists():
            self.build_panel.destroy()
        self.build_panel = None
        self.build_base_pos = None
        self._draw()

    def _do_build(self, unit_name):
        """Execute a build action (panel stays open)."""
        if not self.build_panel or not self.build_panel.winfo_exists():
            return
        if self._multiplayer:
            payload = {"type": BUILD_UNIT, "unit_name": unit_name}
            if self.build_base_pos:
                payload["base_pos"] = list(self.build_base_pos)
            self.client.send(payload)
            self._refresh_build_panel()
        else:
            if self.build_base_pos:
                err = self.world.build_unit_at_pos(1, unit_name, self.build_base_pos)
            else:
                err = self.world.build_unit(1, unit_name)
            if err:
                self.status_var.set(f"Build failed: {err}")
            else:
                self.status_var.set(f"Built a {unit_name}.")
                self._update_gold_display()
                self._refresh_build_panel()
                self._draw()

    def _hex_center(self, col, row):
        x = self.HEX_SIZE * 1.75 * col + 50 + self.view_offset[0]
        if row % 2 == 1:
            x += self.HEX_SIZE * 0.875
        y = self.HEX_SIZE * 1.5 * row + 50 + self.view_offset[1]
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
        my_player = self.player_id if self._multiplayer else 1
        show_reachable = (
            self.selected_army
            and self.selected_army.player == my_player
            and self._is_my_turn()
        )
        my_faction = self.player_factions.get(my_player) if self._multiplayer else self.faction
        if show_reachable:
            occupied = {a.pos for a in w.armies if a is not self.selected_army}
            neighbors = reachable_hexes(
                self.selected_army.pos, ARMY_MOVE_RANGE, w.COLS, w.ROWS, occupied
            )
            # Also include hexes occupied by enemy armies (attack targets)
            for a in w.armies:
                if a.player != self.selected_army.player and not self._is_hidden_objective_guard(a, my_faction):
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
                self.canvas.create_polygon(
                    self._hex_polygon(cx, cy),
                    fill=fill,
                    outline=outline,
                    width=outline_width,
                )

        # Draw bases (behind armies, larger square)
        for base in getattr(w, "bases", []):
            if not base.alive:
                continue
            cx, cy = self._hex_center(base.pos[0], base.pos[1])
            color = PLAYER_COLORS.get(base.player, "#888888")
            s = 22
            outline = "white"
            outline_width = 2
            if self.build_panel and self.build_base_pos == base.pos:
                outline = "#ffdd55"
                outline_width = 3
            self.canvas.create_rectangle(
                cx - s,
                cy - s,
                cx + s,
                cy + s,
                fill=color,
                outline=outline,
                width=outline_width,
            )
            self.canvas.create_text(
                cx, cy - s + 8, text="B", fill="white", font=("Arial", 9, "bold")
            )

        # Draw gold piles
        army_positions = {a.pos for a in w.armies}
        for pile in getattr(w, "gold_piles", []):
            cx, cy = self._hex_center(pile.pos[0], pile.pos[1])
            if pile.pos in army_positions:
                # Show small gold icon at top-right of hex when army is on top
                if hasattr(self, "_gold_sprite_small") and self._gold_sprite_small:
                    s = self.HEX_SIZE
                    self.canvas.create_image(
                        cx + s * 0.45, cy - s * 0.45, image=self._gold_sprite_small
                    )
            elif hasattr(self, "_gold_sprite") and self._gold_sprite:
                self.canvas.create_image(cx, cy, image=self._gold_sprite)

        # Draw objectives (only visible to owning faction)
        for obj in getattr(w, "objectives", []):
            if obj.faction != my_faction:
                continue
            cx, cy = self._hex_center(obj.pos[0], obj.pos[1])
            color = PLAYER_COLORS.get(my_player, "#ffffff")
            self.canvas.create_oval(
                cx - 8,
                cy - 8,
                cx + 8,
                cy + 8,
                outline=color,
                width=2,
            )
            self.canvas.create_text(
                cx,
                cy,
                text="O",
                fill=color,
                font=("Arial", 8, "bold"),
            )
            # Reward indicator (upward arrow) at top-right of hex
            s = self.HEX_SIZE
            ax = cx + s * 0.45
            ay = cy - s * 0.45
            self.canvas.create_polygon(
                ax,
                ay - 6,
                ax - 5,
                ay + 4,
                ax + 5,
                ay + 4,
                fill=color,
                outline="",
            )

        # Draw armies
        for army in w.armies:
            if self._is_hidden_objective_guard(army, my_faction):
                continue
            cx, cy = self._hex_center(army.pos[0], army.pos[1])
            if army.exhausted:
                color = PLAYER_COLORS_EXHAUSTED.get(army.player, "#444444")
            else:
                color = PLAYER_COLORS.get(army.player, "#888888")
            self.canvas.create_oval(
                cx - 16, cy - 16, cx + 16, cy + 16, fill=color, outline="white", width=2
            )
            self.canvas.create_text(
                cx,
                cy,
                text=str(army.total_count),
                fill="white",
                font=("Arial", 12, "bold"),
            )

        self._refresh_army_info_panel()

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

    def _on_pan_start(self, event):
        self._pan_anchor = (event.x, event.y)

    def _on_pan_move(self, event):
        if not self._pan_anchor:
            return
        dx = event.x - self._pan_anchor[0]
        dy = event.y - self._pan_anchor[1]
        self.view_offset[0] += dx
        self.view_offset[1] += dy
        self._pan_anchor = (event.x, event.y)
        self._draw()

    def _on_pan_end(self, event):
        self._pan_anchor = None

    def _pan_by(self, dx, dy):
        self.view_offset[0] += dx
        self.view_offset[1] += dy
        self._draw()

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
                    tk.Label(
                        tw,
                        text=text,
                        justify=tk.LEFT,
                        bg="#ffffdd",
                        font=("Arial", 10),
                        padx=6,
                        pady=4,
                        relief=tk.SOLID,
                        borderwidth=1,
                    ).pack()
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
        my_faction = self.player_factions.get(my_player) if self._multiplayer else self.faction
        clicked_armies = self._visible_armies_at(clicked, my_faction)
        clicked_army = self._pick_target_army(clicked_armies, my_player)

        if not self._is_my_turn():
            if clicked_army:
                if self.selected_army and clicked == self.selected_army.pos:
                    self.selected_army = None
                    self.selected_armies = []
                    self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
                else:
                    self.selected_army = clicked_army
                    self.selected_armies = clicked_armies
                    if clicked_army.player == my_player:
                        self.status_var.set(
                            f"Selected: {clicked_army.label}. Waiting for your turn."
                        )
                    elif clicked_army.player == 0:
                        self.status_var.set("Neutral army selected.")
                    else:
                        self.status_var.set("Enemy army selected.")
                self._draw()
            else:
                if self.selected_army:
                    self.selected_army = None
                    self.selected_armies = []
                    self._draw()
                self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
            return

        # Click own base -> build panel only if no own army, or army already selected
        clicked_base = (
            self.world.get_base_at(clicked) if hasattr(self.world, "bases") else None
        )
        if clicked_base and clicked_base.player == my_player:
            if clicked_army and clicked_army.player == my_player:
                if self.selected_army == clicked_army:
                    # Already selected this army, so open build panel
                    self._show_build_panel(clicked_base.pos)
                    self._draw()
                    return
                # Army here but not selected yet — fall through to select it
            else:
                # No army on base, open build panel directly
                self._show_build_panel(clicked_base.pos)
                self._draw()
                return

        # No army selected yet
        if self.selected_army is None:
            if clicked_army:
                if clicked_army.player == my_player and clicked_army.exhausted:
                    self.status_var.set("That army is exhausted. End Turn to ready it.")
                    return
                self.selected_army = clicked_army
                self.selected_armies = clicked_armies
                if clicked_army.player == my_player:
                    self.status_var.set(
                        f"Selected: {clicked_army.label}. Right-click to move."
                    )
                elif clicked_army.player == 0:
                    self.status_var.set("Neutral army selected.")
                else:
                    self.status_var.set("Enemy army selected.")
                self._draw()
            else:
                self.status_var.set("Click an army to select it.")
            return

        # Click the same army -> deselect
        if clicked == self.selected_army.pos:
            self.selected_army = None
            self.selected_armies = []
            self.status_var.set("Selection cancelled.")
            self._draw()
            return

        # Click another army -> switch selection
        if clicked_army:
            if clicked_army.player == my_player and clicked_army.exhausted:
                self.status_var.set("That army is exhausted. End Turn to ready it.")
                return
            self.selected_army = clicked_army
            self.selected_armies = clicked_armies
            if clicked_army.player == my_player:
                self.status_var.set(
                    f"Selected: {clicked_army.label}. Right-click to move."
                )
            elif clicked_army.player == 0:
                self.status_var.set("Neutral army selected.")
            else:
                self.status_var.set("Enemy army selected.")
            self._draw()
            return

        # Left-click on non-own hex with selection: just deselect
        self.selected_army = None
        self.selected_armies = []
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
        if self.selected_army.player != my_player:
            self.status_var.set("Cannot move an enemy army.")
            return

        if not self._is_my_turn():
            self.status_var.set(f"Waiting for P{self.current_player}'s turn.")
            return

        shift_held = event.state & 0x1
        my_faction = self.player_factions.get(my_player) if self._multiplayer else self.faction
        clicked_armies = self._visible_armies_at(clicked, my_faction)
        clicked_army = self._pick_target_army(clicked_armies, my_player)
        is_own = clicked_army and clicked_army.player == my_player

        # Check reachability within move range
        occupied = {
            a.pos
            for a in self.world.armies
            if a is not self.selected_army
            and not self._is_hidden_objective_guard(a, my_faction)
            and a.pos != clicked
        }
        reachable = reachable_hexes(
            self.selected_army.pos,
            ARMY_MOVE_RANGE,
            self.world.COLS,
            self.world.ROWS,
            occupied,
        )
        if is_own and clicked not in reachable:
            self.status_var.set("Too far. Right-click a highlighted hex to move.")
            return

        # Enemy army hexes are valid attack targets even if "occupied"
        is_enemy = clicked_army and clicked_army.player != my_player
        if clicked not in reachable and not is_enemy:
            self.status_var.set("Too far. Right-click a highlighted hex to move.")
            return
        # For enemy targets, check that we can reach an adjacent hex
        if is_enemy and clicked not in reachable:
            # Check if any neighbor of the enemy is reachable
            adj = hex_neighbors(
                clicked[0], clicked[1], self.world.COLS, self.world.ROWS
            )
            adj_reachable = [
                h for h in adj if h in reachable or h == self.selected_army.pos
            ]
            if not adj_reachable:
                self.status_var.set("Too far. Right-click a highlighted hex to move.")
                return

        if shift_held:
            self._open_split_dialog(clicked, clicked_armies)
            return

        if self._multiplayer:
            self.client.send(
                {
                    "type": MOVE_ARMY,
                    "from": list(self.selected_army.pos),
                    "to": list(clicked),
                }
            )
            self.selected_army = None
            self._refresh_army_info_panel(force=True)
            return

        # Local single-player mode
        # Enemy -> battle
        if is_enemy:
            if clicked_army.player == 0:
                objective = self.world.get_objective_at(clicked)
                if objective and objective.faction != self.faction:
                    self.status_var.set("Objective belongs to another faction.")
                    return
            army = self.selected_army
            self.selected_army = None
            self.selected_armies = []
            self._start_battle(army, clicked_army)
            return
        if is_own:
            moving = self.selected_army
            self.selected_army = None
            self.selected_armies = []
            self.world.merge_armies(clicked_army, moving)
            clicked_army.exhausted = True
            gained = self.world.collect_gold_at(clicked, clicked_army.player)
            if gained:
                self.status_var.set(f"Armies combined and collected {gained} gold.")
            else:
                self.status_var.set("Armies combined.")
            self._update_gold_display()
            self._draw()
            return

        # Empty hex -> move
        army = self.selected_army
        self.selected_army = None
        self.selected_armies = []
        self.world.move_army(army, clicked)
        army.exhausted = True
        gained = self.world.collect_gold_at(clicked, army.player)
        # Check for base destruction
        self._check_local_base_destruction(clicked, army.player)
        if gained:
            self.status_var.set(f"Army moved to {clicked} and collected {gained} gold.")
        else:
            self.status_var.set(f"Army moved to {clicked}.")
        self._update_gold_display()
        self._draw()

    def _check_local_base_destruction(self, pos, moving_player):
        """Capture enemy base at pos in single-player mode."""
        for base in getattr(self.world, "bases", []):
            if base.pos == pos and base.alive and base.player != moving_player:
                base.player = moving_player
                self.status_var.set(f"P{moving_player} captured a base!")

    def _on_escape(self, event):
        if self.selected_army:
            self.selected_army = None
            self.status_var.set("Selection cancelled.")
            self._draw()

    def _on_end_turn(self):
        if self._multiplayer:
            if not self._is_my_turn():
                return
            self.client.send({"type": END_TURN})
            self.selected_army = None
            self.selected_armies = []
            self._refresh_army_info_panel(force=True)
            return

        # Local single-player
        for army in self.world.armies:
            if army.player == 1:
                army.exhausted = False
        income = self.world.grant_income(1)
        self.selected_army = None
        self.selected_armies = []
        if income:
            self.status_var.set(
                f"New turn. Gained {income} gold from bases. Click a P1 army to select it."
            )
        else:
            self.status_var.set("New turn. Click a P1 army to select it.")
        self._update_gold_display()
        self._draw()

    def _make_battle_units(self, army):
        """Convert an army's units list into Battle-compatible dicts."""
        return make_battle_units(army, self._get_effective_unit_stats(army.player))

    def _start_battle(self, attacker, defender):
        """Start a local single-player battle."""
        # Attacker is always battle P1 (left side of screen)
        ow_p1, ow_p2 = attacker, defender

        import random

        p1_units = self._make_battle_units(ow_p1)
        p2_units = self._make_battle_units(ow_p2)
        rng_seed = random.randint(0, 2**31 - 1)

        battle = Battle(p1_units=p1_units, p2_units=p2_units, rng_seed=rng_seed)

        # Hide overworld UI
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.main_frame.pack_forget()
        self.status_var.set("Battle in progress!")

        self.combat_frame = tk.Frame(self.root)
        self.combat_frame.pack(fill=tk.BOTH, expand=True)

        def on_battle_complete(winner, p1_survivors, p2_survivors):
            # Use the GUI's current battle (may differ from original after reset)
            current_battle = (
                self._combat_gui.battle
                if hasattr(self, "_combat_gui") and self._combat_gui
                else battle
            )
            if hasattr(self, "_combat_gui") and self._combat_gui:
                self._combat_gui._close_log()
                self._combat_gui = None
            self.combat_frame.destroy()
            self.combat_frame = None

            result = resolve_battle(
                self.world,
                attacker,
                defender,
                current_battle,
                winner,
                p1_survivors,
                p2_survivors,
            )
            ow_winner = result["winner"]
            summary = result["summary"]

            if result["moved_to"] is not None:
                self._check_local_base_destruction(result["moved_to"], attacker.player)
            if result["gained_gold"]:
                self._update_gold_display()

            if ow_winner == attacker.player and defender.player == 0:
                objective = self.world.get_objective_at(defender.pos)
                if objective and objective.faction == self.player_factions.get(
                    attacker.player
                ):
                    self.world.objectives.remove(objective)
                    upgrades = get_upgrades_for_faction(objective.faction)
                    unlocked = set(self._get_unlocked_upgrades(attacker.player))
                    available = [u["id"] for u in upgrades if u["id"] not in unlocked]
                    self._show_objective_reward_dialog(
                        objective.faction,
                        available,
                        lambda reward: self._grant_objective_reward_local(
                            attacker.player, reward
                        ),
                    )

            if self.battle_log is not None:
                self.battle_log.insert(tk.END, summary)
                battle_id = self._next_local_battle_id
                self._next_local_battle_id += 1
                self._battle_log_ids.append(battle_id)
                self._local_battle_history[battle_id] = {
                    "battle_id": battle_id,
                    "p1_units": p1_units,
                    "p2_units": p2_units,
                    "rng_seed": rng_seed,
                    "attacker_player": ow_p1.player,
                    "defender_player": ow_p2.player,
                }

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
                survivors = p1_survivors if winner == 1 else p2_survivors
                self.status_var.set(
                    f"Battle over. P{ow_winner} won with {survivors} survivors."
                )
            self._draw()

        self._combat_gui = CombatGUI(
            self.combat_frame,
            battle=battle,
            on_complete=on_battle_complete,
            attacker_player=ow_p1.player,
            defender_player=ow_p2.player,
        )

    def _open_split_dialog(self, dest_pos, dest_armies):
        if dest_pos == self.selected_army.pos:
            self.status_var.set("Select a different destination to split.")
            return

        source = self.selected_army
        moving_counts = {name: 0 for name, _ in source.units}

        dialog = tk.Toplevel(self.root)
        dialog.title("Split Army")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        top = tk.Frame(dialog)
        top.pack(padx=10, pady=10)

        left = tk.Frame(top, relief=tk.GROOVE, borderwidth=2, padx=6, pady=6)
        left.pack(side=tk.LEFT, padx=5)
        tk.Label(left, text="Source Army", font=("Arial", 10, "bold")).pack(anchor="w")

        mid = tk.Frame(top, relief=tk.GROOVE, borderwidth=2, padx=6, pady=6)
        mid.pack(side=tk.LEFT, padx=5)
        tk.Label(mid, text="Moving", font=("Arial", 10, "bold")).pack(anchor="w")

        right = tk.Frame(top, relief=tk.GROOVE, borderwidth=2, padx=6, pady=6)
        right.pack(side=tk.LEFT, padx=5)
        tk.Label(right, text="Destination", font=("Arial", 10, "bold")).pack(anchor="w")

        src_labels = {}
        mid_labels = {}

        def _update_labels():
            for name, count in source.units:
                moved = moving_counts.get(name, 0)
                src_labels[name].config(text=f"{count - moved}x {name}")
                mid_labels[name].config(text=f"{moved}x {name}")

        for name, count in source.units:
            row = tk.Frame(left)
            row.pack(anchor="w", pady=2, fill=tk.X)
            lbl = tk.Label(
                row, text=f"{count}x {name}", font=("Arial", 9), width=14, anchor="w"
            )
            lbl.pack(side=tk.LEFT)
            src_labels[name] = lbl
            tk.Button(
                row, text="+1", width=3, command=lambda n=name: _move_units(n, 1)
            ).pack(side=tk.LEFT, padx=2)
            tk.Button(
                row,
                text="+All",
                width=5,
                command=lambda n=name, c=count: _move_units(n, c),
            ).pack(side=tk.LEFT)

            row_mid = tk.Frame(mid)
            row_mid.pack(anchor="w", pady=2, fill=tk.X)
            mid_lbl = tk.Label(
                row_mid, text=f"0x {name}", font=("Arial", 9), width=14, anchor="w"
            )
            mid_lbl.pack(side=tk.LEFT)
            mid_labels[name] = mid_lbl
            tk.Button(
                row_mid, text="-1", width=3, command=lambda n=name: _move_units(n, -1)
            ).pack(side=tk.LEFT, padx=2)
            tk.Button(
                row_mid,
                text="-All",
                width=5,
                command=lambda n=name, c=count: _move_units(n, -c),
            ).pack(side=tk.LEFT)

        if dest_armies:
            for dest_army in dest_armies:
                owner = "Neutral" if dest_army.player == 0 else f"P{dest_army.player}"
                tk.Label(right, text=f"{owner} Army", font=("Arial", 9, "bold")).pack(
                    anchor="w"
                )
                for name, count in dest_army.units:
                    tk.Label(
                        right, text=f"{count}x {name}", font=("Arial", 9), anchor="w"
                    ).pack(anchor="w")
        else:
            tk.Label(right, text="Empty", font=("Arial", 9), anchor="w").pack(
                anchor="w"
            )

        def _move_units(name, delta):
            available = dict(source.units).get(name, 0)
            current = moving_counts.get(name, 0)
            if delta > 0:
                moving_counts[name] = min(available, current + delta)
            else:
                moving_counts[name] = max(0, current + delta)
            _update_labels()

        _update_labels()

        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=(0, 10))

        def on_confirm():
            total_moving = sum(moving_counts.values())
            if total_moving <= 0:
                self.status_var.set("Select at least one unit to move.")
                return

            moving_units = [
                (name, cnt) for name, cnt in moving_counts.items() if cnt > 0
            ]
            if self._multiplayer:
                self.client.send(
                    {
                        "type": SPLIT_MOVE,
                        "from": list(source.pos),
                        "to": list(dest_pos),
                        "units": moving_units,
                    }
                )
                dialog.destroy()
                self.selected_army = None
                self._refresh_army_info_panel(force=True)
                return

            source_units = []
            for name, count in source.units:
                remaining = count - moving_counts.get(name, 0)
                if remaining > 0:
                    source_units.append((name, remaining))
            source.units = source_units
            if not source.units and source in self.world.armies:
                self.world.armies.remove(source)

            moving_army = OverworldArmy(
                player=source.player, units=moving_units, pos=source.pos
            )

            dest_army = self._pick_target_army(dest_armies, source.player)
            if dest_army and dest_army.player != source.player:
                if dest_army.player == 0:
                    objective = self.world.get_objective_at(dest_pos)
                    if objective and objective.faction != self.faction:
                        self.status_var.set("Objective belongs to another faction.")
                        return
                self.world.armies.append(moving_army)
                self.selected_army = None
                self.selected_armies = []
                dialog.destroy()
                self._start_battle(moving_army, dest_army)
                return

            if dest_army and dest_army.player == source.player:
                self.world.merge_armies(dest_army, moving_army)
                dest_army.exhausted = True
                gained = self.world.collect_gold_at(dest_pos, dest_army.player)
                if gained:
                    self.status_var.set(f"Armies combined and collected {gained} gold.")
                else:
                    self.status_var.set("Armies combined.")
            else:
                self.world.armies.append(moving_army)
                self.world.move_army(moving_army, dest_pos)
                moving_army.exhausted = True
                gained = self.world.collect_gold_at(dest_pos, moving_army.player)
                self._check_local_base_destruction(dest_pos, moving_army.player)
                if gained:
                    self.status_var.set(
                        f"Army moved to {dest_pos} and collected {gained} gold."
                    )
                else:
                    self.status_var.set(f"Army moved to {dest_pos}.")

            dialog.destroy()
            self.selected_army = None
            self.selected_armies = []
            self._update_gold_display()
            self._draw()

        tk.Button(btn_row, text="Confirm", width=10, command=on_confirm).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(btn_row, text="Cancel", width=10, command=dialog.destroy).pack(
            side=tk.LEFT, padx=5
        )

    # --- Multiplayer message handling ---

    def _msg_joined(self, msg):
        self.player_id = msg["player_id"]
        self.status_var.set(
            f"You are P{self.player_id}. Waiting for players ({msg['player_count']}/{msg['needed']})..."
        )

    def _msg_faction_prompt(self, msg):
        picking = msg["picking_player"]
        taken = msg.get("taken", [])
        if picking == self.player_id:
            self.status_var.set("Choose your faction!")
            self._pick_faction_multiplayer(taken)
        else:
            self.status_var.set(f"Waiting for P{picking} to choose a faction...")

    def _msg_upgrade_prompt(self, msg):
        picking = msg["picking_player"]
        player_factions = msg.get("player_factions", {})
        self.player_factions = self._coerce_int_keys(player_factions)
        player_heroes = msg.get("player_heroes", {})
        self.player_heroes = self._coerce_int_keys(player_heroes)
        if picking == self.player_id:
            self.status_var.set("Choose your upgrade!")
            self._pick_upgrade_multiplayer(self.player_factions)
        else:
            self.status_var.set(f"Waiting for P{picking} to choose an upgrade...")

    @staticmethod
    def _coerce_int_keys(mapping):
        return {int(k): v for k, v in (mapping or {}).items()}

    def _set_turn_status(self, base_message, my_turn_message=None):
        if self._is_my_turn():
            if my_turn_message:
                self.status_var.set(my_turn_message)
                return
            suffix = f" Your turn (P{self.player_id})."
        else:
            suffix = f" Waiting for P{self.current_player}."
        self.status_var.set(f"{base_message}{suffix}")

    def _apply_world_state(self, msg):
        self.world.armies = deserialize_armies(msg["armies"])
        self.world.bases = deserialize_bases(msg.get("bases", []))
        self.world.gold = {int(k): v for k, v in msg.get("gold", {}).items()}
        self.world.gold_piles = deserialize_gold_piles(msg.get("gold_piles", []))
        self.world.objectives = deserialize_objectives(msg.get("objectives", []))
        self.selected_armies = []
        if "player_factions" in msg:
            self.player_factions = self._coerce_int_keys(msg.get("player_factions", {}))
        if "player_heroes" in msg:
            self.player_heroes = self._coerce_int_keys(msg.get("player_heroes", {}))
        if "player_upgrades" in msg:
            self.player_upgrades = self._coerce_int_keys(msg.get("player_upgrades", {}))

    def _msg_game_start(self, msg):
        self.player_id = msg["player_id"]
        self.current_player = msg["current_player"]
        self.faction = msg.get("faction")
        self._apply_world_state(msg)
        if not self.faction and self.player_factions:
            self.faction = self.player_factions.get(self.player_id)
        self._update_gold_display()
        self._set_turn_status(
            "Game started!",
            my_turn_message=(
                f"Game started! Your turn (P{self.player_id}). "
                "Click your base to build units."
            ),
        )
        self._draw()

    def _msg_state_update(self, msg):
        self._apply_world_state(msg)
        self._update_gold_display()
        self._refresh_build_panel()
        self.current_player = msg["current_player"]
        self.selected_army = None
        status = msg.get("message", "")
        self._set_turn_status(status)
        self._draw()

    def _msg_battle_end(self, msg):
        if self.battle_log is not None:
            self.battle_log.insert(tk.END, msg["summary"])
            self._battle_log_ids.append(msg["battle_id"])

    def _msg_replay_data(self, msg):
        self._show_replay(msg)

    def _msg_game_over(self, msg):
        winner = msg["winner"]
        if winner == self.player_id:
            self.status_var.set("You win!")
        else:
            self.status_var.set(f"P{winner} wins the game!")

    def _msg_error(self, msg):
        self.status_var.set(f"Error: {msg['message']}")

    def _msg_objective_reward_prompt(self, msg):
        faction = msg.get("faction")
        upgrade_ids = msg.get("upgrade_ids", [])
        self._show_objective_reward_dialog(
            faction,
            upgrade_ids,
            lambda reward: self.client.send(
                {"type": OBJECTIVE_REWARD_CHOICE, "reward": reward}
            ),
        )

    _SERVER_MSG_DISPATCH = {
        JOINED: _msg_joined,
        FACTION_PROMPT: _msg_faction_prompt,
        UPGRADE_PROMPT: _msg_upgrade_prompt,
        GAME_START: _msg_game_start,
        STATE_UPDATE: _msg_state_update,
        BATTLE_END: _msg_battle_end,
        REPLAY_DATA: _msg_replay_data,
        GAME_OVER: _msg_game_over,
        ERROR: _msg_error,
        OBJECTIVE_REWARD_PROMPT: _msg_objective_reward_prompt,
    }

    def _on_server_message(self, msg):
        """Handle a message from the server (called from main thread via queue polling)."""
        handler = self._SERVER_MSG_DISPATCH.get(msg.get("type"))
        if handler:
            handler(self, msg)

    def _close_replay(self):
        """Close the replay viewer and return to overworld."""
        if self.combat_frame:
            self.combat_frame.destroy()
            self.combat_frame = None
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self._draw()

    def _on_replay_click(self, event):
        """Handle double-click on battle log to request replay."""
        if not self.battle_log:
            return
        sel = self.battle_log.curselection()
        if sel:
            idx = sel[0]
            if idx < len(self._battle_log_ids):
                battle_id = self._battle_log_ids[idx]
                if self.client:
                    self.client.send(
                        {
                            "type": REQUEST_REPLAY,
                            "battle_id": battle_id,
                        }
                    )
                else:
                    record = self._local_battle_history.get(battle_id)
                    if record:
                        self._show_replay(record)

    def _show_replay(self, msg):
        """Show a battle replay by re-simulating locally with the server's seed."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.main_frame.pack_forget()

        self.combat_frame = tk.Frame(self.root)
        self.combat_frame.pack(fill=tk.BOTH, expand=True)

        battle = Battle(
            p1_units=msg["p1_units"],
            p2_units=msg["p2_units"],
            rng_seed=msg["rng_seed"],
        )

        CombatGUI(
            self.combat_frame,
            battle=battle,
            on_complete=lambda w, p1, p2: self._close_replay(),
            attacker_player=msg.get("attacker_player"),
            defender_player=msg.get("defender_player"),
        )

    def run(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = OverworldGUI(root)
    app.run()


if __name__ == "__main__":
    main()




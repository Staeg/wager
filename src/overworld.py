import random
from dataclasses import dataclass
from .hex import hex_distance
from .protocol import (
    deserialize_armies,
    deserialize_bases,
    deserialize_gold_piles,
    deserialize_objectives,
    serialize_armies,
    serialize_bases,
    serialize_gold_piles,
    serialize_objectives,
)
from .ability_defs import ability
from .constants import (
    NEUTRAL_PLAYER,
    STARTING_GOLD,
    GOLD_PILE_COUNT,
    GOLD_PILE_MIN,
    GOLD_PILE_MAX,
    OBJECTIVE_GUARD_VALUE,
    OBJECTIVE_NEAR_DISTANCE,
)
from .heroes import HERO_STATS

# Canonical unit stats
UNIT_STATS = {
    # Custodians (yellow/orange)
    "Page": {
        "max_hp": 3,
        "damage": 1,
        "range": 1,
        "value": 2,
        "speed": 1.2,
        "abilities": [],
    },
    "Librarian": {
        "max_hp": 2,
        "damage": 0,
        "range": 3,
        "value": 12,
        "abilities": [
            ability("endturn", "sunder", target="random", value=1)
        ],
    },
    "Steward": {"max_hp": 20, "damage": 3, "range": 1, "value": 10, "abilities": []},
    "Gatekeeper": {
        "max_hp": 32,
        "damage": 4,
        "range": 2,
        "value": 25,
        "abilities": [ability("passive", "undying", value=2, aura="R")],
    },
    # Weavers (purple/blue)
    "Apprentice": {
        "max_hp": 8,
        "damage": 1,
        "range": 2,
        "value": 5,
        "abilities": [
            ability("onhit", "push", target="target", value=1)
        ],
    },
    "Conduit": {
        "max_hp": 1,
        "damage": 2,
        "range": 2,
        "value": 10,
        "abilities": [ability("onhit", "freeze", target="random", value=1)],
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
        "abilities": [ability("passive", "armor", value=2)],
    },
    "Kitboy": {
        "max_hp": 6,
        "damage": 2,
        "range": 2,
        "value": 10,
        "abilities": [ability("endturn", "heal", target="area", value=1, range=1)],
    },
    "Artillery": {
        "max_hp": 8,
        "damage": 4,
        "range": 4,
        "value": 25,
        "abilities": [ability("endturn", "strike", target="random", value=2, range=6)],
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
        "abilities": [ability("endturn", "heal", target="random", value=3)],
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
                "endturn", "summon", target="self", count=2, charge=3
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
class Structure:
    player: int
    pos: tuple  # (col, row)
    alive: bool = True
    income: int = 5  # gold per turn
    allows_recruitment: bool = True  # whether units can be built here


# Alias for backward compatibility
Base = Structure


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
        self._spawn_neutral_structures()
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
            if len(candidates) < 3:
                break
            picks = self.rng.sample(candidates, 3)
            for pos in picks:
                occupied.add(pos)
                self.bases.append(Base(player=p, pos=pos))

    def _spawn_neutral_structures(self):
        """Spawn 3 neutral income-only structures per quadrant, each guarded."""
        excluded = {b.pos for b in self.bases if b.alive}
        mid_c = self.COLS // 2
        mid_r = self.ROWS // 2
        quadrants = [
            (range(0, mid_c), range(0, mid_r)),
            (range(mid_c, self.COLS), range(0, mid_r)),
            (range(0, mid_c), range(mid_r, self.ROWS)),
            (range(mid_c, self.COLS), range(mid_r, self.ROWS)),
        ]
        for cols, rows in quadrants:
            available = [(c, r) for r in rows for c in cols if (c, r) not in excluded]
            for _ in range(3):
                if not available:
                    break
                pos = self.rng.choice(available)
                available.remove(pos)
                excluded.add(pos)
                income = self.rng.randint(5, 10)
                self.bases.append(
                    Structure(
                        player=NEUTRAL_PLAYER,
                        pos=pos,
                        income=income,
                        allows_recruitment=False,
                    )
                )
                # Spawn guards worth 6x the income value
                guard_value = 6 * income
                name = self.rng.choice(list(UNIT_STATS.keys()))
                value = UNIT_STATS[name]["value"]
                guard_count = max(1, round(guard_value / value))
                self.armies.append(
                    OverworldArmy(
                        player=NEUTRAL_PLAYER, units=[(name, guard_count)], pos=pos
                    )
                )

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
            available = [(c, r) for r in rows for c in cols if (c, r) not in excluded]
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
                    OverworldArmy(
                        player=NEUTRAL_PLAYER, units=[(name, guard_count)], pos=pile.pos
                    )
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
        base_by_player = {
            p: [b.pos for b in self.bases if b.player == p] for p in range(1, 5)
        }

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
        self.armies.append(OverworldArmy(player=NEUTRAL_PLAYER, units=units, pos=pos))

    def _pick_objective_pos_near(self, base_positions, available):
        if not available:
            return None
        candidates = []
        for pos in available:
            if any(
                hex_distance(pos, bpos) <= OBJECTIVE_NEAR_DISTANCE
                for bpos in base_positions
            ):
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
        income = sum(b.income for b in self.bases if b.alive and b.player == player)
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
        # Find a base that allows recruitment
        base = None
        for b in self.bases:
            if b.player == player and b.alive and b.allows_recruitment:
                base = b
                break
        if not base:
            return "No base that allows recruitment"
        return self.build_unit_at_pos(player, unit_name, base.pos)

    def build_unit_at_pos(self, player, unit_name, pos):
        """Build a unit at a specific base position. Returns error string or None on success."""
        if unit_name not in UNIT_STATS:
            return f"Unknown unit: {unit_name}"
        base = self.get_base_at(pos)
        if not base or base.player != player:
            return "Invalid base"
        if not base.allows_recruitment:
            return "This structure does not allow recruitment"
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

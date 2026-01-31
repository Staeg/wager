"""Message protocol constants and serialization helpers for multiplayer."""

import json

# Message types - Client -> Server
JOIN = "join"
MOVE_ARMY = "move_army"
SPLIT_MOVE = "split_move"
END_TURN = "end_turn"
REQUEST_REPLAY = "request_replay"
BUILD_UNIT = "build_unit"
SELECT_FACTION = "select_faction"
SELECT_UPGRADE = "select_upgrade"

# Message types - Server -> Client
JOINED = "joined"
FACTION_PROMPT = "faction_prompt"
UPGRADE_PROMPT = "upgrade_prompt"
GAME_START = "game_start"
STATE_UPDATE = "state_update"
BATTLE_END = "battle_end"
REPLAY_DATA = "replay_data"
ERROR = "error"
GAME_OVER = "game_over"


def serialize_base(base):
    """Convert a Base to a JSON-serializable dict."""
    return {
        "player": base.player,
        "pos": list(base.pos),
        "alive": base.alive,
    }


def serialize_bases(bases):
    """Convert a list of Base objects to serializable list."""
    return [serialize_base(b) for b in bases]


def serialize_army(army):
    """Convert an OverworldArmy to a JSON-serializable dict."""
    return {
        "player": army.player,
        "units": army.units,
        "pos": list(army.pos),
        "exhausted": army.exhausted,
    }


def serialize_armies(armies):
    """Convert a list of OverworldArmy objects to serializable list."""
    return [serialize_army(a) for a in armies]


def serialize_gold_piles(gold_piles):
    """Convert a list of GoldPile objects to serializable list."""
    return [{"pos": list(p.pos), "value": p.value} for p in gold_piles]


def deserialize_gold_piles(data):
    """Convert serialized gold pile dicts back to GoldPile objects."""
    from .overworld import GoldPile

    return [GoldPile(pos=tuple(p["pos"]), value=p["value"]) for p in data]


def deserialize_armies(data):
    """Convert serialized army dicts back to OverworldArmy objects."""
    from .overworld import OverworldArmy

    armies = []
    for d in data:
        armies.append(
            OverworldArmy(
                player=d["player"],
                units=[tuple(u) for u in d["units"]],
                pos=tuple(d["pos"]),
                exhausted=d["exhausted"],
            )
        )
    return armies


def deserialize_bases(data):
    """Convert serialized base dicts back to Base objects."""
    from .overworld import Base

    return [
        Base(player=d["player"], pos=tuple(d["pos"]), alive=d["alive"]) for d in data
    ]


def encode(msg):
    """Encode a message dict to JSON string."""
    return json.dumps(msg)


def decode(raw):
    """Decode a JSON string to message dict."""
    return json.loads(raw)

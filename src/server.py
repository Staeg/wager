"""Dedicated WebSocket game server for multiplayer Wager of War."""

import asyncio
import random
import argparse
import socket
import sys
import os

if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(__file__))

import websockets

from combat import Battle, Unit
from overworld import Overworld, UNIT_STATS, ARMY_MOVE_RANGE, _reachable_hexes
from overworld import FACTIONS
from protocol import (
    serialize_armies, serialize_bases, encode, decode,
    JOIN, MOVE_ARMY, END_TURN, REQUEST_REPLAY, BUILD_UNIT, SELECT_FACTION,
    JOINED, GAME_START, STATE_UPDATE, BATTLE_END,
    REPLAY_DATA, ERROR, GAME_OVER, FACTION_PROMPT,
)
from combat import hex_neighbors


class BattleRecord:
    """Stores a completed battle for replay."""

    def __init__(self, battle_id, p1_units, p2_units, rng_seed, winner, summary):
        self.battle_id = battle_id
        self.p1_units = p1_units
        self.p2_units = p2_units
        self.rng_seed = rng_seed
        self.winner = winner
        self.summary = summary


class GameServer:
    def __init__(self, num_players=2, host="0.0.0.0", port=8765):
        self.num_players = num_players
        self.host = host
        self.port = port
        self.players = {}  # player_id -> websocket
        self.player_names = {}  # player_id -> name
        self.next_player_id = 1
        self.current_player = 1
        self.world = None
        self.started = False
        self.battle_history = []
        self.next_battle_id = 1
        self.player_factions = {}  # player_id -> faction name
        self._faction_selection_order = []  # order of players to pick factions
        self._faction_selection_idx = 0  # which player is currently picking

    def _build_world(self):
        """Create an Overworld with bases and gold, no starting armies."""
        world = Overworld(num_players=self.num_players)
        return world

    async def broadcast(self, msg):
        """Send message to all connected players."""
        raw = encode(msg)
        for ws in self.players.values():
            try:
                await ws.send(raw)
            except websockets.ConnectionClosed:
                pass

    async def send_to(self, player_id, msg):
        """Send message to a specific player."""
        ws = self.players.get(player_id)
        if ws:
            try:
                await ws.send(encode(msg))
            except websockets.ConnectionClosed:
                pass

    def _state_update_msg(self, message=""):
        return {
            "type": STATE_UPDATE,
            "armies": serialize_armies(self.world.armies),
            "bases": serialize_bases(self.world.bases),
            "gold": self.world.gold,
            "current_player": self.current_player,
            "message": message,
        }

    def _players_with_armies(self):
        """Return set of player IDs that still have armies or alive bases."""
        players = {a.player for a in self.world.armies}
        players |= {b.player for b in self.world.bases if b.alive}
        return players

    def _next_player(self):
        """Advance to next player who still has armies."""
        active = sorted(self._players_with_armies())
        if not active:
            return self.current_player
        idx = active.index(self.current_player) if self.current_player in active else -1
        return active[(idx + 1) % len(active)]

    def _make_battle_units(self, army):
        """Convert an OverworldArmy to Battle-compatible dicts."""
        result = []
        for name, count in army.units:
            s = UNIT_STATS[name]
            spec = {"name": name, "max_hp": s["max_hp"], "damage": s["damage"],
                    "range": s["range"], "count": count}
            for key in ("armor", "heal", "sunder", "push", "ramp", "amplify",
                        "undying", "splash", "repair", "bombardment", "bombardment_range",
                        "rage", "vengeance", "charge", "summon_count"):
                if s.get(key, 0):
                    spec[key] = s[key]
            result.append(spec)
        return result

    async def _run_battle(self, attacker, defender):
        """Run a battle server-side and broadcast the result."""
        battle_id = self.next_battle_id
        self.next_battle_id += 1

        # Ensure lower-numbered overworld player is always battle P1
        if attacker.player <= defender.player:
            ow_p1, ow_p2 = attacker, defender
        else:
            ow_p1, ow_p2 = defender, attacker

        p1_units = self._make_battle_units(ow_p1)
        p2_units = self._make_battle_units(ow_p2)
        rng_seed = random.randint(0, 2**31)

        # Run battle to completion
        Unit._id_counter = 0
        battle = Battle(p1_units=p1_units, p2_units=p2_units, rng_seed=rng_seed)
        while battle.step():
            pass

        battle_winner = battle.winner
        p1_survivors = sum(1 for u in battle.units if u.alive and u.player == 1)
        p2_survivors = sum(1 for u in battle.units if u.alive and u.player == 2)

        # Map battle winner to overworld player
        if battle_winner == 1:
            ow_winner = ow_p1.player
        elif battle_winner == 2:
            ow_winner = ow_p2.player
        else:
            ow_winner = 0

        # Update overworld state
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

        if battle_winner == 0:
            _update_survivors(ow_p1, 1)
            _update_survivors(ow_p2, 2)
            attacker.exhausted = True
        elif battle_winner == 1:
            _update_survivors(ow_p1, 1)
            self.world.armies.remove(ow_p2)
            self.world.move_army(ow_p1, ow_p2.pos)
            ow_p1.exhausted = True
        else:
            _update_survivors(ow_p2, 2)
            self.world.armies.remove(ow_p1)

        summary = f"P{ow_p1.player} vs P{ow_p2.player}: P{ow_winner} wins ({p1_survivors} vs {p2_survivors} survivors)"
        if battle_winner == 0:
            summary = f"P{ow_p1.player} vs P{ow_p2.player}: Draw"

        # Record for replay (just seed + units, lightweight)
        self.battle_history.append(BattleRecord(
            battle_id=battle_id,
            p1_units=p1_units,
            p2_units=p2_units,
            rng_seed=rng_seed,
            winner=ow_winner,
            summary=summary,
        ))

        # Broadcast battle result
        await self.broadcast({
            "type": BATTLE_END,
            "battle_id": battle_id,
            "winner": ow_winner,
            "attacker_player": attacker.player,
            "defender_player": defender.player,
            "summary": summary,
        })

        return ow_winner

    def _check_base_destruction(self, pos, moving_player):
        """Destroy any enemy base at the given position."""
        for base in self.world.bases:
            if base.pos == pos and base.alive and base.player != moving_player:
                base.alive = False

    async def _check_game_over(self):
        """Check if only one player remains."""
        active = self._players_with_armies()
        if len(active) <= 1:
            winner = active.pop() if active else 0
            await self.broadcast({"type": GAME_OVER, "winner": winner})
            return True
        return False

    async def handle_client(self, websocket):
        player_id = None
        try:
            async for raw in websocket:
                msg = decode(raw)
                msg_type = msg.get("type")

                if msg_type == JOIN:
                    if self.started:
                        await websocket.send(encode({"type": ERROR, "message": "Game already started"}))
                        continue
                    player_id = self.next_player_id
                    self.next_player_id += 1
                    self.players[player_id] = websocket
                    self.player_names[player_id] = msg.get("player_name", f"Player {player_id}")

                    await websocket.send(encode({
                        "type": JOINED,
                        "player_id": player_id,
                        "player_count": len(self.players),
                        "needed": self.num_players,
                    }))

                    # Notify all players of count update
                    for pid, ws in self.players.items():
                        if pid != player_id:
                            try:
                                await ws.send(encode({
                                    "type": JOINED,
                                    "player_id": pid,
                                    "player_count": len(self.players),
                                    "needed": self.num_players,
                                }))
                            except websockets.ConnectionClosed:
                                pass

                    if len(self.players) == self.num_players:
                        await self._start_faction_selection()

                elif msg_type == MOVE_ARMY:
                    if not self.started:
                        await self.send_to(player_id, {"type": ERROR, "message": "Game not started"})
                        continue
                    if player_id != self.current_player:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not your turn"})
                        continue

                    from_pos = tuple(msg["from"])
                    to_pos = tuple(msg["to"])

                    army = self.world.get_army_at(from_pos)
                    if not army or army.player != player_id:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not your army"})
                        continue
                    if army.exhausted:
                        await self.send_to(player_id, {"type": ERROR, "message": "Army is exhausted"})
                        continue

                    # Check reachability within move range
                    occupied = {a.pos for a in self.world.armies if a.pos != from_pos}
                    reachable = _reachable_hexes(
                        from_pos, ARMY_MOVE_RANGE, Overworld.COLS, Overworld.ROWS, occupied
                    )

                    target = self.world.get_army_at(to_pos)
                    if target and target.player == player_id:
                        await self.send_to(player_id, {"type": ERROR, "message": "Cannot move onto own army"})
                        continue

                    is_enemy = target and target.player != player_id
                    if to_pos not in reachable and not is_enemy:
                        await self.send_to(player_id, {"type": ERROR, "message": "Out of move range"})
                        continue
                    if is_enemy and to_pos not in reachable:
                        adj = hex_neighbors(to_pos[0], to_pos[1], Overworld.COLS, Overworld.ROWS)
                        if not any(h in reachable or h == from_pos for h in adj):
                            await self.send_to(player_id, {"type": ERROR, "message": "Out of move range"})
                            continue

                    if is_enemy:
                        # Battle
                        await self._run_battle(army, target)
                        # Check for base destruction at battle location
                        if army in self.world.armies:
                            self._check_base_destruction(army.pos, army.player)
                        if await self._check_game_over():
                            continue
                        await self.broadcast(self._state_update_msg(
                            f"Battle resolved between P{army.player} and P{target.player}."
                        ))
                    else:
                        # Move
                        self.world.move_army(army, to_pos)
                        army.exhausted = True
                        # Check for base destruction at new position
                        self._check_base_destruction(to_pos, player_id)
                        if await self._check_game_over():
                            continue
                        await self.broadcast(self._state_update_msg(
                            f"P{player_id} moved army to {to_pos}."
                        ))

                elif msg_type == SELECT_FACTION:
                    faction_name = msg.get("faction")
                    if not self._faction_selection_order:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not in faction selection phase"})
                        continue
                    expected_pid = self._faction_selection_order[self._faction_selection_idx]
                    if player_id != expected_pid:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not your turn to pick"})
                        continue
                    taken = set(self.player_factions.values())
                    if faction_name in taken:
                        await self.send_to(player_id, {"type": ERROR, "message": f"{faction_name} is already taken"})
                        continue
                    if faction_name not in FACTIONS:
                        await self.send_to(player_id, {"type": ERROR, "message": f"Unknown faction: {faction_name}"})
                        continue
                    self.player_factions[player_id] = faction_name
                    self._faction_selection_idx += 1
                    if self._faction_selection_idx >= len(self._faction_selection_order):
                        # All players have picked — start the game
                        self._faction_selection_order = []
                        await self._start_game()
                    else:
                        # Prompt next player
                        await self._prompt_next_faction()

                elif msg_type == BUILD_UNIT:
                    if not self.started:
                        await self.send_to(player_id, {"type": ERROR, "message": "Game not started"})
                        continue
                    if player_id != self.current_player:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not your turn"})
                        continue
                    unit_name = msg.get("unit_name", "")
                    # Restrict to player's faction
                    faction = self.player_factions.get(player_id)
                    if faction and unit_name not in FACTIONS[faction]:
                        await self.send_to(player_id, {"type": ERROR, "message": f"Cannot build {unit_name} — not in your faction"})
                        continue
                    err = self.world.build_unit(player_id, unit_name)
                    if err:
                        await self.send_to(player_id, {"type": ERROR, "message": err})
                    else:
                        await self.broadcast(self._state_update_msg(
                            f"P{player_id} built a {unit_name}."
                        ))

                elif msg_type == END_TURN:
                    if player_id != self.current_player:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not your turn"})
                        continue
                    # Clear exhaustion for current player
                    for army in self.world.armies:
                        if army.player == self.current_player:
                            army.exhausted = False
                    self.current_player = self._next_player()
                    await self.broadcast(self._state_update_msg(
                        f"P{player_id} ended turn. P{self.current_player}'s turn."
                    ))

                elif msg_type == REQUEST_REPLAY:
                    bid = msg.get("battle_id")
                    record = next((b for b in self.battle_history if b.battle_id == bid), None)
                    if record:
                        await self.send_to(player_id, {
                            "type": REPLAY_DATA,
                            "battle_id": bid,
                            "p1_units": record.p1_units,
                            "p2_units": record.p2_units,
                            "rng_seed": record.rng_seed,
                        })
                    else:
                        await self.send_to(player_id, {"type": ERROR, "message": f"Battle {bid} not found"})

        except websockets.ConnectionClosed:
            pass
        finally:
            if player_id and player_id in self.players:
                del self.players[player_id]
                if self.started:
                    await self.broadcast(self._state_update_msg(
                        f"P{player_id} disconnected."
                    ))
                    await self._check_game_over()

    async def _start_faction_selection(self):
        """Begin sequential faction selection: P1 picks first, then P2, etc."""
        self._faction_selection_order = sorted(self.players.keys())
        self._faction_selection_idx = 0
        await self._prompt_next_faction()

    async def _prompt_next_faction(self):
        """Send a faction prompt to the next player who needs to pick."""
        pid = self._faction_selection_order[self._faction_selection_idx]
        taken = list(self.player_factions.values())
        # Notify all players who is picking
        await self.broadcast({
            "type": FACTION_PROMPT,
            "picking_player": pid,
            "taken": taken,
        })

    async def _start_game(self):
        self.started = True
        self.world = self._build_world()
        self.current_player = 1

        for pid in self.players:
            await self.send_to(pid, {
                "type": GAME_START,
                "armies": serialize_armies(self.world.armies),
                "bases": serialize_bases(self.world.bases),
                "gold": self.world.gold,
                "current_player": self.current_player,
                "player_id": pid,
                "faction": self.player_factions.get(pid),
            })

    async def run(self):
        print(f"Server starting on {self.host}:{self.port}, waiting for {self.num_players} players...")
        # Create socket with SO_REUSEADDR so we can rebind immediately after restart
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen()
        sock.setblocking(False)
        async with websockets.serve(self.handle_client, sock=sock):
            await asyncio.Future()  # run forever


def main():
    parser = argparse.ArgumentParser(description="Wager of War multiplayer server")
    parser.add_argument("--players", type=int, default=2, help="Number of players (2-4)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()

    server = GameServer(num_players=args.players, host=args.host, port=args.port)
    asyncio.run(server.run())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nServer error: {e}")
        if getattr(sys, 'frozen', False):
            input("Press Enter to exit...")
        raise

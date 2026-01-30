"""Dedicated WebSocket game server for multiplayer Wager of War."""

import asyncio
import random
import argparse
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import websockets

from combat import Battle, Unit
from overworld import Overworld, OverworldArmy, UNIT_STATS, unit_count
from protocol import (
    serialize_armies, encode, decode,
    JOIN, MOVE_ARMY, END_TURN, REQUEST_REPLAY,
    JOINED, GAME_START, STATE_UPDATE, BATTLE_END,
    REPLAY_DATA, ERROR, GAME_OVER,
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

    def _build_world(self):
        """Create an Overworld with armies distributed for num_players."""
        all_names = list(UNIT_STATS.keys())
        # Generate all C(5,3)=10 three-unit combos
        from itertools import combinations
        combos = list(combinations(all_names, 3))

        # Starting positions per player
        positions = {
            1: [(0, 0), (1, 1), (2, 2), (0, 3), (1, 0)],
            2: [(9, 0), (8, 1), (7, 2), (9, 3), (8, 0)],
            3: [(0, 7), (1, 6), (2, 5), (0, 4), (1, 7)],
            4: [(9, 7), (8, 6), (7, 5), (9, 4), (8, 7)],
        }

        # Distribute combos round-robin
        armies = []
        for i, combo in enumerate(combos):
            player = (i % self.num_players) + 1
            pos_list = positions[player]
            pos_idx = sum(1 for a in armies if a.player == player)
            if pos_idx >= len(pos_list):
                continue  # skip if too many for this player
            units = [(name, unit_count(name)) for name in combo]
            armies.append(OverworldArmy(
                player=player,
                units=units,
                pos=pos_list[pos_idx],
            ))

        world = Overworld.__new__(Overworld)
        world.armies = armies
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
            "current_player": self.current_player,
            "message": message,
        }

    def _players_with_armies(self):
        """Return set of player IDs that still have armies."""
        return {a.player for a in self.world.armies}

    def _next_player(self):
        """Advance to next player who still has armies."""
        active = sorted(self._players_with_armies())
        if not active:
            return self.current_player
        idx = active.index(self.current_player) if self.current_player in active else -1
        return active[(idx + 1) % len(active)]

    def _make_battle_units(self, army):
        """Convert an OverworldArmy to Battle-compatible tuples."""
        result = []
        for name, count in army.units:
            s = UNIT_STATS[name]
            result.append((name, s["max_hp"], s["damage"], s["range"], count, s["armor"], s["heal"], s["sunder"]))
        return result

    async def _run_battle(self, attacker, defender):
        """Run a battle server-side and broadcast the result."""
        battle_id = self.next_battle_id
        self.next_battle_id += 1

        p1_units = self._make_battle_units(attacker)
        p2_units = self._make_battle_units(defender)
        rng_seed = random.randint(0, 2**31)

        # Run battle to completion
        Unit._id_counter = 0
        battle = Battle(p1_units=p1_units, p2_units=p2_units, rng_seed=rng_seed)
        while battle.step():
            pass

        winner = battle.winner
        p1_survivors = sum(1 for u in battle.units if u.alive and u.player == 1)
        p2_survivors = sum(1 for u in battle.units if u.alive and u.player == 2)

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

        if winner == 0:
            _update_survivors(attacker, 1)
            _update_survivors(defender, 2)
            attacker.exhausted = True
        elif winner == 1:
            _update_survivors(attacker, 1)
            self.world.armies.remove(defender)
            self.world.move_army(attacker, defender.pos)
            attacker.exhausted = True
        else:
            _update_survivors(defender, 2)
            self.world.armies.remove(attacker)

        summary = f"P{attacker.player} vs P{defender.player}: P{winner} wins ({p1_survivors} vs {p2_survivors} survivors)"
        if winner == 0:
            summary = f"P{attacker.player} vs P{defender.player}: Draw"

        # Record for replay (just seed + units, lightweight)
        self.battle_history.append(BattleRecord(
            battle_id=battle_id,
            p1_units=p1_units,
            p2_units=p2_units,
            rng_seed=rng_seed,
            winner=winner,
            summary=summary,
        ))

        # Broadcast battle result
        await self.broadcast({
            "type": BATTLE_END,
            "battle_id": battle_id,
            "winner": winner,
            "attacker_player": attacker.player,
            "defender_player": defender.player,
            "summary": summary,
        })

        return winner

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
                        await self._start_game()

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

                    neighbors = hex_neighbors(from_pos[0], from_pos[1], Overworld.COLS, Overworld.ROWS)
                    if to_pos not in neighbors:
                        await self.send_to(player_id, {"type": ERROR, "message": "Not adjacent"})
                        continue

                    target = self.world.get_army_at(to_pos)
                    if target and target.player == player_id:
                        await self.send_to(player_id, {"type": ERROR, "message": "Cannot move onto own army"})
                        continue

                    if target and target.player != player_id:
                        # Battle
                        await self._run_battle(army, target)
                        if await self._check_game_over():
                            continue
                        await self.broadcast(self._state_update_msg(
                            f"Battle resolved between P{army.player} and P{target.player}."
                        ))
                    else:
                        # Move
                        self.world.move_army(army, to_pos)
                        army.exhausted = True
                        await self.broadcast(self._state_update_msg(
                            f"P{player_id} moved army to {to_pos}."
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

    async def _start_game(self):
        self.started = True
        self.world = self._build_world()
        self.current_player = 1

        for pid in self.players:
            await self.send_to(pid, {
                "type": GAME_START,
                "armies": serialize_armies(self.world.armies),
                "current_player": self.current_player,
                "player_id": pid,
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
    main()

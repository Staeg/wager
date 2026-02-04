"""AI controller for single-player mode."""

import random
from dataclasses import dataclass, field

from .hex import bfs_next_step, hex_distance
from .overworld import FACTIONS, UNIT_STATS


@dataclass
class AIState:
    """Per-AI-player state tracking."""

    player_id: int
    mode: str  # "inactive", "passive", "aggressive"
    staging_ground: tuple | None = None  # (col, row) of a friendly base
    targets: dict = field(default_factory=dict)  # {army_id -> target_army_pos}
    next_spend_turn: int = 0
    turn_counter: int = 0


class AIController:
    """Controls AI players based on their mode."""

    def __init__(self, mode: str = "inactive"):
        self.mode = mode
        self.states: dict[int, AIState] = {}  # player_id -> AIState

    def init_player(
        self,
        player_id: int,
        world,
        faction_name: str,
        build_callback,
        log_callback=None,
    ):
        """Initialize an AI player at game start."""
        state = AIState(player_id=player_id, mode=self.mode)
        self.states[player_id] = state

        if self.mode == "inactive":
            # Spend once at start, then do nothing
            self.spend_distributed(player_id, world, faction_name, build_callback)
        elif self.mode == "passive":
            # Spend at start, set next spend turn to 3-7 turns later
            self.spend_distributed(player_id, world, faction_name, build_callback)
            state.next_spend_turn = random.randint(3, 7)
        elif self.mode == "aggressive":
            # Spend distributed, set staging ground, designate targets
            self.spend_distributed(player_id, world, faction_name, build_callback)
            self.set_staging_ground(state, world)
            # Designate targets for all armies using "fair" mode
            for army in world.armies:
                if army.player == player_id:
                    target_army = self.designate_target(army, state, world, mode="fair")
                    if target_army and log_callback:
                        army_name = (
                            f'"{army.moniker}"' if army.moniker else f"at {army.pos}"
                        )
                        target_name = (
                            f'"{target_army.moniker}"'
                            if target_army.moniker
                            else f"at {target_army.pos}"
                        )
                        log_callback(f"P{player_id} {army_name} hunting {target_name}")
            state.next_spend_turn = random.randint(2, 5)

    def spend_distributed(
        self, player_id: int, world, faction_name: str, build_callback
    ):
        """Distribute gold roughly evenly across all faction unit types and bases."""
        names = FACTIONS.get(faction_name, [])
        if not names:
            return

        spent = {n: 0 for n in names}
        bases = world.get_player_bases(player_id)
        if not bases:
            return

        base_spent = {b.pos: 0 for b in bases}

        while world.gold.get(player_id, 0) > 0:
            affordable = [
                n
                for n in names
                if UNIT_STATS[n]["value"] <= world.gold.get(player_id, 0)
            ]
            if not affordable:
                break

            # Pick the affordable unit with the least gold spent so far
            min_spent = min(spent[n] for n in affordable)
            candidates = [n for n in affordable if spent[n] == min_spent]
            name = random.choice(candidates)
            spent[name] += UNIT_STATS[name]["value"]

            # Pick the base with the least gold spent so far
            pos = min(base_spent, key=base_spent.get)
            err = build_callback(player_id, name, pos)
            if err:
                break
            base_spent[pos] += UNIT_STATS[name]["value"]

    def spend_focused(
        self, player_id: int, base_pos: tuple, world, faction_name: str, build_callback
    ):
        """Build units at one specific base with balanced types."""
        names = FACTIONS.get(faction_name, [])
        if not names:
            return

        spent = {n: 0 for n in names}

        while world.gold.get(player_id, 0) > 0:
            affordable = [
                n
                for n in names
                if UNIT_STATS[n]["value"] <= world.gold.get(player_id, 0)
            ]
            if not affordable:
                break

            # Pick the affordable unit with the least gold spent so far
            min_spent = min(spent[n] for n in affordable)
            candidates = [n for n in affordable if spent[n] == min_spent]
            name = random.choice(candidates)
            spent[name] += UNIT_STATS[name]["value"]

            err = build_callback(player_id, name, base_pos)
            if err:
                break

    def designate_target(self, army, state: AIState, world, mode: str = "random"):
        """Assign a target to an army.

        mode="random": Pick a random enemy army
        mode="fair": Pick an army from the player with fewest targeted armies

        Returns: target army or None if no target found
        """
        # Get all non-friendly armies with monikers (excluding neutrals for aggressive targeting)
        enemy_armies = [
            a
            for a in world.armies
            if a.player != state.player_id and a.player != 0 and a.moniker
        ]
        if not enemy_armies:
            # Fall back to any non-friendly army with a moniker
            enemy_armies = [
                a for a in world.armies if a.player != state.player_id and a.moniker
            ]

        if not enemy_armies:
            return None

        army_key = id(army)
        target = None

        if mode == "fair":
            # Count how many of our armies are targeting each player
            target_counts = {}
            for a in world.armies:
                if a.player == state.player_id:
                    target_moniker = state.targets.get(id(a))
                    if target_moniker:
                        target_army = world.get_army_by_moniker(target_moniker)
                        if target_army:
                            target_counts[target_army.player] = (
                                target_counts.get(target_army.player, 0) + 1
                            )

            # Find the player(s) with the fewest armies targeted
            enemy_players = set(a.player for a in enemy_armies)
            min_targeted = min(target_counts.get(p, 0) for p in enemy_players)
            least_targeted_players = [
                p for p in enemy_players if target_counts.get(p, 0) == min_targeted
            ]

            # Pick a random army from a least-targeted player
            candidate_armies = [
                a for a in enemy_armies if a.player in least_targeted_players
            ]
            if candidate_armies:
                target = random.choice(candidate_armies)
                state.targets[army_key] = target.moniker
        else:
            # Random mode: just pick any enemy army
            target = random.choice(enemy_armies)
            state.targets[army_key] = target.moniker

        return target

    def hunt_target(self, army, state: AIState, world, log_callback=None):
        """Move army toward its target or staging ground.

        Returns: (new_pos, target_army) if combat should occur, else (new_pos, None)
        """
        from .overworld import Overworld

        army_key = id(army)
        target_moniker = state.targets.get(army_key)

        # Find target army by moniker
        target_army = None
        target_pos = None
        if target_moniker:
            target_army = world.get_army_by_moniker(target_moniker)
            if target_army and target_army.player != state.player_id:
                target_pos = target_army.pos
            else:
                # Target is gone or became friendly, clear it
                del state.targets[army_key]
                if log_callback and state.staging_ground:
                    army_name = (
                        f'"{army.moniker}"' if army.moniker else f"at {army.pos}"
                    )
                    log_callback(
                        f'P{state.player_id} {army_name}: target "{target_moniker}" lost, '
                        f"returning to staging ground"
                    )
                target_army = None

        if not target_pos:
            # No target, move to staging ground
            if state.staging_ground:
                goal = state.staging_ground
            else:
                return army.pos, None
        else:
            goal = target_pos

        if army.pos == goal:
            # Already at goal
            if target_army and target_army.player != state.player_id:
                return army.pos, target_army
            return army.pos, None

        # Check if we're adjacent to the target and can attack
        if target_pos and hex_distance(army.pos, target_pos) == 1:
            if target_army and target_army.player != state.player_id:
                return army.pos, target_army

        # Build set of occupied hexes (other armies, but not our target)
        occupied = set()
        for a in world.armies:
            if a is not army and a.pos != target_pos:
                occupied.add(a.pos)

        # Get next step toward goal
        next_pos = bfs_next_step(
            army.pos, goal, occupied, Overworld.COLS, Overworld.ROWS
        )

        if next_pos == army.pos:
            # Can't move
            return army.pos, None

        # Check if next_pos has an enemy
        army_at_next = world.get_army_at(next_pos)
        if army_at_next and army_at_next.player != state.player_id:
            # Don't move into enemy, just initiate combat
            return army.pos, army_at_next

        # Move the army
        world.move_army(army, next_pos)

        # After moving, check if now adjacent to target for attack
        if target_pos and hex_distance(next_pos, target_pos) == 1:
            if target_army and target_army.player != state.player_id:
                return next_pos, target_army

        return next_pos, None

    def set_staging_ground(self, state: AIState, world):
        """Pick a random friendly base as the staging ground."""
        bases = world.get_player_bases(state.player_id)
        if bases:
            state.staging_ground = random.choice(bases).pos

    def on_turn_end(
        self,
        world,
        faction_names: dict,
        build_callback,
        battle_callback,
        log_callback=None,
    ):
        """Process AI turns at end of player turn.

        Args:
            world: Overworld instance
            faction_names: dict mapping player_id -> faction_name
            build_callback: callable(player_id, unit_name, pos) -> error or None
            battle_callback: callable(attacker, defender) -> None
            log_callback: optional callable(message) for logging AI actions
        """
        pending_battles = []

        for player_id, state in self.states.items():
            state.turn_counter += 1
            faction_name = faction_names.get(player_id, "")

            if state.mode == "inactive":
                # Do nothing after initial spend
                continue

            elif state.mode == "passive":
                # Spend every 3-7 turns
                if state.turn_counter >= state.next_spend_turn:
                    self.spend_distributed(
                        player_id, world, faction_name, build_callback
                    )
                    state.next_spend_turn = state.turn_counter + random.randint(3, 7)

            elif state.mode == "aggressive":
                # Check if it's time to spend focused
                if state.turn_counter >= state.next_spend_turn:
                    # Pick a random base for focused spending
                    bases = world.get_player_bases(player_id)
                    if bases:
                        base = random.choice(bases)
                        self.spend_focused(
                            player_id, base.pos, world, faction_name, build_callback
                        )
                        # Designate target for newly created army at that base
                        army_at_base = world.get_army_at(base.pos)
                        if army_at_base and army_at_base.player == player_id:
                            target_army = self.designate_target(
                                army_at_base, state, world, mode="random"
                            )
                            if target_army and log_callback:
                                army_name = (
                                    f'"{army_at_base.moniker}"'
                                    if army_at_base.moniker
                                    else f"at {army_at_base.pos}"
                                )
                                target_name = (
                                    f'"{target_army.moniker}"'
                                    if target_army.moniker
                                    else f"at {target_army.pos}"
                                )
                                log_callback(
                                    f"P{player_id} {army_name} hunting {target_name}"
                                )
                    self.set_staging_ground(state, world)
                    state.next_spend_turn = state.turn_counter + random.randint(2, 5)

                # Hunt targets with all armies
                for army in list(world.armies):
                    if army.player != player_id or army.exhausted:
                        continue
                    if army not in world.armies:
                        # Army was removed during iteration
                        continue

                    new_pos, target_army = self.hunt_target(
                        army, state, world, log_callback
                    )
                    army.exhausted = True

                    if target_army:
                        pending_battles.append((army, target_army))

        return pending_battles

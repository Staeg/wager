"""Hex grid utilities (offset coordinates, even-r) and pathfinding."""

from collections import deque


def offset_to_cube(col, row):
    x = col - (row - (row % 2)) // 2
    z = row
    y = -x - z
    return x, y, z


def cube_distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def hex_distance(c1, c2):
    return cube_distance(offset_to_cube(*c1), offset_to_cube(*c2))


def hex_neighbors(col, row, cols, rows):
    parity = row % 2
    if parity == 0:
        dirs = [(1, 0), (-1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1)]
    else:
        dirs = [(1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 1)]
    results = []
    for dc, dr in dirs:
        nc, nr = col + dc, row + dr
        if 0 <= nc < cols and 0 <= nr < rows:
            results.append((nc, nr))
    return results


# --- Pathfinding ---


def bfs_next_step(start, goal, occupied, cols, rows):
    """Return the next hex to move to from start toward goal, avoiding occupied hexes.
    If no full path exists, moves to the unoccupied neighbor closest to goal by hex distance."""
    if start == goal:
        return start

    def _neighbor_priority(current, nb):
        current_dist = hex_distance(current, goal)
        next_dist = hex_distance(nb, goal)
        closer = 0 if next_dist < current_dist else 1
        horizontal = 0 if nb[1] == current[1] else 1
        return (closer, horizontal, next_dist)

    queue = deque()
    queue.append((start, [start]))
    visited = {start}
    while queue:
        current, path = queue.popleft()
        neighbors = hex_neighbors(current[0], current[1], cols, rows)
        neighbors.sort(key=lambda nb: _neighbor_priority(current, nb))
        for nb in neighbors:
            if nb in visited:
                continue
            visited.add(nb)
            new_path = path + [nb]
            if nb == goal:
                return new_path[1]
            if nb not in occupied:
                queue.append((nb, new_path))
    # No full path found — move to the adjacent unoccupied hex closest to goal
    best = start
    best_dist = hex_distance(start, goal)
    best_horizontal = 1
    for nb in hex_neighbors(start[0], start[1], cols, rows):
        if nb not in occupied:
            d = hex_distance(nb, goal)
            horiz = 0 if nb[1] == start[1] else 1
            if d < best_dist or (d == best_dist and horiz < best_horizontal):
                best_dist = d
                best_horizontal = horiz
                best = nb
    return best


def bfs_path_length(start, goal, occupied, cols, rows):
    """Return the BFS path length from start to goal, avoiding occupied hexes.
    The goal itself is allowed even if occupied. Returns a large number if no path."""
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


def reachable_hexes(start, steps, cols, rows, occupied):
    """Return set of hexes reachable from start within `steps` moves, avoiding occupied."""
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
    result = set(visited.keys())
    result.discard(start)
    return result


def bfs_path(start, goal, cols, rows, occupied):
    """Return the path from start to goal avoiding occupied hexes, or None."""
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

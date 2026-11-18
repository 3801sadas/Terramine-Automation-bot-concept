"""Gold Rush solver: minimal clockwise-tap route on the 6x6 tile board."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set

# Directions as (dr, dc). Row increases downward, col increases rightward.
DIRS = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
}
ORDER = ["N", "E", "S", "W"]

TILE_TYPES = ("grass", "straight", "curve", "t_junction", "cross", "dead_end")


@dataclass
class Cell:
    r: int
    c: int
    tile: str = "grass"
    rot: int = 0  # 0..3 clockwise quarter-turns

    @property
    def key(self):
        return (self.r, self.c)


def open_sides(tile: str, rot: int) -> Set[str]:
    """Open neighbour directions for a tile at rotation rot (clockwise turns)."""
    rot %= 4
    if tile == "grass":
        return set()
    if tile == "cross":
        return {"N", "E", "S", "W"}
    if tile in ("straight", "dead_end"):
        base = ["N", "S"] if tile == "straight" else ["N", "E"]
        i0 = (ORDER.index(base[0]) + rot) % 4
        i1 = (ORDER.index(base[1]) + rot) % 4
        return {ORDER[i0], ORDER[i1]}
    if tile == "curve":
        i0 = (ORDER.index("N") + rot) % 4
        i1 = (ORDER.index("E") + rot) % 4
        return {ORDER[i0], ORDER[i1]}
    if tile == "t_junction":
        closed = (ORDER.index("N") + rot) % 4
        return {ORDER[k] for k in range(4) if k != closed}
    if tile == "dead_end":
        i0 = (ORDER.index("N") + rot) % 4
        i1 = (ORDER.index("E") + rot) % 4
        return {ORDER[i0], ORDER[i1]}
    return set()


def neighbours(cell: Cell, board: Dict[Tuple[int, int], Cell]) -> List[Tuple[int, int]]:
    r, c = cell.r, cell.c
    out = []
    for d, (dr, dc) in DIRS.items():
        if d not in open_sides(cell.tile, cell.rot):
            continue
        nr, nc = r + dr, c + dc
        if (nr, nc) in board:
            out.append((nr, nc))
    return out


def solve(board: Dict[Tuple[int, int], Cell], start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
    """BFS over cells, minimising number of moves (taps) from start to goal."""
    if start == goal:
        return [start]
    from collections import deque
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for nb in neighbours(Cell(*cur, tile=board[cur].tile, rot=board[cur].rot), board):
            if nb not in prev:
                prev[nb] = cur
                q.append(nb)
    if goal not in prev:
        return []
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]


def min_taps(board, path) -> int:
    """Sum of clockwise rotations needed to set each tile on the path."""
    taps = 0
    for (r, c) in path:
        cell = board[(r, c)]
        # desired orientation: straight through direction from prev -> here -> next
        # simplified: cost = (3 - rot) % 4 for final orientation; real logic refined in Phase 3b
        taps += (3 - cell.rot) % 4
    return taps

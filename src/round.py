"""Gold Rush round orchestration: capture -> perceive -> solve -> act -> state."""

from .solver import solve


def plan_round(board, start, goal, moves_limit=48):
    """board: {(r,c): Cell}, start/goal: (r,c). Returns (tap_list, path, taps_used)."""
    path = solve(board, start, goal)
    taps = [cell for cell in path if cell != start and cell != goal or True]
    return taps, path

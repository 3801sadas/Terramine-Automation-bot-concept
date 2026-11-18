from solver import Cell, open_sides, solve

def make_board(cells):
    return {(r, c): Cell(r, c, tile=t, rot=ro) for (r, c), (t, ro) in cells.items()}

b = make_board({(0, 0): ("straight", 0), (0, 1): ("straight", 0), (0, 2): ("straight", 0)})
print("open (0,0) rot0 straight:", sorted(open_sides("straight", 0)))
print("open (0,0) rot1 straight:", sorted(open_sides("straight", 1)))
print("open (0,0) rot2 straight:", sorted(open_sides("straight", 2)))
print("open (0,0) rot3 straight:", sorted(open_sides("straight", 3)))
print("open cross:", sorted(open_sides("cross", 0)))
print("open t_junction rot0:", sorted(open_sides("t_junction", 0)))
print("path:", solve(b, (0, 0), (0, 2)))

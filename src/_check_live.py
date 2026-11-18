import sys
sys.path.insert(0, r"C:\Users\Usernom\Documents\Terramine\src")
import perception_v2 as P
from solve_simple import solve_and_validate

res = P.perceive(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\board_live_01.png", exclude_self=True)
print(P.format_grid(res))
out = solve_and_validate(res)
if out:
    sol, _ = out
    print("cost=" + str(sol['cost']) + " taps=" + str(len(sol['path'])))
else:
    print("NO SOLUTION")
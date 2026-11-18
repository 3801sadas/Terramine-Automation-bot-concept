import json, sys, os
import tilegrid
from perception_v2 import perceive, load_calib
from solve_simple import solve_and_validate


def perceive_and_solve(img, excl):
    """Perceive + validate, retrying candidate grid sizes on a fallback (P005).

    If the seam detector could not read either axis, the default 6x6 grid can
    be wrong for a low-level 4x4 board. Try 4/5/6 with the fixed playfield
    frame and keep the first candidate whose plan actually validates.
    """
    res = perceive(img, exclude_self=excl)
    out = solve_and_validate(res)
    if out or res["geom"].get("source") != "default":
        return res, out
    fl, ft, fr, fb = tilegrid.load_frame()
    for n in (4, 5, 6):
        g = {"n": n, "left": fl, "top": ft,
             "cell_x": (fr - fl) / n, "cell_y": (fb - ft) / n}
        r2 = perceive(img, exclude_self=excl, geom=g)
        o2 = solve_and_validate(r2)
        if o2:
            print(f"geometry fallback: n={n}")
            return r2, o2
    return res, out


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png"
    excl = "--exclude" in sys.argv
    mistakes = 0 if "--no-mistakes" in sys.argv else 2
    for i, a in enumerate(sys.argv):
        if a == "--mistakes" and i + 1 < len(sys.argv):
            mistakes = int(sys.argv[i + 1])
    max_total = 46  # stay safely under 48-move limit

    res, out = perceive_and_solve(img, excl)
    print(f"LEP={res['lep']} POT={res['pot']} N={res.get('n', 6)}")
    if not out:
        print("NO VALID SOLUTION (perception may be wrong)")
        sys.exit(1)
    sol, _g = out
    base_cost = sol["cost"]

    # Use the geom from perception for tap centres (works for any grid size)
    geom = res.get("geom", res["cal"]["board"])
    L, T = geom["left"], geom["top"]
    CW, CH = geom["cell_x"], geom["cell_y"]

    def pt(r, c):
        return {"r": r, "c": c,
                "x": int(round(L + c * CW + CW / 2)),
                "y": int(round(T + r * CH + CH / 2))}

    # choose cells for wrong-then-fix mistakes: rotatable path tiles (not LEP/POT/grass)
    path_candidates = []
    for (r, c, tc, _ts) in sol["path"]:
        kind = res["grid"][(r, c)][0]
        if kind in ("LEP", "POT", "grass"):
            continue
        path_candidates.append((r, c, tc, _ts))
    chosen = []
    for item in path_candidates:
        if len(chosen) >= mistakes:
            break
        chosen.append(item)
    # if path too short, pick other rotatable non-grass tiles
    if len(chosen) < mistakes:
        path_set = {(r, c) for (r, c, _, _) in sol["path"]}
        for (r, c), (kind, sides, _) in res["grid"].items():
            if len(chosen) >= mistakes:
                break
            if (r, c) in path_set:
                continue
            if kind in ("LEP", "POT", "grass"):
                continue
            chosen.append((r, c, 0, sides))
    # each mistake = 1 wrong tap + 3 fix taps = +4 moves, final orientation unchanged
    extra_per = 4
    max_extra = 8  # user constraint: at most +8 taps from mistakes
    applied = 0
    for _ in chosen:
        if (applied + 1) * extra_per > max_extra:
            break
        if base_cost + (applied + 1) * extra_per <= max_total:
            applied += 1
        else:
            break
    chosen = chosen[:applied]
    mistake_cells = {(r, c) for (r, c, _, _) in chosen}
    taps = []
    for (r, c, tc, _ts) in sol["path"]:
        # wrong-then-fix: 1 tap away, 3 taps back, then perform intended taps
        if (r, c) in mistake_cells:
            taps.append(pt(r, c))                     # wrong
            for _ in range(3):
                taps.append(pt(r, c))  # fix
            mistake_cells.discard((r, c))
        for _ in range(tc):
            taps.append(pt(r, c))
    # any leftover chosen cells (off-path) would be unsafe to tap after solve; skip them
    actual_extra = applied * extra_per if not mistake_cells else (applied - len(mistake_cells)) * extra_per
    print("COST", base_cost, "(validated)", f"+{actual_extra} mistakes" if actual_extra else "+0 mistakes", f"= {base_cost + actual_extra} total")
    if actual_extra:
        print(f"MISTAKES wrong-then-fix applied={actual_extra // extra_per}")
    print("TAPS_JSON=" + json.dumps(taps))
    print("TOTAL_TAPS=" + str(len(taps)))
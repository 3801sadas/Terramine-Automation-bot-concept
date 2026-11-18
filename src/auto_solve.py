import json, os, sys
from collections import deque
from PIL import Image
import numpy as np

IMG = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\auto_01.png"
ASSET_DIR = r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure\res\drawable-mdpi"
CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"

with open(CALIB) as f:
    cal = json.load(f)
L,T,R,B = cal["board"]["left"],cal["board"]["top"],cal["board"]["right"],cal["board"]["bottom"]
cw,ch = cal["board"]["cell_w"],cal["board"]["cell_h"]
centers = cal["centers"]  # row-major r0c0..r5c5

# Open sides for each tile type at rotation 0 (N,E,S,W). CW rotation shifts.
# Based on common pipe/road tile conventions; will validate.
# straight H: W-E; curve: N-E; t_junction: N-E-S (opens 3, closed W?); cross: all; deadend: N; grass: none
TILE_OPEN = {
    "grass": set(),
    "straight": {"E","W"},  # horizontal
    "curve": {"N","E"},
    "t": {"N","E","S"},
    "cross": {"N","E","S","W"},
    "deadend": {"N"},
}
ORDER = ["N","E","S","W"]
OPP = {"N":"S","E":"W","S":"N","W":"E"}
DIRS = {"N":(-1,0),"E":(0,1),"S":(1,0),"W":(0,-1)}  # (dr,dc)

def rot_open(tile, rot):
    base = TILE_OPEN[tile]
    out = set()
    for d in base:
        out.add(ORDER[(ORDER.index(d)+rot)%4])
    return out

# Load templates
CELL = 168
types = {"grass":"assets_images_goldmine_tilegrass.png","straight":"assets_images_goldmine_tilestraighth.png",
         "curve":"assets_images_goldmine_tilecurve.png","t":"assets_images_goldmine_tiletjunction.png",
         "cross":"assets_images_goldmine_tilecross.png","deadend":"assets_images_goldmine_tiledeadend.png"}
templates = []
for name, fn in types.items():
    path = os.path.join(ASSET_DIR, fn)
    base = np.asarray(Image.open(path).convert("L").resize((CELL,CELL), Image.LANCZOS), dtype=np.float32)
    for rot in range(4):
        arr = np.asarray(Image.fromarray(base.astype(np.uint8)).rotate(-90*rot, expand=False), dtype=np.float32)
        a = arr - arr.mean(); n = np.linalg.norm(a)
        if n < 1e-6: n = 1e-6
        templates.append((name, rot, a/n))

im = np.asarray(Image.open(IMG).convert("L"), dtype=np.float32)
board = {}  # (r,c) -> (tile, rot)
for r in range(6):
    for c in range(6):
        x0 = int(round(L + c*cw)); y0 = int(round(T + r*ch))
        cell = im[y0:y0+CELL, x0:x0+CELL]
        if cell.shape != (CELL,CELL):
            # pad/crop
            cell = im[y0:min(y0+CELL,im.shape[0]), x0:min(x0+CELL,im.shape[1])]
            if cell.size == 0: board[(r,c)]=("grass",0); continue
            pad = np.zeros((CELL,CELL), dtype=np.float32); pad[:cell.shape[0],:cell.shape[1]]=cell; cell=pad
        v = cell - cell.mean(); n = np.linalg.norm(v)
        if n < 1e-6: n = 1e-6
        v = v/n
        best = max(((float((v*a).sum()), (name,rot)) for name,rot,a in templates), key=lambda x:x[0])
        board[(r,c)] = best[1]

# Find leprechaun and pot by looking for bright sprite overlays / gold color in original
imc = np.asarray(Image.open(IMG).convert("RGB"))
def find_special():
    lep = pot = None
    for r in range(6):
        for c in range(6):
            x0=int(round(L+c*cw)); y0=int(round(T+r*ch))
            reg = imc[y0:y0+CELL, x0:x0+CELL].astype(np.float32)
            if reg.size==0: continue
            # leprechaun: has green hat/skin tones; pot: golden yellow mass
            gold = ((reg[:,:,0]>200)&(reg[:,:,1]>160)&(reg[:,:,2]<100)).sum()
            bright = (reg.mean(2)>220).sum()
            green = ((reg[:,:,1]>reg[:,:,0]*0.9)&(reg[:,:,1]>100)&(reg[:,:,0]<180)).sum()
            # heuristics - pot is very golden, lep has distinct sprite
            if gold > 800 and pot is None:
                pot = (r,c)
            if green > 600 and lep is None and (r,c)!=pot:
                lep = (r,c)
    # fallback: leftmost non-grass-ish as start, rightmost as goal
    if lep is None:
        for c in range(6):
            for r in range(6):
                if board[(r,c)][0]!="grass": lep=(r,c); break
            if lep: break
    if pot is None:
        for c in range(5,-1,-1):
            for r in range(6):
                if board[(r,c)][0]!="grass": pot=(r,c); break
            if pot: break
    return lep, pot

lep, pot = find_special()
# Solve: try all rotations of start? Better: find path allowing rotations.
# Since 48 moves, brute-ish: for path, compute min rotations to connect adjacent.
# Use Dijkstra on (r,c,in_dir?) - simpler: try to find connected path with current orientations,
# if not, try rotating tiles on candidate paths.
from heapq import heappush, heappop

def dijkstra(board, start, goal):
    # state: (r,c) - cost is taps to make path work? This is complex.
    # Simpler: ignore cost first, find ANY connected path with current open sides; if none, suggest rotations.
    # Check connectivity with current orientations
    pass

# Build adjacency with current orientations
def connected_adj(board):
    adj = {k:[] for k in board}
    for (r,c),(tile,rot) in board.items():
        sides = rot_open(tile,rot)
        for d,(dr,dc) in DIRS.items():
            if d in sides:
                nb=(r+dr,c+dc)
                if nb in board:
                    nbs = rot_open(board[nb][0],board[nb][1])
                    if OPP[d] in nbs:
                        adj[(r,c)].append(nb)
    return adj

adj = connected_adj(board)
# BFS for path
prev={lep:None}; q=deque([lep])
while q:
    cur=q.popleft()
    if cur==pot: break
    for nb in adj[cur]:
        if nb not in prev: prev[nb]=cur; q.append(nb)

taps = []
if pot in prev:
    path=[]; cur=pot
    while cur: path.append(cur); cur=prev[cur]
    path.reverse()
    print("PATH FOUND:", path)
else:
    print("NO PATH with current orientations")
    print("lep",lep,"pot",pot)
    print("board:", {f"{r},{c}":f"{t}{rot}" for (r,c),(t,rot) in board.items()})
    # Fallback: tap tiles that might connect - try rotating each non-grass tile once (max 48)
    # Prioritize tiles on shortest geometric path
    # Simple: rotate all road tiles in order, up to move limit
    for r in range(6):
        for c in range(6):
            t,rot = board[(r,c)]
            if t != "grass" and (r,c) not in (lep,pot):
                taps.append((r,c))

# Output taps as coordinates
if taps:
    out = [{"r":r,"c":c,"x":int(round(L+c*cw+cw/2)),"y":int(round(T+r*ch+ch/2))} for r,c in taps]
    print("TAPS:", json.dumps(out))
else:
    print("TAPS:[]")

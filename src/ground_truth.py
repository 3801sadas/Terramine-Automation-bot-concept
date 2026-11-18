"""Ground truth for run_01.png (user-provided). States use open-side notation."""
# (r,c): (kind, open_sides) where kind in grass/str/curv/dead/T/cross/LEP/POT
# open_sides as frozenset of N,E,S,W
GT = {
(0,0):("grass",frozenset()),(0,1):("curv",frozenset("NW")),(0,2):("curv",frozenset("NE")),(0,3):("grass",frozenset()),(0,4):("dead",frozenset("S")),(0,5):("grass",frozenset()),
(1,0):("LEP",frozenset("E")),(1,1):("curv",frozenset("SW")),(1,2):("curv",frozenset("NW")),(1,3):("str",frozenset("NS")),(1,4):("curv",frozenset("NE")),(1,5):("grass",frozenset()),
(2,0):("grass",frozenset()),(2,1):("grass",frozenset()),(2,2):("curv",frozenset("SW")),(2,3):("str",frozenset("NS")),(2,4):("curv",frozenset("SW")),(2,5):("POT",frozenset("W")),
(3,0):("grass",frozenset()),(3,1):("str",frozenset("EW")),(3,2):("curv",frozenset("NW")),(3,3):("dead",frozenset("E")),(3,4):("str",frozenset("NS")),(3,5):("grass",frozenset()),
(4,0):("grass",frozenset()),(4,1):("grass",frozenset()),(4,2):("grass",frozenset()),(4,3):("dead",frozenset("W")),(4,4):("grass",frozenset()),(4,5):("grass",frozenset()),
(5,0):("grass",frozenset()),(5,1):("str",frozenset("EW")),(5,2):("grass",frozenset()),(5,3):("grass",frozenset()),(5,4):("curv",frozenset("NW")),(5,5):("grass",frozenset()),
}
LEP=(1,0); POT=(2,5)
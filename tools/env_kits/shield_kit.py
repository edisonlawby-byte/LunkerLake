"""Loon Lake environment kit (Canadian Shield lake, northern Ontario / Quebec).

Reference look: low, rounded "whaleback" outcrops of pink-grey granite polished smooth by the glaciers, sliding gently
into dark clear water; black and orange lichen, a dark water-stain band at the waterline, long joints and cracks
running across the rock, glacial erratic boulders sitting on top; beaver lodges of piled sticks and mud.
Pieces: whaleback (one long sculpted outcrop the game bends along the shore), erratic, beaver_lodge.
Usage: python3 shield_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(43)

GRANITE = (.66, .55, .52); STICK = (.4, .31, .22)


def granite_col(p, key):
    c = .82 + .1 * n3(p, .15, 2) + .06 * n3(p, 1.8, 5)
    r, g, b = c * 1.02, c * .96, c * .95
    black = max(0, n3(p, .35, 11) - .2) * 1.6   # black rock-tripe lichen
    orange = max(0, n3(p, .9, 19) - .42) * 2.2  # orange lichen spots
    crack = max(0, 1 - abs(noise.noise(Vector((p.x * .06 + p.y * .03, p.y * .02, 4)))) * 14)  # long joints
    r, g, b = r * (1 - .55 * black) * (1 + .35 * orange), g * (1 - .55 * black) * (1 + .1 * orange), b * (1 - .5 * black) * (1 - .3 * orange)
    k = 1 - .55 * crack
    if p.z < .7:  # water stain
        k *= .5 + .15 * n3(p, 2, 1)
    return (r * k, g * k, b * k)


def whaleback(L=80.0, seed=2):
    """gently rounded granite from 3 m under water out on the lake side (-Y) up to rounded crests 14 m inland,
    then dipping back into the forest floor; the ends fade into the shore"""
    P = Part('whaleback')
    m = mat('granite', GRANITE, .7)
    b = P.bm(m)
    NX, NY = 110, 34
    grid = []
    for i in range(NX + 1):
        x = L * i / NX
        end = smooth01(x / 10) * smooth01((L - x) / 10)
        crest = (2.5 + 4.5 * (.5 + .5 * noise.noise(Vector((x * .045, 0, seed))))) * end
        col = []
        for j in range(NY + 1):
            y = -8 + 30 * j / NY
            t = (y + 8) / 30
            # rises from under the water to the crest, then rolls back down behind it
            prof = math.sin(math.pi * min(1, t * 1.25)) ** .8 if t < .8 else max(0, 1 - (t - .8) * 4) * .9
            z = -3.2 + (crest + 3.2) * prof
            z += 1.1 * noise.noise(Vector((x * .07, y * .07, seed + 1))) * prof  # rounded humps
            z += .12 * noise.noise(Vector((x * .5, y * .5, seed + 2)))
            z -= .35 * max(0, 1 - abs(noise.noise(Vector((x * .06 + y * .03, y * .02, 4)))) * 14)  # cracks as grooves
            z -= 2 * (1 - end)
            col.append(b.verts.new((x - L / 2, y, z)))
        grid.append(col)
    for i in range(NX):
        for j in range(NY):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    return P.build(granite_col, smooth=True)


def erratic():
    P = Part('erratic')
    m = mat('granite', GRANITE, .7)
    boulder(P, m, 0, 0, .8, 2.2, sq=.8, seed=5, detail=2)
    boulder(P, m, 3.2, 1.4, .3, 1.1, sq=.75, seed=9, detail=2)
    return P.build(granite_col, smooth=True)


def beaver_lodge():
    """a dome of peeled sticks and mud, about 5 m across and 1.6 m above the water"""
    P = Part('beaver_lodge')
    m = mat('sticks', STICK, .95)
    mud = mat('mud', (.28, .23, .17), .95)
    boulder(P, mud, 0, 0, -.6, 2.6, sq=.75, seed=3, detail=2)
    for k in range(70):
        t = random.uniform(0, math.tau)
        ph = random.uniform(0, 1.2)
        r = 2.7
        x, y, z = math.cos(t) * math.cos(ph) * r, math.sin(t) * math.cos(ph) * r, -.6 + math.sin(ph) * r * .75
        a = random.uniform(0, math.tau)
        L = random.uniform(1.2, 3.2)
        dx, dy, dz = math.cos(a) * L / 2, math.sin(a) * L / 2, random.uniform(-.4, .4)
        logp(P, m, x - dx, y - dy, z - dz, x + dx, y + dy, z + dz, random.uniform(.03, .07), 4)
    return P.build(lambda p, key: (.85 + .15 * n3(p, 3, 1),) * 3)


export([whaleback(), erratic(), beaver_lodge()], OUT, BLEND)

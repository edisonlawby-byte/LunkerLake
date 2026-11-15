"""Lunker Lake environment kit (Midwest natural lake).

Reference look: big weeping willows leaning over the marshy cove with curtains of hanging yellow-green branches down
to the water; private wooden docks with boat lifts in front of the cabins.
Pieces: willow (weeping willow), private_dock (dock with a boat lift and a bench).
Usage: python3 midwest_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(53)

BARK = (.32, .27, .21); WILLOW = (.52, .6, .22); TIMBER = (.5, .38, .26); TIMBER_D = (.32, .24, .17); ALU = (.7, .72, .74)


def willow():
    P = Part('willow')
    bm_, lm = mat('willow_bark', BARK, .9), mat('willow_leaf', WILLOW, .8)
    # short thick trunk leaning toward the water (-Y), forking into a few big limbs
    logp(P, bm_, 0, 0, -.3, .2, -.8, 3.2, .55, 9)
    limbs = []
    for k in range(5):
        t = k / 5 * math.tau + random.uniform(-.3, .3)
        r = random.uniform(2.2, 3.6)
        end = (math.cos(t) * r * .6, -.8 + math.sin(t) * r * .6 - .6, 3.2 + random.uniform(2.5, 4.2))
        logp(P, bm_, .2, -.8, 3.0, *end, .25, 6)
        limbs.append(end)
    # crown: arching branch tips with long hanging strands (thin double-sided ribbons)
    b = P.bm(lm)
    for k in range(280):
        lx, ly, lz = random.choice(limbs)
        t = random.uniform(0, math.tau)
        rr_ = random.uniform(.5, 4.6)
        x0, y0 = lx + math.cos(t) * rr_, ly + math.sin(t) * rr_
        z0 = lz + 1.6 - .2 * rr_ * rr_ + random.uniform(-.5, .5)  # dome
        L = random.uniform(1.8, 3.6) + .55 * rr_ + random.uniform(0, 1.2)  # longer toward the outside: ragged hem
        w = random.uniform(.18, .38)
        ox, oy = math.cos(t) * .5, math.sin(t) * .5  # strands hang slightly outward
        prev = None
        for s in range(6):
            u = s / 5
            cx, cy, cz = x0 + ox * u, y0 + oy * u, z0 - L * u
            ww = w * (1 - .6 * u)
            v = (b.verts.new((cx - math.sin(t) * ww, cy + math.cos(t) * ww, cz)), b.verts.new((cx + math.sin(t) * ww, cy - math.cos(t) * ww, cz)))
            if prev:
                b.faces.new([prev[0], prev[1], v[1], v[0]])
            prev = v
    # a few leafy masses on top so the crown reads as solid from a distance
    for lx, ly, lz in limbs:
        boulder(P, lm, lx, ly, lz + .9, random.uniform(2.0, 2.8), sq=.6, seed=lx * 3, detail=1)
    return P.build(lambda p, key: (.8 + .2 * n3(p, .9, 3), .9 + .1 * n3(p, .9, 4), .8) if key == 'willow_leaf' else wood_col(p, key))


def private_dock():
    P = Part('private_dock')
    w, wd, al = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9), mat('alu', ALU, .4, .7)
    for y in range(-12, 2, 2):  # straight walk out from the shore (y=+1) toward the lake (-Y)
        for x in (-.75, .75):
            logp(P, wd, x, y, -2, x, y, .55, .09, 6)
    y = -12.0
    while y < 1.5:
        P.box(w, -.9, .9, y, y + .26, .55, .62)
        y += .3
    P.box(w, -.9, 4.5, -12.2, -10.4, .55, .62)  # L at the end
    for x in (1, 4.2):
        logp(P, wd, x, -11.3, -2, x, -11.3, .55, .09, 6)
    # boat lift beside the dock: four aluminium posts, two cross-beams, canopy frame
    for x in (1.6, 4.4):
        for y in (-9.8, -4.2):
            P.box(al, x - .05, x + .05, y - .05, y + .05, -1.5, 2.4)
        P.box(al, x - .04, x + .04, -9.8, -4.2, 2.35, 2.45)
    for y in (-9.8, -4.2):
        P.box(al, 1.6, 4.4, y - .04, y + .04, .2, .3)
    P.box(mat('canvas', (.15, .3, .5), .8), 1.5, 4.5, -10, -4, 2.45, 2.5)
    # bench at the end
    P.box(wd, -.7, .7, -11.9, -11.5, .95, 1.0)
    for x in (-.6, .6):
        P.box(wd, x - .05, x + .05, -11.85, -11.55, .62, .95)
    return P.build(wood_col)


export([willow(), private_dock()], OUT, BLEND)

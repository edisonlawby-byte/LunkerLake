"""Rimba Reservoir environment kit (Malaysian jungle reservoir among limestone karst towers, like Kenyir/Temenggor and
the karst lakes of the peninsula).

Reference look: sheer grey-white limestone towers rising straight out of the water, with vertical fluting (karren),
black and rust streaks running down, a wave-cut notch at the waterline, and jungle clinging to every ledge and the
crown; bleached drowned trees with bare branches standing in the flooded valley; floating raft houses (rumah rakit)
on blue drums.
Pieces: karst_a / karst_b / karst_c (towers), dead_tree, raft_house.
Usage: python3 rimba_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(17)

LIME = (.78, .76, .71); LEAF = (.22, .4, .14); DEAD = (.72, .71, .67); TIMBER = (.45, .32, .2); TIMBER_D = (.3, .21, .14)
ZINC = (.58, .58, .6); DRUM = (.12, .32, .62)


def lime_col(p, key):
    th = math.atan2(p.y, p.x)
    c = .78 + .12 * n3(p, .08, 2) + .06 * n3(p, .6, 5)
    streak = max(0, noise.noise(Vector((math.cos(th) * 6, math.sin(th) * 6, p.z * .03))) - .05) * 2.0  # runs down the face
    rust = max(0, n3(p, .12, 9) - .25) * 1.6
    moss = max(0, n3(p, .3, 13) - .3) * 1.5
    r, g, b = c, c * .97, c * .92
    r, g, b = r * (1 + .25 * rust), g * (1 + .05 * rust), b * (1 - .2 * rust)
    k = 1 - .5 * min(1, streak)
    r, g, b = r * k * (1 - .45 * moss), g * k * (1 - .15 * moss), b * k * (1 - .5 * moss)
    if p.z < 2.6:  # dark wet notch
        w = .55 + .2 * n3(p, 1, 1)
        r, g, b = r * w, g * w, b * w
    return (r, g, b)


def karst(name, H, R0, seed, crowns=1):
    random.seed(seed)
    P = Part(name)
    m = mat('limestone', LIME, .9)
    b = P.bm(m)
    N = 56
    zs = [-8 + i * 1.0 for i in range(int(H + 8) + 1)]
    off = Vector((seed * 3.1, seed * 1.7, 0))

    def rad(th, z):
        u = max(0, z) / H
        c = Vector((math.cos(th) * 1.4, math.sin(th) * 1.4, 0)) + off
        lobes = .42 * noise.noise(c) + .16 * noise.noise(c * 2.3 + Vector((0, 0, z * .03))) + .1 * noise.noise(c * 4 + Vector((0, 0, math.floor(z / 7) * 3.7)))
        prof = 1 - .22 * u ** 1.4 + .1 * noise.noise(Vector((seed, 0, z * .05)))
        flute = (.015 + .03 * u) * math.sin(11 * th + 3 * noise.noise(Vector((th, z * .04, seed))))
        notch = -.16 * math.exp(-((z - 1.2) / 1.3) ** 2)
        ledge = .06 * math.sin(z * .45 + seed)
        return R0 * max(.25, prof + lobes + flute + notch + ledge)

    rings = []
    for z in zs:
        rings.append([b.verts.new((math.cos(t) * rad(t, z), math.sin(t) * rad(t, z), z)) for t in [k / N * math.tau for k in range(N)]])
    # crown: rings drawing in over a few metres, with pinnacles pushed up by noise
    top = zs[-1]
    for j in range(1, 7):
        f = 1 - j / 7
        ring = []
        for k in range(N):
            t = k / N * math.tau
            pin = max(0, noise.noise(Vector((math.cos(t) * 2, math.sin(t) * 2, j * .3)) + off)) * 9 * crowns * (1 - f)
            r = rad(t, top) * f ** .6
            ring.append(b.verts.new((math.cos(t) * r, math.sin(t) * r, top + 7 * (1 - f * f) + pin)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(N):
            b.faces.new([rings[i][k], rings[i][(k + 1) % N], rings[i + 1][(k + 1) % N], rings[i + 1][k]])
    cap = b.verts.new((0, 0, top + 8))
    for k in range(N):
        b.faces.new([rings[-1][k], rings[-1][(k + 1) % N], cap])
    # jungle on the crown and clinging to ledges
    lm = mat('leaf', LEAF, .85)
    for k in range(int(30 + R0 * 3.5)):
        t = random.uniform(0, math.tau)
        r = rad(t, top) * random.uniform(0, 1.0)
        boulder(P, lm, math.cos(t) * r, math.sin(t) * r, top + random.uniform(1, 7), random.uniform(3, 6), sq=.6, seed=k * 1.3, detail=1)
    for k in range(int(20 + H * 1.0)):
        t = random.uniform(0, math.tau)
        z = random.uniform(6, top - 2)
        r = rad(t, z) * 1.02
        boulder(P, lm, math.cos(t) * r, math.sin(t) * r, z, random.uniform(2, 4.5), sq=.75, seed=k * 2.9 + 1, detail=1)
    return P.build(lambda p, key: (.75 + .25 * n3(p, .9, 3), .9 + .1 * n3(p, .9, 4), .75) if key == 'leaf' else lime_col(p, key), smooth=True)


def dead_tree():
    """a bleached drowned tree: a crooked tapering trunk (base well under water), long bare forking branches"""
    P = Part('dead_tree')
    m = mat('deadwood', DEAD, .9)
    h = 14
    pts = [(0, 0, -6), (.3, .1, 4), (.1, .5, 9), (.6, .3, h)]
    for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        logp(P, m, *a, *b, .32 - k * .08, 7)
    for k in range(7):
        z = random.uniform(h * .4, h * .95)
        t = random.uniform(0, math.tau)
        L = random.uniform(3, 6.5) * (1.25 - z / h)
        ex, ey, ez = math.cos(t) * L, math.sin(t) * L, z + L * random.uniform(.5, 1.1)
        logp(P, m, .3, .3, z, ex, ey, ez, .11 * (1.2 - z / h), 5)
        for q in range(3):
            t2 = t + random.uniform(-.9, .9)
            l2 = random.uniform(1.2, 2.6)
            logp(P, m, ex, ey, ez, ex + math.cos(t2) * l2, ey + math.sin(t2) * l2, ez + random.uniform(.6, 1.8), .04, 4)
    return P.build(lambda p, key: (.85 + .15 * n3(p, 1.5, 2),) * 3 if p.z > .3 else (.45,) * 3)


def raft_house():
    P = Part('raft_house')
    w, wd, dr = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9), mat('drum_blue', DRUM, .5)
    for x in (-3.4, -1.15, 1.15, 3.4):  # rows of floating drums
        for y in [-4.5 + i * 1.5 for i in range(7)]:
            logp(P, dr, x, y - .6, 0, x, y + .6, 0, .32, 10)
    P.box(wd, -4.2, 4.2, -5.2, 5.2, .32, .5)
    P.box(w, -4.3, 4.3, -5.3, 5.3, .5, .6)
    for x in (-3, 3):
        P.box(w, x - .06, x + .06, -1.5, 4.2, .6, 3.0)
    P.box(w, -3, 3, 4.14, 4.26, .6, 3.0)
    for x0, x1 in ((-3, -.8), (.8, 3)):
        P.box(w, x0, x1, -1.56, -1.44, .6, 3.0)
    P.box(mat('lamp', (1, .82, .5), .3), -2.4, -1.4, -1.6, -1.58, 1.4, 2.2)
    for x in (-4.1, 0, 4.1):  # verandah posts on the open lake side
        P.box(wd, x - .07, x + .07, -5.1, -4.95, .6, 2.9)
    zm = mat('zinc', ZINC, .45, .6)
    b = P.bm(zm)
    for s in (-1, 1):
        v = [b.verts.new(c) for c in ((0, -5.6, 4.4), (0, 4.7, 4.4), (s * 4.7, 4.7, 2.7), (s * 4.7, -5.6, 2.7))]
        b.faces.new(v if s < 0 else v[::-1])
        b.faces.new([b.verts.new((c.co.x, c.co.y, c.co.z - .06)) for c in v][::-1] if s < 0 else [b.verts.new((c.co.x, c.co.y, c.co.z - .06)) for c in v])
    return P.build(wood_col)


export([karst('karst_a', 58, 15, 1), karst('karst_b', 36, 9, 2), karst('karst_c', 82, 20, 3, crowns=1.4), dead_tree(), raft_house()], OUT, BLEND)

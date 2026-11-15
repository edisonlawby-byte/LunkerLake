"""Sungai Deras environment kit (upland jungle river, Pahang, Malaysia).

Pieces: rope_bridge (60 m hanging plank bridge with timber A-frame towers; the game scales it to the crossing),
waterfall (granite cliff with a white cascade and a foam apron), kampung_house (Malay timber house on stilts with a
zinc roof and verandah), jetty (plank jetty on piles with a shelter), sampan (wooden river boat), river_boulders
(big rounded granite boulders), fallen_tree (a jungle giant lying from the bank into the water), bamboo (an arching
clump of culms with leaf tufts).
Usage: python3 deras_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(23)

TIMBER = (.45, .3, .19); TIMBER_D = (.3, .2, .13); ZINC = (.55, .55, .56); ROPE = (.55, .47, .33); GRANITE = (.55, .53, .5)
FOAM = (.92, .95, .96); BARK = (.42, .36, .3); BAMBOO = (.55, .6, .25); LEAF = (.22, .4, .12)


def granite_col(p, key):
    c = .72 + .16 * n3(p, .5, 2) + .08 * n3(p, 3, 7)
    moss = max(0, n3(p, .6, 13) - .15) * 1.4 * (1 if p.z > .3 else .3)
    r, g, b = c, c * .97, c * .92
    r, g, b = r * (1 - .45 * moss), g * (1 - .2 * moss), b * (1 - .5 * moss)
    if p.z < .5:
        k = .5 + .15 * n3(p, 2, 1)
        r, g, b = r * k, g * k, b * k
    return (r, g, b)


def foam_col(p, key):
    s = .8 + .2 * n3(Vector((p.x * 3, p.y, p.z * .15)), 1, 5)
    return (s, s, min(1, s * 1.04))


def zinc_col(p, key):
    rust = max(0, n3(p, .9, 4) - .2) * 1.3
    c = .85 + .15 * n3(Vector((p.x * 6, p.y * .3, p.z)), 1, 2)
    return (c * (1 + .4 * rust), c * (1 - .05 * rust), c * (1 - .35 * rust))


def rope_bridge(L=60.0, H=8.0, sag=3.2):
    P = Part('rope_bridge')
    w, wd, rp = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9), mat('rope', ROPE, .95)
    N = 80
    zf = lambda x: H - sag * (1 - (2 * x / L) ** 2)
    for i in range(N):  # planks
        x0 = -L / 2 + L * i / N
        x1 = x0 + L / N * .8
        z = zf((x0 + x1) / 2)
        P.box(w, x0, x1, -.75, .75, z - .06, z)
    for y in (-.8, .8):  # rope rails (deck stringers and handrails)
        for dz, r in ((-.08, .05), (1.1, .035)):
            pts = [(-L / 2 + L * i / 24, y, zf(-L / 2 + L * i / 24) + dz) for i in range(25)]
            for a, b in zip(pts[:-1], pts[1:]):
                logp(P, rp, *a, *b, r, 5)
        for i in range(0, N, 4):  # hangers
            x = -L / 2 + L * i / N
            logp(P, rp, x, y, zf(x), x, y, zf(x) + 1.1, .015, 4)
    for x in (-L / 2, L / 2):  # timber A-frame towers on each bank
        for y in (-1.1, 1.1):
            logp(P, wd, x, y * 1.4, -3, x, y, H + 2.6, .16, 6)
        P.box(wd, x - .15, x + .15, -1.4, 1.4, H + 2.2, H + 2.5)
    return P.build(wood_col)


def waterfall(W=26.0, H=18.0, seed=4):
    """granite step-cliff (lake side -Y) with a white cascade sheet over it and a foam apron on the pool"""
    P = Part('waterfall')
    m = mat('granite', GRANITE, .9)
    b = P.bm(m)
    NX, NZ = 40, 40
    grid = []
    for i in range(NX + 1):
        x = -W / 2 + W * i / NX
        end = smooth01((x + W / 2) / 6) * smooth01((W / 2 - x) / 6)
        top = H * (.85 + .15 * noise.noise(Vector((x * .1, 0, seed)))) * end
        col = []
        for j in range(NZ + 1):
            z = -5 + (top + 5) * j / NZ
            y = .45 * z / max(H, 1) * 6 - 1.2 * noise.noise(Vector((x * .15, z * .15, seed))) - .5 * abs(noise.noise(Vector((x * .5, z * .5, seed + 3))))
            y += 6 * (1 - end)
            col.append(b.verts.new((x, y, z)))
        grid.append(col)
    for i in range(NX):
        for j in range(NZ):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    P2 = None
    # cascade: a curved sheet a little in front of the rock, wider at the bottom
    f = mat('foam', FOAM, .3)
    fb = P.bm(f)
    rows = []
    for j in range(31):
        t = j / 30
        z = H * .97 - (H * .97 + .2) * t
        half = 2.2 + 3.0 * t ** 1.5
        row = []
        for i in range(9):
            u = -1 + 2 * i / 8
            x = u * half + .6 * math.sin(t * 5 + u * 2)
            y = .45 * z / H * 6 - 1.6 - .4 * (1 - u * u) - 1.2 * t * t
            row.append(fb.verts.new((x, y, z)))
        rows.append(row)
    for j in range(30):
        for i in range(8):
            fb.faces.new([rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]])
    # foam apron where the fall hits the pool
    for k in range(14):
        a = random.uniform(0, math.tau)
        r = random.uniform(0, 7)
        cx, cy = math.cos(a) * r * 1.3, -4 - abs(math.sin(a)) * r
        s = random.uniform(1, 2.6)
        v = [fb.verts.new((cx + math.cos(t) * s * random.uniform(.7, 1.2), cy + math.sin(t) * s * .7, .05 + k * .004)) for t in [q / 8 * math.tau for q in range(8)]]
        fb.faces.new(v)
    o = P.build(lambda p, key: foam_col(p, key) if key == 'foam' else granite_col(p, key), smooth=True)
    return o


def kampung_house():
    P = Part('kampung_house')
    w, wd = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9)
    W, D, S = 9, 7, 1.9  # stilts lift the floor 1.9 m
    for x in (-W / 2, -W / 6, W / 6, W / 2):
        for y in (-D / 2, 0, D / 2):
            P.box(wd, x - .12, x + .12, y - .12, y + .12, -.6, S)
    P.box(wd, -W / 2 - .2, W / 2 + .2, -D / 2 - 1.8, D / 2 + .2, S, S + .15)  # floor incl. verandah (lake side)
    for y in (-D / 2, D / 2):  # plank walls with a lighter band of window shutters
        P.box(w, -W / 2, W / 2, y - .06, y + .06, S + .15, S + 2.6)
    for x in (-W / 2, W / 2):
        P.box(w, x - .06, x + .06, -D / 2, D / 2, S + .15, S + 2.6)
    for x in (-3, -1, 1.6, 3.2):
        P.box(mat('shutter', (.2, .32, .3), .7), x - .45, x + .45, -D / 2 - .1, -D / 2 - .05, S + 1.0, S + 2.0)
        P.box(mat('lamp', (1, .8, .45), .3), x - .35, x + .35, -D / 2 - .07, -D / 2 - .04, S + 1.1, S + 1.9)
    for x in (-W / 2 - .1, -1.5, 1.5, W / 2 + .1):  # verandah posts and rail
        P.box(wd, x - .07, x + .07, -D / 2 - 1.75, -D / 2 - 1.6, S + .15, S + 2.6)
    P.box(wd, -W / 2, W / 2, -D / 2 - 1.78, -D / 2 - 1.7, S + .9, S + 1.0)
    for k in range(6):  # front stairs
        P.box(wd, -.6, .6, -D / 2 - 1.9 - k * .35, -D / 2 - 1.6 - k * .35, S - .3 - k * .33, S - .22 - k * .33)
    # steep gabled zinc roof, ridge along X, deep eaves over the verandah
    zm = mat('zinc', ZINC, .45, .6)
    b = P.bm(zm)
    z0, rise = S + 2.6, 2.6
    for s in (-1, 1):
        ye = (-D / 2 - 2.2) if s < 0 else (D / 2 + .7)
        v = [b.verts.new(c) for c in ((-W / 2 - .7, -.75, z0 + rise), (W / 2 + .7, -.75, z0 + rise), (W / 2 + .7, ye, z0 - .3), (-W / 2 - .7, ye, z0 - .3))]
        b.faces.new(v if s > 0 else v[::-1])
        b.faces.new([b.verts.new((c.co.x, c.co.y, c.co.z - .06)) for c in v][::-1] if s > 0 else [b.verts.new((c.co.x, c.co.y, c.co.z - .06)) for c in v])
    b = P.bm(w)
    for x in (-W / 2, W / 2):  # gable ends
        v = [b.verts.new(c) for c in ((x, -D / 2, z0), (x, D / 2, z0), (x, -.75, z0 + rise))]
        b.faces.new(v if x > 0 else v[::-1])
    return P.build(lambda p, key: zinc_col(p, key) if key == 'zinc' else wood_col(p, key))


def jetty():
    P = Part('jetty')
    w, wd = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9)
    for y in range(-14, 3, 2):
        for x in (-.9, .9):
            logp(P, wd, x, y, -2.5, x, y, .5, .1, 6)
    y = -14.0
    while y < 2:
        P.box(w, -1.1, 1.1, y, y + .26, .5, .58)
        y += .3
    # small shelter at the end with an attap-style (thatch) roof
    for x in (-1.1, 1.1):
        for yy in (-13.8, -11.2):
            P.box(wd, x - .06, x + .06, yy - .06, yy + .06, .58, 2.7)
    th = mat('attap', (.5, .4, .26), .95)
    b = P.bm(th)
    for s in (-1, 1):
        v = [b.verts.new(c) for c in ((0, -14.4, 3.5), (0, -10.6, 3.5), (s * 1.8, -10.6, 2.5), (s * 1.8, -14.4, 2.5))]
        b.faces.new(v if s < 0 else v[::-1])
    return P.build(wood_col)


def sampan():
    P = Part('sampan')
    hull_part(P, mat('timber', TIMBER, .85), 6.5, 1.1, .45, z=.3, deadrise=.4, bow=.5)
    P.box(mat('timber_dark', TIMBER_D, .9), -.5, .5, -1.2, -.9, .2, .3)
    return P.build(wood_col)


def river_boulders():
    P = Part('river_boulders')
    m = mat('granite', GRANITE, .9)
    for i in range(7):
        r = random.uniform(1.0, 3.2)
        boulder(P, m, random.uniform(-6, 6), random.uniform(-4, 4), r * .1, r, sq=random.uniform(.6, .8), seed=i * 2.3, detail=2)
    return P.build(granite_col, smooth=True)


def fallen_tree():
    P = Part('fallen_tree')
    m = mat('bark', BARK, .9)
    # trunk from the bank (y=+6, up on the bank) out into the water (y=-16, sunk), slight bend
    pts = [(0, 6, 1.4), (.5, 0, .5), (1.2, -8, -.3), (1.6, -16, -1.2)]
    for a, b in zip(pts[:-1], pts[1:]):
        logp(P, m, *a, *b, .75, 10)
    for k in range(9):  # root plate
        t = k / 9 * math.tau
        logp(P, m, 0, 6.3, 1.4, math.cos(t) * 2.6, 7.2, 1.4 + math.sin(t) * 2.4, .28, 6)
    for k in range(6):  # dead branches
        y = -4 - k * 2.2
        s = 1 if k % 2 else -1
        logp(P, m, 1.0 + k * .1, y, 0, 1.0 + s * random.uniform(2.5, 4.5), y - 1.5, random.uniform(-.5, 2.5), .16, 5)
    return P.build(lambda p, key: (.9 + .1 * n3(p, 2, 1),) * 3)


def bamboo():
    P = Part('bamboo')
    cm, lm = mat('bamboo', BAMBOO, .6), mat('leaf', LEAF, .8)
    for k in range(18):
        a = random.uniform(0, math.tau)
        r0 = random.uniform(0, .8)
        x0, y0 = math.cos(a) * r0, math.sin(a) * r0
        h = random.uniform(8, 13)
        lean = random.uniform(.25, .55)
        prev = (x0, y0, -.2)
        for s in range(1, 7):  # arching culm in 6 segments
            t = s / 6
            p = (x0 + math.cos(a) * lean * h * t * t, y0 + math.sin(a) * lean * h * t * t, h * t * (1 - .25 * t))
            logp(P, cm, *prev, *p, .07 * (1 - .5 * t), 5)
            prev = p
        for q in range(3):  # leaf tufts toward the tip
            t = .55 + .2 * q
            boulder(P, lm, x0 + math.cos(a) * lean * h * t * t, y0 + math.sin(a) * lean * h * t * t, h * t * (1 - .25 * t) - .3,
                    random.uniform(.9, 1.5), sq=.45, seed=k + q, detail=1)
    return P.build(lambda p, key: (.85 + .15 * n3(p, 1.5, 3),) * 3)


export([rope_bridge(), waterfall(), kampung_house(), jetty(), sampan(), river_boulders(), fallen_tree(), bamboo()], OUT, BLEND)

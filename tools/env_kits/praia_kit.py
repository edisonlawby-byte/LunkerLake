"""Praia Branca environment kit (clearwater Amazon river: white beaches, rock rapids, riverboat landing).

Pieces: riverboat (two-deck wooden Amazon passenger boat with hammocks), flutuante (floating store on logs with a palm
roof), lodge_hut (eco-lodge hut on stilts with a conical palm-thatch roof), rabeta (dugout canoe with a long-tail
motor), pedral (dark, smooth rock slabs of a rapid with foam), sand_spit (a low white sandbar island), beach_strip
(one wide white beach the game bends along the shore), fallen_tree (dead tree lying into the river).
Usage: python3 praia_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(31)

WHITE = (.86, .86, .83); BLUE = (.1, .3, .62); RED = (.7, .14, .1); TIMBER = (.45, .32, .2); TIMBER_D = (.3, .21, .14)
THATCH = (.55, .45, .28); DARKROCK = (.2, .19, .18); SAND = (.92, .88, .76); FOAM = (.92, .95, .96); BARK = (.45, .4, .34)


def paint_col(p, key):
    c = .9 + .1 * n3(p, 2, 1)
    return (c, c, c)


def rock_col(p, key):
    c = .8 + .25 * n3(p, .7, 3)
    wet = 1 if p.z < .25 else 0
    return (c * (1 - .3 * wet), c * (1 - .3 * wet), c * (1 - .28 * wet))


def sand_col(p, key):
    c = .93 + .07 * n3(p, .5, 2)
    if p.z < .15:  # wet sand at the waterline
        c *= .78
    return (c, c * .98, c * .94)


def riverboat():
    P = Part('riverboat')
    hull, wh, bl, rd = mat('timber', TIMBER, .85), mat('paint_white', WHITE, .6), mat('paint_blue', BLUE, .6), mat('paint_red', RED, .6)
    L, W = 20, 5
    hull_part(P, wh, L, W, 1.6, z=.9, deadrise=.3, bow=.35)  # bow toward +Y
    P.box(bl, -W / 2 - .02, W / 2 + .02, -L / 2 + .6, L / 2 - 3, .55, .9)  # blue stripe along the sheer
    P.box(hull, -W / 2 + .1, W / 2 - .1, -L / 2 + .4, L / 2 - 2.5, .9, 1.05)  # main deck
    for deck_z, y1 in ((1.05, L / 2 - 3.2), (3.4, L / 2 - 4.5)):
        for x in (-W / 2 + .2, W / 2 - .2):  # posts
            for y in [-L / 2 + .6 + i * 2.2 for i in range(int((y1 + L / 2) / 2.2) + 1)]:
                P.box(wh, x - .07, x + .07, y - .07, y + .07, deck_z, deck_z + 2.3)
        P.box(wh, -W / 2, W / 2, -L / 2 + .3, y1 + .3, deck_z + 2.3, deck_z + 2.45)  # deck above / roof
        P.box(bl, -W / 2 - .02, W / 2 + .02, -L / 2 + .3, y1 + .3, deck_z + 2.2, deck_z + 2.3)
        P.box(wh, -W / 2, W / 2, -L / 2 + .4, y1, deck_z + .9, deck_z + 1.0)  # rail height band
    P.box(wh, -1.3, 1.3, L / 2 - 6, L / 2 - 4.4, 5.85, 7.5)  # wheelhouse
    P.box(mat('lamp', (1, .85, .55), .3), -1.32, 1.32, L / 2 - 4.5, L / 2 - 4.42, 6.5, 7.2)
    cols = [(.85, .2, .2), (.2, .5, .85), (.95, .75, .15), (.2, .65, .3), (.9, .4, .6)]
    for k in range(14):  # hammocks
        y = -L / 2 + 1.5 + k % 7 * 2.0
        z = 2.3 + (k // 7) * 2.35
        P.box(mat(f'hammock{k % 5}', cols[k % 5], .9), -1.8, 1.8, y - .35, y + .35, z, z + .25)
    return P.build(paint_col)


def flutuante():
    P = Part('flutuante')
    w, wd = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9)
    for x in (-3.5, -1.2, 1.2, 3.5):  # floating logs
        logp(P, wd, x, -5, .05, x, 5, .05, .45, 8)
    P.box(w, -4.2, 4.2, -5.2, 5.2, .45, .6)
    for x in (-3.4, 3.4):
        P.box(mat('wall_green', (.25, .55, .45), .8), x - .06, x + .06, -2, 4, .6, 2.9)
    P.box(mat('wall_green', (.25, .55, .45), .8), -3.4, 3.4, 3.94, 4.06, .6, 2.9)
    P.box(mat('wall_green', (.25, .55, .45), .8), -3.4, -1, -2.06, -1.94, .6, 2.9)
    P.box(mat('wall_green', (.25, .55, .45), .8), 1, 3.4, -2.06, -1.94, .6, 2.9)
    th = mat('thatch', THATCH, .95)
    b = P.bm(th)
    for s in (-1, 1):
        v = [b.verts.new(c) for c in ((0, -3, 4.4), (0, 5, 4.4), (s * 4.6, 5, 2.6), (s * 4.6, -3, 2.6))]
        b.faces.new(v if s < 0 else v[::-1])
    return P.build(wood_col)


def lodge_hut():
    P = Part('lodge_hut')
    w, wd = mat('timber', TIMBER, .85), mat('timber_dark', TIMBER_D, .9)
    R0, S = 3.6, 1.6
    for k in range(8):
        a = k / 8 * math.tau
        logp(P, wd, math.cos(a) * R0, math.sin(a) * R0, -.5, math.cos(a) * R0, math.sin(a) * R0, S + 2.5, .12, 6)
    b = P.bm(w)
    ring = [b.verts.new((math.cos(k / 16 * math.tau) * (R0 + .8), math.sin(k / 16 * math.tau) * (R0 + .8), S)) for k in range(16)]
    b.faces.new(ring)
    b = P.bm(mat('wall_white', (.9, .87, .8), .8))
    for k in range(16):  # low walls with a gap for the door on the lake side
        a0, a1 = k / 16 * math.tau, (k + 1) / 16 * math.tau
        if abs(((a0 + a1) / 2) - 3 * math.pi / 2) < .25:
            continue
        v = [b.verts.new((math.cos(a) * R0, math.sin(a) * R0, z)) for a, z in ((a0, S), (a1, S), (a1, S + 2.2), (a0, S + 2.2))]
        b.faces.new(v)
    th = mat('thatch', THATCH, .95)
    b = P.bm(th)
    apex = b.verts.new((0, 0, S + 6.2))
    rim = [b.verts.new((math.cos(k / 16 * math.tau) * (R0 + 1.6), math.sin(k / 16 * math.tau) * (R0 + 1.6), S + 1.9)) for k in range(16)]
    for k in range(16):
        b.faces.new([rim[k], rim[(k + 1) % 16], apex])
    for k in range(5):  # stairs down toward the lake (-Y)
        P.box(wd, -.6, .6, -R0 - .9 - k * .4, -R0 - .5 - k * .4, S - .35 - k * .35, S - .25 - k * .35)
    P.box(mat('lamp', (1, .85, .55), .3), -.5, .5, -R0 - .02, -R0 + .05, S + .3, S + 1.9)
    return P.build(lambda p, key: (.85 + .15 * n3(Vector((p.x * 3, p.y * 3, p.z * 8)), 1, 2),) * 3 if key == 'thatch' else wood_col(p, key))


def rabeta():
    P = Part('rabeta')
    m = mat('canoe_wood', (.4, .28, .18), .85)
    hull_part(P, m, 7.0, .95, .45, z=.3, deadrise=.5, bow=.4)
    P.box(mat('paint_blue', BLUE, .6), -.49, .49, -3.2, 2.8, .2, .3)
    P.box(mat('motor', (.12, .12, .13), .4, .3), -.2, .2, -3.4, -3.0, .3, .8)
    logp(P, mat('motor', (.12, .12, .13), .4, .3), 0, -3.2, .5, 0, -5.6, -.3, .04, 5)  # long-tail shaft
    return P.build(wood_col)


def pedral():
    P = Part('pedral')
    m, f = mat('darkrock', DARKROCK, .45), mat('foam', FOAM, .3)
    for i in range(9):  # smooth, rounded, polished-looking slabs
        r = random.uniform(1.2, 3.2)
        boulder(P, m, random.uniform(-8, 8), random.uniform(-5, 5), -r * .25, r, sq=random.uniform(.35, .55), seed=i * 4.1, detail=2)
    b = P.bm(f)
    for k in range(16):  # foam where the water pours between the rocks
        cx, cy = random.uniform(-9, 9), random.uniform(-6, 6)
        s = random.uniform(.8, 2.4)
        v = [b.verts.new((cx + math.cos(t) * s * random.uniform(.6, 1.3), cy + math.sin(t) * s * .5, .04 + k * .003)) for t in [q / 8 * math.tau for q in range(8)]]
        b.faces.new(v)
    return P.build(lambda p, key: (.95,) * 3 if key == 'foam' else rock_col(p, key), smooth=True)


def sand_spit(L=46.0, W=12.0):
    P = Part('sand_spit')
    m = mat('sand', SAND, .95)
    b = P.bm(m)
    NX, NY = 30, 10
    grid = []
    for i in range(NX + 1):
        x = -L / 2 + L * i / NX
        col = []
        for j in range(NY + 1):
            y = -W / 2 + W * j / NY
            u, v = 2 * x / L, 2 * y / W
            z = .9 * (1 - u * u) * (1 - v * v) - .7 + .1 * noise.noise(Vector((x * .2, y * .2, 1)))
            col.append(b.verts.new((x, y * (1 - .35 * u * u), z)))
        grid.append(col)
    for i in range(NX):
        for j in range(NY):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    return P.build(sand_col, smooth=True)


def beach_strip(L=90.0):
    """a wide beach: from 2 m under water out on the lake side (-Y) up to 2.6 m high 18 m inland, ends fading"""
    P = Part('beach_strip')
    m = mat('sand', SAND, .95)
    b = P.bm(m)
    NX, NY = 60, 16
    grid = []
    for i in range(NX + 1):
        x = L * i / NX
        end = smooth01(x / 10) * smooth01((L - x) / 10)
        col = []
        for j in range(NY + 1):
            y = -8 + 40 * j / NY
            z = -2 + 8.0 * smooth01((y + 8) / 40) ** .6 + .12 * noise.noise(Vector((x * .15, y * .15, 3)))
            z -= 2.5 * (1 - end)
            col.append(b.verts.new((x - L / 2, y, z)))
        grid.append(col)
    for i in range(NX):
        for j in range(NY):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    return P.build(sand_col, smooth=True)


def fallen_tree():
    P = Part('fallen_tree')
    m = mat('bark', BARK, .9)
    pts = [(0, 5, 1.2), (.4, -1, .3), (1.0, -9, -.4), (1.5, -17, -1.2)]
    for a, b in zip(pts[:-1], pts[1:]):
        logp(P, m, *a, *b, .7, 10)
    for k in range(8):
        t = k / 8 * math.tau
        logp(P, m, 0, 5.3, 1.2, math.cos(t) * 2.4, 6.1, 1.2 + math.sin(t) * 2.2, .26, 6)
    for k in range(6):
        y = -3 - k * 2.4
        s = 1 if k % 2 else -1
        logp(P, m, 1.0, y, 0, 1.0 + s * random.uniform(2.5, 4.5), y - 1.5, random.uniform(-.5, 2.5), .15, 5)
    return P.build(lambda p, key: (.75 + .1 * n3(p, 2, 1),) * 3)


export([riverboat(), flutuante(), lodge_hut(), rabeta(), pedral(), sand_spit(), beach_strip(), fallen_tree()], OUT, BLEND)

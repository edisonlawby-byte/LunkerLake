"""Glacier Lake environment kit (Canadian Rockies): a long, cold, turquoise glacial-trough lake.

Pieces: trestle (one 12 m bay of a timber railway trestle: pile bent, stringers, ties, rails), logjam (bleached drift
logs with root wads), lodge (log lodge with stone chimney, green metal roof and porch), boathouse (red board-and-batten
on pilings, open to the lake), canoe, scree_slope (one sculpted talus slope the game bends along the shore).
Usage: python3 glacier_kit.py <out.glb> [out.blend]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kitlib import *

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(11)

CREO = (.27, .22, .17); DRIFT = (.56, .53, .48); LOGW = (.55, .38, .22); STONE = (.55, .54, .52); GREENR = (.2, .33, .24)
RED = (.55, .14, .1); STEEL = (.35, .33, .31); GRANITE = (.5, .5, .5); WOOD_D = (.33, .25, .18)


def drift_col(p, key):
    return .78 + .22 * n3(Vector((p.x * 2, p.y * 2, p.z * 6)), 1, 3)


def stone_col(p, key):
    c = .8 + .2 * n3(p, 3, 5)
    return (c, c * .98, c * .95)


def trestle():
    P = Part('trestle')
    w = mat('creosote', CREO, .9)
    # pile bent at x=0: four piles (outer two battered), cap, two girts and X-bracing
    for y, lean in ((-2.1, -.35), (-.7, 0), (.7, 0), (2.1, .35)):
        logp(P, w, 0, y + lean, -9, 0, y, 6.0, .17, 8)
    P.box(w, -.2, .2, -2.6, 2.6, 6.0, 6.4)
    for z in (-1.0, 3.0):
        P.box(w, -.08, .08, -2.4, 2.4, z, z + .22)
    logp(P, w, -.1, -2.3, -.8, -.1, 2.3, 5.8, .09, 6)
    logp(P, w, .1, 2.3, -.8, .1, -2.3, 5.8, .09, 6)
    # deck: stringers, ties, rails, guard timbers
    for y in (-1.1, -.4, .4, 1.1):
        P.box(w, -6, 6, y - .14, y + .14, 6.4, 7.05)
    x = -6
    while x < 6:
        P.box(w, x, x + .22, -1.5, 1.5, 7.05, 7.25)
        x += .55
    for y in (-.72, .72):
        P.box(mat('steel', STEEL, .5, .7), -6, 6, y - .04, y + .04, 7.25, 7.4)
    for y in (-1.45, 1.45):
        P.box(w, -6, 6, y - .1, y + .1, 7.25, 7.45)
    return P.build(wood_col)


def logjam():
    P = Part('logjam')
    w = mat('driftwood', DRIFT, .95)
    for i in range(26):
        L = random.uniform(5, 12)
        a = random.uniform(-.6, .6) + (math.pi / 2 if random.random() < .3 else 0)
        cx, cy = random.uniform(-6, 6), random.uniform(-3, 3)
        z = random.uniform(-.4, 1.8) + (.3 if i > 14 else 0)
        dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
        r = random.uniform(.18, .42)
        logp(P, w, cx - dx, cy - dy, z + random.uniform(-.5, .5), cx + dx, cy + dy, z + random.uniform(-.5, .5), r, 8)
        if random.random() < .35:  # root wad: short stubs radiating from one end
            ex, ey, ez = cx + dx, cy + dy, z
            for k in range(7):
                t = k / 7 * math.tau
                logp(P, w, ex, ey, ez, ex + math.cos(a) * .3 + .2 * math.cos(t), ey + math.sin(a) * .3 + 1.1 * math.sin(t),
                     ez + 1.1 * math.cos(t), r * .45, 5)
    return P.build(drift_col)


def gable(P, m, x0, x1, y0, y1, z0, rise, th=.12):
    """two roof planes, ridge along X"""
    b = P.bm(m)
    yc = (y0 + y1) / 2
    for s in (-1, 1):
        ye = y0 if s < 0 else y1
        v = [b.verts.new(c) for c in ((x0, yc, z0 + rise), (x1, yc, z0 + rise), (x1, ye, z0), (x0, ye, z0))]
        f = b.faces.new(v if s > 0 else v[::-1])
        v2 = [b.verts.new((c.co.x, c.co.y, c.co.z - th)) for c in v]
        b.faces.new(v2[::-1] if s > 0 else v2)
        for i in range(4):
            j = (i + 1) % 4
            b.faces.new([v[i], v[j], v2[j], v2[i]] if s > 0 else [v[j], v[i], v2[i], v2[j]])


def gable_y(P, m, x0, x1, y0, y1, z0, rise, th=.12):
    """two roof planes, ridge along Y, plus the triangular gable ends"""
    b = P.bm(m)
    xc = (x0 + x1) / 2
    for s in (-1, 1):
        xe = x0 if s < 0 else x1
        v = [b.verts.new(c) for c in ((xc, y0, z0 + rise), (xc, y1, z0 + rise), (xe, y1, z0), (xe, y0, z0))]
        b.faces.new(v if s < 0 else v[::-1])
        v2 = [b.verts.new((c.co.x, c.co.y, c.co.z - th)) for c in v]
        b.faces.new(v2[::-1] if s < 0 else v2)


def lodge():
    P = Part('lodge')
    lg, lgd = mat('logs', LOGW, .85), mat('logs_dark', (.4, .27, .16), .85)
    W, D, H = 12, 8, 3.4
    k = 0
    z = 0
    while z < H:
        m = lg if k % 2 else lgd
        for y in (-D / 2, D / 2):
            logp(P, m, -W / 2 - .4, y, z + .19, W / 2 + .4, y, z + .19, .2, 8)
        for x in (-W / 2, W / 2):
            logp(P, m, x, -D / 2 - .4, z + .37, x, D / 2 + .4, z + .37, .2, 8)
        z += .36
        k += 1
    P.box(lgd, -W / 2, W / 2, -D / 2, D / 2, -.6, .05)  # floor / foundation
    # gable ends filled with boards
    b = P.bm(lgd)
    for x in (-W / 2, W / 2):
        v = [b.verts.new(c) for c in ((x, -D / 2, H), (x, D / 2, H), (x, 0, H + 3.0))]
        b.faces.new(v if x > 0 else v[::-1])
    gable(P, mat('roof_green', GREENR, .5, .3), -W / 2 - .8, W / 2 + .8, -D / 2 - 1.0, D / 2 + 1.0, H - .25, 3.4)
    # stone chimney on the east end
    P.box(mat('stone', STONE, .95), W / 2 + .2, W / 2 + 1.5, -.8, .8, -.6, H + 4.2, sub=1)
    # lake-side porch: deck, posts, its own lean-to roof
    P.box(lg, -W / 2, W / 2, -D / 2 - 3, -D / 2, .1, .3)
    for x in (-W / 2 + .3, -2, 2, W / 2 - .3):
        logp(P, lg, x, -D / 2 - 2.8, .3, x, -D / 2 - 2.8, 2.7, .12, 6)
    b = P.bm(mat('roof_green', GREENR, .5, .3))
    v = [b.verts.new(c) for c in ((-W / 2, -D / 2, 3.1), (W / 2, -D / 2, 3.1), (W / 2, -D / 2 - 3.3, 2.6), (-W / 2, -D / 2 - 3.3, 2.6))]
    b.faces.new(v)
    b.faces.new([b.verts.new((c.co.x, c.co.y, c.co.z - .08)) for c in v][::-1])
    # windows and door (lake side), glowing at night
    for x in (-4, -1.6, 2.6, 4.6):
        P.box(mat('lamp', (1, .82, .5), .3), x - .55, x + .55, -D / 2 - .25, -D / 2 - .18, 1.1, 2.1)
    P.box(mat('door', (.3, .18, .1), .8), .1, 1.1, -D / 2 - .26, -D / 2 - .18, .3, 2.3)
    return P.build(wood_col)


def boathouse():
    P = Part('boathouse')
    red, wh = mat('red_boards', RED, .85), mat('trim', (.85, .84, .8), .7)
    w = mat('creosote', CREO, .9)
    L, W, H = 12, 7, 4.2  # extends from the shore (y=+2) out over the water (y=-10)
    y0, y1 = -10, 2
    for x in (-W / 2, W / 2):  # piles
        for y in range(y0, y1 + 1, 3):
            logp(P, w, x, y, -3, x, y, .6, .16, 6)
    P.box(w, -W / 2 - 1.6, -W / 2, y0, y1, .6, .8)  # side catwalk (west)
    P.box(w, W / 2, W / 2 + .2, y0, y1, .6, .8)
    for x in (-W / 2, W / 2):  # board-and-batten walls (the lake end stays open)
        P.box(red, x - .08, x + .08, y0, y1, .8, H)
        for y in [y0 + i * .6 for i in range(21)]:
            P.box(red, x - .12, x + .12, y, y + .07, .8, H)
    P.box(red, -W / 2, W / 2, y1 - .16, y1, .8, H)
    P.box(wh, -W / 2 - .1, W / 2 + .1, y0 - .1, y0 + .1, H - .5, H)  # header over the boat door
    for x in (-W / 2, W / 2):
        P.box(wh, x - .14, x + .14, y0 - .12, y0 + .12, .8, H)
    gable_y(P, mat('roof_grey', (.32, .33, .34), .6, .2), -W / 2 - .7, W / 2 + .7, y0 - .5, y1 + .5, H, 2.2)
    b = P.bm(red)
    for y in (y0, y1):  # triangular gable ends
        v = [b.verts.new(c) for c in ((-W / 2, y, H), (W / 2, y, H), (0, y, H + 2.2))]
        b.faces.new(v if y < 0 else v[::-1])
    return P.build(wood_col)


def canoe():
    P = Part('canoe')
    m = mat('canoe_red', (.7, .12, .08), .4)
    hull_part(P, m, 5.0, .86, .36, z=.3, deadrise=.5, bow=.45)
    for y in (-1.2, 0, 1.2):
        P.box(mat('canoe_wood', WOOD_D, .8), -.4, .4, y - .05, y + .05, .22, .28)
    return P.build()


def scree_col(p, key):
    c = .62 + .12 * n3(p, .4, 2) + .1 * n3(p, 2.5, 8)
    lichen = max(0, n3(p, .8, 17) - .2) * 1.3
    r, g, b = c, c * .99, c * .97
    r, g, b = r * (1 - .25 * lichen), g * (1 - .18 * lichen), b * (1 - .3 * lichen)
    if p.z < .6:
        k = .55 + .15 * n3(p, 3, 1)
        r, g, b = r * k, g * k, b * k
    return (r, g, b)


def scree_slope(L=70.0, H=26.0, seed=3):
    """one sheet of talus: blocky rubble at the angle of repose (~34 deg) from 6 m under water up to the cliff foot,
    with rock ribs and gullies running down it; ends taper into the hillside (bent along the shore in the game)"""
    P = Part('scree_slope')
    m = mat('scree', GRANITE, .95)
    b = P.bm(m)
    NX, NZ = int(L / .7), 70
    tan = math.tan(math.radians(34))
    grid = []
    for i in range(NX + 1):
        x = L * i / NX
        end = smooth01(x / 12) * smooth01((L - x) / 12)
        top = (H * (.65 + .35 * noise.noise(Vector((x * .03, 2, seed))))) * end
        col = []
        for j in range(NZ + 1):
            z = -6 + (top + 6) * j / NZ
            y = (z + 6) / tan - 6 / tan
            gully = .9 * noise.noise(Vector((x * .09, 0, seed + 4)))  # ribs and gullies down the slope
            lump = 1.1 * abs(noise.noise(Vector((x * .35, y * .35, z * .35 + seed)))) + .3 * noise.noise(Vector((x * 1.4, z * 1.4, seed + 7)))
            y += -gully - lump + 3 * (1 - end)
            col.append(b.verts.new((x - L / 2, y, z + lump * .5)))
        grid.append(col)
    for i in range(NX):
        for j in range(NZ):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    return P.build(scree_col, smooth=True)


def boulders():
    """a scatter of angular-but-weathered granite blocks for the scree foot and slope"""
    P = Part('boulders')
    m = mat('scree', GRANITE, .95)
    for i in range(11):
        r = random.uniform(.5, 2.0)
        boulder(P, m, random.uniform(-6, 6), random.uniform(-3, 3), r * .2, r, sq=random.uniform(.55, .85), seed=i * 3.7, detail=1)
    return P.build(scree_col)


export([trestle(), logjam(), lodge(), boathouse(), canoe(), boulders()], OUT, BLEND)

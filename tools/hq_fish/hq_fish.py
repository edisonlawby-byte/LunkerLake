"""Builds the high-quality fish in Blender from the rectified reference photos (rectify.py / merge.py output).

Per species:
  body   lofted from the real outline (traced from the side photo, in standard lengths), with cross-sections whose
         width comes from 3D scans of related fish (largemouth bass, bluegill) scaled per species; the gill cover,
         cheek bone and jaw are sculpted in as raised edges and grooves along the lines traced on the photo.
         Skin = the photo itself, straightened onto the body; detail normal map for scales and edges.
  fins   membranes cut from the photo (dorsal, anal, tail in the mid-plane; pectoral and other paired fins as
         angled flaps on each side), with opacity, in one texture atlas.
  eye    a glossy eyeball wearing the real eye from the photo.
Frame (same as the game's other fish): snout at x=+0.5, tail base at x=-0.5, 1 unit = standard length, z up.

Usage: python3 hq_fish.py <out dir> sm,cr,br   (reads out/<sp>/ next to this script)
Writes <out dir>/hq/<sp>.glb (geometry) and <out dir>/hq/<sp>_{skin,nrm,atlas,atlas_a}.jpg, plus <out dir>/fish_hq.blend
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
SPS = sys.argv[2].split(',')
os.makedirs(os.path.join(OUT, 'hq'), exist_ok=True)

# width / depth along the body, measured on the scans (measure_scan.py), pectoral-fin bumps removed and smoothed
SCAN_WD = {
    'bass': [(0, .52), (.15, .55), (.3, .6), (.45, .63), (.6, .645), (.7, .66), (.8, .69), (.88, .72), (.94, .8), (.985, .9), (1, .9)],
    'bluegill': [(0, .36), (.15, .42), (.3, .44), (.45, .46), (.6, .48), (.7, .47), (.8, .49), (.88, .55), (.94, .64), (.985, .8), (1, .8)],
    # pike: near-round body, head flattened into the 'duck bill' (wider than deep toward the snout)
    'pike': [(0, .6), (.2, .68), (.45, .74), (.65, .78), (.78, .85), (.86, .98), (.93, 1.25), (.98, 1.5), (1, 1.5)],
    # trout and char: compressed body, head about as wide as deep
    'trout': [(0, .4), (.2, .48), (.45, .55), (.65, .58), (.8, .64), (.9, .72), (.96, .78), (1, .78)],
    # snakehead: round tube-like body, broad flat head
    'snakehead': [(0, .45), (.2, .6), (.45, .78), (.65, .85), (.8, .95), (.9, 1.05), (.96, 1.05), (1, 1.0)],
    # featherback / knifefish: very thin blade, head a little thicker
    'knife': [(0, .2), (.2, .24), (.45, .28), (.65, .32), (.8, .4), (.9, .5), (.96, .58), (1, .58)],
    # burbot: round eel-like body, broad flat head
    'burbot': [(0, .35), (.2, .55), (.45, .8), (.65, .95), (.8, 1.15), (.9, 1.3), (.96, 1.35), (1, 1.3)],
    # catfish: round-bellied body, broad flat head
    'catfish': [(0, .45), (.2, .55), (.45, .72), (.62, .85), (.72, 1.0), (.8, 1.18), (.88, 1.35), (.95, 1.45), (1, 1.4)],
}
# which scan each species follows and how much slimmer/fatter (barramundi is more compressed than a bass; crappie
# a little more than a bluegill), widest point height (fraction of depth from the back)
SPEC = {'sm': ('bass', .96, .55), 'cr': ('bluegill', .9, .55), 'br': ('bass', .84, .55), 'lm': ('bass', 1.0, .55), 'gd': ('bass', 1.0, .55),
        'sp': ('bass', .95, .55), 'bg': ('bluegill', 1.0, .55), 'pk': ('pike', 1.0, .5), 'cf': ('catfish', 1.0, .6),
        'wa': ('bass', .82, .52), 'yp': ('bass', .85, .52), 'mu': ('pike', 1.0, .5), 'tm': ('pike', 1.0, .5),
        'lt': ('trout', 1.0, .5), 'bt': ('trout', 1.0, .5), 'rt': ('trout', 1.0, .5), 'bu': ('burbot', 1.0, .55),
        'ts': ('snakehead', 1.0, .5), 'hs': ('snakehead', 1.0, .5), 'hb': ('trout', 1.0, .5), 'ma': ('trout', 1.05, .5),
        'gg': ('bluegill', 1.05, .55), 'rc': ('catfish', 1.0, .6), 'fb': ('knife', 1.0, .55),
        'pb': ('bass', .9, .55), 'bp': ('bass', .9, .55), 'pr': ('bluegill', 1.0, .55), 'py': ('trout', .95, .5),
        'ar': ('knife', 1.6, .5), 'rtc': ('catfish', 1.0, .6), 'wf': ('snakehead', .9, .5), 'ap': ('snakehead', .95, .5)}
# fin flap angles (degrees out from the body) and the fin texture layout
PEC_ANGLE, PEL_ANGLE = 16, 14
IRIS_RATIO = {'sm': 1.85, 'cr': 1.7, 'br': 1.9, 'lm': 1.9, 'gd': 1.9, 'sp': 1.85, 'bg': 1.6, 'pk': 1.7, 'cf': 1.5, 'wa': 1.5, 'yp': 1.7, 'mu': 1.7, 'tm': 1.7, 'lt': 1.8, 'bt': 1.8, 'rt': 1.8, 'bu': 1.7, 'ts': 1.6, 'hs': 1.6, 'hb': 1.6, 'ma': 1.6, 'gg': 1.7, 'rc': 1.5, 'fb': 1.6, 'pb': 1.8, 'bp': 1.8, 'pr': 1.7, 'py': 1.7, 'ar': 1.6, 'rtc': 1.5, 'wf': 1.6, 'ap': 1.6}  # iris diameter / pupil diameter, from the reference photos
# iris colours (RGB, pupil edge -> outer edge): smallmouth bronze-orange to red, crappie bright gold to olive-gold,
# barramundi gold to pale amber
IRIS_COL = {'sm': ((.85, .5, .18), (.42, .12, .06)), 'cr': ((.9, .74, .28), (.42, .36, .16)), 'br': ((.86, .68, .34), (.55, .44, .3)),
            'lm': ((.78, .6, .22), (.4, .3, .12)), 'gd': ((.85, .62, .2), (.5, .32, .1)), 'sp': ((.8, .45, .18), (.45, .16, .08)),
            'bg': ((.5, .42, .3), (.22, .2, .16)), 'pk': ((.9, .78, .4), (.55, .45, .25)), 'cf': ((.55, .55, .5), (.25, .25, .22)),
            'wa': ((.75, .72, .6), (.38, .36, .3)), 'yp': ((.85, .7, .3), (.45, .36, .15)), 'mu': ((.85, .72, .4), (.5, .42, .24)),
            'tm': ((.85, .72, .4), (.5, .42, .24)), 'lt': ((.75, .65, .4), (.35, .3, .2)), 'bt': ((.72, .6, .35), (.32, .26, .16)),
            'rt': ((.8, .7, .45), (.4, .34, .22)), 'bu': ((.6, .55, .38), (.28, .25, .18)),
            'ts': ((.75, .3, .15), (.35, .12, .06)), 'hs': ((.75, .55, .3), (.35, .25, .12)), 'hb': ((.85, .75, .45), (.45, .38, .22)),
            'ma': ((.8, .55, .3), (.4, .26, .14)), 'gg': ((.85, .45, .25), (.4, .2, .1)), 'rc': ((.6, .58, .5), (.28, .26, .22)),
            'fb': ((.8, .78, .65), (.4, .38, .3)),
            'pb': ((.88, .3, .12), (.45, .1, .05)), 'bp': ((.88, .3, .12), (.45, .1, .05)), 'pr': ((.85, .55, .3), (.45, .25, .12)),
            'py': ((.8, .75, .55), (.4, .36, .25)), 'ar': ((.75, .72, .6), (.35, .33, .26)), 'rtc': ((.6, .58, .5), (.28, .26, .22)),
            'wf': ((.85, .55, .2), (.45, .25, .08)), 'ap': ((.7, .65, .45), (.32, .3, .2))}
# barbels: (u of the root, height 0 back..1 belly, side 1/-1/0, length SL, backward, downward, root radius)
BARBELS = {'ar': [(.995, .88, .3, .085, -1, -.35, .003), (.995, .88, -.3, .085, -1, -.35, .003)],  # forward-pointing chin barbels
           'rtc': [(.985, .55, 1, .3, .55, .35, .005), (.985, .55, -1, .3, .55, .35, .005),
                   (.955, .97, .35, .09, .4, .8, .0028), (.955, .97, -.35, .09, .4, .8, .0028),
                   (.94, .95, .75, .1, .45, .75, .0028), (.94, .95, -.75, .1, .45, .75, .0028)],
           'cf': [(.985, .55, 1, .2, .55, .35, .0045), (.985, .55, -1, .2, .55, .35, .0045),     # maxillary (long)
                  (.955, .97, .35, .07, .4, .8, .0025), (.955, .97, -.35, .07, .4, .8, .0025),  # chin, inner
                  (.94, .95, .75, .085, .45, .75, .0025), (.94, .95, -.75, .085, .45, .75, .0025),  # chin, outer
                  (.985, .22, .7, .035, .5, -.6, .0018), (.985, .22, -.7, .035, .5, -.6, .0018)],  # nasal
           'rc': [(.985, .55, 1, .22, .55, .35, .0045), (.985, .55, -1, .22, .55, .35, .0045),
                  (.955, .97, .35, .08, .4, .8, .0025), (.955, .97, -.35, .08, .4, .8, .0025),
                  (.985, .22, .7, .06, .5, -.6, .002), (.985, .22, -.7, .06, .5, -.6, .002)],
           'bu': [(.96, .98, 0, .045, .3, .85, .0028),  # single chin barbel
                  (.99, .3, .6, .02, .4, -.5, .0014), (.99, .3, -.6, .02, .4, -.5, .0014)]}  # tiny nasal tubes
PINK_FIX = {'br': (.72, .45)}  # (from u, from t): open mouth / gills showing pink in the head photo


def interp_table(tab, u):
    xs, ys = zip(*tab)
    return np.interp(u, xs, ys)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-12), 0, 1)
    q = a + ab * t
    return np.linalg.norm(p - q), q, t


def poly_signed(p, poly):
    """distance from p to the polyline and which side it is on (+1 toward the snout: larger u)."""
    best = (1e9, None)
    for i in range(len(poly) - 1):
        d, q, t = seg_dist(p, poly[i], poly[i + 1])
        if d < best[0]:
            best = (d, q, i)
    d, q, i = best
    a, b = poly[i], poly[i + 1]
    tang = b - a
    nrm = np.array([tang[1], -tang[0]])
    if nrm[0] < 0:
        nrm = -nrm  # point toward the snout
    s = 1 if np.dot(p - q, nrm) >= 0 else -1
    return d, s


def centred_eye(path, iris_ratio=1.9, seed=1, palette=None):
    """A square-on eye made from the photo eye. Photos catch the eye at an angle (pupil off-centre and oval), which
    looks wrong on a round eyeball. So: find the pupil (darkest blob near the centre; centre and axes from its
    moments), read the real iris colours all the way round it (just outside the pupil and further out), and paint a
    round iris with those colours and fine radial fibres around a round, centred pupil."""
    import cv2
    from PIL import Image
    rng = np.random.default_rng(seed)
    im = cv2.resize(cv2.imread(path), (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    g = cv2.GaussianBlur(cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2.5)
    yy, xx = np.mgrid[:256, :256]
    near = (xx - 128) ** 2 + (yy - 128) ** 2 < 85 ** 2
    m = ((g <= np.percentile(g[near], 14)) & near).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA] - .5 * np.hypot(cen[1:, 0] - 128, cen[1:, 1] - 128) ** 1.5)
    py, px = np.nonzero(lab == k)
    cx, cy = px.mean(), py.mean()
    cov = np.cov(np.stack([px - cx, py - cy]))
    ev_, evec = np.linalg.eigh(cov)
    ax = 2 * np.sqrt(ev_)  # semi-axes of the pupil ellipse
    # colour of the iris all round: per angle, median along the band from just outside the pupil
    NA = 180
    phis = np.linspace(-math.pi, math.pi, NA, endpoint=False)
    inner, outer = np.zeros((NA, 3), np.float32), np.zeros((NA, 3), np.float32)
    for i, ph in enumerate(phis):
        d = np.cos(ph) * evec[:, 1] * ax[1] + np.sin(ph) * evec[:, 0] * ax[0]
        def band(k0, k1):
            pts = [im[int(np.clip(cy + d[1] * kk, 0, 255)), int(np.clip(cx + d[0] * kk, 0, 255))] for kk in np.linspace(k0, k1, 8)]
            return np.median(pts, 0)
        inner[i] = band(1.12, 1.3)
        outer[i] = band(1.35, min(iris_ratio, 1.8) * .95)
    # smooth round the eye (removes sky reflections crossing the iris) and limit brightness outliers
    def smooth(c):
        c = np.concatenate([c[-12:], c, c[:12]])
        c = np.stack([np.convolve(c[:, j], np.ones(9) / 9, 'same') for j in range(3)], 1)[12:-12]
        # colours far from the eye's typical colour (sky reflections, glints) are pulled back to it
        med = np.median(c, 0)
        dist = np.linalg.norm(c - med, axis=1, keepdims=True)
        w = np.clip((dist - .06) / .1, 0, 1)
        c = c * (1 - w) + med * w
        # photo irises sit in the shadow of the cornea: lift to a living-eye brightness and saturation
        lum = c.mean(1, keepdims=True)
        c = med.mean() + (c - c.mean(1, keepdims=True)) * 1.5 + (lum - med.mean())
        c = c * (.42 / max(float(np.median(c.mean(1))), 1e-3))
        return np.clip(c, 0, 1)
    inner, outer = smooth(inner), smooth(outer)
    R_IRIS = 92
    R_PUP = R_IRIS / iris_ratio
    dx, dy = xx - 128.0, yy - 128.0
    rho = np.sqrt(dx * dx + dy * dy)
    ia = ((np.arctan2(dy, dx) + math.pi) / (2 * math.pi) * NA).astype(int) % NA
    s_ = np.clip((rho - R_PUP) / (R_IRIS - R_PUP), 0, 1)[..., None]
    if palette:
        # species iris colours (from the reference boards; photo irises are shadowed by the cornea), with the
        # photo's own light-and-dark pattern round the eye kept as shading
        pin, pout = np.array(palette[0][::-1], np.float32), np.array(palette[1][::-1], np.float32)
        mod = lambda c: np.clip(c.mean(1) / max(float(c.mean()), 1e-3), .8, 1.2)[:, None]
        inner, outer = pin * mod(inner), pout * mod(outer)
    sc_ = s_ ** .55
    iris = (inner[ia] * (1 - sc_) + outer[ia] * sc_) * .62  # seen through the cornea, irises read darker than paint
    iris = iris * (1 - .3 * np.clip(-dy / R_IRIS, 0, 1) ** 1.5)[..., None]  # darker upper iris, shaded by the brow
    # radial fibres and a few flecks
    fib = rng.normal(0, 1, 720)
    fib = np.convolve(np.concatenate([fib[-6:], fib, fib[:6]]), np.ones(3) / 3, 'same')[6:-6]
    fa = ((np.arctan2(dy, dx) + math.pi) / (2 * math.pi) * 720).astype(int) % 720
    iris = iris * (1 + .07 * fib[fa][..., None] * (.4 + .6 * s_))
    # bright metallic ring at the pupil margin, as in bass and crappie eyes
    iris = iris * (1 + .18 * np.exp(-((rho - R_PUP - 3) / 3) ** 2)[..., None])
    iris = iris * (1 - .35 * s_ ** 2)  # darker toward the edge
    # pupil: near-black with a faint depth, soft edge; dark limbal ring; socket rim to the eyeball edge
    pup = np.array([.025, .02, .018], np.float32) + .04 * np.clip(1 - rho / R_PUP, 0, 1)[..., None]
    w_p = np.clip((R_PUP + 2.5 - rho) / 5, 0, 1)[..., None]
    out = iris * (1 - w_p) + pup * w_p
    out = out * (1 - .5 * np.exp(-((rho - R_IRIS) / 4.5) ** 2))[..., None]
    rim = np.clip((rho - R_IRIS) / 5, 0, 1)[..., None]
    out = out * (1 - rim) + outer.mean(0) * .3 * rim
    print('  eye: pupil at', round(cx), round(cy), 'axes', np.round(ax, 1))
    return Image.fromarray((np.clip(out, 0, 1)[:, :, ::-1] * 255).astype(np.uint8))

def build(sp):
    D = json.load(open(os.path.join(HERE, 'out', sp, 'data.json')))
    U = np.array(D['u'])
    TOP, BOT = np.array(D['top']), np.array(D['bot'])
    scan, kw, tW = SPEC[sp]
    lines = {k: np.array(D[k]) for k in ('gill', 'preop', 'mouth') if D.get(k)}

    def top(u):
        return float(np.interp(u, U, TOP))

    def bot(u):
        return float(np.interp(u, U, BOT))

    def halfw(u, t):
        """half width of the body at u, relative height t (0 back .. 1 belly)."""
        d = top(u) + bot(u)
        wmax = interp_table(SCAN_WD[scan], u) * kw * d
        s = .5 * t / tW if t < tW else .5 + .5 * (t - tW) / (1 - tW)
        return .5 * wmax * math.sin(math.pi * min(max(s, 0), 1)) ** .62

    # ---- body ----
    # rings along the body, denser at the head and the tail base
    g = np.linspace(0, 1, 170)
    us = np.clip(g + .06 * np.sin(2 * math.pi * g) * -1 * 0, 0, 1)
    us = 1 - (1 - g) ** 1.25  # more rings toward the snout
    us[0] = -.004
    K = 40  # segments per side, back to belly
    ts = (1 - np.cos(np.pi * np.arange(K + 1) / K)) / 2
    verts, uvs, faces = [], [], []
    ring_idx = []
    for i, u in enumerate(us):
        uu = min(max(u, 0), .9995)
        tp, bt = top(uu), bot(uu)
        row = {}
        for side in (1, -1):
            for k, t in enumerate(ts):
                if side == -1 and k in (0, K):
                    row[(side, k)] = row[(1, k)]
                    continue
                v = tp - t * (tp + bt)
                y = side * halfw(uu, t)
                row[(side, k)] = len(verts)
                verts.append([u - .5, y, v])
                uvs.append((uu, 1 - t))
        ring_idx.append(row)
    V = np.array(verts)
    # sculpted head lines: gill-cover flap edge (raised just ahead of the line, sharp step), cheek bone (softer),
    # jaw (groove)
    disp = np.zeros(len(V))
    for key, amp, width, groove in (('gill', .0045, .016, .0016), ('preop', .0022, .012, .001), ('mouth', 0, .006, .0024)):
        if key not in lines:
            continue
        poly = lines[key]
        umin = poly[:, 0].min() - .05
        for n, p in enumerate(V):
            u = p[0] + .5
            if u < umin or abs(p[1]) < 1e-5:
                continue
            d, s = poly_signed(np.array([u, p[2]]), poly)
            if d > width * 2.5:
                continue
            if key == 'mouth':
                disp[n] -= groove * math.exp(-(d / width) ** 2)
            elif s > 0:
                disp[n] += amp * math.exp(-d / width) * smoothstep(0, .0025, d) - groove * math.exp(-(d / .0025) ** 2)
            else:
                disp[n] -= groove * math.exp(-(d / .003) ** 2)
    me = bpy.data.meshes.new('body_' + sp)
    for i in range(len(us) - 1):
        a, b = ring_idx[i], ring_idx[i + 1]
        for side in (1, -1):
            for k in range(K):
                q = [a[(side, k)], a[(side, k + 1)], b[(side, k + 1)], b[(side, k)]]
                faces.append(q[::-1] if side == 1 else q)
    # end caps: tail base (flat, hidden by the fin root) and snout point
    for end, rr in ((0, ring_idx[0]), (1, ring_idx[-1])):
        loop = [rr[(1, k)] for k in range(K + 1)] + [rr[(-1, k)] for k in range(K - 1, 0, -1)]
        c = V[loop].mean(0)
        if end == 1:
            c[0] += .004
        ci = len(V)
        V = np.vstack([V, c])
        uvs.append((min(max(us[-1 if end else 0], 0), .9995), .5))
        disp = np.append(disp, 0)
        for j in range(len(loop)):
            f = [loop[j], loop[(j + 1) % len(loop)], ci]
            faces.append(f if end == 0 else f[::-1])
    me.from_pydata(V.tolist(), [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.update()
    # displace along normals
    me.calc_normals_split() if hasattr(me, 'calc_normals_split') else None
    nrm = np.array([v.normal[:] for v in me.vertices])
    co = np.array([v.co[:] for v in me.vertices]) + nrm * disp[:, None]
    for v, c in zip(me.vertices, co):
        v.co = c
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    body = bpy.data.objects.new('body_' + sp, me)

    # ---- texture atlas for fins, paired fins and the eye ----
    from PIL import Image
    src = os.path.join(HERE, 'out', sp)
    atlas = Image.new('RGB', (1024, 1024), (90, 90, 80))
    alpha = Image.new('L', (1024, 1024), 0)
    atlas.paste(Image.open(os.path.join(src, 'fins.jpg')).resize((1024, 512), Image.LANCZOS), (0, 0))
    alpha.paste(Image.open(os.path.join(src, 'fins_a.jpg')).convert('L').resize((1024, 512), Image.LANCZOS), (0, 0))
    slots = [(0, 512), (512, 512), (0, 768)]
    pslot = {}
    for n, p in enumerate(D.get('patches', [])):
        x0, y0 = slots[n]
        atlas.paste(Image.open(os.path.join(src, p['name'] + '.jpg')).resize((512, 256), Image.LANCZOS), (x0, y0))
        alpha.paste(Image.open(os.path.join(src, p['name'] + '_a.jpg')).convert('L').resize((512, 256), Image.LANCZOS), (x0, y0))
        pslot[p['name']] = (x0, y0)
    atlas.paste(centred_eye(os.path.join(src, 'eye.jpg'), IRIS_RATIO.get(sp, 1.9), palette=IRIS_COL.get(sp)), (512, 768))
    alpha.paste(255, (512, 768, 768, 1024))
    hq = os.path.join(OUT, 'hq')
    atlas.save(os.path.join(hq, f'{sp}_atlas.jpg'), quality=88)
    alpha.save(os.path.join(hq, f'{sp}_atlas_a.jpg'), quality=90)
    # skin clean-up: the photo's own eye is painted over with the skin around it (the eyeball sits there instead, and
    # a second eye showed beside it from an angle), leaving a dark socket rim; pink gill/mouth showing through an
    # open mouth is toned down to the throat colour
    import cv2
    sk = cv2.imread(os.path.join(src, 'skin.jpg'))
    Hs, Ws = sk.shape[:2]
    E = D['eye']
    tp_, bt_ = top(E['u']), bot(E['u'])
    cx, cy = E['u'] * Ws, (tp_ - E['v']) / (tp_ + bt_) * Hs
    rx, ry = E['r'] * Ws, E['r'] / (tp_ + bt_) * Hs
    m = np.zeros((Hs, Ws), np.uint8)
    cv2.ellipse(m, (int(cx), int(cy)), (int(rx * 1.02), int(ry * 1.02)), 0, 0, 360, 255, -1)
    sk = cv2.inpaint(sk, m, 9, cv2.INPAINT_TELEA)
    ring = np.zeros((Hs, Ws), np.float32)
    cv2.ellipse(ring, (int(cx), int(cy)), (int(rx * 1.06), int(ry * 1.06)), 0, 0, 360, 1.0, max(2, int(rx * .12)))
    ring = cv2.GaussianBlur(ring, (0, 0), max(1.5, rx * .05))[..., None]
    sk = (sk * (1 - .45 * ring)).astype(np.uint8)
    if sp in PINK_FIX:
        u0_, t0_ = PINK_FIX[sp]
        hsv = cv2.cvtColor(sk, cv2.COLOR_BGR2HSV).astype(np.float32)
        hue, sat = hsv[..., 0], hsv[..., 1]
        pink = (((hue > 150) | (hue < 8)) & (sat > 30)).astype(np.float32)
        reg = np.zeros((Hs, Ws), np.float32); reg[int(t0_ * Hs):, int(u0_ * Ws):] = 1
        w_ = cv2.GaussianBlur(pink * cv2.GaussianBlur(reg, (0, 0), 20), (0, 0), 4)
        hsv[..., 1] = sat * (1 - .85 * w_)
        hsv[..., 2] = hsv[..., 2] * (1 - .1 * w_)
        sk = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    cv2.imwrite(os.path.join(hq, f'{sp}_skin.jpg'), sk, [cv2.IMWRITE_JPEG_QUALITY, 86])
    Image.open(os.path.join(src, 'nrm.jpg')).save(os.path.join(hq, f'{sp}_nrm.jpg'), quality=88)

    # ---- fins ----
    FU = D['fin_uv']

    def fin_uv(u, v):  # whole-fish straightened texture, top half of the atlas (image y down -> uv y up)
        x = (u - FU['u0']) / (FU['u1'] - FU['u0'])
        y = (FU['v1'] - v) / (FU['v1'] - FU['v0'])
        return (x, 1 - .5 * y)

    fv, ff, fuv = [], [], []

    def quad_strip(cols, bend):
        """cols: (u, inner v, outer v); a membrane in the mid-plane, gently cupped sideways."""
        n0 = len(fv)
        for c, (u, a, b) in enumerate(cols):
            for j, v in enumerate(np.linspace(a, b, 7)):
                f = j / 6
                y = bend * math.sin(math.pi * c / max(1, len(cols) - 1)) * f * f
                fv.append((u - .5, y, v))
                fuv.append(fin_uv(u, v))
        for c in range(len(cols) - 1):
            for j in range(6):
                a0 = n0 + c * 7 + j
                ff.append([a0, a0 + 1, a0 + 8, a0 + 7])

    for f in D['fins']:
        cols = f['cols']
        if f['k'] == 'c':
            cols = [(u, a, b) for u, a, b in cols]
        quad_strip(cols, .006 if f['k'] != 'c' else .004)
    # paired / extra fins from their own photo patches
    for p in D.get('patches', []):
        poly = np.array(p['poly'])
        tex = np.array(p['tex'])
        x0, y0 = pslot[p['name']]
        k = p['k']
        if k == 'sd':  # spiny dorsal: mid-plane, like the other median fins
            sides = [0]
        else:
            sides = [1, -1]
        # fin root: the end nearest the head for pectorals, the front edge for pelvics
        root = poly[np.argmax(poly[:, 0])]
        ang = math.radians(PEC_ANGLE if k == 'pec' else PEL_ANGLE)
        tris = tessellate_polygon([[Vector((x, y, 0)) for x, y in poly]])
        for side in sides:
            n0 = len(fv)
            for (u, v), (tx, ty) in zip(poly, tex):
                if side == 0:
                    y = 0
                else:
                    t = (top(min(u, .999)) - v) / max(top(min(u, .999)) + bot(min(u, .999)), 1e-3)
                    y = side * (halfw(min(max(root[0], 0), .999), min(max(t, 0), 1)) + .003 + max(0, root[0] - u) * math.tan(ang))
                    if k == 'pel':  # pelvic fins hang under the belly, splayed
                        y = side * (.01 + max(0, root[0] - u) * math.tan(ang))
                fv.append((u - .5, y, v))
                fuv.append(((x0 + tx * 512) / 1024, 1 - (y0 + ty * 256) / 1024))
            for t in tris:
                ff.append([n0 + i for i in (t if side >= 0 else t[::-1])])
    # catfish barbels (whiskers): tapered tubes, dark (they use the pupil pixels of the atlas)
    if sp in BARBELS:
        dark_uv = ((512 + 128) / 1024, 1 - (768 + 128) / 1024)
        for (u0, vk, side_w, length, d_back, d_down, r0) in BARBELS[sp]:
            uu = min(u0, .995)
            v0 = top(uu) - vk * (top(uu) + bot(uu))
            y0 = side_w * max(halfw(uu, vk), .004)
            start = np.array([u0 - .5, y0, v0])
            dirv = np.array([-d_back, np.sign(y0) * .35 if y0 else 0, -d_down])
            dirv = dirv / np.linalg.norm(dirv)
            N, RG = 12, 5
            pts = [start + dirv * length * (k / N) + np.array([0, 0, -.25 * length * (k / N) ** 2]) for k in range(N + 1)]
            base = len(fv)
            for k, c in enumerate(pts):
                t_ = pts[min(k + 1, N)] - pts[max(k - 1, 0)]
                t_ = t_ / np.linalg.norm(t_)
                a_ = np.cross(t_, [0, 0, 1.0]); a_ = a_ / (np.linalg.norm(a_) + 1e-9)
                b_ = np.cross(t_, a_)
                r = r0 * (1 - .85 * k / N)
                for j in range(RG):
                    an = 2 * math.pi * j / RG
                    fv.append(tuple(c + r * (math.cos(an) * a_ + math.sin(an) * b_)))
                    fuv.append(dark_uv)
            for k in range(N):
                for j in range(RG):
                    a0, a1 = base + k * RG + j, base + k * RG + (j + 1) % RG
                    ff.append([a0, a1, a1 + RG, a0 + RG])
    fme = bpy.data.meshes.new('fins_' + sp)
    fme.from_pydata(fv, [], ff)
    fl = fme.uv_layers.new(name='UVMap')
    for poly in fme.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            fl.data[li].uv = fuv[fme.loops[li].vertex_index]
    fme.update()
    fins = bpy.data.objects.new('fins_' + sp, fme)

    # ---- eyes ----
    E = D['eye']
    r = E['r'] * 1.08
    ev, ef, euv = [], [], []
    eu = E['u']
    tp, bt = top(eu), bot(eu)
    t = (tp - E['v']) / (tp + bt)
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    K_EYE, PROTRUDE = .62, .14  # flatter dome, sits nearly flush with the head like a real fish eye
    for side in (1, -1):
        # where the eye centre meets the head surface, and which way the surface faces there (averaged over the eye)
        hit = bvh.ray_cast(Vector((eu - .5, side * 1.0, E['v'])), Vector((0, -side, 0)))
        c = hit[0]
        nrm_ = Vector((0, 0, 0))
        for du in (-r * .8, 0, r * .8):
            for dv in (-r * .8, 0, r * .8):
                h2 = bvh.ray_cast(Vector((eu - .5 + du, side * 1.0, E['v'] + dv)), Vector((0, -side, 0)))
                if h2[0] is not None:
                    nrm_ += h2[1] if h2[1].y * side > 0 else -h2[1]
        axis = (nrm_.normalized() + Vector((.12, 0, 0))).normalized()  # fish eyes look a touch forward
        fx = Vector((1, 0, 0)) - axis * axis.x
        fx.normalize()
        fy = axis.cross(fx).normalized()
        if fy.z < 0:
            fy = -fy
        cc = c + axis * (PROTRUDE * r - K_EYE * r)
        n0 = len(ev)
        SEG, RING = 32, 14
        rows = []
        for i in range(RING + 1):
            th = i / RING * math.pi * .7
            row = []
            for j in range(SEG):
                a = j / SEG * 2 * math.pi
                lx, ly, lz = math.sin(th) * math.cos(a), math.sin(th) * math.sin(a), math.cos(th)
                row.append(len(ev))
                ev.append(cc + r * (fx * lx + fy * ly + axis * (K_EYE * lz)))
                # photo eye: the crop spans 1.25 r around the centre; the eyeball rim (sin .62pi=.93) reaches ~r
                q = .8 / math.sin(math.pi * .7) * .97
                euv.append(((512 + 128 + lx * 128 * q) / 1024, 1 - (768 + 128 - ly * 128 * q) / 1024))
                if i == 0:
                    break
            rows.append(row)
        for i in range(RING):
            ra, rb = rows[i], rows[i + 1]
            for j in range(SEG):
                if i == 0:
                    f = [ra[0], rb[j], rb[(j + 1) % SEG]]
                else:
                    f = [ra[j], rb[j], rb[(j + 1) % SEG], ra[(j + 1) % SEG]]
                ef.append(f[::-1] if side == 1 else f)
    eme = bpy.data.meshes.new('eye_' + sp)
    eme.from_pydata([tuple(v) for v in ev], [], ef)
    el = eme.uv_layers.new(name='UVMap')
    for poly in eme.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            el.data[li].uv = euv[eme.loops[li].vertex_index]
    eme.update()
    eye = bpy.data.objects.new('eye_' + sp, eme)
    return body, fins, eye


def image(path, colour=True):
    im = bpy.data.images.load(path, check_existing=True)
    if not colour:
        im.colorspace_settings.name = 'Non-Color'
    return im


def materials(sp, body, fins, eye):
    hq = os.path.join(OUT, 'hq')
    # body: wet skin
    m = bpy.data.materials.new('skin_' + sp)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = image(os.path.join(hq, f'{sp}_skin.jpg'))
    nm = nt.nodes.new('ShaderNodeTexImage'); nm.image = image(os.path.join(hq, f'{sp}_nrm.jpg'), False)
    nn = nt.nodes.new('ShaderNodeNormalMap'); nn.inputs['Strength'].default_value = 1.0
    nt.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(nm.outputs['Color'], nn.inputs['Color'])
    nt.links.new(nn.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = .48
    for name, val in (('Coat Weight', .22), ('Coat Roughness', .22), ('Specular IOR Level', .35)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val
    body.data.materials.append(m)
    # fins: translucent membrane
    f = bpy.data.materials.new('fins_' + sp)
    f.use_nodes = True
    nt = f.node_tree
    b2 = nt.nodes['Principled BSDF']
    at = nt.nodes.new('ShaderNodeTexImage'); at.image = image(os.path.join(hq, f'{sp}_atlas.jpg'))
    aa = nt.nodes.new('ShaderNodeTexImage'); aa.image = image(os.path.join(hq, f'{sp}_atlas_a.jpg'), False)
    nt.links.new(at.outputs['Color'], b2.inputs['Base Color'])
    nt.links.new(aa.outputs['Color'], b2.inputs['Alpha'])
    b2.inputs['Roughness'].default_value = .5
    if 'Transmission Weight' in b2.inputs:
        b2.inputs['Transmission Weight'].default_value = .15
    if hasattr(f, 'surface_render_method'):
        f.surface_render_method = 'DITHERED'
    fins.data.materials.append(f)
    # eye: glossy cornea over the photo eye
    e = bpy.data.materials.new('eye_' + sp)
    e.use_nodes = True
    nt = e.node_tree
    b3 = nt.nodes['Principled BSDF']
    et = nt.nodes.new('ShaderNodeTexImage'); et.image = at.image
    nt.links.new(et.outputs['Color'], b3.inputs['Base Color'])
    b3.inputs['Roughness'].default_value = .05
    if 'Coat Weight' in b3.inputs:
        b3.inputs['Coat Weight'].default_value = 1
        b3.inputs['Coat Roughness'].default_value = .02
    eye.data.materials.append(e)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
objs = []
for n, sp in enumerate(SPS):
    body, fins, eye = build(sp)
    root = bpy.data.objects.new(sp + ' HQ', None)
    sc.collection.objects.link(root)
    for o in (body, fins, eye):
        sc.collection.objects.link(o)
        o.parent = root
        objs.append(o)
    materials(sp, body, fins, eye)
    print(sp, 'body', len(body.data.vertices), 'v', len(body.data.polygons), 'f; fins', len(fins.data.polygons), 'f; eye', len(eye.data.polygons), 'f')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'fish_hq.blend'))
# geometry for the game, one small file per species (textures are separate .jpg files): <out>/hq/<sp>.glb
for sp in SPS:
    for o in bpy.context.scene.objects:
        o.select_set(o.name in (f'body_{sp}', f'fins_{sp}', f'eye_{sp}'))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'hq', sp + '.glb'), use_selection=True, export_format='GLB',
                              export_materials='NONE', export_normals=True, export_texcoords=True, export_yup=True,
                              export_apply=False, export_animations=False)
print('exported')

"""Automatic first trace of a side photo (replaces most of the hand tracing done for the pilot fish).

From the cut-out mask: body axis, which end is the head (the tail end has the narrow tail stem), snout tip and tail
base (where the tail fin starts to widen after the stem). Then from the species data (FishBase measurements and the
game's fitted fin layout): fin bases along the back and belly, pectoral fin, gill line, cheek line, mouth; the eye is
found as the darkest round spot near where FishBase says it is. Hands are found by skin colour.
Everything is written as a trace JSON for rectify.py; anything wrong is then nudged by hand after one overlay check.

Usage: python3 -I auto_trace.py <photo> <mask png> <key> <out json> [credit json] [overrides json]
"""
import json, sys, math
import numpy as np, cv2

PH, MK, KEY, OUT = sys.argv[1:5]
CREDIT = json.loads(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != '-' else None
OVR = json.loads(sys.argv[6]) if len(sys.argv) > 6 else {}
HERE = __file__.rsplit('/', 1)[0]
FB = json.load(open(HERE + '/ref/fbref.json'))[KEY]['ratios']
S = json.load(open(HERE + '/ref/species.json'))[KEY]['look']
RF = json.load(open(HERE + '/ref/ref_fix.json')).get(KEY, {})
LOOK = dict(S, **RF)
# body family: pectoral length/height (SL), mouth end relative to the eye, belly fin trailing length
FAM = {'bass': dict(pec=(.2, .075), mouth=-1.1, pel=.14), 'sunfish': dict(pec=(.25, .07), mouth=1.4, pel=.15),
       'catfish': dict(pec=(.15, .06), mouth=2.2, pel=.12), 'pike': dict(pec=(.13, .045), mouth=-.6, pel=.12), 'perch': dict(pec=(.17, .06), mouth=-.6, pel=.14),
       'trout': dict(pec=(.15, .055), mouth=-1.3, pel=.11), 'burbot': dict(pec=(.12, .05), mouth=.3, pel=.08),
       'snakehead': dict(pec=(.14, .06), mouth=-.9, pel=.08), 'carp': dict(pec=(.18, .06), mouth=1.2, pel=.13),
       'knife': dict(pec=(.1, .045), mouth=-.4, pel=.04)}
FAMILY = {'lm': 'bass', 'sp': 'bass', 'sm': 'bass', 'gd': 'bass', 'bg': 'sunfish', 'cr': 'sunfish', 'cf': 'catfish', 'pk': 'pike',
          'wa': 'perch', 'yp': 'perch', 'mu': 'pike', 'tm': 'pike', 'lt': 'trout', 'bt': 'trout', 'rt': 'trout', 'bu': 'burbot',
          'ts': 'snakehead', 'hs': 'snakehead', 'hb': 'carp', 'ma': 'carp', 'gg': 'sunfish', 'rc': 'catfish', 'fb': 'knife', 'br': 'bass'}
fam = FAM[FAMILY.get(KEY, 'bass')]

img = cv2.imread(PH)
mask = (cv2.imread(MK, 0) > 127).astype(np.uint8)
H0, W0 = mask.shape
ys, xs = np.nonzero(mask)
P = np.stack([xs, ys], 1).astype(np.float64)
c0 = P.mean(0)
ev, evec = np.linalg.eigh(np.cov((P - c0).T))
ax = evec[:, 1]  # long axis
if ax[0] < 0:
    ax = -ax
nx = np.array([-ax[1], ax[0]])  # perpendicular
if nx[1] > 0:
    nx = -nx  # 'up' in the photo
t = (P - c0) @ ax
s = (P - c0) @ nx
tmin, tmax = t.min(), t.max()
NB = 400
bins = np.clip(((t - tmin) / (tmax - tmin) * (NB - 1)).astype(int), 0, NB - 1)
top = np.full(NB, np.nan); bot = np.full(NB, np.nan)
for b in range(NB):
    sel = s[bins == b]
    if len(sel) > 3:
        top[b], bot[b] = np.percentile(sel, 99.5), np.percentile(sel, .5)
ok = ~np.isnan(top)
idx = np.arange(NB)
top = np.interp(idx, idx[ok], top[ok]); bot = np.interp(idx, idx[ok], bot[ok])
h = cv2.GaussianBlur((top - bot).reshape(1, -1).astype(np.float32), (0, 0), 3).ravel()
hmax = h.max()


def stem(end):
    """narrowest point in the 6-35% window from one end, and how narrow."""
    r = range(int(.06 * NB), int(.35 * NB)) if end == 0 else range(int(.65 * NB), int(.94 * NB))
    i = min(r, key=lambda k: h[k])
    return i, h[i] / hmax


i0, r0 = stem(0)
i1, r1 = stem(1)
tail_end = 0 if r0 < r1 else 1
if OVR.get('head'):  # checked by eye on the contact sheet
    tail_end = 0 if OVR.pop('head') == 'right' else 1
ip = i0 if tail_end == 0 else i1
OVR = dict(OVR)
# tail base: from the stem toward the tail end, where the outline starts to flare into the tail fin
step = -1 if tail_end == 0 else 1
k = ip
while 0 < k < NB - 1 and h[k] < h[ip] * 1.18:
    k += step
itb = k - step * 2
head_i = NB - 1 if tail_end == 0 else 0
tb_t = tmin + itb / (NB - 1) * (tmax - tmin)
tb_s = (top[itb] + bot[itb]) / 2
# snout: the farthest mask point at the head end, near the head's mid-height
hb = slice(max(0, head_i - 6), head_i + 1) if head_i > 0 else slice(0, 7)
sn_t = tmax if tail_end == 0 else tmin
near_head = np.abs(t - sn_t) < (tmax - tmin) * .02
sn_s = np.median(s[near_head])


def to_img(tt, ss):
    return (c0 + ax * tt + nx * ss).tolist()


snout = to_img(sn_t, sn_s)
tbase = to_img(tb_t, tb_s)
if 'snout' in OVR:
    snout = OVR.pop('snout')
if 'tbase' in OVR:
    tbase = OVR.pop('tbase')
L = math.dist(snout, tbase)
tr = {'photo': PH, 'mask': MK, 'mid': [[round(v, 1) for v in snout], [round(v, 1) for v in tbase]]}
# geometry helpers along the snout->tail-base line (u = 1 at the snout)
SN, TB = np.array(snout), np.array(tbase)
dvec = (SN - TB) / L
up = np.array([-dvec[1], dvec[0]])
if up[1] > 0:
    up = -up


def px(u, v):
    return (TB + dvec * u * L + up * v * L).tolist()


def outline(u, side):
    """raw silhouette distance (SL) from the midline at u, up (side=1) or down (-1)."""
    p0 = TB + dvec * u * L
    best = 0
    for k in range(1, int(.6 * L)):
        q = p0 + up * side * k
        x, y = int(round(q[0])), int(round(q[1]))
        if not (0 <= x < W0 and 0 <= y < H0) or not mask[y, x]:
            if k - best > 6:
                break
            continue
        best = k
    return best / L


fins = LOOK.get('fins', [])
spans_top, spans_bot = [], []
d = [f for f in fins if f['k'] == 'd']
if d:
    spans_top.append(('d', min(f['a'] for f in d), max(f['b'] for f in d)))
for f in fins:
    if f['k'] in ('adi',):
        spans_top.append(('ad', f['a'] - .01, f['b'] + .01))
    if f['k'] == 'a':
        spans_bot.append(('a', f['a'], f['b']))
    if f['k'] == 'pel':
        spans_bot.append(('pel', f['u'] - fam['pel'], f['u'] + .01))
spans_bot.sort(key=lambda x: x[1])
# merge overlapping belly spans (pelvic trailing back to the anal fin)
merged = []
for sp in spans_bot:
    if merged and sp[1] < merged[-1][2]:
        merged[-1] = (merged[-1][0], merged[-1][1], max(merged[-1][2], sp[2]))
    else:
        merged.append(sp)
spans_bot = merged


def body_edge(u0, lo, hi, side):
    """u near u0 where the silhouette is narrowest (bare body edge, not a fin hanging past it)."""
    cand = np.linspace(u0 + lo, u0 + hi, 13)
    vals = [outline(u, side) for u in cand]
    return float(cand[int(np.argmin(vals))])


def span(kind, a, b, side):
    ua, ub = a - .006, b + .006
    if SNAP:
        ua = body_edge(ua, -.05, .01, side)  # rear end: fins trail back past their base
        ub = body_edge(ub, -.01, .065, side)
    va, vb = outline(ua, side) * side, outline(ub, side) * side
    body = []
    if side == 1 and .3 < (ua + ub) / 2 < .8 and ub - ua > .12:
        # the fin hides the back under it: rebuild the arch so the deepest point matches FishBase body depth
        um = (ua + ub) / 2
        lin = (va + vb) / 2
        need = FB.get('BD', .3) * float(OVR.get('bd_scale', 1)) - outline(um, -1)
        bulge = max(0.0, need - lin)
        for s_ in (.2, .4, .5, .6, .8):
            u_ = ua + (ub - ua) * s_
            v_ = va + (vb - va) * s_ + bulge * 4 * s_ * (1 - s_)
            body.append([round(c, 1) for c in px(u_, v_)])
    return {'fin': kind, 'a': [round(v, 1) for v in px(ua, va)], 'b': [round(v, 1) for v in px(ub, vb)],
            'base': [round(v, 1) for v in px(ua, va)], 'body': body}


if 'spans_top' in OVR:  # fin positions read off the check image (u along the body), for unusual photos
    spans_top = [tuple(x) for x in OVR.pop('spans_top')]
if 'spans_bot' in OVR:
    spans_bot = [tuple(x) for x in OVR.pop('spans_bot')]
SNAP = OVR.pop('snap', True)
tr['top'] = [span(k_, a, b, 1) for k_, a, b in spans_top]
tr['bot'] = [span(k_, a, b, -1) for k_, a, b in spans_bot]
# eye: darkest round spot near the expected place
E = LOOK.get('eye', {})
eu = 1 - FB.get('POL', .07) - FB.get('ED', .04) / 2
er = FB.get('ED', .04) / 2 * 1.15
top_e, bot_e = outline(eu, 1), outline(eu, -1)
ev_ = top_e - E.get('t', .33) * (top_e + bot_e)
g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), max(1.5, er * L * .3))
best = None
for du in np.linspace(-.04, .04, 17):
    for dv in np.linspace(-.05, .05, 17):
        x, y = px(eu + du, ev_ + dv)
        x, y = int(x), int(y)
        if 0 <= x < W0 and 0 <= y < H0:
            val = g[y, x] + 40 * (abs(du) + abs(dv)) * 4
            if best is None or val < best[0]:
                best = (val, x, y)
_, ex, ey = best
if 'eye_at' in OVR:
    ex, ey = OVR.pop('eye_at')
tr['eye'] = [ex, ey, OVR.pop('eye_r', round(er * L))]
# pectoral fin: base just behind the gill line, about 60% down the side, swept back
pu = next((f['u'] for f in fins if f['k'] == 'pec'), 1 - FB.get('PPEL', .3))
pt, pb = outline(pu, 1), outline(pu, -1)
pv = pt - .62 * (pt + pb)
pl, phh = fam['pec']
poly = []
for a in np.linspace(0, 2 * math.pi, 14, endpoint=False):
    cu = pu - pl / 2 + math.cos(a) * pl / 2
    cv = pv - .01 + math.sin(a) * phh / 2 * (1 - .5 * max(0, -math.cos(a)))
    poly.append([round(v, 1) for v in px(cu, cv)])
tr['pec'] = poly
# head lines
ug = 1 - FB.get('HL', .3)


def vline(u_at, bow, t0=.12, t1=.92, n=6):
    pts = []
    for tt in np.linspace(t0, t1, n):
        tp, bt = outline(u_at, 1), outline(u_at, -1)
        u = u_at + bow * math.sin(math.pi * tt) - .015 * tt
        v = tp - tt * (tp + bt)
        pts.append([round(c, 1) for c in px(u, v)])
    return pts


tr['gill'] = vline(ug, -.02)
tr['preop'] = vline(ug + .07, -.015, .2, .85)
mouth_end = eu - fam['mouth'] * er
tr['mouth'] = [[round(c, 1) for c in px(.995, -.01)], [round(c, 1) for c in px((1 + mouth_end) / 2, -.03)],
               [round(c, 1) for c in px(mouth_end, -.045)]]
# hands: skin colour on or right next to the fish
ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
skin = ((ycc[..., 1] > 140) & (ycc[..., 1] < 175) & (ycc[..., 2] > 85) & (ycc[..., 2] < 125) & (ycc[..., 0] > 60)).astype(np.uint8)
skin &= cv2.dilate(mask, np.ones((9, 9), np.uint8))
skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
occ = []
cnts, _ = cv2.findContours(cv2.dilate(skin, np.ones((15, 15), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for c in (cnts if OVR.pop('hands', False) else []):
    if cv2.contourArea(c) > (L * .03) ** 2:
        occ.append(cv2.approxPolyDP(c, 3, True)[:, 0].tolist())
tr['occ'] = occ
tr['bg_tol'] = 0
if CREDIT:
    tr['credit'] = CREDIT
tr.update(OVR)
json.dump(tr, open(OUT, 'w'), indent=1)
print(KEY, 'SL px', round(L), 'tail at', 'left' if tail_end == 0 else 'right', 'stem ratio', round(min(r0, r1), 2), 'eye', ex, ey, 'hands', len(occ))

"""Turns one traced side photo into everything the Blender build needs (all lengths in standard lengths, SL):

  outline   body top/bottom along the body (u = 0 tail base .. 1 snout), fins cut away along their bases
  skin.jpg  the flank straightened between the body outlines (x = u, y = back -> belly), with the pectoral fin,
            hands etc. filled from neighbouring skin, and the photo's uneven lighting evened out
  nrm.jpg   detail normal map from the skin (scales, lateral line) plus the gill-cover, cheek and mouth edges
  fins.jpg / fins_a.jpg   the whole fish straightened (fins included) and the fin-only opacity
  eye.jpg   the real eye, cropped square around the pupil
  data.json outline, fin strips, pectoral outline, eye, head lines

Usage: python3 -I rectify.py <trace.json> <out dir>
"""
import json, os, sys
import numpy as np, cv2
from scipy.interpolate import PchipInterpolator

T = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
img = cv2.imread(T['photo'])[:, :, ::-1].astype(np.float32) / 255
H0, W0 = img.shape[:2]
mask = cv2.imread(T['mask'], 0) > 127
# dirt, grass and debris stuck to the fish (opt-in: 'specks': size in px): small blobs much darker or more
# saturated-off-colour than the skin around them are painted over from their surroundings
if T.get('specks'):
    k_ = int(T['specks']) | 1
    u8 = (img * 255).astype(np.uint8)
    g_ = cv2.cvtColor(u8, cv2.COLOR_RGB2GRAY).astype(np.float32)
    med = cv2.medianBlur(cv2.cvtColor(u8, cv2.COLOR_RGB2GRAY), k_ * 2 + 1).astype(np.float32)
    dark = ((med - g_) > float(T.get('speck_thr', 38))) & mask
    dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n_, lab_, st_, _ = cv2.connectedComponentsWithStats(dark)
    sp_ = np.zeros_like(dark)
    for i_ in range(1, n_):
        if st_[i_, cv2.CC_STAT_AREA] < k_ * k_ * 1.5 and max(st_[i_, 2], st_[i_, 3]) < k_ * 2.5:
            sp_[lab_ == i_] = 1
    sp_ = cv2.dilate(sp_, np.ones((5, 5), np.uint8))
    img = cv2.inpaint(u8, sp_ * 255, 5, cv2.INPAINT_TELEA).astype(np.float32) / 255
    print('specks removed', n_ - 1)
# cast shadows on the fish in the photo (a hand, the photographer): lifted to match the lit skin beside them, per colour
# channel, measured in a band along the shadow edge
for sh in T.get('shade', []):
    pm = np.zeros((H0, W0), np.uint8)
    cv2.fillPoly(pm, [np.array(sh['poly'], np.int32)], 255)
    near_in = cv2.erode(pm, np.ones((5, 5), np.uint8)) & ~cv2.erode(pm, np.ones((81, 81), np.uint8)) & np.where(mask, 255, 0).astype(np.uint8)
    near_out = cv2.dilate(pm, np.ones((81, 81), np.uint8)) & ~cv2.dilate(pm, np.ones((5, 5), np.uint8)) & np.where(mask, 255, 0).astype(np.uint8)
    gin, gout = img[near_in > 0], img[near_out > 0]
    if 'probe' in sh:  # explicit boxes [x0, y0, x1, y1] in shadow and in light
        (a0, b0_, a1, b1_), (c0, d0, c1, d1) = sh['probe']
        gin, gout = img[b0_:b1_, a0:a1].reshape(-1, 3), img[d0:d1, c0:c1].reshape(-1, 3)
    gain = np.clip(np.median(gout, 0) / np.maximum(np.median(gin, 0), 1e-3), 1, 2.5)
    if 'gain' in sh:  # cap: keep part of the natural darkening so the skin doesn't wash out
        gain = 1 + (gain - 1) * float(sh['gain'])
    soft = cv2.GaussianBlur(pm.astype(np.float32) / 255, (0, 0), float(sh.get('feather', 8)))[..., None]
    img = np.clip(img * (1 + (gain - 1) * soft), 0, 1)
    print('shade gain', np.round(gain, 2))

# ---------- midline: u = 1 at the snout, 0 at the tail base ----------
M = np.array(T['mid'], float)
if len(M) > 2:  # bent fish: smooth spline through the traced midline points
    from scipy.interpolate import splprep, splev
    tck, _ = splprep(M.T, s=len(M) * 30.0, k=min(3, len(M) - 1))
    M = np.array(splev(np.linspace(0, 1, 240), tck)).T
seg = np.diff(M, axis=0)
sl = np.linalg.norm(seg, axis=1)
L = sl.sum()  # standard length in pixels
cum = np.concatenate([[0], np.cumsum(sl)])


def mid(u):
    """point, unit direction toward the snout, unit 'up' normal (image coords) for u (array)."""
    u = np.atleast_1d(np.asarray(u, float))
    s = (1 - u) * L
    k = np.clip(np.searchsorted(cum, s, side='right') - 1, 0, len(sl) - 1)
    f = (s - cum[k]) / sl[k]
    p = M[k] + seg[k] * f[:, None]
    d = -seg[k] / sl[k][:, None]
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    flip = n[:, 1] > 0  # 'up' must point up in the photo
    n[flip] *= -1
    return p, d, n


def to_uv(pts):
    """photo pixel points -> (u, v) in SL (v up)."""
    us = np.linspace(-.5, 1.1, 6401)
    p, d, n = mid(us)
    out = []
    for q in np.atleast_2d(pts):
        i = np.argmin(np.linalg.norm(p - q, axis=1))
        out.append((us[i], float(np.dot(q - p[i], n[i]) / L)))
    return np.array(out)


def to_px(u, v):
    p, d, n = mid(u)
    return p + n * (np.asarray(v, float) * L)[:, None]


# ---------- raw silhouette extent along the normals ----------
NU = 1400
U = np.linspace(-.42, 1.04, NU)
P, D, N = mid(U)


def extent(sign, start=0.0):
    out = np.zeros(NU)
    steps = np.arange(0, int(.75 * L))
    for i in range(NU):
        q = P[i] + N[i] * sign * (steps[:, None] + start * L)
        x, y = np.round(q[:, 0]).astype(int), np.round(q[:, 1]).astype(int)
        ok = (x >= 0) & (x < W0) & (y >= 0) & (y < H0)
        inside = np.zeros(len(steps), bool)
        inside[ok] = mask[y[ok], x[ok]]
        # farthest point reached through the mask from the midline (gaps of a few pixels allowed)
        last, gap = -1, 0
        for k, v in enumerate(inside):
            if v:
                last, gap = k, 0
            else:
                gap += 1
                if gap > 5:
                    break
        out[i] = (last + 1) / L if last >= 0 else 0
    return out


top_raw, bot_raw = extent(1), extent(-1)
present = (top_raw + bot_raw) > .004
u_tail_end = float(U[present][0])

# ---------- body outline with the fins cut away ----------
top_body, bot_body = top_raw.copy(), bot_raw.copy()


def splice(arr, sign, span):
    a, b = to_uv([span['a']])[0], to_uv([span['b']])[0]
    ua, ub = sorted([a[0], b[0]])
    pts = [(a[0], sign * a[1]), (b[0], sign * b[1])] + [tuple(r * np.array([1, sign])) for r in to_uv(span.get('body', []))] if span.get('body') else [(a[0], sign * a[1]), (b[0], sign * b[1])]
    pts = sorted(pts)
    # tie the ends to the measured outline just outside the span
    def at(u):
        return float(np.interp(u, U, arr))
    xs = [ua - .02, ua - .006] + [p[0] for p in pts] + [ub + .006, ub + .02]
    ys = [at(ua - .02), at(ua - .006)] + [p[1] for p in pts] + [at(ub + .006), at(ub + .02)]
    o = np.argsort(xs)
    xs, ys = np.array(xs)[o], np.array(ys)[o]
    keep = np.concatenate([[True], np.diff(xs) > 1e-4])
    f = PchipInterpolator(xs[keep], ys[keep])
    sel = (U >= ua) & (U <= ub)
    arr[sel] = f(U[sel])
    return ua, ub


spans = []
for sp in T.get('top', []):
    spans.append(('top', sp, splice(top_body, 1, sp)))
for sp in T.get('bot', []):
    spans.append(('bot', sp, splice(bot_body, -1, sp)))
if T.get('head_bot'):
    hb = to_uv(T['head_bot'])
    hb = hb[np.argsort(hb[:, 0])]
    u0 = hb[0, 0]
    xs = np.concatenate([[u0 - .03, u0 - .012], hb[:, 0]])
    ys = np.concatenate([[np.interp(u0 - .03, U, bot_body), np.interp(u0 - .012, U, bot_body)], -hb[:, 1]])
    f = PchipInterpolator(xs, ys)
    sel = (U >= u0 - .012) & (U <= hb[-1, 0])
    bot_body[sel] = f(U[sel])
if T.get('head_top'):
    ht = to_uv(T['head_top'])
    ht = ht[np.argsort(ht[:, 0])]
    u0 = ht[0, 0]
    xs = np.concatenate([[u0 - .03, u0 - .012], ht[:, 0]])
    ys = np.concatenate([[np.interp(u0 - .03, U, top_body), np.interp(u0 - .012, U, top_body)], ht[:, 1]])
    f = PchipInterpolator(xs, ys)
    sel = (U >= u0 - .012) & (U <= ht[-1, 0])
    top_body[sel] = f(U[sel])
# smooth lightly (mask edges are a few pixels rough); keep the body between tail base and snout
k = cv2.getGaussianKernel(9, 2.0).ravel()
top_body = np.convolve(np.pad(top_body, 4, mode='edge'), k, 'valid')
bot_body = np.convolve(np.pad(bot_body, 4, mode='edge'), k, 'valid')
body = (U >= 0) & (U <= 1)

# ---------- skin: the flank straightened between the outlines ----------
SW, SH = 2048, 1024
us = (np.arange(SW) + .5) / SW
ts = (np.arange(SH) + .5) / SH
INS = float(T.get('inset', .004))  # sample the skin a little inside the silhouette (edge pixels hold background)
tb = np.interp(us, U, top_body) - INS
bb = np.interp(us, U, bot_body) - INS
p, d, n = mid(us)
v = tb[None, :] - ts[:, None] * (tb + bb)[None, :]  # SH x SW
mapx = (p[None, :, 0] + n[None, :, 0] * v * L).astype(np.float32)
mapy = (p[None, :, 1] + n[None, :, 1] * v * L).astype(np.float32)
skin = cv2.remap(img, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
mapx_s, mapy_s = mapx, mapy
# areas marked on the straightened skin (u, t fractions) instead of on the photo: converted to photo pixels
def uv2px(poly):
    return [[float(mapx[min(SH - 1, int(t_ * SH)), min(SW - 1, int(u_ * SW))]), float(mapy[min(SH - 1, int(t_ * SH)), min(SW - 1, int(u_ * SW))])] for u_, t_ in poly]
if T.get('pec_uv'):
    T['pec'] = uv2px(T['pec_uv'])
T['paint'] = T.get('paint', []) + [uv2px(q) for q in T.get('paint_uv', [])]
# what must be replaced: outside the silhouette (fin bases cut away, gaps), pectoral fin, occluders
hole = np.zeros((H0, W0), np.uint8)
for poly in [T.get('pec')] + T.get('occ', []) + T.get('paint', []) + [e['poly'] for e in T.get('extra', []) if e.get('hole')]:
    if poly:
        cv2.fillPoly(hole, [np.array(poly, np.int32)], 255)
hole = cv2.dilate(hole, np.ones((7, 7), np.uint8))
hole |= np.where(mask, 0, 255).astype(np.uint8)
holes = cv2.remap(hole, mapx, mapy, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=255) > 0
# texels near the back or belly edge that match the background colour (silhouette edge spill)
ring = cv2.dilate(mask.astype(np.uint8), np.ones((41, 41), np.uint8)).astype(bool) & ~cv2.dilate(mask.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
bgc = img[ring][::7]
_, _, cent = cv2.kmeans(bgc.astype(np.float32), 5, None, (cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-3), 2, cv2.KMEANS_PP_CENTERS)
dist = np.min(np.linalg.norm(skin[:, :, None, :] - cent[None, None], axis=-1), axis=-1)
near_edge = ((ts < .1) | (ts > .9))[:, None]
if float(T.get('bg_tol', .07)) > 0:
    holes |= near_edge & (dist < float(T.get('bg_tol', .07)))
holes = cv2.morphologyEx(holes.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)


def fill_holes(a, hm):
    """Fills each hole with a block of neighbouring skin shifted in one piece (so scales and markings stay
    coherent). Several shifts are tried (along the body either way, toward the back or belly) and the one whose
    source holds the fewest holes wins; the block is then feathered into its surroundings."""
    from scipy import ndimage
    a = a.copy()
    Hh, Wd = hm.shape
    lab, nlab = ndimage.label(hm)
    order = sorted(range(1, nlab + 1), key=lambda k: -(lab == k).sum())
    objs = ndimage.find_objects(lab)
    filled = hm.copy()
    for k in order:
        ys, xs = objs[k - 1]
        h, w = ys.stop - ys.start, xs.stop - xs.start
        jj, ii = np.nonzero(lab == k)
        cands = []
        for m in (1, 2):
            cands += [(0, -m * (w + 12)), (0, m * (w + 12)), (-m * (h + 6), 0), (m * (h + 6), 0)]
        best, bc = None, 1e9
        for dy, dx in cands:
            sj, si = jj + dy, ii + dx
            ok = (sj >= 0) & (sj < Hh) & (si >= 0) & (si < Wd)
            if ok.mean() < .98:
                continue
            bad = filled[np.clip(sj, 0, Hh - 1), np.clip(si, 0, Wd - 1)].mean()
            cost = bad + .02 * (abs(dy) / Hh * 4 + abs(dx) / Wd)  # prefer near, and along the body
            if (ys.start < Hh * .04 or ys.stop > Hh * .96) and dx != 0:
                cost += .5  # gaps along the back or belly edge: copy skin from just inside, not from along the body
            if cost < bc:
                best, bc = (dy, dx), cost
        if best is None:
            best = (0, -(w + 12)) if xs.start > w + 12 else (0, w + 12)
        sj, si = np.clip(jj + best[0], 0, Hh - 1), np.clip(ii + best[1], 0, Wd - 1)
        a[jj, ii] = a[sj, si]
        filled[jj, ii] = filled[sj, si]  # still bad if the source was bad (next pass of a smaller hole can't use it)
    return a


skin_raw = skin.copy()
pm = np.zeros((H0, W0), np.uint8)
for poly in T.get('paint', []):
    cv2.fillPoly(pm, [np.array(poly, np.int32)], 255)
painted = cv2.remap(pm, mapx_s, mapy_s, cv2.INTER_NEAREST) > 0
cv2.imwrite(os.path.join(OUT, 'valid.png'), np.where(holes & ~painted, 0, 255).astype(np.uint8))
skin = fill_holes(skin, holes)
feather = np.clip(cv2.GaussianBlur(cv2.dilate(holes.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32), (0, 0), 5), 0, 1)[..., None]
# match the filled patches' brightness and colour to the skin around them (low frequencies from the surroundings)
valid = (~holes).astype(np.float32)
sig = 36
def lowpass(sg):
    w_ = cv2.GaussianBlur(valid, (0, 0), sg)
    return cv2.GaussianBlur(skin_raw * valid[..., None], (0, 0), sg) / np.maximum(w_, 1e-4)[..., None], w_
lv1, w1 = lowpass(sig)
lv2, w2 = lowpass(sig * 3.5)
k_ = np.clip(w1 / .25, 0, 1)[..., None]
lowV = lv1 * k_ + lv2 * (1 - k_)
lowF = cv2.GaussianBlur(skin, (0, 0), sig) * k_ + cv2.GaussianBlur(skin, (0, 0), sig * 3.5) * (1 - k_)
skin = np.where(holes[..., None], np.clip(skin - lowF + lowV, 0, 1), skin)
skin = np.where(holes[..., None], skin, skin_raw * (1 - feather * .6) + cv2.GaussianBlur(skin, (0, 0), 2) * feather * .6)
# even out the lighting: keep the back-to-belly shading (averaged along the body) but remove patches of glare and
# shadow along it
lum = skin @ np.array([.3, .59, .11], np.float32)
low = cv2.GaussianBlur(lum, (0, 0), SH * .06)
target = np.repeat(np.median(low[:, int(SW * .08):int(SW * .9)], axis=1, keepdims=True), SW, 1)
target = cv2.GaussianBlur(target, (0, 0), 8)
gain = np.clip(target / np.maximum(low, 1e-3), .6, 1.7) ** float(T.get('delight', .7))
skin = np.clip(skin * gain[..., None], 0, 1)
def grade(a):
    """colour correction for washed-out or colour-cast photos: {'gain': [r, g, b], 'sat': x, 'contrast': x}"""
    G = T.get('grade')
    if not G:
        return a
    a = a * np.array(G.get('gain', [1, 1, 1]), np.float32)
    lum = a @ np.array([.3, .59, .11], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * float(G.get('sat', 1))
    m_ = float(np.median(lum))
    a = m_ + (a - m_) * float(G.get('contrast', 1))
    return np.clip(a, 0, 1)


skin = grade(skin)
cv2.imwrite(os.path.join(OUT, 'skin.jpg'), (skin[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- detail normal map ----------
lum = skin @ np.array([.3, .59, .11], np.float32)
hp = cv2.GaussianBlur(lum, (0, 0), 1.0) - cv2.GaussianBlur(lum, (0, 0), 7)
hp = hp / (np.percentile(np.abs(hp), 98) + 1e-6)
height = np.clip(hp, -1.5, 1.5) * .6
# head edges: gill cover, cheek bone, mouth (raised flap edges with a groove in front)
edges = np.zeros((SH, SW), np.float32)


def draw_line(poly, depth, width):
    if not poly:
        return
    q = to_uv(poly)
    pts = []
    for u_, v_ in q:
        dd_ = np.interp(u_, U, top_body) + np.interp(u_, U, bot_body)
        if dd_ < 1e-3:
            continue
        t_ = (np.interp(u_, U, top_body) - v_) / dd_
        pts.append((u_ * SW, t_ * SH))
    im = np.zeros((SH, SW), np.float32)
    cv2.polylines(im, [np.array(pts, np.int32)], False, 1.0, width, cv2.LINE_AA)
    return im * depth


for key, dep, wid in (('gill', 1.0, 5), ('preop', .6, 4), ('mouth', .8, 4)):
    e = draw_line(T.get(key), dep, wid)
    if e is not None:
        edges += e
height -= cv2.GaussianBlur(edges, (0, 0), 2.0) * 1.6
gy, gx = np.gradient(cv2.GaussianBlur(height, (0, 0), .7))
strength = float(T.get('nrm', 2.2))
nx, ny, nz = -gx * strength, gy * strength, np.ones_like(gx)
nl = np.sqrt(nx * nx + ny * ny + nz * nz)
nrm = np.stack([nx / nl, ny / nl, nz / nl], -1) * .5 + .5
cv2.imwrite(os.path.join(OUT, 'nrm.jpg'), (nrm[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])

# ---------- whole fish straightened (fins) ----------
u_lo, u_hi = u_tail_end - .015, 1.03
v_hi = float(top_raw.max()) + .02
v_lo = -float(bot_raw.max()) - .02
FW, FH = 2048, 1024
fu = u_lo + (np.arange(FW) + .5) / FW * (u_hi - u_lo)
fv = v_hi - (np.arange(FH) + .5) / FH * (v_hi - v_lo)
p, d, n = mid(fu)
mapx = (p[None, :, 0] + n[None, :, 0] * fv[:, None] * L).astype(np.float32)
mapy = (p[None, :, 1] + n[None, :, 1] * fv[:, None] * L).astype(np.float32)
full = cv2.remap(img, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
fmask = cv2.remap(mask.astype(np.float32), mapx, mapy, cv2.INTER_LINEAR) > .5
tbf = np.interp(fu, U, top_body)
bbf = np.interp(fu, U, bot_body)
inset = .006
in_body = (fv[:, None] < tbf[None, :] - inset) & (fv[:, None] > -bbf[None, :] + inset) & (fu[None, :] > .012)
fin_a = (fmask & ~in_body).astype(np.float32)
pec = np.zeros((H0, W0), np.uint8)
if T.get('pec'):
    cv2.fillPoly(pec, [np.array(T['pec'], np.int32)], 255)
pec_f = cv2.remap(pec, mapx, mapy, cv2.INTER_LINEAR) > 127
fin_a = np.maximum(fin_a, pec_f * float(T.get('pec_alpha', .9)))
fin_a = cv2.GaussianBlur(fin_a, (0, 0), 1.0)
# bleed fin colours outward so the soft edges don't pick up background
src = (fin_a > .5).astype(np.uint8)
bleed = full.copy()
known = src.astype(bool)
for _ in range(24):
    dil = cv2.dilate(bleed * known[..., None], np.ones((3, 3), np.float32))
    cnt = cv2.dilate(known.astype(np.float32), np.ones((3, 3), np.float32))
    s3 = cv2.blur(bleed * known[..., None], (3, 3)) * 9
    c3 = cv2.blur(known.astype(np.float32), (3, 3)) * 9
    new = (~known) & (c3 > 0)
    bleed[new] = s3[new] / c3[new][:, None]
    known = known | new
full = np.where((fin_a > .5)[..., None], full, bleed)
# lighten the fin texture's lighting the same gentle way
full = grade(full)
cv2.imwrite(os.path.join(OUT, 'fins.jpg'), (np.clip(full, 0, 1)[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
cv2.imwrite(os.path.join(OUT, 'fins_a.jpg'), (np.clip(fin_a, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
# fin normal map (rays)
fl = full @ np.array([.3, .59, .11], np.float32)
fh = cv2.GaussianBlur(fl, (0, 0), .8) - cv2.GaussianBlur(fl, (0, 0), 5)
fh = np.clip(fh / (np.percentile(np.abs(fh), 98) + 1e-6), -1.5, 1.5) * .5
gy, gx = np.gradient(fh)
nx, ny, nz = -gx * 2, gy * 2, np.ones_like(gx)
nl = np.sqrt(nx * nx + ny * ny + nz * nz)
cv2.imwrite(os.path.join(OUT, 'fins_n.jpg'), ((np.stack([nx / nl, ny / nl, nz / nl], -1) * .5 + .5)[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- fin strips (columns from the body edge to the fin's outer edge) ----------


def strip(u0, u1, side, inner_off=.014, ncol=48):
    cols = []
    for u_ in np.linspace(u0, u1, ncol):
        if side == 'top':
            inner = float(np.interp(u_, U, top_body)) - inner_off
            outer = max(float(np.interp(u_, U, top_raw)), inner + inner_off + .002) + .012
            cols.append((float(u_), inner, outer))
        else:
            inner = -float(np.interp(u_, U, bot_body)) + inner_off
            outer = min(-float(np.interp(u_, U, bot_raw)), inner - inner_off - .002) - .012
            cols.append((float(u_), inner, outer))
    return cols


fins = []
for side, sp, (ua, ub) in spans:
    if not sp.get('fin'):
        continue
    fins.append({'k': sp['fin'], 'side': side, 'cols': strip(ua - .01, ub + .004, side),
                 'base': [float(x) for x in sorted(to_uv([[sp['base'][0], sp['a'][1]], [sp['base'][1], sp['b'][1]]])[:, 0])]})
# caudal: from its tip to just inside the body
cols = []
for u_ in np.linspace(u_tail_end - .006, .04, 56):
    t_ = float(np.interp(u_, U, top_raw)) + .012
    b_ = -float(np.interp(u_, U, bot_raw)) - .012
    if u_ > 0:
        t_ = min(t_, float(np.interp(u_, U, top_body)) - .004)
        b_ = max(b_, -float(np.interp(u_, U, bot_body)) + .004)
    cols.append((float(u_), b_, t_))
fins.append({'k': 'c', 'side': 'mid', 'cols': cols})
pec_uv = to_uv(T['pec']).tolist() if T.get('pec') else None


def fin_patch(name, poly, src=None, spines=0, alpha=.92):
    """Own texture for a fin drawn as a polygon: the photo inside it (or another fin's pixels from 'src', warped
    onto it when the fin itself is hidden or folded), with the polygon as opacity; returns the outline in SL."""
    poly = np.array(poly, np.float32)
    x0, y0 = poly.min(0); x1, y1 = poly.max(0)
    PW, PH = 512, 256
    dst = np.float32([[0, 0], [PW, 0], [PW, PH]])
    if src is None:
        A = cv2.getAffineTransform(np.float32([[x0, y0], [x1, y0], [x1, y1]]), dst)
        col = cv2.warpAffine(img, A, (PW, PH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    else:
        sp = np.array(src, np.float32)
        sx0, sy0 = sp.min(0); sx1, sy1 = sp.max(0)
        # src corners in the same orientation as the fin (both point toward the tail)
        A = cv2.getAffineTransform(np.float32([[sx0, sy0], [sx1, sy0], [sx1, sy1]]), dst)
        col = cv2.warpAffine(img, A, (PW, PH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    q = (poly - [x0, y0]) / [max(x1 - x0, 1), max(y1 - y0, 1)] * [PW, PH]
    al = np.zeros((PH, PW), np.float32)
    cv2.fillPoly(al, [np.round(q).astype(np.int32)], 1.0)
    if spines:
        # membrane dips between the spine tips along the top edge
        top = np.array([np.argmax(al[:, i] > .5) if al[:, i].any() else PH for i in range(PW)])
        xs_ = np.linspace(0, PW, spines + 1)
        for i in range(PW):
            ph_ = (i - xs_[0]) / (PW / spines) % 1
            dip = (np.sin(ph_ * np.pi)) ** .7 * .28 * (PH - top[i]) * (1 if 0 < i < PW - 1 else 0)
            al[top[i]:top[i] + int(dip), i] = 0
        # the spines themselves: thin dark lines kept fully opaque
        for xx in xs_[:-1] + PW / spines * .02:
            xi = int(min(PW - 1, xx))
            al[top[xi]:, max(0, xi - 1):xi + 2] = np.maximum(al[top[xi]:, max(0, xi - 1):xi + 2], (al[top[xi]:, max(0, xi - 1):xi + 2] >= 0) * 1.0) * (al[:, max(0, xi - 1):xi + 2].sum(0) > 0)[None, :]
    al = cv2.GaussianBlur(al, (0, 0), 1.2) * alpha
    cv2.imwrite(os.path.join(OUT, name + '.jpg'), (np.clip(col, 0, 1)[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(os.path.join(OUT, name + '_a.jpg'), (np.clip(al, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
    uv = to_uv(poly)
    return {'name': name, 'poly': uv.tolist(), 'tex': ((poly - [x0, y0]) / [max(x1 - x0, 1), max(y1 - y0, 1)]).tolist()}


patches = []
if T.get('pec'):
    patches.append(dict(fin_patch('pec', T['pec'], T.get('pec_src')), k='pec'))
for i, e in enumerate(T.get('extra', [])):
    patches.append(dict(fin_patch(f"{e['k']}{i}", e['poly'], e.get('src'), e.get('spines', 0)), k=e['k']))

# ---------- eye ----------
ex, ey, er = T['eye']
eu, ev = to_uv([[ex, ey]])[0]
c = int(er * 1.25)
if T.get('eye_tex') != 'game':
    crop = img[int(ey) - c:int(ey) + c, int(ex) - c:int(ex) + c]
    crop = np.clip(cv2.resize(crop, (256, 256), interpolation=cv2.INTER_CUBIC), 0, 1)
    _, de, _ = mid([eu])
    if de[0, 0] < 0:  # snout to the left in the photo: flip so the snout side is on the right, as on the skin
        crop = crop[:, ::-1]
    ang = np.degrees(np.arctan2(-de[0, 1], abs(de[0, 0])))  # level the body axis
    crop = cv2.warpAffine(crop, cv2.getRotationMatrix2D((128, 128), -ang if de[0, 0] > 0 else ang, 1), (256, 256), borderMode=cv2.BORDER_REFLECT)
    cv2.imwrite(os.path.join(OUT, 'eye.jpg'), (crop[:, :, ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])


def lines(key):
    return to_uv(T[key]).tolist() if T.get(key) else None


data = {'L_px': float(L), 'u': U.tolist(), 'top': top_body.tolist(), 'bot': bot_body.tolist(),
        'top_raw': top_raw.tolist(), 'bot_raw': bot_raw.tolist(), 'u_tail_end': u_tail_end,
        'fin_uv': {'u0': u_lo, 'u1': u_hi, 'v0': v_lo, 'v1': v_hi}, 'fins': fins, 'pec': pec_uv, 'patches': patches,
        'eye': {'u': float(eu), 'v': float(ev), 'r': er / L, 'crop_r': c / L, 'tex': T.get('eye_tex', 'photo')},
        'gill': lines('gill'), 'preop': lines('preop'), 'mouth': lines('mouth'), 'credit': T.get('credit')}
json.dump(data, open(os.path.join(OUT, 'data.json'), 'w'))
# check image: outline over the straightened fish
chk = (np.clip(full, 0, 1) * 255).astype(np.uint8)[:, :, ::-1].copy()
def fy(v_):
    return int((v_hi - v_) / (v_hi - v_lo) * FH)
def fx(u_):
    return int((u_ - u_lo) / (u_hi - u_lo) * FW)
for arr, s_, col in ((top_body, 1, (0, 255, 255)), (bot_body, -1, (0, 255, 255)), (top_raw, 1, (255, 0, 255)), (bot_raw, -1, (255, 0, 255))):
    pts = np.array([(fx(u_), fy(s_ * a_)) for u_, a_ in zip(U, arr) if u_ >= u_lo], np.int32)
    cv2.polylines(chk, [pts], False, col, 2)
for f in fins:
    for u_, a_, b_ in f['cols'][::4]:
        cv2.line(chk, (fx(u_), fy(a_)), (fx(u_), fy(b_)), (0, 160, 255), 1)
if pec_uv:
    cv2.polylines(chk, [np.array([(fx(a), fy(b)) for a, b in pec_uv], np.int32)], True, (0, 255, 0), 2)
cv2.circle(chk, (fx(eu), fy(ev)), int(er / L / (u_hi - u_lo) * FW), (0, 0, 255), 2)
cv2.imwrite(os.path.join(OUT, 'check.jpg'), cv2.resize(chk, (1400, 700)), [cv2.IMWRITE_JPEG_QUALITY, 85])
print('SL px', round(L), 'tail end u', round(u_tail_end, 3), 'max depth', round(float((top_body + bot_body)[body].max()), 3))

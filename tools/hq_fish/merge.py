"""Joins two rectified photos of one species into one: the rear (body, tail, fins) from one and the front (head,
pectoral fin, eye) from another, cross-faded along the body. Both are already in standard-length units, so the
outlines line up; the front photo's colours are matched to the rear's in the overlap.

Usage: python3 -I merge.py <rear dir> <front dir> <out dir> <u0> <u1> [bottom u0 u1]
  u0..u1   where the skin and the back outline fade from rear to front
  bottom   separate fade window for the belly outline (when the front photo's belly is hidden)
"""
import json, os, shutil, sys
import numpy as np, cv2

R, F, OUT = sys.argv[1:4]
u0, u1 = float(sys.argv[4]), float(sys.argv[5])
b0, b1 = (float(sys.argv[6]), float(sys.argv[7])) if len(sys.argv) > 7 else (u0, u1)
os.makedirs(OUT, exist_ok=True)
dr, df = json.load(open(os.path.join(R, 'data.json'))), json.load(open(os.path.join(F, 'data.json')))
U = np.array(dr['u'])


def ramp(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


wt, wb = ramp(U, u0, u1), ramp(U, b0, b1)
out = dict(dr)
out['top'] = (np.array(dr['top']) * (1 - wt) + np.array(df['top']) * wt).tolist()
out['bot'] = (np.array(dr['bot']) * (1 - wb) + np.array(df['bot']) * wb).tolist()
# textures
sr = cv2.imread(os.path.join(R, 'skin.jpg')).astype(np.float32) / 255
sf = cv2.imread(os.path.join(F, 'skin.jpg')).astype(np.float32) / 255
W = sr.shape[1]
us = (np.arange(W) + .5) / W
band = (us > u0 - .03) & (us < u1 + .03)
rows = slice(int(.08 * sr.shape[0]), int(.92 * sr.shape[0]))
for c in range(3):  # match the front photo's colour statistics to the rear's in the overlap
    a, b = sr[rows, band, c], sf[rows, band, c]
    sf[..., c] = (sf[..., c] - b.mean()) * (a.std() / max(b.std(), 1e-4)) + a.mean()
vf = cv2.imread(os.path.join(F, 'valid.png'), 0).astype(np.float32) / 255
vf = cv2.GaussianBlur(cv2.erode(vf, np.ones((25, 25), np.uint8)), (0, 0), 10)
tt = ((np.arange(sr.shape[0]) + .5) / sr.shape[0])[:, None]
w = np.maximum(ramp(us, u0, u1)[None, :] * (tt < .5) + ramp(us, b0, b1)[None, :] * (tt >= .5), 0)
w = cv2.GaussianBlur(w.astype(np.float32), (0, 0), 6)
w = (w * vf)[..., None]
skin = np.clip(sr * (1 - w) + sf * w, 0, 1)
cv2.imwrite(os.path.join(OUT, 'skin.jpg'), (skin * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
nr = cv2.imread(os.path.join(R, 'nrm.jpg')).astype(np.float32)
nf = cv2.imread(os.path.join(F, 'nrm.jpg')).astype(np.float32)
cv2.imwrite(os.path.join(OUT, 'nrm.jpg'), (nr * (1 - w) + nf * w).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
# fins from the rear photo; pectoral patch, eye and head lines from the front photo
for f in ('fins.jpg', 'fins_a.jpg', 'fins_n.jpg'):
    shutil.copy(os.path.join(R, f), os.path.join(OUT, f))
pats = [p for p in dr.get('patches', []) if p['k'] != 'pec']
for p in df.get('patches', []):
    if p['k'] == 'pec':
        pats.append(p)
for p in pats:
    src = F if p in df.get('patches', []) else R
    for ext in ('.jpg', '_a.jpg'):
        im = cv2.imread(os.path.join(src, p['name'] + ext))
        cv2.imwrite(os.path.join(OUT, p['name'] + ext), im)
out['patches'] = pats
if os.path.exists(os.path.join(F, 'eye.jpg')):
    shutil.copy(os.path.join(F, 'eye.jpg'), os.path.join(OUT, 'eye.jpg'))
out['eye'] = df['eye']
for k in ('gill', 'preop', 'mouth'):
    out[k] = df[k]
out['credit'] = [dr['credit'], df['credit']]
json.dump(out, open(os.path.join(OUT, 'data.json'), 'w'))
cv2.imwrite(os.path.join(OUT, 'check.jpg'), cv2.resize((skin * 255).astype(np.uint8), (1400, 700)))
print('merged', R, '+', F)

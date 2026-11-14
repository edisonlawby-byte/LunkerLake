"""Ranks candidate photos of one species for use as a skin source, so only the best few need looking at.
Good: one fish lying flat and side-on, whole fish in frame, straight, horizontal, little skin-coloured area (hands),
reasonably large in the picture, sharp. Writes a contact sheet of the top N with scores.
python3 -I score.py <key> <cand dir> <out.jpg> [N] [length/depth with tail]"""
import json, sys, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

KEY, CD, OUT = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
LD = float(sys.argv[5]) if len(sys.argv) > 5 else 3.6  # expected total length / body depth in a side view
meta = json.load(open(os.path.join(CD, f'{KEY}_meta.json')))
res = []
for i, m in enumerate(meta):
    p = os.path.join(CD, m['file'])
    img = cv2.imread(p)
    if img is None:
        continue
    h0, w0 = img.shape[:2]
    s = 480 / max(h0, w0)
    sm = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    H, W = sm.shape[:2]
    mask = np.zeros((H, W), np.uint8)
    try:
        cv2.grabCut(sm, mask, (int(W * .03), int(H * .03), int(W * .94), int(H * .94)), np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        continue
    fg = ((mask == 1) | (mask == 3)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    if n < 2:
        continue
    k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    fg = (lab == k).astype(np.uint8)
    area = fg.mean()
    cnts, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (cx, cy), (rw, rh), ang = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
    L, D = max(rw, rh), max(1, min(rw, rh))
    tilt = abs(((ang if rw >= rh else ang + 90) + 90) % 180 - 90)
    elong = L / D
    # skin-coloured pixels (hands) near the fish
    ycc = cv2.cvtColor(sm, cv2.COLOR_BGR2YCrCb)
    skin = ((ycc[..., 1] > 140) & (ycc[..., 1] < 175) & (ycc[..., 2] > 85) & (ycc[..., 2] < 125) & (ycc[..., 0] > 60)).astype(np.uint8)
    near = cv2.dilate(fg, np.ones((15, 15), np.uint8))
    hand = (skin & near).sum() / max(1, fg.sum())
    border = (fg[0].mean() + fg[-1].mean() + fg[:, 0].mean() + fg[:, -1].mean())
    sharp = cv2.Laplacian(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), cv2.CV_64F)[fg > 0].var() if fg.sum() else 0
    score = (1.0
             - 2.5 * abs(np.log(elong / LD))          # side-on, right proportions
             - .03 * tilt                              # horizontal
             - 3 * max(0, hand - .02)                  # hands
             - 4 * border                              # cut off at the frame
             - 2 * max(0, .12 - area) - 1.5 * max(0, area - .6)
             + .15 * min(np.log1p(sharp) / 6, 1)
             + .3 * min(max(w0, h0) / 2000, 1))
    res.append((score, i, dict(elong=round(elong, 2), tilt=round(tilt), hand=round(hand, 3), area=round(area, 2), lic=m['license'])))
res.sort(reverse=True)
json.dump([{'i': i, 'score': round(s, 3), **d} for s, i, d in res], open(OUT.replace('.jpg', '.json'), 'w'), indent=0)
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
TW, TH, C = 400, 270, 4
S = Image.new('RGB', (TW * C, TH * ((min(N, len(res)) + C - 1) // C)), (20, 20, 20))
d = ImageDraw.Draw(S)
for k, (sc, i, dd) in enumerate(res[:N]):
    im = Image.open(os.path.join(CD, meta[i]['file'])).convert('RGB')
    im.thumbnail((TW - 4, TH - 4))
    X, Y = (k % C) * TW, (k // C) * TH
    S.paste(im, (X + 2, Y + 2))
    d.rectangle([X, Y, X + 150, Y + 26], fill=(0, 0, 0))
    d.text((X + 4, Y + 2), f"#{i}  {sc:.2f}", font=f, fill=(255, 220, 80))
S.save(OUT, quality=82)
print(KEY, len(meta), 'photos; top:', [(i, round(s, 2)) for s, i, _ in res[:N]])

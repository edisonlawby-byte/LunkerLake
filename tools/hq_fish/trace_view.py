"""Draws trace JSONs over their photos (mask outline, midline, fin spans, eye, pectoral, head lines), several per image.
python3 -I trace_view.py out.jpg trace1.json trace2.json ..."""
import sys, json, cv2, numpy as np
tiles = []
for p in sys.argv[2:]:
    T = json.load(open(p)); im = cv2.imread(T['photo']); m = cv2.imread(T['mask'], 0)
    cnt, _ = cv2.findContours((m > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(im, cnt, -1, (0, 255, 255), 3)
    pl = lambda pts, col, closed=False: cv2.polylines(im, [np.array(pts, np.int32)], closed, col, 4)
    pl(T['mid'], (255, 0, 255))
    for sp in T.get('top', []) + T.get('bot', []):
        for k in ('a', 'b'):
            cv2.circle(im, tuple(int(v) for v in sp[k]), 12, (0, 0, 255) if k == 'a' else (255, 0, 0), -1)
    cv2.circle(im, tuple(int(v) for v in T['eye'][:2]), int(T['eye'][2]), (0, 255, 0), 4)
    pl(T['pec'], (0, 255, 0), True)
    for k, col in (('gill', (255, 255, 0)), ('preop', (255, 200, 0)), ('mouth', (0, 128, 255))):
        if T.get(k): pl(T[k], col)
    for o in T.get('occ', []): pl(o, (0, 0, 255), True)
    s = 760 / im.shape[1]; tiles.append(cv2.resize(im, None, fx=s, fy=s))
    cv2.putText(tiles[-1], p.split('/')[-1], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
W = 760 * 2; rows = []
for i in range(0, len(tiles), 2):
    a = tiles[i]; b = tiles[i + 1] if i + 1 < len(tiles) else np.zeros_like(a)
    h = max(a.shape[0], b.shape[0]); pad = lambda x: cv2.copyMakeBorder(x, 0, h - x.shape[0], 0, 0, cv2.BORDER_CONSTANT)
    rows.append(np.hstack([pad(a), pad(b)]))
cv2.imwrite(sys.argv[1], np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])

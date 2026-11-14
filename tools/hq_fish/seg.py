"""Fish silhouette from a side photo with OpenCV GrabCut (rectangle start, optional polygons forced to background
or foreground), cleaned to the largest blob. python3 -I seg.py <img> <out mask png> x0,y0,x1,y1 [spec.json]"""
import sys, json
import numpy as np, cv2
img = cv2.imread(sys.argv[1]); out = sys.argv[2]
x0, y0, x1, y1 = map(int, sys.argv[3].split(','))
spec = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
S = .5  # work at half resolution
sm = cv2.resize(img, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
mask = np.zeros(sm.shape[:2], np.uint8)
bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
cv2.grabCut(sm, mask, (int(x0 * S), int(y0 * S), int((x1 - x0) * S), int((y1 - y0) * S)), bg, fg, 6, cv2.GC_INIT_WITH_RECT)
def poly(key, val):
    for p in spec.get(key, []):
        cv2.fillPoly(mask, [np.array(p, np.float32).__mul__(S).astype(np.int32)], val)
if spec:
    poly('bg', cv2.GC_BGD); poly('fg', cv2.GC_FGD); poly('pfg', cv2.GC_PR_FGD)
    cv2.grabCut(sm, mask, None, bg, fg, 4, cv2.GC_INIT_WITH_MASK)
m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]); m = np.where(lab == k, 255, 0).astype(np.uint8)
# fill holes
inv = cv2.bitwise_not(m); n, lab, st, _ = cv2.connectedComponentsWithStats(inv)
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] < 4000: m[lab == i] = 255
m = cv2.resize(m, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
m = np.where(m > 127, 255, 0).astype(np.uint8)
cv2.imwrite(out, m)
ov = img.copy(); ov[m == 0] = (ov[m == 0] * .3).astype(np.uint8)
cnt, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(ov, cnt, -1, (0, 255, 255), 3)
cv2.imwrite(out.replace('.png', '_ov.jpg'), cv2.resize(ov, None, fx=.6, fy=.6), [cv2.IMWRITE_JPEG_QUALITY, 85])
print('mask', out, int((m > 0).sum()))

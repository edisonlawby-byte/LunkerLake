"""HQ fish on a 3D SCAN's own shape (for species whose scan already has a better body than the photo trace gives):
the rectified photo (rectify.py output: whole fish straightened, fins included) is projected onto the scan from the
side, matching the scan's body top/bottom to the photo's body outline slice by slice, so markings land in the right
place even though the scan and the photo fish differ a little in shape. The eye is the scan's eyeball wearing the
round iris made by hq_fish.py (run `hq_fish.py build <sp>` first for the atlas).

Usage: python3 scan_hq.py <scan.glb> <body object> <eye object> <sp> <build dir>
Writes <build dir>/hq/<sp>.glb (body_<sp>, fins_<sp> (empty), eye_<sp>) and <sp>_skin.jpg / <sp>_nrm.jpg.
"""
import bpy, sys, os, json, math
import numpy as np, cv2

SCAN, BODY, EYE, SP, BUILD = sys.argv[1:6]
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'out', SP, 'data.json')))
U = np.array(D['u']); TOP = np.array(D['top']); BOT = np.array(D['bot']); FU = D['fin_uv']
HQ = os.path.join(BUILD, 'hq')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SCAN)
body = bpy.data.objects[BODY]; eye = bpy.data.objects[EYE]
for o in (body, eye):
    o.data.transform(o.matrix_world); o.matrix_world.identity(); o.parent = None
me = body.data
co = np.array([v.co[:] for v in me.vertices])
x, lat, z = co[:, 0], co[:, 1], co[:, 2]
# scan body top/bottom per slice from the flanks (thin fins sit near the midline and are ignored)
NB = 80
edges = np.linspace(x.min(), x.max(), NB + 1)
st, sb = np.full(NB, np.nan), np.full(NB, np.nan)
for b in range(NB):
    m = (x >= edges[b]) & (x <= edges[b + 1])
    if m.sum() < 8:
        continue
    w = np.abs(lat[m]).max()
    fl = m & (np.abs(lat) > .35 * w)
    if fl.sum() < 4:
        continue
    st[b], sb[b] = z[fl].max(), z[fl].min()
idx = np.arange(NB); ok = ~np.isnan(st)
st = np.interp(idx, idx[ok], st[ok]); sb = np.interp(idx, idx[ok], sb[ok])
k = np.ones(5) / 5
st = np.convolve(np.pad(st, 2, mode='edge'), k, 'valid'); sb = np.convolve(np.pad(sb, 2, mode='edge'), k, 'valid')
cx = (edges[:-1] + edges[1:]) / 2
u = x + .5
s_top, s_bot = np.interp(x, cx, st), np.interp(x, cx, sb)
t = (s_top - z) / np.maximum(s_top - s_bot, 1e-4)           # 0 at the scan's back, 1 at its belly (fins beyond)
p_top, p_bot = np.interp(u, U, TOP), np.interp(u, U, BOT)  # photo body outline (SL, v up)
v = p_top - t * (p_top + p_bot)
uvx = (u - FU['u0']) / (FU['u1'] - FU['u0'])
uvy = 1 - (FU['v1'] - v) / (FU['v1'] - FU['v0'])
ul = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name='UVMap')
for p in me.polygons:
    for li in p.loop_indices:
        vi = me.loops[li].vertex_index
        ul.data[li].uv = (float(np.clip(uvx[vi], .01, .99)), float(np.clip(uvy[vi], .01, .99)))
# eye: the scan eyeball's own disc coordinates -> the iris in the atlas (bottom-middle tile)
el = eye.data.uv_layers[0]
for li in range(len(el.data)):
    a, b = el.data[li].uv
    lx, ly = (a - .5) * 2, (b - .5) * 2
    el.data[li].uv = ((640 + lx * 128 * .97) / 1024, 1 - (896 - ly * 128 * .97) / 1024)
# fins: the scan has its fins in the body mesh; the game expects a fins mesh, so a single invisible triangle
fme = bpy.data.meshes.new('fins_' + SP)
fme.from_pydata([(0, 0, 0), (1e-4, 0, 0), (0, 1e-4, 0)], [], [(0, 1, 2)])
fu = fme.uv_layers.new(name='UVMap')
for d in fu.data:
    d.uv = (.95, .03)  # fully transparent corner of the atlas
fins = bpy.data.objects.new('fins_' + SP, fme); bpy.context.scene.collection.objects.link(fins)
body.name = body.data.name = 'body_' + SP
eye.name = eye.data.name = 'eye_' + SP
# skin = the straightened whole-fish photo; normal map from its fine detail (scales, fin rays)
full = cv2.imread(os.path.join(HERE, 'out', SP, 'fins.jpg'))
# where the scan reaches past the photo fish (bigger fins, tail), the photo has background: fill those parts with
# the nearest fish colour (smeared outward), so fins never show streaks of ground or sky
fa = cv2.imread(os.path.join(HERE, 'out', SP, 'fins_a.jpg'), 0).astype(np.float32) / 255
FH, FW = full.shape[:2]
fu_ = FU['u0'] + (np.arange(FW) + .5) / FW * (FU['u1'] - FU['u0'])
fv_ = FU['v1'] - (np.arange(FH) + .5) / FH * (FU['v1'] - FU['v0'])
inb = (fv_[:, None] < np.interp(fu_, U, TOP)[None, :]) & (fv_[:, None] > -np.interp(fu_, U, BOT)[None, :]) & (fu_[None, :] > 0)
sat = cv2.cvtColor(full, cv2.COLOR_BGR2HSV)[..., 1]
known = (inb | ((fa > .5) & (sat > int(os.environ.get('FIN_SAT', 45))))).astype(np.uint8)  # grey backdrop is not fin
known = cv2.erode(known, np.ones((5, 5), np.uint8))
# fill = smoothly spread colours of the known fish pixels only (normalised blur), so nothing comes from the background
kf = known.astype(np.float32)
num = sum(cv2.GaussianBlur(full.astype(np.float32) * kf[..., None], (0, 0), sg) for sg in (20, 80))
den = sum(cv2.GaussianBlur(kf, (0, 0), sg) for sg in (20, 80))[..., None]
fill = num / np.maximum(den, 1e-4)
fill[den[..., 0] < 1e-3] = np.median(full[known > 0], 0)
fill = (fill * .85).astype(np.uint8)  # fins read a little darker/translucent
w_ = cv2.GaussianBlur(known.astype(np.float32), (0, 0), 2)[..., None]
full = (full * w_ + fill * (1 - w_)).astype(np.uint8)
# the flank itself comes from the cleaned skin (fins, hands and the photo's eye painted out by rectify.py)
skin = cv2.imread(os.path.join(HERE, 'out', SP, 'skin.jpg'))
SH_, SW_ = skin.shape[:2]
tp_, bt_ = np.interp(fu_, U, TOP)[None, :], np.interp(fu_, U, BOT)[None, :]
tt_ = (tp_ - fv_[:, None]) / np.maximum(tp_ + bt_, 1e-4)
mx = np.broadcast_to((np.clip(fu_, 0, .9995) * SW_)[None, :], tt_.shape).astype(np.float32)
my = (np.clip(tt_, 0, .9995) * SH_).astype(np.float32)
flank = cv2.remap(skin, mx, my, cv2.INTER_LINEAR)
wb = cv2.GaussianBlur((inb & (tt_ > .03) & (tt_ < .97)).astype(np.float32), (0, 0), 3)[..., None]
full = (full * (1 - wb) + flank * wb).astype(np.uint8)
cv2.imwrite(os.path.join(HQ, f'{SP}_skin.jpg'), full, [cv2.IMWRITE_JPEG_QUALITY, 88])
g = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
h = cv2.GaussianBlur(g, (0, 0), 1) - cv2.GaussianBlur(g, (0, 0), 6)
h = np.clip(h / (np.percentile(np.abs(h), 98) + 1e-6), -1.5, 1.5) * .5
gy, gx = np.gradient(h)
nx, ny, nz = -gx * 2.2, gy * 2.2, np.ones_like(gx)
nl = np.sqrt(nx * nx + ny * ny + nz * nz)
cv2.imwrite(os.path.join(HQ, f'{SP}_nrm.jpg'), ((np.stack([nz / nl, ny / nl, nx / nl], -1) * .5 + .5) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
for o in bpy.context.scene.objects:
    o.select_set(o in (body, eye, fins))
bpy.ops.export_scene.gltf(filepath=os.path.join(HQ, SP + '.glb'), use_selection=True, export_format='GLB', export_materials='NONE',
                          export_normals=True, export_texcoords=True, export_yup=True, export_apply=False, export_animations=False)
print('scan HQ', SP, len(me.vertices), 'verts')

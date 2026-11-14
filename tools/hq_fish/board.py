"""Reference board per species: the side photo used for the skin, head and skin close-ups, more side views, top and
front views, the measurements used for the shape, and photo credits. python3 -I board.py"""
import json, os
from PIL import Image, ImageDraw, ImageFont
F = '/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf'
fb, fr, fs = ImageFont.truetype(F % '-Bold', 30), ImageFont.truetype(F % '', 17), ImageFont.truetype(F % '', 14)
flab = ImageFont.truetype(F % '-Bold', 18)
FB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ref', 'fbref.json')))
B = {
 'sm': dict(name='Smallmouth Bass', sci='Micropterus dolomieu', side=38, skin=(980, 560, 1460, 880), head=1, alt=[36, 13], top=29, front=18,
            width='Cross-sections: measured on the 3D scan of a largemouth bass (same genus): width 0.62-0.70 of depth, widest just below mid-height.',
            scales='Lateral-line scales 67-81 (FishBase)'),
 'cr': dict(name='Black Crappie', sci='Pomoxis nigromaculatus', side=0, skin=(900, 640, 1380, 960), head=8, alt=[30, 14], top=22, front=28,
            width='Cross-sections: measured on the 3D scan of a bluegill (same family): width 0.40-0.50 of depth; crappie is slightly flatter.',
            scales='Lateral-line scales 36-44 (FishBase)'),
 'br': dict(name='Barramundi', sci='Lates calcarifer', side=18, skin=(900, 330, 1380, 650), head=44, alt=[26, 34], top=46, front=6,
            width='Cross-sections: width from the top-down photo (dorsal view) and the head-on photo.',
            scales='Lateral-line scales 52-61 (FishBase)'),
}
def load(key, i):
    m = json.load(open(f'cand/{key}_meta.json'))[i]
    p = 'orig/' + m['file'] if os.path.exists('orig/' + m['file']) else 'cand/' + m['file']
    return Image.open(p).convert('RGB'), m
def fit(im, w, h):
    im = im.copy(); im.thumbnail((w, h), Image.LANCZOS); return im
for key, b in B.items():
    W, H = 1800, 1450
    S = Image.new('RGB', (W, H), (24, 26, 28)); d = ImageDraw.Draw(S)
    d.text((24, 18), f"{b['name']}", font=fb, fill=(245, 225, 160)); d.text((24 + d.textlength(b['name'], font=fb) + 14, 28), b['sci'], font=fr, fill=(200, 200, 190))
    credits = []
    def tile(im, m, x, y, w, h, label):
        t = fit(im, w, h); S.paste(t, (x + (w - t.width) // 2, y + (h - t.height) // 2))
        d.rectangle([x, y, x + 8 + d.textlength(label, font=flab) + 8, y + 26], fill=(0, 0, 0)); d.text((x + 8, y + 3), label, font=flab, fill=(255, 215, 90))
        if m and m['url'] not in [c[1] for c in credits]: credits.append((m['attribution'], m['url']))
    im, m = load(key, b['side']); tile(im, m, 20, 70, 1180, 760, 'SIDE - skin and outline source')
    tile(im.crop(b['skin']), None, 1220, 70, 560, 370, 'SKIN close-up (1:1 pixels)')
    im2, m2 = load(key, b['head']); tile(im2, m2, 1220, 460, 560, 370, 'HEAD')
    y = 850
    for k, (i, lab) in enumerate([(b['alt'][0], 'SIDE 2'), (b['alt'][1], 'SIDE 3'), (b['top'], 'TOP'), (b['front'], 'FRONT')]):
        im3, m3 = load(key, i); tile(im3, m3, 20 + k * 445, y, 435, 420, lab)
    f = FB[key]['ratios']
    txt = (f"FishBase (fractions of standard length): body depth {f['BD']:.2f}  head {f['HL']:.2f}  eye {f['ED']:.3f}  "
           f"dorsal fin starts {f['PDL']:.2f} from the snout  anal {f['PAL']:.2f}  tail height {f['CH']:.2f}.  {b['scales']}.")
    d.text((24, 1290), txt, font=fr, fill=(225, 225, 215)); d.text((24, 1316), b['width'], font=fr, fill=(225, 225, 215))
    d.text((24, 1352), 'Photos (iNaturalist research-grade observations):', font=fs, fill=(180, 180, 170))
    for n, (a, u) in enumerate(credits):
        d.text((24 + (n % 2) * 880, 1374 + (n // 2) * 20), f"{a}  {u}", font=fs, fill=(160, 160, 150))
    S.save(f'board_{key}.jpg', quality=88); print('board', key, len(credits))

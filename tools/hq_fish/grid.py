"""Overlays a labelled pixel grid (in ORIGINAL image pixels) on a photo for reading landmark coordinates.
python3 -I grid.py <img> <out> [step] [crop x0,y0,x1,y1] [view width]"""
import sys
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1:3]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 100
im = Image.open(src).convert('RGB')
box = tuple(int(v) for v in sys.argv[4].split(',')) if len(sys.argv) > 4 and sys.argv[4] != '-' else (0, 0, im.width, im.height)
VW = int(sys.argv[5]) if len(sys.argv) > 5 else 1400
im = im.crop(box)
s = VW / im.width
im = im.resize((VW, int(im.height * s)), Image.LANCZOS)
d = ImageDraw.Draw(im)
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
x = (box[0] // step + 1) * step
while x < box[2]:
    X = (x - box[0]) * s; d.line([(X, 0), (X, im.height)], fill=(255, 255, 0) if x % (step * 5) == 0 else (255, 60, 60), width=1); d.text((X + 2, 2), str(x), fill=(255, 255, 0), font=f); x += step
y = (box[1] // step + 1) * step
while y < box[3]:
    Y = (y - box[1]) * s; d.line([(0, Y), (im.width, Y)], fill=(255, 255, 0) if y % (step * 5) == 0 else (255, 60, 60), width=1); d.text((2, Y + 2), str(y), fill=(255, 255, 0), font=f); y += step
im.save(out, quality=88)

"""Cycles renders of the HQ fish: whole side, 3/4 front, head close-up and top view per species, stitched in a grid.
python3 render_hq.py fish_hq.blend out.png sm,cr,br [samples] [width]"""
import bpy, sys, math, os, tempfile
from mathutils import Vector
blend, out, sps = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 64
W = int(sys.argv[5]) if len(sys.argv) > 5 else 640
H = int(W * .56)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.device = 'CPU'
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
nt = w.node_tree
bg = nt.nodes['Background']
grad = nt.nodes.new('ShaderNodeTexGradient'); grad.gradient_type = 'LINEAR'
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
mp.inputs['Rotation'].default_value = (0, -math.pi / 2, 0)  # gradient along z (sky above, dark water below)
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (.05, .07, .07, 1)
ramp.color_ramp.elements[1].color = (.75, .85, .95, 1)
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], grad.inputs['Vector'])
nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(30))
# a soft neutral backdrop
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -.45))
floor = bpy.context.active_object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.16, .17, .17, 1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .9
floor.data.materials.append(fm)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
roots = {o.name.split(' ')[0]: o for o in bpy.data.objects if o.type == 'EMPTY'}
for o in roots.values():
    for c in o.children:
        c.hide_render = True
VIEWS = (('side', (0, -2.2, .08), (-.05, 0, 0), 50), ('front34', (.95, -.85, .25), (.15, 0, 0), 50),
         ('head', (.42, -.62, .06), (.36, 0, 0), 70), ('top', (0, -.6, 2.0), (-.05, 0, 0), 50))
tiles = []
for sp in sps:
    for c in roots[sp].children:
        c.hide_render = False
    for name, off, look, lens in VIEWS:
        cam.location = Vector(off)
        cam.data.lens = lens
        d = Vector(look) - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(tempfile.gettempdir(), f'hq_{sp}_{name}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append(p)
    for c in roots[sp].children:
        c.hide_render = True
from PIL import Image
cols = len(VIEWS)
S = Image.new('RGB', (W * cols, H * len(sps)))
for i, p in enumerate(tiles):
    S.paste(Image.open(p).convert('RGB'), ((i % cols) * W, (i // cols) * H))
S.save(out)
print('saved', out)

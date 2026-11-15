"""Shared helpers for the Blender environment kits (run with bpy as a module, Blender 5).
Conventions: metres; origin at the waterline; the LAKE side of every shore piece faces Blender -Y (three.js +Z after
glTF export, which the game turns toward the lake). Colour variation is baked into vertex colours ("Col"), multiplied
into one simple material per surface.
"""
import bpy, bmesh, sys, math, random
from mathutils import Vector, noise

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

MATS = {}


def mat(name, rgb, rough=.8, metal=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    ca = nt.nodes.new('ShaderNodeVertexColor')
    ca.layer_name = 'Col'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1
    mix.inputs['A'].default_value = (*rgb, 1)
    nt.links.new(ca.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    MATS[name] = m
    return m




class Part:
    """Accumulates boxes / cylinders / custom faces into one bmesh per material, then one object per piece."""

    def __init__(self, name):
        self.name = name
        self.bms = {}

    def bm(self, m):
        if m.name not in self.bms:
            self.bms[m.name] = (bmesh.new(), m)
        return self.bms[m.name][0]

    def box(self, m, x0, x1, y0, y1, z0, z1, sub=0):
        b = self.bm(m)
        ret = bmesh.ops.create_cube(b, size=1)
        vs = ret['verts']
        for v in vs:
            v.co.x = x0 + (v.co.x + .5) * (x1 - x0)
            v.co.y = y0 + (v.co.y + .5) * (y1 - y0)
            v.co.z = z0 + (v.co.z + .5) * (z1 - z0)
        if sub:
            edges = list({e for v in vs for e in v.link_edges})
            ret = bmesh.ops.subdivide_edges(b, edges=edges, cuts=sub, use_grid_fill=True)
            vs = [v for v in vs if v.is_valid] + [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
        return vs

    def cyl(self, m, x, y, z0, z1, r, seg=12, r2=None, axis='z'):
        b = self.bm(m)
        ret = bmesh.ops.create_cone(b, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=z1 - z0)
        for v in ret['verts']:
            c = v.co.copy()
            if axis == 'z':
                v.co = Vector((x + c.x, y + c.y, (z0 + z1) / 2 + c.z))
            elif axis == 'x':
                v.co = Vector(((z0 + z1) / 2 + c.z, y + c.y, x + c.x))
            else:
                v.co = Vector((x + c.x, (z0 + z1) / 2 + c.z, y + c.y))
        return ret['verts']

    def build(self, colfn=None, smooth=False):
        objs = []
        for key, (b, m) in self.bms.items():
            me = bpy.data.meshes.new(self.name + '_' + key)
            b.to_mesh(me)
            b.free()
            ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
            for i, v in enumerate(me.vertices):
                c = colfn(v.co, key) if colfn else 1.0
                c = c if isinstance(c, tuple) else (c, c, c)
                ca.data[i].color = (*c, 1)
            me.materials.append(m)
            for p in me.polygons:
                p.use_smooth = smooth
            o = bpy.data.objects.new(self.name + '_' + key, me)
            SC.collection.objects.link(o)
            objs.append(o)
        # join into one object named after the piece
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        o.name = self.name
        o.data.name = self.name
        return o


def n3(p, s=1.0, o=0.0):
    return noise.noise(Vector((p.x * s + o, p.y * s + o * .7, p.z * s - o * .3)))


def wood_col(p, key):
    return .82 + .18 * n3(Vector((p.x * 3, p.y * .4, p.z * 3)), 1, 2)


def smooth01(t):
    t = min(1, max(0, t))
    return t * t * (3 - 2 * t)


def hull_part(P, m, L, W, H, x=0, y=0, z=0, deadrise=.35, bow=.45):
    b = P.bm(m)
    rows = []
    for i in range(15):
        t = i / 14
        yy = -L / 2 + L * t
        k = 1 - (max(0, t - (1 - bow)) / bow) ** 1.7 if t > 1 - bow else 1
        k *= 1 - .12 * (1 - t) ** 3
        hw = W / 2 * max(.04, k)
        zb = -H * (1 - .7 * max(0, t - .6) / .4)
        rows.append([b.verts.new((x - hw, y + yy, z + 0)), b.verts.new((x - hw * .85, y + yy, z + zb * .5)),
                     b.verts.new((x, y + yy, z + zb)), b.verts.new((x + hw * .85, y + yy, z + zb * .5)), b.verts.new((x + hw, y + yy, z + 0))])
    for i in range(14):
        for j in range(4):
            b.faces.new([rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]])
    deck = rows[0] + rows[-1]
    # deck cap
    for i in range(14):
        b.faces.new([rows[i][4], rows[i + 1][4], rows[i + 1][0], rows[i][0]])
    b.faces.new([rows[0][j] for j in range(5)])



def export(pieces, out, blend=None):
    for i, o in enumerate(pieces):
        o.location.x = i * 40  # spread out in the .blend; the game uses each piece at its own origin
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=blend)
    for o in pieces:
        o.location.x = 0
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_vertex_color='ACTIVE', export_all_vertex_colors=False, export_animations=False)
    print('kit', [o.name for o in pieces], sum(len(o.data.polygons) for o in pieces), 'faces')


def boulder(P, m, x, y, z, r, sq=.7, seed=0, detail=2):
    """a rounded, slightly flattened boulder (icosphere pushed around by noise)"""
    b = P.bm(m)
    ret = bmesh.ops.create_icosphere(b, subdivisions=detail, radius=r)
    for v in ret['verts']:
        c = v.co.copy()
        k = 1 + .22 * noise.noise(c * (1.3 / r) + Vector((seed, seed * .7, 0))) + .08 * noise.noise(c * (4 / r) + Vector((0, seed, 3)))
        v.co = Vector((x + c.x * k * 1.15, y + c.y * k, z + c.z * k * sq))
    return ret['verts']


def logp(P, m, x0, y0, z0, x1, y1, z1, r, seg=8):
    """a log (cylinder) between two points"""
    b = P.bm(m)
    a, c = Vector((x0, y0, z0)), Vector((x1, y1, z1))
    d = c - a
    ret = bmesh.ops.create_cone(b, cap_ends=True, segments=seg, radius1=r, radius2=r * .9, depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized())
    for v in ret['verts']:
        v.co = rot @ v.co + (a + c) / 2
    return ret['verts']

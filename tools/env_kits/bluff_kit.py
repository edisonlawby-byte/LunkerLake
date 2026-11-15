"""Bluff Reservoir environment kit (Blender 5, run with bpy): modular pieces for a deep Ozark highland reservoir.

Conventions (so the game can place pieces along any shoreline): metres; origin at the waterline; the LAKE side of every
shore piece faces Blender -Y (= three.js +Z after glTF export, which the game turns toward the lake). Colour variation
(concrete stains, wood grain, rock bedding) is baked into vertex colours, so one simple material per surface is enough.

Pieces: dam_seg, dam_gate, intake_tower, bridge_span, bridge_pier, marina, ramp, bait_shop, bass_boat, pontoon,
ledge_a/b/c (limestone bluff ledges).
Usage: python3 bluff_kit.py <out.glb> [out.blend]
"""
import bpy, bmesh, sys, math, random
from mathutils import Vector, noise

OUT = sys.argv[1]
BLEND = sys.argv[2] if len(sys.argv) > 2 else None
random.seed(5)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

# ---------------------------------------------------------------- materials
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


CONC = (.66, .65, .61); CONC_D = (.5, .49, .46); STEEL_G = (.27, .36, .33); ASPH = (.13, .13, .14); RAIL = (.55, .57, .58)
WOOD = (.52, .4, .28); WOOD_D = (.33, .25, .18); FLOAT = (.12, .12, .12); ROOF = (.55, .58, .6); LIME = (.8, .78, .72)

# ---------------------------------------------------------------- mesh helpers


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


def concrete_col(p, key):
    """mottled concrete, darker water stain band and streaks below the deck edge."""
    c = .82 + .14 * n3(p, .35) + .08 * n3(p, 2.1, 3) + .05 * n3(p, 7, 5)
    if -1.2 < p.z < 1.0:
        c *= .72 + .1 * n3(p, 1.3, 7)
    if p.z < -1.2:
        c *= .6
    streak = max(0, n3(Vector((p.x * 1.7, 0, 0)), 1, 11)) * max(0, (8 - p.z) / 8)
    c *= 1 - .38 * min(1, streak * 1.4)
    return c


def wood_col(p, key):
    return .82 + .18 * n3(Vector((p.x * 3, p.y * .4, p.z * 3)), 1, 2)


def rock_col(p, key):
    """limestone: bedding bands, orange iron stains, black water streaks running down, dark lichen, wet band."""
    bed = .5 + .5 * math.sin(p.z * 5.5 + n3(p, .6) * 2)
    c = .62 + .22 * bed + .12 * n3(p, 1.5, 4)
    r, g, b = c, c * .96, c * .88
    iron = max(0, n3(p, .45, 21)) * 1.4
    r, g, b = r * (1 + .25 * iron), g * (1 + .05 * iron), b * (1 - .2 * iron)
    streak = max(0, n3(Vector((p.x * 2.2, p.y * .3, 0)), 1, 31) - .15) * 1.8
    lichen = max(0, n3(p, 1.1, 41) - .25) * 1.6
    k = (1 - .35 * min(1, streak)) * (1 - .25 * min(1, lichen))
    if p.z < .8:
        k *= .5 + .15 * n3(p, 2, 9)
    return (r * k, g * k * (1 + .06 * lichen), b * k)


# ---------------------------------------------------------------- dam
def dam_seg():
    P = Part('dam_seg')
    c, cd = mat('concrete', CONC, .85), mat('concrete_dark', CONC_D, .9)
    # lake face with lift lines (shallow grooves every 2.4 m) and a slight batter
    for k, z0 in enumerate([-8 + i * 2.4 for i in range(8)]):
        z1 = min(z0 + 2.34, 9)
        P.box(c, -6, 6, -.0 - .02 * (z0 + 8) / 2, 7.6, z0, z1, sub=3)
    P.box(cd, -6.02, -5.94, -.1, 7.6, -8, 9)  # vertical joint
    P.box(c, -6, 6, -.4, .35, 9, 10.1, sub=2)  # parapet
    P.box(cd, -6, 6, -.45, .4, 10.1, 10.25)
    P.box(mat('asphalt', ASPH, .95), -6, 6, .35, 7.2, 9, 9.08)
    for x in (-6 + i * 1.5 for i in range(9)):  # back railing posts
        P.box(mat('rail', RAIL, .5, .6), x - .04, x + .04, 7.25, 7.33, 9.08, 10.1)
    P.box(mat('rail', RAIL, .5, .6), -6, 6, 7.25, 7.35, 9.95, 10.05)
    # lamp post
    P.cyl(mat('rail', RAIL, .5, .6), 0, .1, 10.25, 15, .08, 8)
    P.box(mat('rail', RAIL, .5, .6), -.05, .05, .1, 1.3, 14.9, 15)
    P.box(mat('lamp', (1, .93, .7), .3), -.25, .25, 1.0, 1.5, 14.7, 14.9)
    return P.build(concrete_col)


def dam_gate():
    P = Part('dam_gate')
    c, st = mat('concrete', CONC, .85), mat('gate_steel', STEEL_G, .55, .5)
    for sx in (-6, 4.8):  # piers
        P.box(c, sx, sx + 1.2, -2.2, 7.6, -8, 12, sub=3)
        P.cyl(c, sx + .6, -2.2, -8, 12, .6, 12)  # rounded nose
    P.box(c, -4.8, 4.8, -.6, 7.6, -8, -1.2, sub=3)  # ogee crest under the gate
    # tainter gate: curved skin plate between the piers
    b = P.bm(st)
    R, cy, cz = 7.0, 5.2, 2.2
    verts = []
    for i in range(13):
        a = math.radians(-35 + 70 * i / 12)
        y, z = cy - R * math.cos(a), cz + R * math.sin(a)
        verts.append([b.verts.new((-4.75, y, z)), b.verts.new((4.75, y, z))])
    for i in range(12):
        b.faces.new([verts[i][0], verts[i][1], verts[i + 1][1], verts[i + 1][0]])
    for k in range(5):  # horizontal ribs
        a = math.radians(-30 + 60 * k / 4)
        y, z = cy - R * math.cos(a) + .08, cz + R * math.sin(a)
        P.box(st, -4.75, 4.75, y, y + .25, z - .1, z + .1)
    for sx in (-4.0, 4.0):  # gate arms
        P.box(st, sx - .12, sx + .12, -1.6, cy, cz - .15, cz + .15)
    # deck and hoist house over the bay
    P.box(c, -6, 6, -.4, 7.6, 9, 9.6)
    P.box(mat('asphalt', ASPH, .95), -6, 6, .35, 7.2, 9.6, 9.66)
    P.box(c, -6, 6, -.4, .35, 9.6, 10.6)
    P.box(mat('hoist', (.78, .76, .7), .8), -5.5, 5.5, -2.2, .3, 12, 15, sub=1)
    P.box(mat('roof_metal', ROOF, .4, .7), -5.8, 5.8, -2.5, .6, 15, 15.3)
    for wx in (-3.5, 0, 3.5):
        P.box(mat('window', (.12, .16, .2), .2, .2), wx - .7, wx + .7, -2.25, -2.2, 13, 14)
    return P.build(concrete_col)


def intake_tower():
    P = Part('intake_tower')
    c = mat('concrete', CONC, .85)
    P.box(c, -3, 3, -3, 3, -9, 15, sub=4)
    P.box(c, -3.4, 3.4, -3.4, 3.4, 15, 15.6)
    P.box(mat('hoist', (.78, .76, .7), .8), -2.6, 2.6, -2.6, 2.6, 15.6, 18.6)
    P.box(mat('roof_metal', ROOF, .4, .7), -3, 3, -3, 3, 18.6, 18.9)
    for z in (2, 6, 10):
        for x in (-1.2, 1.2):
            P.box(mat('window', (.12, .16, .2), .2, .2), x - .3, x + .3, -3.05, -3.0, z, z + 1.6)
    # trash racks at the waterline
    for x in [-2.6 + i * .4 for i in range(14)]:
        P.box(mat('gate_steel', STEEL_G, .55, .5), x - .04, x + .04, -3.1, -3.0, -6, 1.5)
    # catwalk to the dam (+Y)
    P.box(mat('gate_steel', STEEL_G, .55, .5), -.9, .9, 3, 17, 14.6, 15)
    P.box(mat('gate_steel', STEEL_G, .55, .5), -.7, .7, 3, 17, 14.2, 14.6)
    for x in (-.95, .95):
        P.box(mat('rail', RAIL, .5, .6), x - .03, x + .03, 3, 17, 15.9, 16)
        for y in range(4, 17, 2):
            P.box(mat('rail', RAIL, .5, .6), x - .03, x + .03, y, y + .06, 15, 16)
    return P.build(concrete_col)


# ---------------------------------------------------------------- bridge
def bridge_span(L=30.0):
    P = Part('bridge_span')
    c, st = mat('concrete', CONC, .85), mat('girder', (.32, .42, .4), .5, .45)
    h = L / 2
    P.box(c, -h, h, -5.6, 5.6, 9.0, 9.55, sub=2)
    P.box(mat('asphalt', ASPH, .95), -h, h, -4.6, 4.6, 9.55, 9.6)
    P.box(mat('paint', (.9, .78, .2), .6), -h, h, -.08, .08, 9.6, 9.61)
    for s in (-1, 1):
        P.box(c, -h, h, s * 4.6 - .25, s * 4.6 + .25, 9.55, 10.45)  # jersey barriers
        P.box(mat('paint', (.92, .92, .9), .6), -h, h, s * 4.2 - .06, s * 4.2 + .06, 9.6, 9.61)
    for y in (-3.6, -1.2, 1.2, 3.6):  # plate girders
        P.box(st, -h, h, y - .18, y + .18, 7.7, 9.0)
        P.box(st, -h, h, y - .45, y + .45, 7.6, 7.75)
        P.box(st, -h, h, y - .4, y + .4, 8.9, 9.0)
    for x in [-h + 1 + i * 3.5 for i in range(int(L / 3.5))]:  # cross frames
        P.box(st, x - .06, x + .06, -3.6, 3.6, 7.9, 8.8)
    P.cyl(mat('rail', RAIL, .5, .6), 0, 5.1, 10.45, 16, .1, 8)
    P.box(mat('rail', RAIL, .5, .6), -.05, .05, 3.6, 5.1, 15.9, 16)
    P.box(mat('lamp', (1, .93, .7), .3), -.25, .25, 3.5, 4.0, 15.7, 15.9)
    return P.build(concrete_col)


def bridge_pier():
    P = Part('bridge_pier')
    c = mat('concrete', CONC, .85)
    P.box(c, -1.1, 1.1, -5.8, 5.8, 6.6, 7.6, sub=2)
    for y in (-3.4, 3.4):
        P.cyl(c, 0, y, -12, 6.6, .85, 16)
    P.box(c, -.5, .5, -3.4, 3.4, -1.5, -.6)  # strut
    return P.build(concrete_col)


# ---------------------------------------------------------------- marina
def marina():
    """Main floating walkway from the shore (+Y end at origin) out into the lake (-Y), slip fingers both sides,
    a covered slip roof, fuel pump at the end."""
    P = Part('marina')
    w, wd, fl = mat('deck_wood', WOOD, .9), mat('deck_wood_dark', WOOD_D, .9), mat('float', FLOAT, .6)
    dz = .45
    L = 34
    P.box(fl, -1.1, 1.1, -L, 0, -.25, .3)
    for y in [-L + i * .32 for i in range(int(L / .32))]:
        P.box(w, -1.25, 1.25, y, y + .28, .3, dz)
    for s in (-1, 1):
        for k in range(5):
            y0 = -6 - k * 5.6
            x0, x1 = (1.25, 9.25) if s > 0 else (-9.25, -1.25)
            P.box(fl, x0 + .1, x1 - .1, y0 - .5, y0, -.25, .3)
            for x in [x0 + i * .32 for i in range(int((x1 - x0) / .32))]:
                P.box(w, x, x + .28, y0 - .55, y0 + .05, .3, dz)
            P.box(mat('cleat', RAIL, .4, .8), x1 - .5, x1 - .3, y0 - .3, y0 - .2, dz, dz + .12)
        # roof posts along the fingers
        for k in range(6):
            y0 = -3.5 - k * 5.6
            P.box(mat('post', (.6, .62, .64), .5, .6), s * 9 - .07, s * 9 + .07, y0 - .07, y0 + .07, dz, 4.6)
            P.box(mat('post', (.6, .62, .64), .5, .6), s * 1.3 - .07, s * 1.3 + .07, y0 - .07, y0 + .07, dz, 5.6)
    # gabled corrugated roof over the slips
    b = P.bm(mat('roof_metal', ROOF, .4, .7))
    for s in (-1, 1):
        for i in range(34):
            x0 = s * (1.3 + (9.6 - 1.3) * i / 34)
            x1 = s * (1.3 + (9.6 - 1.3) * (i + 1) / 34)
            z0 = 5.7 - (abs(x0) - 1.3) * .14 + (.04 if i % 2 else 0)
            z1 = 5.7 - (abs(x1) - 1.3) * .14 + (.04 if (i + 1) % 2 else 0)
            v = [b.verts.new((x0, -32, z0)), b.verts.new((x1, -32, z1)), b.verts.new((x1, -2.5, z1)), b.verts.new((x0, -2.5, z0))]
            b.faces.new(v if s > 0 else v[::-1])
    P.box(mat('roof_metal', ROOF, .4, .7), -1.4, 1.4, -32, -2.5, 5.7, 5.85)
    # fuel pump and light posts at the end
    P.box(mat('pump', (.85, .15, .12), .5), -.4, .4, -L + .5, -L + 1.1, dz, dz + 1.6)
    P.box(mat('pump_top', (.95, .95, .92), .5), -.45, .45, -L + .45, -L + 1.15, dz + 1.6, dz + 1.9)
    for y in (-2, -L + 2):
        P.cyl(mat('rail', RAIL, .5, .6), 1.1, y, dz, dz + 3.2, .06, 8)
        P.box(mat('lamp', (1, .93, .7), .3), .95, 1.25, y - .15, y + .15, dz + 3.1, dz + 3.3)
    # gangway to shore
    P.box(mat('rail', RAIL, .5, .6), -.8, .8, 0, 6, .4, .5)
    return P.build(wood_col)


def ramp():
    P = Part('ramp')
    c = mat('concrete', CONC, .85)
    b = P.bm(c)
    W, L = 7, 26
    rows = []
    for i in range(27):
        y = -L / 2 + L * i / 26
        z = -2.2 + 4.4 * i / 26
        rows.append([b.verts.new((x, y, z)) for x in (-W / 2, -W / 4, 0, W / 4, W / 2)])
    for i in range(26):
        for j in range(4):
            b.faces.new([rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]])
    for s in (-1, 1):
        P.box(mat('post', (.6, .62, .64), .5, .6), s * 3.7 - .1, s * 3.7 + .1, -8, 13, -1.4, .9)
    return P.build(concrete_col)


def bait_shop():
    P = Part('bait_shop')
    wall, trim = mat('siding', (.42, .5, .44), .85), mat('trim', (.92, .9, .84), .7)
    P.box(wall, -5, 5, -3.5, 3.5, 0, 3.4, sub=2)
    b = P.bm(mat('roof_metal_red', (.55, .16, .12), .45, .6))
    for s in (-1, 1):
        v = [b.verts.new((-5.6, s * 4.1, 3.2)), b.verts.new((5.6, s * 4.1, 3.2)), b.verts.new((5.6, 0, 4.9)), b.verts.new((-5.6, 0, 4.9))]
        b.faces.new(v if s < 0 else v[::-1])
    for s in (-1, 1):  # gable ends
        g = [b.verts.new((s * 5.0, -3.5, 3.4)), b.verts.new((s * 5.0, 3.5, 3.4)), b.verts.new((s * 5.0, 0, 4.85))]
        b.faces.new(g if s > 0 else g[::-1])
    P.box(mat('deck_wood', WOOD, .9), -5.5, 5.5, -6, -3.5, 0, .35)  # porch (lake side)
    for x in (-5.2, -1.8, 1.8, 5.2):
        P.box(trim, x - .08, x + .08, -5.9, -5.75, .35, 3.2)
    P.box(mat('roof_metal_red', (.55, .16, .12), .45, .6), -5.6, 5.6, -6.2, -3.4, 3.1, 3.25)
    P.box(mat('door', (.3, .22, .16), .8), -.6, .6, -3.56, -3.5, 0, 2.2)
    for x in (-3.2, 3.2):
        P.box(mat('window', (.12, .16, .2), .2, .2), x - .9, x + .9, -3.56, -3.5, 1.1, 2.3)
        P.box(trim, x - 1.0, x + 1.0, -3.6, -3.55, 1.0, 2.4)
    # sign board (blank boards with painted stripes: no real brand names)
    P.box(mat('sign', (.95, .93, .86), .7), -3, 3, -6.3, -6.2, 3.3, 4.3)
    P.box(mat('sign_red', (.75, .12, .1), .7), -3, 3, -6.32, -6.29, 3.75, 3.95)
    P.box(mat('ice', (.2, .45, .75), .5), 3.4, 4.6, -6.0, -5.3, .35, 1.6)  # ice chest
    return P.build(wood_col)


# ---------------------------------------------------------------- boats
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


def bass_boat():
    """Metal-flake bass boat, bow toward -Y."""
    P = Part('bass_boat')
    hull_part(P, mat('flake_red', (.62, .05, .05), .25, .55), 6.2, 2.2, .55, z=.35)
    P.box(mat('carpet', (.18, .2, .22), .95), -.78, .78, -1.6, 2.6, .36, .4)
    P.box(mat('carpet', (.18, .2, .22), .95), -.45, .45, -2.4, -1.6, .36, .4)
    P.box(mat('console', (.85, .85, .82), .4), .35, 1.0, .2, .9, .4, 1.25)
    P.box(mat('window', (.12, .16, .2), .1, .2), .35, 1.0, .1, .2, 1.0, 1.35)
    for x in (-.5, .5):
        P.box(mat('seat', (.1, .1, .1), .6), x - .3, x + .3, 1.5, 2.0, .4, .9)
    P.box(mat('motor', (.08, .08, .09), .3, .3), -.35, .35, 3.1, 3.7, .2, 1.4)
    P.box(mat('motor', (.08, .08, .09), .3, .3), -.12, .12, 3.3, 3.5, -.6, .2)
    P.cyl(mat('rail', RAIL, .5, .6), 0, -2.9, .4, 1.2, .04, 6)  # trolling motor shaft
    return P.build(lambda p, k: 1.0 + .08 * n3(p, 3, 1))


def pontoon():
    P = Part('pontoon')
    for x in (-1.0, 1.0):
        P.cyl(mat('tube', (.82, .84, .86), .3, .8), x, 0, -3.4, 3.4, .3, 14, axis='y')
    P.box(mat('deck_carpet', (.3, .32, .36), .95), -1.3, 1.3, -3.6, 3.6, .3, .38)
    P.box(mat('fence', (.88, .88, .86), .4, .4), -1.3, 1.3, -3.4, 3.4, .38, 1.15)
    P.box(mat('carpet', (.18, .2, .22), .95), -1.22, 1.22, -3.32, 3.32, .38, 1.16)
    P.box(mat('bimini', (.15, .25, .45), .8), -1.3, 1.3, -1.0, 1.6, 2.1, 2.15)
    for x in (-1.25, 1.25):
        for y in (-1.0, 1.6):
            P.box(mat('rail', RAIL, .5, .6), x - .025, x + .025, y - .025, y + .025, 1.15, 2.1)
    P.box(mat('motor', (.08, .08, .09), .3, .3), -.3, .3, 3.6, 4.1, .1, 1.2)
    return P.build()


# ---------------------------------------------------------------- limestone bluff ledges
# Reference: Ozark reservoir bluffs (Table Rock, Bull Shoals, Beaver): near-vertical grey-buff dolomite/limestone rising
# straight out of the water, thick beds split by thin recessed partings, vertical joints that break each bed into
# blocks (some fallen out), black water streaks and orange iron stains running down, chunk rock at the waterline.
random.seed(7)
BEDS = []  # one bed sequence shared by every piece, so the beds line up from piece to piece along the shore
z = -4.0
while z < 28:
    th = random.uniform(.7, 2.3)
    BEDS.append((z, z + th, False))
    z += th
    pt = random.uniform(.12, .32)
    BEDS.append((z, z + pt, True))  # thin shaly parting, recessed (reads as a dark line)
    z += pt


def bluff_col(p, key):
    bi = next((i for i, (z0, z1, _) in enumerate(BEDS) if z0 <= p.z < z1), 0)
    c = .66 + .1 * math.sin(bi * 2.3) + .07 * n3(p, .35, 4) + .04 * n3(p, 2.5, 6)
    r, g, b = c * 1.0, c * .95, c * .86
    streak = max(0, n3(Vector((p.x * .7, p.y * .3, p.z * .06)), 1, 31) - .2) * 1.6   # long dark runs down from ledges
    streak *= max(0, n3(Vector((p.x * .25, 0, p.z * .12)), 1, 33) + .2)
    lichen = max(0, n3(p, .9, 41) - .3) * 1.2
    r, g, b = r * (1 - .3 * lichen), g * (1 - .22 * lichen), b * (1 - .35 * lichen)
    iron = max(0, n3(Vector((p.x * .9, p.y, p.z * .5)), .8, 21) - .15) * 1.8
    r, g, b = r * (1 + .22 * iron), g * (1 + .04 * iron), b * (1 - .25 * iron)
    k = 1 - .45 * min(1, streak)
    if p.z < .9:  # wet, algae-dark band at the waterline
        k *= .68 + .15 * max(0, n3(p, 2, 9))
    return (r * k, g * k, b * k * 1.02)


def smooth01(t):
    t = min(1, max(0, t))
    return t * t * (3 - 2 * t)


def bluff_wall(name='bluff_wall', L=80.0, H=22.0, seed=5):
    """ONE continuous sculpted rock face (no separate blocks). A regular grid along the wall (x) and up (z), pushed
    out toward the lake (-Y) by: a gentle overall bulge, thick beds that stick out by different amounts along the
    wall, thin recessed partings between beds, V-shaped vertical joint cracks, a slight lean back with height and fine
    roughness. Above the local cliff height the grid folds back over the top into the hill. The ends drop to nothing,
    so the game can bend one wall along a stretch of shoreline with no seams."""
    random.seed(seed)
    P = Part(name)
    m = mat('limestone', LIME, .92)
    b = P.bm(m)
    NX, DZ = int(L / .65), .22
    zs = [-4 + i * DZ for i in range(int((H + 3 + 4) / DZ) + 1)]
    beds = [(z0, z1, pt) for z0, z1, pt in BEDS if z0 < H + 3]
    # joints per bed: x positions; about half continue from the bed below
    jts, prev = [], []
    for z0, z1, pt in beds:
        if pt:
            jts.append(prev)
            continue
        xs = [x for x in prev if random.random() < .55]
        x = random.uniform(0, 2)
        while x < L:
            xs.append(x)
            x += random.uniform(1.6, 4.5)
        prev = sorted(xs)
        jts.append(prev)
    grid = []
    for i in range(NX + 1):
        x = L * i / NX
        end = smooth01(x / 14) * smooth01((L - x) / 14)
        hx = (H * (.7 + .3 * noise.noise(Vector((x * .03, 1.5, seed))))) * end - 1.5 * (1 - end)
        col = []
        for z in zs:
            bi = next((k for k, (z0, z1, _) in enumerate(beds) if z0 <= z < z1), len(beds) - 1)
            z0, z1, pt = beds[bi]
            d = 2.2 * noise.noise(Vector((x * .03, z * .04, seed + 1)))           # big buttresses and bays
            d += 1.0 * noise.noise(Vector((x * .06, bi * 3.1, seed + 2)))         # each bed sticks out its own amount
            u = (z - z0) / max(z1 - z0, 1e-3)
            if pt:
                d -= .9                                                          # parting: recessed dark line
            else:
                d -= .35 * (1 - math.sin(math.pi * u)) ** 3                      # bed edges round off into the partings
                for xj in jts[bi]:
                    w = abs(x - xj)
                    if w < .7:
                        d -= .8 * (1 - w / .7) ** 1.5                            # vertical joint crack
            d -= .07 * max(0, z)                                                 # leans back as it rises
            d += .12 * noise.noise(Vector((x * .9, z * .9, seed + 3))) - 4.5 * (1 - end)  # roughness; ends sink into the hill
            y = -d
            zz = z
            if z > hx:                                                          # fold back over the top into the hill
                k = z - hx
                y = -d + k * 3.2
                zz = hx + .35 * math.sin(min(k, 1.2) * 1.3) - max(0, k - 1.2) * .6
            col.append(b.verts.new((x - L / 2, y, zz)))
        grid.append(col)
    for i in range(NX):
        for j in range(len(zs) - 1):
            b.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    o = P.build(bluff_col, smooth=True)
    return o


pieces = [dam_seg(), dam_gate(), intake_tower(), bridge_span(), bridge_pier(), marina(), ramp(), bait_shop(), bass_boat(), pontoon(),
          bluff_wall()]
for i, o in enumerate(pieces):
    o.location.x = i * 40  # spread out in the .blend; the game uses each piece at its own origin
if BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
for o in pieces:
    o.location.x = 0
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                          export_vertex_color='ACTIVE', export_all_vertex_colors=False, export_animations=False)
print('kit', [o.name for o in pieces], sum(len(o.data.polygons) for o in pieces), 'faces')

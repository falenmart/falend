"""
Lav Tahti (Lava Throne) - Blender uretici script, Roblox uyumlu

Calistirma:
  python3 blender/build_lava_throne.py            # FBX + dokular + .blend
  python3 blender/build_lava_throne.py --render   # ayrica onizleme renderlari
  python3 blender/build_lava_throne.py --quick    # hizli deneme (dusuk cozunurluk)
  blender --background --python blender/build_lava_throne.py -- --render

Yontem:
  1. Yuksek detayli kaya govdesi: voxel remesh + gurultu + oyulmus lav damarlari
  2. Dusuk poligonlu oyun modeli (decimate) + UV
  3. Yuksekten dusuge bake: Renk, Normal, Puruzluluk, Metaliklik (+AO renge islenir)
     -> Roblox SurfaceAppearance icin PNG'ler
  4. Parlayan her sey ayri Neon parca: damarlar, lav selalesi, nehirler,
     havuz, volkan agizlari, run, pence kureleri, boynuz uclari, alevler

Olcek: 1 Blender birimi = 1 stud. Oturma yuksekligi zeminden ~2 stud.
"""

import math
import os
import random
import sys

import bpy  # noqa: I001  (bmesh'ten once yuklenmeli)
import bmesh
import numpy as np
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_chairs import box, cyl, join, new_obj, prism, torus  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
QUICK = "--quick" in ARGS
RENDER = "--render" in ARGS

TEX = 256 if QUICK else 1024          # Roblox SurfaceAppearance en fazla 1024
ROCK_TEX = 128 if QUICK else 512
VOXEL_BODY = 0.07 if QUICK else 0.03
VOXEL_PLAT = 0.12 if QUICK else 0.055
TRI_LIMIT = 20000                     # Roblox MeshPart siniri

EXPORT_DIR = os.path.join(HERE, "export", "LavaThrone")
TEX_DIR = os.path.join(EXPORT_DIR, "textures")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")

PLAT_TOP = 1.0
BACK_DEPTH = 1.0
BACK_M = (Matrix.Translation((0, 1.9, PLAT_TOP - 0.1))
          @ Matrix.Rotation(math.radians(-5), 4, "X"))
BACK_R = BACK_M.to_3x3()

# Sirtlik konturu (u=x, v=z, sirtlik tabanindan). Ust kisim 5 sivri tac.
OUTLINE = [(-2.3, 0.0), (2.3, 0.0), (2.6, 6.4), (2.95, 8.1), (2.0, 7.25),
           (1.35, 9.0), (0.6, 7.95), (0.0, 10.1), (-0.6, 7.95), (-1.35, 9.0),
           (-2.0, 7.25), (-2.95, 8.1), (-2.6, 6.4)]
RUNE_UV = Vector((0.0, 6.1))
RUNE_R = 1.0
POOL = Vector((0.0, 3.75))
POOL_R = 1.05
VENTS = [Vector((math.cos(a) * 6.15, math.sin(a) * 6.15))
         for a in (math.radians(d) for d in (45, 135, 225, 315))]
ORB_R = 0.36
ORBS = {s: Vector((s * 2.5, -2.05, 4.16)) for s in (-1, 1)}

rng = random.Random(1912)


# ---------------------------------------------------------------------------
# Genel yardimcilar
# ---------------------------------------------------------------------------

def sstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def apply_mods(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    me.name = obj.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def remesh(obj, voxel, smooth_iter=0):
    m = obj.modifiers.new("Remesh", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    if smooth_iter:
        s = obj.modifiers.new("Smooth", "SMOOTH")
        s.factor = 0.6
        s.iterations = smooth_iter
    apply_mods(obj)


def delete_faces(obj, pred):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    dead = [f for f in bm.faces if pred(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(obj.data)
    bm.free()


def single_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def set_attr(me, name, values):
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", np.asarray(values, dtype=np.float32))


def displace(obj, fn, attrs=("heat", "micro")):
    """fn(p, n) -> (yer degistirme, heat, micro). Normal yonunde uygular."""
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    nr = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.vertex_normals.foreach_get("vector", nr)
    co = co.reshape(-1, 3)
    nr = nr.reshape(-1, 3)
    out = co.copy()
    a0 = np.zeros(n, np.float32)
    a1 = np.zeros(n, np.float32)
    for i in range(n):
        d, h, m = fn(Vector(co[i]), Vector(nr[i]))
        out[i] = co[i] + nr[i] * d
        a0[i] = h
        a1[i] = m
    me.vertices.foreach_set("co", out.ravel())
    set_attr(me, attrs[0], a0)
    set_attr(me, attrs[1], a1)
    me.update()


def make_low(high, name, target, coll):
    low = high.copy()
    low.data = high.data.copy()
    low.name = name
    coll.objects.link(low)
    d = low.modifiers.new("Decimate", "DECIMATE")
    d.ratio = min(1.0, target / max(1, tris(high)))
    d.use_collapse_triangulate = True
    apply_mods(low)
    for p in low.data.polygons:
        p.use_smooth = True
    return low


def bvh(obj):
    return BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())


def spline(ctrl, n):
    """Catmull-Rom egrisi uzerinde n nokta."""
    ctrl = [Vector(c) for c in ctrl]
    m = len(ctrl)
    out = []
    for k in range(n):
        t = k / (n - 1) * (m - 1)
        i = min(int(t), m - 2)
        f = t - i
        p0, p1 = ctrl[max(i - 1, 0)], ctrl[i]
        p2, p3 = ctrl[i + 1], ctrl[min(i + 2, m - 1)]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * f
                          + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3))
    return out


def resample(pts, step):
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        t = step - acc
        while t <= seg:
            out.append(a.lerp(b, t / seg))
            t += step
        acc = seg - (t - step)
    if (out[-1] - pts[-1]).length > step * 0.3:
        out.append(pts[-1])
    return out


def sweep_bm(bm, pts, radii, normals=None, sides=8, flat=1.0, cap=True,
             rfn=None):
    """Nokta dizisi boyunca boru/serit. rfn(i, aci) yaricap carpani."""
    n = len(pts)
    rings = []
    prev = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        t = t.normalized() if t.length > 1e-9 else Vector((0, 0, 1))
        n0 = normals[i] if normals else prev
        if n0 is None:
            n0 = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        b = t.cross(n0)
        if b.length < 1e-6:
            b = t.orthogonal()
        b.normalize()
        nn = b.cross(t).normalized()
        prev = nn
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            r = radii[i] * (rfn(i, a) if rfn else 1.0)
            ring.append(bm.verts.new(p + b * (math.cos(a) * r)
                                     + nn * (math.sin(a) * r * flat)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((r0[j], r1[j], r1[k], r0[k]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return rings


def mesh_obj(name, bm, coll, material, smooth=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_obj(name, bm, coll, material, smooth=smooth)


# 2B cokgen yardimcilari ----------------------------------------------------

def pip(p, poly):
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def dist_poly(p, poly):
    best = 1e9
    p = Vector(p)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        a, b = Vector(a), Vector(b)
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        best = min(best, (p - (a + ab * t)).length)
    return best


def inset(poly, d):
    """CCW cokgeni d kadar iceri al (mitre kirpilmis)."""
    out = []
    n = len(poly)
    for i in range(n):
        p0, p1, p2 = (Vector(poly[i - 1]), Vector(poly[i]),
                      Vector(poly[(i + 1) % n]))
        e1 = (p1 - p0).normalized()
        e2 = (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x))
        n2 = Vector((-e2.y, e2.x))
        m = (n1 + n2)
        if m.length < 1e-6:
            m = n1
        m.normalize()
        k = d / max(0.35, m.dot(n1))
        out.append(p1 + m * k)
    return out


# Duzlem + damar agi ----------------------------------------------------------

class Plane:
    def __init__(self, origin, u, v, n):
        self.o, self.u, self.v, self.n = (Vector(origin), Vector(u),
                                          Vector(v), Vector(n))

    def to3d(self, uv, h=0.0):
        return self.o + self.u * uv[0] + self.v * uv[1] + self.n * h

    def to2d(self, p):
        d = p - self.o
        return d.dot(self.u), d.dot(self.v), d.dot(self.n)


def back_plane(front=True):
    s = -1 if front else 1
    return Plane(BACK_M @ Vector((0, s * BACK_DEPTH / 2, 0)),
                 BACK_R @ Vector((-s, 0, 0)) if not front else
                 BACK_R @ Vector((1, 0, 0)),
                 BACK_R @ Vector((0, 0, 1)),
                 BACK_R @ Vector((0, s, 0)))


class VeinNet:
    """Duzlem uzerindeki 2B catlak cizgileri: oyma + isi alani."""

    def __init__(self, plane, lines, width, depth, heat_r, min_dot=0.35,
                 max_h=0.9, glow=0.7):
        self.plane, self.lines = plane, lines
        self.width, self.depth, self.heat_r = width, depth, heat_r
        self.min_dot, self.max_h, self.glow = min_dot, max_h, glow
        pts, tap = [], []
        for line, rad in lines:
            for a, b, ra, rb in zip(line, line[1:], rad, rad[1:]):
                steps = max(1, int((b - a).length / 0.02))
                for k in range(steps):
                    f = k / steps
                    q = a.lerp(b, f)
                    pts.append((q.x, q.y, 0.0))
                    tap.append(ra + (rb - ra) * f)
        self.kd = KDTree(len(pts))
        for i, q in enumerate(pts):
            self.kd.insert(q, i)
        self.kd.balance()
        self.taper = tap

    def sample(self, p, n):
        if n.dot(self.plane.n) < self.min_dot:
            return 0.0, 0.0, 99.0
        u, v, h = self.plane.to2d(p)
        if abs(h) > self.max_h:
            return 0.0, 0.0, 99.0
        _, i, dist = self.kd.find((u, v, 0.0))
        tp = self.taper[i]
        w = self.width * (0.55 + 0.45 * tp)
        g = sstep(w, 0.0, dist)
        heat = max(g, self.glow * tp * math.exp(-dist / self.heat_r))
        return self.depth * g * (0.6 + 0.4 * tp), heat, dist

    def tubes(self, coll, name, material, target, radius, sides=5,
              flat=0.8, lift=0.0, step=0.1, h=0.8):
        tree = bvh(target)
        pl = self.plane
        bm = bmesh.new()
        for line, rad in self.lines:
            line = resample(line, step)
            seg, nrm, rr = [], [], []

            def flush():
                if len(seg) > 2:
                    sweep_bm(bm, seg, rr, nrm, sides=sides, flat=flat)

            radf = taper_along(rad, len(line))
            for k, uv in enumerate(line):
                o = pl.to3d(uv, h)
                hit = tree.ray_cast(o, -pl.n, h + 1.2)
                if hit[0] is None:
                    flush()
                    seg, nrm, rr = [], [], []
                    continue
                seg.append(hit[0] + hit[1] * lift)
                nrm.append(hit[1])
                rr.append(radius * radf[k])
            flush()
        return mesh_obj(name, bm, coll, material)


def taper_along(rad, n):
    if n == 1:
        return [rad[0]]
    out = []
    for k in range(n):
        t = k / (n - 1) * (len(rad) - 1)
        i = min(int(t), len(rad) - 2) if len(rad) > 1 else 0
        f = t - i
        out.append(rad[i] if len(rad) == 1 else
                   rad[i] + (rad[i + 1] - rad[i]) * f)
    return out


def cracks(seeds, inside, step=0.1, jitter=0.3, branch=0.07, bias=0.15,
           max_depth=2):
    """Simsek benzeri dallanan catlaklar (2B)."""
    lines = []

    def walk(p, ang, length, depth, r0):
        pts, rad = [p], [r0]
        a = ang
        n = max(2, int(length / step))
        for i in range(n):
            a += rng.gauss(0, jitter)
            a = a * (1 - bias) + ang * bias
            q = pts[-1] + Vector((math.cos(a), math.sin(a))) * step
            if not inside(q):
                break
            pts.append(q)
            rad.append(r0 * (0.3 + 0.7 * (1 - (i + 1) / n)))
            if depth < max_depth and i > 2 and rng.random() < branch:
                walk(q, a + rng.choice((-1, 1)) * rng.uniform(0.5, 1.1),
                     length * (1 - i / n) * 0.6, depth + 1, rad[-1] * 0.75)
        if len(pts) > 2:
            lines.append((pts, rad))

    for p, ang, length in seeds:
        walk(Vector(p), ang, length, 0, 1.0)
    return lines


# Kaya gurultusu ------------------------------------------------------------

def rock_base(p, plates=1.7, amp=1.0):
    big = noise.fractal(p * 0.42, 1.0, 2.0, 3)
    mid = noise.fractal(p * 1.5 + Vector((5.2, 1.3, 7.7)), 0.7, 2.0, 4)
    d, cells = noise.voronoi(p * plates, distance_metric="DISTANCE",
                             exponent=2.5)
    crack = max(0.0, 1.0 - (d[1] - d[0]) / 0.09)
    plate = noise.noise(cells[0] * 7.31)
    d2, _ = noise.voronoi(p * plates * 2.6 + Vector((3, 7, 1)),
                          distance_metric="DISTANCE", exponent=2.5)
    crack2 = max(0.0, 1.0 - (d2[1] - d2[0]) / 0.06)
    disp = amp * (0.05 * big + 0.018 * mid + 0.022 * plate
                  - 0.04 * crack ** 2 - 0.012 * crack2 ** 2)
    return disp, crack ** 3 + 0.35 * crack2 ** 3


# ---------------------------------------------------------------------------
# Malzemeler (bake kanallari + onizleme)
# ---------------------------------------------------------------------------

CH = {}


def nodes_of(m):
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    return nt


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def link(nt, a, b):
    nt.links.new(a, b)


def ramp(nt, fac, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    el = r.color_ramp.elements
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    el[1].position, el[1].color = stops[-1][0], (*stops[-1][1], 1)
    for pos, col in stops[1:-1]:
        e = el.new(pos)
        e.color = (*col, 1)
    link(nt, fac, r.inputs["Fac"])
    return r.outputs["Color"]


def mix_rgb(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    link(nt, fac, m.inputs[0])
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = (*val, 1)
        else:
            link(nt, val, sock)
    return m.outputs[2]


def math_node(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for sock, val in zip(n.inputs, (a, b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            sock.default_value = val
        else:
            link(nt, val, sock)
    return n.outputs[0]


def map_range(nt, val, a, b, c=0.0, d=1.0):
    n = node(nt, "ShaderNodeMapRange")
    n.inputs[1].default_value, n.inputs[2].default_value = a, b
    n.inputs[3].default_value, n.inputs[4].default_value = c, d
    link(nt, val, n.inputs[0])
    return n.outputs[0]


def tex_noise(nt, scale, detail=6.0, rough=0.55, offset=(0, 0, 0)):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = offset
    link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    n = node(nt, "ShaderNodeTexNoise", Scale=scale, Detail=detail,
             Roughness=rough)
    link(nt, mp.outputs["Vector"], n.inputs["Vector"])
    return n.outputs["Fac"]


def attr(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = name
    return a.outputs["Fac"]


def value(nt, v):
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


HEAT_STOPS = [(0.0, (0.05, 0.004, 0.0)), (0.3, (0.42, 0.03, 0.0)),
              (0.62, (1.0, 0.24, 0.015)), (1.0, (1.0, 0.7, 0.2))]


def finish(m, nt, color, rough, metal, emit=None, emit_strength=0.0):
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    link(nt, color, bsdf.inputs["Base Color"])
    link(nt, rough, bsdf.inputs["Roughness"])
    link(nt, metal, bsdf.inputs["Metallic"])
    if emit is not None:
        link(nt, emit, bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    out = nt.nodes["Material Output"]
    link(nt, bsdf.outputs[0], out.inputs["Surface"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "BakeEmit"
    CH[m.name] = {"bsdf": bsdf, "emit": em, "color": color,
                  "roughness": rough, "metallic": metal}
    return m


def rock_material(name, dark, light, gloss, heat_gain=1.0):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    base = ramp(nt, tex_noise(nt, 1.1, 8, 0.6), [(0.35, dark), (0.7, light)])
    speck = tex_noise(nt, 18.0, 4, 0.5, (3, 1, 2))
    base = mix_rgb(nt, map_range(nt, speck, 0.55, 0.75, 0, 0.35), base,
                   tuple(c * 0.5 for c in dark))
    h = math_node(nt, "MAXIMUM", attr(nt, "heat"),
                  math_node(nt, "MULTIPLY", attr(nt, "micro"), 0.55 * heat_gain))
    hcol = ramp(nt, h, HEAT_STOPS)
    hmix = map_range(nt, h, 0.03, 0.4)
    color = mix_rgb(nt, hmix, base, hcol)
    rough = map_range(nt, tex_noise(nt, 2.4, 3, 0.5, (9, 2, 4)), 0.35, 0.65,
                      gloss[0], gloss[1])
    rough = math_node(nt, "ADD", rough, math_node(nt, "MULTIPLY", hmix, 0.45),
                      clamp=True)
    return finish(m, nt, color, rough, value(nt, 0.0), hcol, 0.0)


def gold_material(name):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    color = ramp(nt, tex_noise(nt, 6.0, 6, 0.6),
                 [(0.3, (0.62, 0.38, 0.12)), (0.7, (1.0, 0.74, 0.32))])
    rough = map_range(nt, tex_noise(nt, 14.0, 4, 0.5, (4, 4, 4)), 0.3, 0.7,
                      0.16, 0.38)
    return finish(m, nt, color, rough, value(nt, 1.0))


def horn_material(name):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    band = attr(nt, "micro")
    base = mix_rgb(nt, band, (0.012, 0.01, 0.01), (0.09, 0.07, 0.06))
    grain = tex_noise(nt, 9.0, 6, 0.6)
    base = mix_rgb(nt, map_range(nt, grain, 0.4, 0.7, 0, 0.4), base,
                   (0.16, 0.12, 0.09))
    h = attr(nt, "heat")
    color = mix_rgb(nt, h, base, ramp(nt, h, HEAT_STOPS))
    rough = map_range(nt, band, 0, 1, 0.28, 0.5)
    return finish(m, nt, color, rough, value(nt, 0.0))


def route(mats, channel):
    """Bake icin malzeme ciktisini bir kanala (emission) baglar."""
    for m in mats:
        c = CH[m.name]
        nt = m.node_tree
        out = nt.nodes["Material Output"]
        if channel is None:
            link(nt, c["bsdf"].outputs[0], out.inputs["Surface"])
        else:
            link(nt, c[channel], c["emit"].inputs["Color"])
            c["emit"].inputs["Strength"].default_value = 1.0
            link(nt, c["emit"].outputs[0], out.inputs["Surface"])


PULSES = []


def lava_material(name, strength=10.0, crust=0.0, scale=2.5,
                  flow=(0, 0, 0)):
    """Neon parcalarin onizleme malzemesi (Roblox'ta Material = Neon)."""
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    n1 = node(nt, "ShaderNodeTexNoise", Scale=scale, Detail=8.0,
              Roughness=0.6)
    link(nt, mp.outputs["Vector"], n1.inputs["Vector"])
    col = ramp(nt, n1.outputs["Fac"], [(0.3, (0.75, 0.06, 0.0)),
                                       (0.5, (1.0, 0.32, 0.02)),
                                       (0.7, (1.0, 0.78, 0.25))])
    pulse = nt.nodes.new("ShaderNodeValue")
    pulse.outputs[0].default_value = strength
    PULSES.append((pulse, strength))
    s = pulse.outputs[0]
    base = (0.3, 0.03, 0.0)
    if crust > 0:
        vor = node(nt, "ShaderNodeTexVoronoi", Scale=scale * 1.6)
        link(nt, mp.outputs["Vector"], vor.inputs["Vector"])
        k = map_range(nt, vor.outputs["Distance"], 0.25, 0.45, 1.0, 0.0)
        k = math_node(nt, "MULTIPLY", k, crust)
        s = math_node(nt, "MULTIPLY", s, math_node(nt, "SUBTRACT", 1.0, k))
        base = (0.02, 0.012, 0.01)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Roughness"].default_value = 0.6
    link(nt, col, bsdf.inputs["Emission Color"])
    link(nt, s, bsdf.inputs["Emission Strength"])
    link(nt, bsdf.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m["mapping"] = mp.name
    m["flow"] = flow
    return m


def flame_material(name, color, strength):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    fac = map_range(nt, lw.outputs["Facing"], 0.2, 0.95, 0.0, 1.0)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1))
    pulse = nt.nodes.new("ShaderNodeValue")
    pulse.outputs[0].default_value = strength
    PULSES.append((pulse, strength))
    link(nt, pulse.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    link(nt, fac, mix.inputs[0])
    link(nt, em.outputs[0], mix.inputs[1])
    link(nt, tr.outputs[0], mix.inputs[2])
    link(nt, mix.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


def simple_material(name, color, rough=0.5, metal=0.0, sheen=0.0):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Tint"].default_value = (1.0, 0.45, 0.45, 1)
    link(nt, bsdf.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m.diffuse_color = (*color, 1)
    return m


def pbr_material(name, maps):
    m = bpy.data.materials.new(name)
    nt = nodes_of(m)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")

    def img(key):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = maps[key]
        return n.outputs["Color"]

    link(nt, img("color"), bsdf.inputs["Base Color"])
    link(nt, img("roughness"), bsdf.inputs["Roughness"])
    if "metallic" in maps:
        link(nt, img("metallic"), bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    link(nt, img("normal"), nm.inputs["Color"])
    link(nt, nm.outputs["Normal"], bsdf.inputs["Normal"])
    link(nt, bsdf.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# Bake
# ---------------------------------------------------------------------------

def bake_set(name, low, highs, size, channels, extrusion=0.08, ray=0.25):
    scene = bpy.context.scene
    keep = set(highs) | {low}
    hidden = []
    for ob in scene.objects:
        if ob not in keep and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    bmat = bpy.data.materials.new(f"{name}_Bake")
    nt = nodes_of(bmat)
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    low.data.materials.clear()
    low.data.materials.append(bmat)
    for p in low.data.polygons:
        p.material_index = 0
    mats = {m for h in highs for m in h.data.materials if m}
    scene.render.bake.margin = max(2, size // 160)
    scene.render.bake.margin_type = "EXTEND"
    imgs = {}
    for ch in channels:
        img = bpy.data.images.new(f"{name}_{ch}", size, size, alpha=False)
        img.colorspace_settings.name = "sRGB" if ch == "color" else "Non-Color"
        tex.image = img
        bpy.ops.object.select_all(action="DESELECT")
        for h in highs:
            h.select_set(True)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        kind = {"normal": "NORMAL", "ao": "AO"}.get(ch, "EMIT")
        route(mats, None if kind != "EMIT" else ch)
        scene.cycles.samples = 48 if kind == "AO" else 4
        bpy.ops.object.bake(type=kind, use_selected_to_active=True,
                            cage_extrusion=extrusion,
                            max_ray_distance=ray, use_clear=True)
        imgs[ch] = img
        print(f"  bake {name}/{ch} ok")
    route(mats, None)
    for ob in hidden:
        ob.hide_render = False

    if "ao" in imgs:
        c = np.array(imgs["color"].pixels[:], np.float32).reshape(-1, 4)
        ao = np.array(imgs["ao"].pixels[:], np.float32).reshape(-1, 4)[:, :1]
        c[:, :3] *= (0.35 + 0.65 * ao) ** 0.6
        imgs["color"].pixels.foreach_set(c.ravel())
        bpy.data.images.remove(imgs.pop("ao"))
    os.makedirs(TEX_DIR, exist_ok=True)
    label = {"color": "Color", "normal": "Normal", "roughness": "Roughness",
             "metallic": "Metalness"}
    for ch, img in imgs.items():
        path = os.path.join(TEX_DIR, f"{name}_{label[ch]}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.source = "FILE"
        img.filepath = path
        img.colorspace_settings.name = ("sRGB" if ch == "color"
                                        else "Non-Color")
        img.reload()
    low.data.materials.clear()
    low.data.materials.append(pbr_material(f"{name}_PBR", imgs))
    bpy.data.materials.remove(bmat)
    return imgs


def unwrap(obj, margin=0.004):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60),
                             island_margin=margin)
    try:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    except (RuntimeError, TypeError):
        pass
    bpy.ops.object.mode_set(mode="OBJECT")


# ---------------------------------------------------------------------------
# Tahtin govdesi
# ---------------------------------------------------------------------------

FRONT = back_plane(True)
REAR = back_plane(False)


def front_inside(q):
    return (pip(q, OUTLINE) and dist_poly(q, OUTLINE) > 0.32
            and (q - RUNE_UV).length > RUNE_R + 0.02 and q.y > 0.3)


def build_vein_nets():
    nets = {}
    # On: runden disari yayilan ve tac uclarindan inen damarlar
    seeds = []
    for k in range(9):
        a = math.radians(k * 40 + rng.uniform(-12, 12) + 10)
        seeds.append((RUNE_UV + Vector((math.cos(a), math.sin(a)))
                      * (RUNE_R + 0.05), a, rng.uniform(3.5, 5.5)))
    for u, v in ((1.35, 8.5), (-1.35, 8.5), (0.0, 9.5), (2.5, 7.4),
                 (-2.5, 7.4)):
        seeds.append(((u, v), math.radians(-90 + rng.uniform(-15, 15)),
                      2.5))
    for u in (-1.8, 1.8):
        seeds.append(((u, 0.45), math.radians(90 + rng.uniform(-20, 20)),
                      3.0))
    nets["front"] = VeinNet(FRONT, cracks(seeds, front_inside), 0.085,
                            0.07, 0.3)

    # Arka: ortada lav selalesi kanali + yana dallanan catlaklar
    chan = [Vector((0.08 * math.sin(v * 1.7), v))
            for v in np.linspace(8.25, -0.1, 70)]
    nets["fall"] = VeinNet(REAR, [(chan, [1.0] * len(chan))], 0.42, 0.1,
                           0.5, glow=0.9)

    def rear_inside(q):
        return pip(q, OUTLINE) and dist_poly(q, OUTLINE) > 0.3 and q.y > 0.2

    seeds = [(Vector((s * 0.45, v)), math.radians(90 - s * 90 + rng.uniform(
        -25, 25)), rng.uniform(1.2, 2.2))
        for v in (1.5, 3.0, 4.5, 6.0, 7.2) for s in (-1, 1)]
    nets["rear"] = VeinNet(REAR, cracks(seeds, rear_inside), 0.08, 0.065,
                           0.3)

    # Kaide onu ve kolcak dis yanlari
    ped = Plane((0, -1.8, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    seeds = [((u, 1.05), math.radians(90 + rng.uniform(-30, 30)), 1.4)
             for u in (-1.5, -0.5, 0.5, 1.5)]
    nets["pedestal"] = VeinNet(ped, cracks(
        seeds, lambda q: abs(q.x) < 1.85 and 1.0 < q.y < 2.2, step=0.07),
        0.07, 0.06, 0.25)
    for s in (-1, 1):
        pl = Plane((s * 2.975, 0, 0), (0, s, 0), (0, 0, 1), (s, 0, 0))
        seeds = [((u, 1.05), math.radians(90 + rng.uniform(-30, 30)), 2.6)
                 for u in (-1.3, 0.0, 1.3)]
        nets[f"arm{s}"] = VeinNet(pl, cracks(
            seeds, lambda q: abs(q.x) < 1.7 and 1.0 < q.y < 3.45, step=0.08),
            0.075, 0.06, 0.25)
    return nets


def build_body_high(coll, nets):
    parts = [box("p_ped", coll, None, (4.0, 3.6, 1.3), (0, 0, 1.6)),
             box("p_slab", coll, None, (4.3, 3.9, 0.42), (0, -0.05, 2.4))]
    for s in (-1, 1):
        parts.append(box(f"p_arm{s}", coll, None, (0.95, 3.6, 2.6),
                         (s * 2.5, -0.1, 2.3)))
        parts.append(box(f"p_cap{s}", coll, None, (1.2, 3.9, 0.36),
                         (s * 2.5, -0.15, 3.62)))
    back = prism("p_back", coll, None, [(u, v - 0.1 if v == 0 else v)
                                        for u, v in OUTLINE], BACK_DEPTH)
    back.matrix_world = BACK_M
    body = join(parts + [back], "BodyRock_High")
    remesh(body, VOXEL_BODY, smooth_iter=4)
    delete_faces(body, lambda c, n: n.z < -0.8 and c.z < PLAT_TOP + 0.05)

    net_list = list(nets.values())

    def fn(p, n):
        disp, micro = rock_base(p)
        groove = heat = 0.0
        for net in net_list:
            g, h, _ = net.sample(p, n)
            groove = max(groove, g)
            heat = max(heat, h)
        if n.dot(FRONT.n) > 0.4:
            u, v, h = FRONT.to2d(p)
            if abs(h) < 0.5:
                d = (Vector((u, v)) - RUNE_UV).length
                t = sstep(RUNE_R + 0.12, RUNE_R - 0.05, d)
                disp = disp * (1 - t) - 0.07 * t
                micro *= 1 - t
        return disp - groove, heat, micro * (1 - min(1, heat * 2))

    displace(body, fn)
    return body


def rune_local(y_off=0.0):
    """Run bolgesinde sirtlik yerel koordinati -> dunya matrisi."""
    return BACK_M @ Matrix.Translation(
        (RUNE_UV.x, -BACK_DEPTH / 2 + 0.07 + y_off, RUNE_UV.y)) \
        @ Matrix.Rotation(math.radians(90), 4, "X")


def build_gold(coll, mat, body_hi, quality):
    hi = quality == "high"
    sides = 10 if hi else 5
    bm = bmesh.new()
    tree = bvh(body_hi)

    # Sirtlik konturunu izleyen altin serit
    path = inset(OUTLINE, 0.2)
    path = [q for q in path] + [path[0]]
    path = resample(path, 0.03 if hi else 0.11)
    pts, nrm = [], []
    for q in path:
        if q.y < 3.05:   # oturan oyuncunun arkasi: serit yalnizca ust kisimda
            if len(pts) > 2:
                sweep_bm(bm, pts, [0.075] * len(pts), nrm, sides, 0.55)
            pts, nrm = [], []
            continue
        hit = tree.ray_cast(FRONT.to3d(q, 0.8), -FRONT.n, 2.0)
        if hit[0] is not None:
            pts.append(hit[0] + hit[1] * 0.02)
            nrm.append(hit[1])
    if len(pts) > 2:
        sweep_bm(bm, pts, [0.075] * len(pts), nrm, sides, 0.55)

    # Oturak on kenari seridi
    pts, nrm = [], []
    for x in np.linspace(-2.05, 2.05, 90 if hi else 24):
        hit = tree.ray_cast(Vector((x, -3.0, 2.42)), Vector((0, 1, 0)), 2.0)
        if hit[0] is not None:
            pts.append(hit[0] + hit[1] * 0.02)
            nrm.append(hit[1])
    sweep_bm(bm, pts, [0.07] * len(pts), nrm, sides, 0.55)

    # Run cercevesi (iki halka + 4 sivri + goz bebegi)
    M = rune_local()
    tmp = []
    tmp.append(torus("g_r1", coll, None, RUNE_R - 0.16, 0.075,
                     major=64 if hi else 32, minor=10 if hi else 6))
    tmp.append(torus("g_r2", coll, None, RUNE_R - 0.02, 0.035,
                     major=64 if hi else 32, minor=8 if hi else 5))
    for k in range(4):
        a = k * math.pi / 2
        t = prism(f"g_sp{k}", coll, None, [(-0.1, 0), (0.1, 0), (0, 0.32)],
                  0.06)
        t.matrix_world = (Matrix.Rotation(a - math.pi / 2, 4, "Z")
                          @ Matrix.Translation((0, RUNE_R - 0.06, 0))
                          @ Matrix.Rotation(-math.pi / 2, 4, "X"))
        tmp.append(t)
    pupil = prism("g_pupil", coll, None, lens(0.06, 0.62), 0.05,
                  rot=(0, 0, 0))
    pupil.matrix_world = Matrix.Translation((0, 0, 0.06)) \
        @ Matrix.Rotation(-math.pi / 2, 4, "X")
    tmp.append(pupil)
    for t in tmp:
        t.matrix_world = M @ t.matrix_world

    # Pence: her kurede 4 altin tirnak + taban halkasi
    for s, c in ORBS.items():
        tmp.append(torus(f"g_wrist{s}", coll, None, 0.3, 0.075,
                         (c.x, c.y, c.z - ORB_R + 0.02),
                         major=32 if hi else 16, minor=10 if hi else 6))
        for k in range(4):
            phi = math.radians(45 + 90 * k)
            ctrl = []
            for th in (-80, -55, -25, 5, 32):
                th = math.radians(th)
                d = Vector((math.cos(phi) * math.cos(th),
                            math.sin(phi) * math.cos(th), math.sin(th)))
                ctrl.append(c + d * (ORB_R + 0.06))
            th = math.radians(55)
            ctrl.append(c + Vector((math.cos(phi) * math.cos(th),
                                    math.sin(phi) * math.cos(th),
                                    math.sin(th))) * (ORB_R - 0.03))
            pts = spline(ctrl, 24 if hi else 9)
            rad = [0.1 * (1 - i / (len(pts) - 1)) ** 0.8 + 0.012
                   for i in range(len(pts))]
            sweep_bm(bm, pts, rad, None, sides, 1.0)
    obj = mesh_obj(f"Gold_{quality}", bm, coll, mat)
    return single_material(join([obj] + tmp, f"Gold_{quality}"), mat)


def lens(w, h, n=12):
    pts = []
    for i in range(n + 1):
        t = math.pi * i / n
        pts.append((w * math.sin(t) ** 1.2, h / 2 * math.cos(t)))
    for i in range(n - 1, 0, -1):
        t = math.pi * i / n
        pts.append((-w * math.sin(t) ** 1.2, h / 2 * math.cos(t)))
    return pts


def horn_points(s, n):
    ctrl = [BACK_M @ Vector((s * 2.0, 0.0, 6.6)),
            (s * 3.3, 2.75, 8.15), (s * 4.25, 2.95, 9.55),
            (s * 4.4, 3.35, 11.0), (s * 3.75, 3.85, 12.05),
            (s * 3.2, 4.1, 12.3)]
    return spline(ctrl, n)


def horn_radius(t):
    return 0.6 * (1 - t) ** 0.85 + 0.012


def build_horn(coll, mat, s, quality, t0=0.0, t1=0.88, name=None):
    hi = quality == "high"
    n = 170 if hi else 40
    sides = 28 if hi else 10
    allp = horn_points(s, 400)
    i0, i1 = int(t0 * 399), int(t1 * 399)
    pts = resample(allp[i0:i1 + 1], (horn_len(allp) * (t1 - t0)) / n)
    ts = [t0 + (t1 - t0) * i / (len(pts) - 1) for i in range(len(pts))]

    def ridge(t):
        return max(0.0, math.sin(t * 2 * math.pi * 13)) ** 2 * (1 - t)

    if hi:
        rad = [horn_radius(t) * (1 + 0.075 * ridge(t)) for t in ts]

        def rfn(i, a):
            p = pts[i]
            return 1 + 0.035 * noise.noise(p * 3.0 + Vector((a, 0, 0)))
    else:
        rad = [horn_radius(t) * 1.03 for t in ts]
        rfn = None
    bm = bmesh.new()
    sweep_bm(bm, pts, rad, None, sides, 1.0, rfn=rfn)
    obj = mesh_obj(name or f"Horn{s}_{quality}", bm, coll, mat)
    if hi:
        heat, band = [], []
        for t in ts:
            heat += [sstep(0.55, 0.88, t) ** 1.4] * sides
            band += [ridge(t)] * sides
        nv = len(obj.data.vertices)
        set_attr(obj.data, "heat", heat[:nv])
        set_attr(obj.data, "micro", band[:nv])
    return obj


def horn_len(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

def disk(name, coll, R, z0, z1, wob, seed, seg=128):
    bm = bmesh.new()
    lo, hi = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        r = R * (1 + wob * noise.noise(Vector((math.cos(a) * 1.4 + seed,
                                               math.sin(a) * 1.4, seed))))
        lo.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, z0)))
        hi.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, z1)))
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    return mesh_obj(name, bm, coll, None, smooth=False)


def river_inside(q):
    r = q.length
    if r > 7.2 or r < 2.4:
        return False
    if abs(q.x) < 1.5 and q.y < -4.9:
        return False
    if any((q - v).length < 1.15 for v in VENTS):
        return False
    return (q - POOL).length > POOL_R + 0.05 or q.y > POOL.y + 0.9


def build_river_net():
    seeds = []
    for ang, r in ((-62, 3.0), (-118, 3.0), (-12, 3.45), (-168, 3.45)):
        a = math.radians(ang)
        seeds.append(((math.cos(a) * r, math.sin(a) * r), a, 5.0))
    for s in (-1, 1):
        a = math.radians(90 - s * 68)
        seeds.append(((s * 0.95, POOL.y + 0.25), a, 5.0))
    lines = cracks(seeds, river_inside, step=0.15, jitter=0.22, branch=0.035,
                   bias=0.2, max_depth=1)
    lines = [(pts, [1.0] * len(pts)) for pts, _ in lines]
    top = Plane((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    return VeinNet(top, lines, 0.24, 0.13, 0.9, min_dot=-2, max_h=9,
                   glow=0.85)


def build_platform_high(coll, river):
    parts = [disk("t1", coll, 7.2, -0.05, 0.5, 0.045, 1.0),
             disk("t2", coll, 5.4, 0.45, PLAT_TOP, 0.05, 7.0),
             box("st1", coll, None, (2.8, 1.1, 0.5), (0, -5.75, 0.5)),
             box("st2", coll, None, (3.0, 1.0, 0.3), (0, -7.4, 0.12))]
    for i, v in enumerate(VENTS):
        parts.append(cyl(f"v{i}", coll, None, 0.95, 1.8,
                         (v.x, v.y, 1.35), r2=0.36, verts=24, smooth=False))
    plat = join(parts, "Platform_High")
    remesh(plat, VOXEL_PLAT, smooth_iter=3)
    delete_faces(plat, lambda c, n: n.z < -0.7 and c.z < 0.05)

    def fn(p, n):
        disp, micro = rock_base(p, plates=1.15, amp=1.15)
        g, h, dist = river.sample(p, n)
        q = Vector((p.x, p.y))
        prox = math.exp(-dist / 1.2)
        dp = (q - POOL).length
        if p.z > PLAT_TOP - 0.15:
            t = sstep(POOL_R + 0.2, POOL_R - 0.25, dp)
            disp = disp * (1 - t) - 0.22 * t
            h = max(h, t, 0.8 * math.exp(-max(0, dp - POOL_R) / 0.5))
            prox = max(prox, math.exp(-max(0, dp - POOL_R) / 1.0))
        for v in VENTS:
            dv = (q - v).length
            if p.z > 1.9:
                t = sstep(0.42, 0.15, dv)
                disp -= 0.38 * t
                h = max(h, t)
            prox = max(prox, math.exp(-dv / 1.3) * 0.8)
        return disp - g, h, micro * (0.15 + 0.85 * prox) * (1 - min(1, h * 2))

    displace(plat, fn)
    return plat


# ---------------------------------------------------------------------------
# Neon parcalar
# ---------------------------------------------------------------------------

def ribbon_from_hits(tree, origins, direction, width, flat, lift=0.0,
                     sides=8):
    pts, nrm, rr = [], [], []
    for o, w in zip(origins, width):
        hit = tree.ray_cast(o, direction, 4.0)
        if hit[0] is not None:
            pts.append(hit[0] + hit[1] * lift)
            nrm.append(hit[1])
            rr.append(w)
    return pts, nrm, rr


def build_lavafall(coll, mat, body_hi, plat_hi):
    tb, tp = bvh(body_hi), bvh(plat_hi)
    vs = np.linspace(8.25, 0.2, 90)
    origins = [REAR.to3d((0.08 * math.sin(v * 1.7), v), 0.8) for v in vs]
    widths = [0.24 + 0.14 * (1 - v / 8.25) for v in vs]
    p1, n1, r1 = ribbon_from_hits(tb, origins, -REAR.n, widths, 0.35, 0.0)
    base = p1[-1]
    tail = [Vector((0.0, y, 4.0)) for y in np.linspace(base.y + 0.15,
                                                       POOL.y, 14)]
    p2, n2, r2 = ribbon_from_hits(tp, tail, Vector((0, 0, -1)),
                                  [0.4] * len(tail), 0.3, -0.02)
    bm = bmesh.new()
    sweep_bm(bm, p1 + p2, r1 + r2, n1 + n2, sides=10, flat=0.35)
    # tepedeki kaynak (catlak agzi)
    src = p1[0]
    s = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8,
                                  radius=0.28)
    bmesh.ops.scale(bm, vec=(1.3, 0.5, 0.8), verts=s["verts"])
    bmesh.ops.translate(bm, vec=src, verts=s["verts"])
    return mesh_obj("Lavafall", bm, coll, mat)


def build_pool(coll, mat, plat_hi):
    bm = bmesh.new()
    rings, seg = 8, 40
    z = PLAT_TOP - 0.1
    center = bm.verts.new((POOL.x, POOL.y, z))
    prev = None
    for i in range(1, rings + 1):
        r = POOL_R * 1.05 * i / rings
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            p = Vector((POOL.x + math.cos(a) * r, POOL.y + math.sin(a) * r, z))
            p.z += 0.025 * noise.noise(p * 2.5)
            ring.append(bm.verts.new(p))
        for j in range(seg):
            k = (j + 1) % seg
            if prev is None:
                bm.faces.new((center, ring[j], ring[k]))
            else:
                bm.faces.new((prev[j], ring[j], ring[k], prev[k]))
        prev = ring
    return mesh_obj("LavaPool", bm, coll, mat)


def build_vent_lava(coll, mat, plat_hi):
    tree = bvh(plat_hi)
    out = []
    for i, v in enumerate(VENTS):
        hit = tree.ray_cast(Vector((v.x, v.y, 5)), Vector((0, 0, -1)), 9)
        z = hit[0].z + 0.06 if hit[0] else 2.0
        bm = bmesh.new()
        s = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8,
                                      radius=0.3)
        bmesh.ops.scale(bm, vec=(1, 1, 0.35), verts=s["verts"])
        bmesh.ops.translate(bm, vec=(v.x, v.y, z), verts=s["verts"])
        out.append(mesh_obj(f"VentLava_{i + 1}", bm, coll, mat))
    return out


def build_rune(coll, mat):
    M = rune_local(-0.02)
    parts = [torus("RuneGlow", coll, None, RUNE_R - 0.31, 0.05, major=56,
                   minor=8)]
    eye = prism("rg_eye", coll, None, lens(0.2, 0.9), 0.05)
    eye.matrix_world = Matrix.Translation((0, 0, 0.02)) \
        @ Matrix.Rotation(-math.pi / 2, 4, "X")
    parts.append(eye)
    for k in range(6):
        a = math.radians(30 + 60 * k)
        if k in (1, 4):
            continue
        d = box(f"rg_t{k}", coll, None, (0.09, 0.09, 0.05),
                (math.cos(a) * 0.48, math.sin(a) * 0.48, 0.0),
                rot=(0, 0, math.pi / 4))
        parts.append(d)
    for p in parts:
        p.matrix_world = M @ p.matrix_world
    return single_material(join(parts, "RuneGlow"), mat)


def flame_bm(bm, base, up, side, height, width, bend, seed, sides=16,
             rings=22):
    fwd = up.cross(side).normalized()
    prev = None
    for i in range(rings + 1):
        t = i / rings
        r = width * min(1.0, t * 5) ** 0.5 * (1 - t) ** 0.7
        c = base + up * (t * height) + side * (bend * t * t)
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            wob = 1 + 0.22 * t * math.sin(3 * a + t * 9 + seed)
            ring.append(bm.verts.new(c + side * (math.cos(a) * r * wob)
                                     + fwd * (math.sin(a) * r * 0.55 * wob)))
        if prev:
            for j in range(sides):
                k = (j + 1) % sides
                bm.faces.new((prev[j], ring[j], ring[k], prev[k]))
        else:
            bm.faces.new(list(reversed(ring)))
        prev = ring


def build_flames(coll, outer, inner):
    up = BACK_R @ Vector((0, 0, 1))
    side = BACK_R @ Vector((1, 0, 0))
    spots = [((-2.0, 7.25), 1.3, 0.42, -0.25), ((2.0, 7.25), 1.3, 0.42, 0.25),
             ((-0.6, 7.95), 1.7, 0.5, -0.15), ((0.6, 7.95), 1.7, 0.5, 0.15),
             ((0.0, 9.3), 2.3, 0.55, 0.0)]
    objs = []
    for i, ((u, v), h, w, bend) in enumerate(spots):
        y = 0.25 if i == 4 else 0.0
        base = BACK_M @ Vector((u, y, v - 0.25))
        for kind, mat, sc in (("Flame", outer, 1.0), ("FlameCore", inner,
                                                      0.62)):
            bm = bmesh.new()
            flame_bm(bm, base + up * 0.05 * (sc < 1), up, side, h * sc,
                     w * sc, bend * sc, seed=i * 1.7)
            o = mesh_obj(f"{kind}_{i + 1}", bm, coll, mat)
            o.data.transform(Matrix.Translation(-base))
            o.location = base
            objs.append(o)
    return objs


def build_cushion(coll, velvet, gold):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=56, v_segments=28, radius=1.0)
    a, b, c, e = 1.48, 1.32, 0.2, 0.22
    tufts = [Vector((x, y)) for x in (-0.8, 0.0, 0.8) for y in (-0.5, 0.45)]
    for v in bm.verts:
        x, y, z = v.co
        p = Vector((math.copysign(abs(x) ** e, x) * a,
                    math.copysign(abs(y) ** e, y) * b,
                    math.copysign(abs(z) ** e, z) * c))
        if p.z > 0:
            for t in tufts:
                p.z -= 0.07 * math.exp(-((p.xy - t).length_squared) / 0.025)
        v.co = p
    center = Vector((0, -0.15, 2.82))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    seat = mesh_obj("Seat", bm, coll, velvet)
    bm = bmesh.new()
    for t in tufts:
        s = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6,
                                      radius=0.06)
        bmesh.ops.scale(bm, vec=(1, 1, 0.6), verts=s["verts"])
        bmesh.ops.translate(bm, vec=(t.x, t.y - 0.15, 2.82 + c - 0.065),
                            verts=s["verts"])
    buttons = mesh_obj("Seat_Buttons", bm, coll, gold)
    return seat, buttons


def build_magma_rock_high(coll, mat):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=6 if not QUICK else 4,
                               radius=1.0)
    rock = mesh_obj("MagmaRock_High", bm, coll, mat)
    rock.data.transform(Matrix.Diagonal((1.0, 0.82, 0.72, 1)))
    rock.data.update()

    def fn(p, n):
        big = noise.fractal(p * 0.9 + Vector((4, 4, 4)), 1.0, 2.0, 3)
        d, cells = noise.voronoi(p * 1.8, distance_metric="DISTANCE",
                                 exponent=2.5)
        crack = max(0.0, 1.0 - (d[1] - d[0]) / 0.12)
        plate = noise.noise(cells[0] * 5.3)
        disp = 0.2 * big + 0.07 * plate - 0.09 * crack ** 2
        return disp, crack ** 1.5, 0.0

    displace(rock, fn)
    return rock


# ---------------------------------------------------------------------------
# Animasyon (onizleme)
# ---------------------------------------------------------------------------

def cyclic(obj_or_data):
    ad = obj_or_data.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        if not any(m.type == "CYCLES" for m in fc.modifiers):
            fc.modifiers.new("CYCLES")


def animate(scene, objs, rocks):
    # Magma kayalari: merkez etrafinda yorunge + inip kalkma
    pivot = bpy.data.objects.new("RockOrbit", None)
    scene.collection.objects.link(pivot)
    for r in rocks:
        mw = r.matrix_world.copy()
        r.parent = pivot
        r.matrix_world = mw
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert("rotation_euler", index=2, frame=1)
    pivot.rotation_euler = (0, 0, 2 * math.pi)
    pivot.keyframe_insert("rotation_euler", index=2, frame=481)
    cyclic(pivot)
    for fc in _curves(pivot):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    for i, r in enumerate(rocks):
        z0 = r.location.z
        for fr, dz in ((1, 0), (40 + i * 7, 0.35), (120, 0)):
            r.location.z = z0 + dz
            r.keyframe_insert("location", index=2, frame=fr)
        r.rotation_euler.z += 0
        rz = r.rotation_euler.copy()
        r.keyframe_insert("rotation_euler", frame=1)
        r.rotation_euler = (rz.x + 0.6, rz.y + 0.4, rz.z + 1.2)
        r.keyframe_insert("rotation_euler", frame=240)
        r.rotation_euler = rz
        r.keyframe_insert("rotation_euler", frame=480)
        cyclic(r)
    # Alevler titrer
    for o in objs:
        if o.name.startswith("Flame"):
            k = hash(o.name) % 7
            for fr, s in ((1, (1, 1, 1)), (6 + k, (1.08, 1.0, 1.12)),
                          (14 + k, (0.94, 1.0, 0.93)), (24, (1, 1, 1))):
                o.scale = s
                o.keyframe_insert("scale", frame=fr)
            cyclic(o)
    # Lav malzemeleri nabiz gibi atar
    for i, (val, base) in enumerate(PULSES):
        out = val.outputs[0]
        for fr, f in ((1, 1.0), (30 + i % 3 * 5, 1.35), (60, 1.0)):
            out.default_value = base * f
            out.keyframe_insert("default_value", frame=fr)
        nt = val.id_data
        cyclic(nt)
    for m in bpy.data.materials:
        if "mapping" in m:
            mp = m.node_tree.nodes[m["mapping"]]
            flow = Vector(m["flow"])
            mp.inputs["Location"].default_value = (0, 0, 0)
            mp.inputs["Location"].keyframe_insert("default_value", frame=1)
            mp.inputs["Location"].default_value = flow
            mp.inputs["Location"].keyframe_insert("default_value", frame=240)
            for fc in _curves(m.node_tree):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            cyclic(m.node_tree)


def _curves(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        return [fc for layer in ad.action.layers for strip in layer.strips
                for bag in strip.channelbags for fc in bag.fcurves]


# ---------------------------------------------------------------------------
# Onizleme sahnesi
# ---------------------------------------------------------------------------

def build_preview(scene, fx_coll):
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.006, 0.005, 0.008, 1)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    ground = bpy.data.objects.new("Ground", bpy.data.meshes.new("Ground"))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=80)
    bm.to_mesh(ground.data)
    bm.free()
    ground.location.z = -0.02
    ground.data.materials.append(rock_material(
        "Ash", (0.004, 0.0035, 0.0035), (0.012, 0.01, 0.009), (0.75, 0.95)))
    fx_coll.objects.link(ground)

    def light(name, kind, loc, energy, color, size=1.0, target=(0, 0, 5)):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if kind == "AREA":
            ld.size = size
        else:
            ld.shadow_soft_size = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        d = Vector(target) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        fx_coll.objects.link(lo)

    light("Rim_Cool", "AREA", (-12, 14, 16), 9000, (0.45, 0.6, 1.0), 8)
    light("Rim_Cool2", "AREA", (13, 12, 10), 4000, (0.5, 0.62, 1.0), 6)
    light("Fill", "AREA", (4, -20, 9), 1500, (1.0, 0.85, 0.75), 10)
    light("Under", "POINT", (0, -3.5, 1.4), 300, (1.0, 0.35, 0.08), 1.0)

    # Kor parcaciklari (yalnizca onizleme; Roblox'ta ParticleEmitter)
    bm = bmesh.new()
    r = random.Random(5)
    for _ in range(110):
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(0.5, 6.5)
        z = 1.0 + r.random() ** 1.6 * 11.5
        s = bmesh.ops.create_icosphere(bm, subdivisions=1,
                                       radius=r.uniform(0.01, 0.03))
        bmesh.ops.translate(bm, vec=(math.cos(a) * d, math.sin(a) * d, z),
                            verts=s["verts"])
    emb = mesh_obj("Embers", bm, fx_coll, lava_material("EmberGlow", 40, 0,
                                                        1.0))
    emb.visible_shadow = False

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    fx_coll.objects.link(cam)
    scene.camera = cam
    return cam


def aim(cam, target, dist, height, angle, lens):
    t = Vector(target)
    cam.location = t + Vector((math.sin(angle) * dist,
                               -math.cos(angle) * dist, height))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z",
                                                          "Y").to_euler()
    cam.data.lens = lens


def setup_compositor(scene):
    try:
        tree = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        tree.interface.new_socket("Image", in_out="OUTPUT",
                                  socket_type="NodeSocketColor")
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        out = tree.nodes.new("NodeGroupOutput")
        for name, val in (("Type", "Bloom"), ("Quality", "High"),
                          ("Threshold", 1.0), ("Strength", 0.6),
                          ("Size", 0.6)):
            if name in gl.inputs:
                try:
                    gl.inputs[name].default_value = val
                except (TypeError, ValueError):
                    pass
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], out.inputs[0])
        scene.compositing_node_group = tree
        scene.render.compositor_device = "CPU"
        scene.render.use_compositing = True
        print("compositor: bloom acik")
    except Exception as exc:  # compositor API surume gore degisir
        print("compositor atlandi:", exc)


def render_views(scene, cam):
    os.makedirs(RENDER_DIR, exist_ok=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24 if QUICK else 160
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.view_settings.exposure = -0.3
    w, h = (640, 480) if QUICK else (1280, 960)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    setup_compositor(scene)
    scene.frame_set(40)
    views = [
        ("Hero", (0, 0.5, 5.6), 24, 6.0, math.radians(-28), 42),
        ("CloseUp", (0, 0.4, 5.6), 10.5, 2.2, math.radians(-14), 38),
        ("Back", (0, 1.5, 5.0), 21, 6.5, math.radians(150), 40),
        ("LowAngle", (0, 0.5, 6.4), 15.5, -4.2, math.radians(22), 26),
    ]
    for name, tgt, dist, hgt, ang, lens in views:
        aim(cam, tgt, dist, hgt, ang, lens)
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("render:", name)


# ---------------------------------------------------------------------------
# Ana akis
# ---------------------------------------------------------------------------

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, 240

    work = bpy.data.collections.new("High")
    scene.collection.children.link(work)
    out = bpy.data.collections.new("LavaThrone")
    scene.collection.children.link(out)
    fx = bpy.data.collections.new("PreviewOnly")
    scene.collection.children.link(fx)

    m_obsidian = rock_material("Obsidian", (0.012, 0.01, 0.012),
                               (0.05, 0.04, 0.042), (0.16, 0.42))
    m_basalt = rock_material("Basalt", (0.012, 0.011, 0.011),
                             (0.05, 0.042, 0.038), (0.45, 0.8))
    m_gold = gold_material("Gold")
    m_horn = horn_material("Horn")
    m_magma = rock_material("MagmaRock", (0.015, 0.012, 0.012),
                            (0.06, 0.045, 0.04), (0.35, 0.7), 1.6)
    lava_v = lava_material("Lava_Veins", 9.0, 0.0, 6.0, (0, 0, -2))
    lava_f = lava_material("Lava_Flow", 7.0, 0.35, 2.2, (0, 0, -3))
    lava_r = lava_material("Lava_River", 7.0, 0.45, 1.8, (1.5, 1.5, 0))
    lava_o = lava_material("Lava_Orb", 14.0, 0.0, 4.0, (0, 0, 1))
    fl_out = flame_material("Flame_Outer", (1.0, 0.28, 0.03), 18.0)
    fl_in = flame_material("Flame_Inner", (1.0, 0.72, 0.25), 26.0)
    velvet = simple_material("Velvet", (0.07, 0.002, 0.008), 0.8, 0, 1.0)
    gold_simple = simple_material("GoldButtons", (1.0, 0.72, 0.3), 0.25, 1)

    # --- Govde ---------------------------------------------------------
    print("Govde (yuksek detay)...")
    nets = build_vein_nets()
    body_hi = build_body_high(work, nets)
    body_hi.data.materials.append(m_obsidian)
    gold_hi = build_gold(work, m_gold, body_hi, "high")
    horns_hi = [build_horn(work, m_horn, s, "high") for s in (-1, 1)]
    print(f"  yuksek: govde {tris(body_hi)}, altin {tris(gold_hi)} ucgen")

    print("Govde (oyun modeli)...")
    body_lo = make_low(body_hi, "BodyRock_Low", 9000 if not QUICK else 3000,
                       out)
    gold_lo = build_gold(out, m_gold, body_hi, "low")
    horns_lo = [build_horn(out, m_horn, s, "low") for s in (-1, 1)]
    throne = join([body_lo, gold_lo] + horns_lo, "ThroneBody")
    unwrap(throne)
    bake_set("ThroneBody", throne, [body_hi, gold_hi] + horns_hi, TEX,
             ["color", "normal", "roughness", "metallic", "ao"])

    # --- Platform ------------------------------------------------------
    print("Platform...")
    river = build_river_net()
    plat_hi = build_platform_high(work, river)
    plat_hi.data.materials.append(m_basalt)
    plat_lo = make_low(plat_hi, "Platform", 9500 if not QUICK else 3000, out)
    unwrap(plat_lo)

    # --- Neon parcalar (bake'ten once: AO icin sahnede olsunlar) ------
    print("Neon parcalar...")
    neon = [
        nets["front"].tubes(out, "LavaVeins_Front", lava_v, body_hi, 0.055),
        nets["rear"].tubes(out, "LavaVeins_Back", lava_v, body_hi, 0.05),
        join([nets["pedestal"].tubes(out, "a", lava_v, body_hi, 0.045,
                                     step=0.07),
              nets["arm-1"].tubes(out, "b", lava_v, body_hi,
                                                   0.045, step=0.08),
              nets["arm1"].tubes(out, "c", lava_v, body_hi, 0.045,
                                 step=0.08)], "LavaVeins_Base"),
        build_lavafall(out, lava_f, body_hi, plat_hi),
        build_pool(out, lava_f, plat_hi),
        river.tubes(out, "LavaRivers", lava_r, plat_hi, 0.2, sides=8,
                    flat=0.32, lift=0.0, step=0.12, h=6.0),
        build_rune(out, lava_o),
    ]
    neon += build_vent_lava(out, lava_f, plat_hi)
    for s in (-1, 1):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14,
                                  radius=ORB_R)
        bmesh.ops.translate(bm, vec=ORBS[s], verts=bm.verts)
        neon.append(mesh_obj(f"ClawOrb_{'L' if s < 0 else 'R'}", bm, out,
                             lava_o))
        neon.append(build_horn(out, lava_v, s, "low", 0.86, 1.0,
                               f"HornTip_{'L' if s < 0 else 'R'}"))
    neon += build_flames(out, fl_out, fl_in)
    seat, buttons = build_cushion(out, velvet, gold_simple)

    bake_set("Platform", plat_lo, [plat_hi], TEX,
             ["color", "normal", "roughness", "ao"], extrusion=0.1, ray=0.3)

    # --- Magma kayalari ------------------------------------------------
    print("Magma kayalari...")
    rock_hi = build_magma_rock_high(work, m_magma)
    rock_lo = make_low(rock_hi, "MagmaRock_1", 520, out)
    unwrap(rock_lo, 0.01)
    bake_set("MagmaRock", rock_lo, [rock_hi], ROCK_TEX,
             ["color", "normal", "roughness", "ao"], extrusion=0.15, ray=0.4)
    rocks = [rock_lo]
    for i in range(1, 6):
        r = rock_lo.copy()
        r.data = rock_lo.data.copy()  # FBX: ortak mesh malzeme uyarisi verir
        r.name = f"MagmaRock_{i + 1}"
        out.objects.link(r)
        rocks.append(r)
    for i, r in enumerate(rocks):
        a = math.radians(15 + i * 60 + rng.uniform(-12, 12))
        d = rng.uniform(5.0, 5.8)
        r.location = (math.cos(a) * d, math.sin(a) * d,
                      rng.uniform(3.2, 7.0))
        r.rotation_euler = (rng.uniform(0, 3), rng.uniform(0, 3),
                            rng.uniform(0, 3))
        s = rng.uniform(0.42, 0.7)
        r.scale = (s, s, s)

    # Yuksek detayli kaynaklar artik gereksiz
    for ob in list(work.objects):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.collections.remove(work)

    # --- Kontrol + disa aktarma ---------------------------------------
    total = 0
    for ob in out.objects:
        t = tris(ob)
        total += t
        if t > TRI_LIMIT:
            raise RuntimeError(f"{ob.name}: {t} ucgen > {TRI_LIMIT}")
        print(f"  {ob.name:<18} {t:>6} ucgen")
    print(f"[OK] LavaThrone: {len(out.objects)} parca, {total} ucgen")

    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in out.objects:
        ob.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(EXPORT_DIR, "LavaThrone.fbx"),
        use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
        bake_anim=False, path_mode="COPY", embed_textures=True)

    animate(scene, list(out.objects), rocks)
    cam = build_preview(scene, fx)
    aim(cam, (0, 0.5, 5.6), 24, 6.0, math.radians(-28), 42)
    bpy.ops.file.make_paths_relative() if bpy.data.filepath else None
    blend = os.path.join(EXPORT_DIR, "LavaThrone.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, relative_remap=True)
    if RENDER:
        render_views(scene, cam)
        bpy.ops.wm.save_as_mainfile(filepath=blend, relative_remap=True)
    print("Bitti:", EXPORT_DIR)


if __name__ == "__main__":
    main()

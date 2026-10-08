"""
Strawberry Beanie Set - Roblox UGC asset builder for Blender.

Builds, fully procedurally:
  * SB_Head            - chibi head mesh with the painted face texture (skin, eyes, blush, freckles)
  * SB_Hair            - long wavy blonde hair (bangs, front locks, back hair)      < 4000 tris
  * SB_Beanie          - slouchy pink ribbed beanie with strawberry + flower patch  < 4000 tris
  * SB_HairBeanieCombo - hair + beanie as a single accessory (lower LOD)            < 4000 tris
plus textures, Roblox classic Shirt/Pants templates, a face decal, FBX exports,
a .blend file, preview renders and the mesh data used by the Roblox rig builder.

Run headless:   python3 build_strawberry_set.py            (pip install bpy)
           or:  blender -b -P build_strawberry_set.py
Inside Blender (e.g. via blender-mcp "execute_blender_code"): set SB_OUT_DIR env
var or edit OUT_DIR below; renders are skipped unless SB_RENDER=1.

Units: 1 Blender unit = 1 Roblox stud (scene unit scale 0.01, centimetres).
Orientation: character faces -Y in Blender, +Z is up (Roblox FBX convention).
"""
import json
import math
import os
import random
import re

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    OUT_DIR = os.environ.get("SB_OUT_DIR", os.path.dirname(_HERE))
except NameError:  # executed via exec() inside Blender
    OUT_DIR = os.environ.get("SB_OUT_DIR", os.path.expanduser("~/StrawberrySet"))

TEX_DIR = os.path.join(OUT_DIR, "textures")
EXP_DIR = os.path.join(OUT_DIR, "exports")
PREV_DIR = os.path.join(OUT_DIR, "previews")
RBX_DIR = os.path.join(OUT_DIR, "roblox")
for _d in (TEX_DIR, EXP_DIR, PREV_DIR, RBX_DIR):
    os.makedirs(_d, exist_ok=True)

DO_RENDER = (bpy.app.background or os.environ.get("SB_RENDER") == "1") and os.environ.get("SB_RENDER") != "0"
random.seed(7)
RNG = np.random.default_rng(7)

# --------------------------------------------------------------------------- colours
SKIN = (245, 215, 195)
HAIR = (240, 218, 160)
BEANIE_PINK = (236, 168, 178)
CREAM = (246, 239, 226)

# --------------------------------------------------------------------------- head shape
# Superellipsoid "chibi block" head, centre at origin, ~1.24 x 1.16 x 1.24 studs.
HA, HB, HC, HN = 0.62, 0.58, 0.62, 2.8


def head_r(d):
    s = (abs(d.x) / HA) ** HN + (abs(d.y) / HB) ** HN + (abs(d.z) / HC) ** HN
    return s ** (-1.0 / HN)


def ang_dir(a, e):
    """a: degrees around (0 = front/-Y, +90 = character's left/+X), e: elevation degrees."""
    ar, er = math.radians(a), math.radians(e)
    return Vector((math.sin(ar) * math.cos(er), -math.cos(ar) * math.cos(er), math.sin(er)))


def surf(a, e, off=0.0):
    d = ang_dir(a, e)
    return d * (head_r(d) + off)


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------- mesh builder
def _face_normal(pts):
    if len(pts) == 4:
        return (pts[2] - pts[0]).cross(pts[3] - pts[1])
    return (pts[1] - pts[0]).cross(pts[2] - pts[0])


class MeshBuilder:
    def __init__(self):
        self.V, self.F, self.UV = [], [], []

    def add(self, part, ref=lambda c: Vector((0, 0, 0))):
        V, F, UV = part
        score = 0.0
        for f in F:
            pts = [V[i] for i in f]
            c = sum(pts, Vector()) / len(pts)
            score += _face_normal(pts).dot(c - ref(c))
        if score < 0:  # make the whole part face outward
            F = [tuple(reversed(f)) for f in F]
            UV = [list(reversed(u)) for u in UV]
        base = len(self.V)
        self.V.extend(V)
        self.F.extend(tuple(base + i for i in f) for f in F)
        self.UV.extend(UV)

    def tris(self):
        return sum(len(f) - 2 for f in self.F)

    def to_object(self, name, material):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.V], [], self.F)
        uvl = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for k, li in enumerate(poly.loop_indices):
                uvl.data[li].uv = self.UV[poly.index][k]
        me.validate()
        me.update()
        me.shade_smooth()
        me.materials.append(material)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def grid_part(cols, rows, pos_fn, uv_fn, keep_fn=None, top=None, bottom=None, a0=-180.0):
    """Lat/long style grid. rows: ordered row params; columns span 360 deg from a0.
    top/bottom: optional pole row params. uv_fn(row, ang, face_centre_ang)."""
    step = 360.0 / cols
    angs = [a0 + step * j for j in range(cols)]
    V, idx = [], {}
    for i, r in enumerate(rows):
        for j, a in enumerate(angs):
            idx[i, j] = len(V)
            V.append(pos_fn(r, a))
    F, UV = [], []
    for i in range(len(rows) - 1):
        r1, r2 = rows[i], rows[i + 1]
        for j in range(cols):
            j2 = (j + 1) % cols
            a1, a2 = angs[j], angs[j] + step
            ac, rc = (a1 + a2) / 2, (r1 + r2) / 2
            if keep_fn and not keep_fn(rc, ac):
                continue
            F.append((idx[i, j], idx[i, j2], idx[i + 1, j2], idx[i + 1, j]))
            UV.append([uv_fn(r1, a1, ac), uv_fn(r1, a2, ac), uv_fn(r2, a2, ac), uv_fn(r2, a1, ac)])
    for pole, ri, is_top in ((top, len(rows) - 1, True), (bottom, 0, False)):
        if pole is None:
            continue
        pi = len(V)
        V.append(pos_fn(pole, 0.0))
        r = rows[ri]
        for j in range(cols):
            j2 = (j + 1) % cols
            a1, a2 = angs[j], angs[j] + step
            ac = (a1 + a2) / 2
            if keep_fn and not keep_fn((r + pole) / 2, ac):
                continue
            if is_top:
                F.append((idx[ri, j], idx[ri, j2], pi))
                UV.append([uv_fn(r, a1, ac), uv_fn(r, a2, ac), uv_fn(pole, ac, ac)])
            else:
                F.append((pi, idx[ri, j2], idx[ri, j]))
                UV.append([uv_fn(pole, ac, ac), uv_fn(r, a2, ac), uv_fn(r, a1, ac)])
    used = sorted({i for f in F for i in f})
    remap = {o: n for n, o in enumerate(used)}
    return [V[i] for i in used], [tuple(remap[i] for i in f) for f in F], UV


def ellipsoid_part(center, ax, ay, az, segs, rings, rect, shape_fn=None):
    """ax/ay/az: scaled local axes (ay = 'up' of the ellipsoid). rect = (u0, v0, w, h)."""
    u0, v0, w, h = rect

    def pos(e, a):
        er, ar = math.radians(e), math.radians(a)
        lx, ly, lz = math.cos(er) * math.cos(ar), math.sin(er), math.cos(er) * math.sin(ar)
        if shape_fn:
            lx, ly, lz = shape_fn(lx, ly, lz)
        return center + ax * lx + ay * ly + az * lz

    def uv(e, a, ac):
        return (u0 + w * (a + 180) / 360, v0 + h * (e + 90) / 180)

    rows = [-90 + 180 * i / rings for i in range(1, rings)]
    return grid_part(segs, rows, pos, uv, top=90, bottom=-90)


def catmull_dense(ctrl, per_seg=24):
    P = [Vector(c) for c in ctrl]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = []
    for i in range(len(ctrl) - 1):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(per_seg):
            f = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3))
    out.append(Vector(ctrl[-1]))
    return out


def resample(pts, n):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + (b - a).length)
    total = cum[-1]
    out, j = [], 0
    for k in range(n):
        t = total * k / (n - 1)
        while j < len(cum) - 2 and cum[j + 1] < t:
            j += 1
        f = (t - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        out.append(pts[j].lerp(pts[j + 1], min(max(f, 0), 1)))
    return out, total


def clump_part(ctrl, nseg, sides, w0, t0, uv_u0, uv_du, hang_side=None, wave_amp=0.0,
               wave_len=0.9, wave_phase=0.0, taper_start=0.7, tip_len=0.05, flare=0.4):
    pts, length = resample(catmull_dense(ctrl), nseg + 1)
    p0 = pts[0]
    a0 = math.atan2(p0.x, -p0.y)
    tan0 = Vector((math.cos(a0), math.sin(a0), 0))
    hs = None
    if hang_side is not None:
        hs = Vector(hang_side) if Vector(hang_side).dot(tan0) >= 0 else -Vector(hang_side)

    def frames(P):
        Ts, Ss = [], []
        for k in range(len(P)):
            Ts.append((P[min(k + 1, len(P) - 1)] - P[max(k - 1, 0)]).normalized())
        for k, p in enumerate(P):
            ang = math.atan2(p.x, -p.y)
            s0 = Vector((math.cos(ang), math.sin(ang), 0))
            if hs is not None:
                s0 = s0.lerp(hs, smoothstep(-0.35, -0.9, p.z))
            T = Ts[k]
            s = s0 - T * s0.dot(T)
            Ss.append(s.normalized() if s.length > 1e-6 else (Ss[-1] if Ss else Vector((1, 0, 0))))
        return Ts, Ss, [T.cross(S) for T, S in zip(Ts, Ss)]

    Ts, Ss, Ns = frames(pts)
    if wave_amp:
        newp = []
        for k, p in enumerate(pts):
            l = length * k / nseg
            ramp = smoothstep(-0.45, -1.0, p.z)
            ph = 2 * math.pi * l / wave_len + wave_phase
            newp.append(p + Ss[k] * wave_amp * math.sin(ph) * ramp + Ns[k] * wave_amp * 0.35 * math.cos(ph) * ramp)
        pts = newp
        Ts, Ss, Ns = frames(pts)

    V, F, UV, rings = [], [], [], []
    for k, p in enumerate(pts):
        s = k / nseg
        prof = 0.8 + flare * smoothstep(0, 0.45, s)
        if s > taper_start:
            prof *= lerp(1.0, 0.25, (s - taper_start) / (1 - taper_start))
        ring = []
        for m in range(sides):
            th = 2 * math.pi * m / sides
            ring.append(len(V))
            V.append(p + Ss[k] * (w0 * prof * math.cos(th)) + Ns[k] * (t0 * prof * math.sin(th)))
        rings.append(ring)
    tip = len(V)
    V.append(pts[-1] + Ts[-1] * tip_len)

    def uv(k, m):
        return (uv_u0 + uv_du * m / sides, 1.0 - 0.97 * k / nseg)

    for k in range(nseg):
        for m in range(sides):
            m2 = (m + 1) % sides
            F.append((rings[k][m], rings[k][m2], rings[k + 1][m2], rings[k + 1][m]))
            UV.append([uv(k, m), uv(k, m + 1), uv(k + 1, m + 1), uv(k + 1, m)])
    for m in range(sides):
        m2 = (m + 1) % sides
        F.append((rings[-1][m], rings[-1][m2], tip))
        UV.append([uv(nseg, m), uv(nseg, m + 1), (uv_u0 + uv_du * (m + 0.5) / sides, 0.01)])

    def ref(c):
        return min(pts, key=lambda q: (q - c).length_squared)

    return (V, F, UV), ref


# --------------------------------------------------------------------------- texture helpers
def save_png(arr_vup, path):
    """arr_vup: float HxWx(3|4) in 0..1, row 0 = bottom (Blender UV convention)."""
    img = (np.clip(arr_vup[::-1], 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img, "RGBA" if img.shape[2] == 4 else "RGB").save(path)
    return path


def c3(rgb):
    return np.array(rgb, dtype=np.float64) / 255.0


K_U, K_V = 2.5, 2.0  # head UV compression (more texels on the face)


def comp(t, k):
    return t * k / (1 + (k - 1) * abs(t))


def decomp(g, k):
    return g / (k - (k - 1) * np.abs(g))


def head_uv(a, e):
    return (0.5 + 0.5 * comp(a / 180.0, K_U), 0.5 + 0.5 * comp(e / 90.0, K_V))


class FacePainter:
    """Paints in (a, e) degree space - shared by the head texture and the face decal."""

    def __init__(self, A, E, base_rgb, base_alpha, aa):
        self.A, self.E, self.aa = A, E, aa
        self.rgb = np.empty(A.shape + (3,))
        self.rgb[:] = c3(base_rgb)
        self.alpha = np.full(A.shape, float(base_alpha))

    def m(self, d):
        return np.clip(0.5 - d / self.aa, 0, 1)

    def ell(self, ca, ce, ra, re, rot=0.0):
        x, y = self.A - ca, self.E - ce
        if rot:
            c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            x, y = x * c + y * s, -x * s + y * c
        return (np.sqrt((x / ra) ** 2 + (y / re) ** 2) - 1) * min(ra, re)

    def paint(self, color, mask):
        col = color if isinstance(color, np.ndarray) and color.ndim == 3 else c3(color)
        mk = mask[..., None]
        self.rgb = self.rgb * (1 - mk) + col * mk
        self.alpha = self.alpha + mask * (1 - self.alpha)

    def draw_face(self):
        A, E = self.A, self.E
        # blush (wide, across cheeks and nose)
        for s in (-1, 1):
            g = np.exp(-(((A - s * 20) / 11.5) ** 2 + ((E + 18) / 5.0) ** 2))
            self.paint((238, 120, 128), 0.7 * g)
        self.paint((238, 120, 128), 0.42 * np.exp(-((A / 9) ** 2 + ((E + 16.5) / 3.2) ** 2)))
        # freckles
        rnd = random.Random(3)
        for _ in range(26):
            s = rnd.choice((-1, 1))
            fa, fe = s * rnd.uniform(6, 28), rnd.uniform(-22, -13)
            if abs(fa) < 7 and fe > -15:
                continue
            self.paint((186, 108, 96), 0.75 * self.m(self.ell(fa, fe, 0.42, 0.38)))
        # cheek glints
        for s in (-1, 1):
            for da, de, r in ((2.5, 1.5, 0.45), (5.0, -1.0, 0.3), (-3.0, -2.0, 0.28)):
                self.paint((255, 255, 255), 0.85 * self.m(self.ell(s * 20 + da, -18 + de, r, r)))
        # eyes
        for s in (-1, 1):
            ca, ce = s * EYE_A, EYE_E
            lid = lid_at(ca, ce, s, A)  # upper lid line, gently droops outward
            eye = np.minimum(self.m(self.ell(ca, ce, 9.0, 8.4)), self.m(E - lid))
            self.paint((252, 248, 248), eye)
            ia, ie = ca - s * 0.6, ce - 0.8
            t = np.clip((E - (ce - 8.5)) / 13.0, 0, 1)[..., None]
            grad = c3((178, 108, 88)) * (1 - t) + c3((58, 30, 30)) * t
            iris = self.m(self.ell(ia, ie, 6.7, 8.0)) * eye
            self.paint(grad, iris)
            rim = np.clip(1 - np.abs(self.ell(ia, ie, 6.7, 8.0)) / 0.9, 0, 1) * eye
            self.paint((60, 30, 30), 0.55 * rim)
            self.paint((36, 18, 18), self.m(self.ell(ia, ce + 0.3, 2.6, 3.7)) * eye)
            self.paint((40, 20, 20), 0.55 * np.clip(1 - (lid - E) / 2.6, 0, 1) * eye)  # lid shadow
            self.paint((255, 255, 255), self.m(self.ell(ia + 2.3, ce + 2.0, 1.7, 2.1)) * eye)
            self.paint((255, 255, 255), self.m(self.ell(ia - 2.4, ce - 4.4, 0.8, 0.8)) * eye)
            self.paint((255, 255, 255), 0.9 * self.m(self.ell(ia + 0.9, ce - 2.2, 0.45, 0.45)) * eye)
            # lower lash (outer half)
            ring = np.abs(self.ell(ca, ce, 9.0, 8.4)) - 0.22
            low = self.m(ring) * (E < ce - 2.5) * np.clip(s * (A - ca) / 6.0 + 0.3, 0, 1)
            self.paint((95, 50, 45), 0.8 * low)
            # thick upper lash line + wing
            o = np.clip(s * (A - ca) / 8.0, 0, 1)
            band = (self.m(self.ell(ca, ce, 9.9, 9.4)) * self.m(lid - 0.45 - E)
                    * self.m(E - (lid + 0.75 + 0.75 * o)))
            self.paint((44, 24, 24), band)
            wa = ca + s * 9.4
            self.paint((44, 24, 24), self.m(self.ell(wa, lid_at(ca, ce, s, wa) - 0.3, 2.6, 0.75, rot=-s * 22)))
            for k, (da, rot) in enumerate(((5.5, 55), (7.3, 40), (3.4, 70))):
                la = ca + s * da
                self.paint((44, 24, 24), self.m(self.ell(la + s * 0.6, lid_at(ca, ce, s, la) + 1.6,
                                                         1.25, 0.32, rot=s * rot)))
            # eyebrows (thin, soft)
            brow = np.abs(self.ell(s * 17.0, 6.0, 6.0, 2.0)) - 0.26
            self.paint((176, 128, 104), 0.85 * self.m(brow) * (E > 6.5)
                       * np.clip(s * (A - s * 11.5) / 2.0, 0, 1))
        # tiny cat smile
        for s in (-1, 1):
            arc = np.abs(self.ell(s * 0.95, -26.0, 0.95, 0.85)) - 0.18
            self.paint((118, 48, 48), self.m(arc) * (E < -26.0))


EYE_A, EYE_E = 18.0, -7.5


def lid_at(ca, ce, s, a):
    return ce + 6.0 - 0.07 * (s * (a - ca))


def make_head_texture(path, size=1024):
    u = (np.arange(size) + 0.5) / size
    U, Vv = np.meshgrid(u, u)  # row index -> v (bottom up)
    A = 180 * decomp(2 * U - 1, K_U)
    E = 90 * decomp(2 * Vv - 1, K_V)
    p = FacePainter(A, E, SKIN, 1.0, aa=0.22)
    p.rgb *= (1 - 0.06 * np.clip((-E - 45) / 30, 0, 1))[..., None]  # soft neck shade
    p.draw_face()
    return save_png(p.rgb, path)


def make_face_decal(path, size=512):
    u = (np.arange(size) + 0.5) / size
    U, Vv = np.meshgrid(u, u)
    A, E = (U - 0.5) * 90, (Vv - 0.5) * 90 - 8
    p = FacePainter(A, E, SKIN, 0.0, aa=0.25)
    p.draw_face()
    return save_png(np.dstack([p.rgb, p.alpha]), path)


# atlas layout (shared by hair + beanie so the combo uses one texture)
HAIR_RECT = (0.0, 0.0, 0.5, 1.0)
BODY_RECT = (0.5, 0.45, 0.5, 0.55)
CUFF_RECT = (0.5, 0.15, 0.5, 0.30)
STRAW_RECT = (0.5, 0.0, 0.2, 0.15)
LEAF_RECT = (0.7, 0.0, 0.1, 0.15)
PETAL_RECT = (0.8, 0.0, 0.1, 0.15)
YELLOW_RECT = (0.9, 0.0, 0.1, 0.15)


def make_atlas(path, size=1024):
    img = np.zeros((size, size, 3))

    def px(rect):
        u0, v0, w, h = rect
        return slice(int(v0 * size), int((v0 + h) * size)), slice(int(u0 * size), int((u0 + w) * size))

    # hair strands (vertical lines along v)
    ys, xs = px(HAIR_RECT)
    H, W = ys.stop - ys.start, xs.stop - xs.start
    col_noise = RNG.normal(0, 1, W)
    k = np.exp(-np.linspace(-3, 3, 9) ** 2)
    col_noise = np.convolve(col_noise, k / k.sum(), mode="same")
    col_noise = col_noise / np.abs(col_noise).max()
    xx = np.arange(W)
    low = 0.5 * np.sin(xx / W * 2 * np.pi * 7 + 1.3) + 0.5 * np.sin(xx / W * 2 * np.pi * 17)
    yy = np.arange(H)[:, None] / H
    wob = 0.04 * np.sin(yy * 2 * np.pi * 3 + xx[None, :] * 0.05)
    shade = 1 + 0.11 * col_noise[None, :] + 0.05 * low[None, :] + wob
    shade *= 1 - 0.08 * np.clip((yy - 0.88) / 0.12, 0, 1)  # darker roots (v near 1)
    shade *= 1 + 0.05 * np.clip((0.1 - yy) / 0.1, 0, 1)  # lighter tips
    hl = np.exp(-((yy - 0.72) / 0.05) ** 2) * (0.6 + 0.4 * (col_noise[None, :] > 0))  # gloss band
    img[ys, xs] = c3(HAIR)[None, None, :] * shade[..., None] + 0.10 * hl[..., None]

    def knit(rect, ribs, row_px, contrast):
        ys, xs = px(rect)
        H, W = ys.stop - ys.start, xs.stop - xs.start
        x = np.arange(W)[None, :]
        y = np.arange(H)[:, None]
        per = W / ribs
        xl = (x % per) / per
        ridge = np.sin(np.pi * xl) ** 0.6
        lx = 2 * xl - 1
        st = 0.5 + 0.5 * np.cos(2 * np.pi * ((y / row_px + 0.45 * np.abs(lx)) % 1.0))
        fuzz = RNG.normal(0, 0.035, (H, W))
        b = (1 - contrast) + contrast * ridge + 0.07 * st * ridge + fuzz
        img[ys, xs] = c3(BEANIE_PINK)[None, None, :] * b[..., None]

    knit(BODY_RECT, 32, 15, 0.26)
    knit(CUFF_RECT, 32, 10, 0.34)

    # strawberry swatch: red gradient with seeds
    ys, xs = px(STRAW_RECT)
    H, W = ys.stop - ys.start, xs.stop - xs.start
    y = np.arange(H)[:, None] / H
    x = np.arange(W)[None, :]
    red = c3((214, 58, 78)) * (1 - y[..., None]) + c3((246, 104, 118)) * y[..., None]
    red = np.broadcast_to(red, (H, W, 3)).copy()
    for row in range(5):
        cy = (row + 0.5) / 5 * H
        for cx in np.arange(0, W, W / 9) + (row % 2) * W / 18:
            d = ((x - cx) / 3.2) ** 2 + ((np.arange(H)[:, None] - cy) / 4.2) ** 2
            red[d < 1] = c3((255, 232, 150))
    img[ys, xs] = red

    def swatch(rect, top, bottom):
        ys, xs = px(rect)
        H = ys.stop - ys.start
        t = (np.arange(H) / H)[:, None, None]
        img[ys, xs] = c3(bottom) * (1 - t) + c3(top) * t

    swatch(LEAF_RECT, (140, 196, 110), (88, 150, 76))
    swatch(PETAL_RECT, (255, 255, 252), (240, 232, 230))
    swatch(YELLOW_RECT, (255, 226, 120), (240, 190, 70))
    return save_png(img, path)


# --------------------------------------------------------------------------- materials
def image_material(name, img_path, rough=0.7, sheen=0.0):
    img = bpy.data.images.load(img_path, check_existing=True)
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    if sheen and "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    return mat


def color_material(name, rgb, rough=0.8):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*[(c / 255) ** 2.2 for c in rgb], 1)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


# --------------------------------------------------------------------------- assets
def build_head(mat):
    S, R = 56, 32
    rows = [-90 + 180 * i / R for i in range(1, R)]
    b = MeshBuilder()
    b.add(grid_part(S, rows, lambda e, a: surf(a, e), lambda e, a, ac: head_uv(a, e), top=90, bottom=-90))
    return b.to_object("SB_Head", mat), b.tris()


def hairline(a):
    x = abs(a)
    if x < 45:
        return 22
    if x < 100:
        return lerp(22, -22, (x - 45) / 55)
    return lerp(-22, -48, (x - 100) / 80)


def hair_parts(b, lod=1.0):
    rnd = random.Random(11)
    # scalp cap
    S, R = (24, 12) if lod >= 1 else (18, 9)
    rows = [lerp(-50, 86, i / (R - 1)) for i in range(R)]
    u0, _, uw, _ = HAIR_RECT
    b.add(grid_part(S, rows, lambda e, a: surf(a, e, 0.035),
                    lambda e, a, ac: (u0 + uw * (a + 180) / 360, (e + 90) / 180),
                    keep_fn=lambda e, a: e > hairline(a), top=90))
    nb, sb = (14, 6) if lod >= 1 else (9, 5)  # long clump segments / sides
    nf, sf = (8, 6) if lod >= 1 else (6, 5)  # bangs

    def uvslice():
        return rnd.uniform(0.0, 0.40), 0.10

    # back hair - two layers for volume
    for i, a0 in enumerate((180 - 14, -166, 146, -146, 128, -128, 110, -110, 180)):
        layer = 0.05 if i % 2 else 0.0
        sx = 1 if a0 > 0 else -1
        p2 = surf(a0, -30, 0.07)
        x2 = p2.x if abs(p2.x) > 0.02 else 0.02 * sx
        zend = -2.55 + rnd.uniform(-0.15, 0.12)
        ctrl = [surf(a0, 40, 0.02), surf(a0, 5, 0.05), p2,
                (x2 * 1.25, max(p2.y, 0.6) + layer, -0.45),
                (x2 * 1.45 + 0.05 * sx, 0.66 + layer, -1.2),
                (x2 * 1.55, 0.69 + layer, -1.9),
                (x2 * 1.6, 0.66 + layer, zend)]
        u, du = uvslice()
        part, ref = clump_part(ctrl, nb, sb, rnd.uniform(0.17, 0.21), 0.075, u, du,
                               hang_side=(1, 0, 0), wave_amp=0.075, wave_len=rnd.uniform(0.8, 1.0),
                               wave_phase=rnd.uniform(0, 6.28), taper_start=0.78, flare=0.5)
        b.add(part, ref)
    # front locks over the shoulders
    for a0, xs, ln in ((56, 0.52, -2.15), (-56, 0.52, -2.25), (74, 0.74, -2.3), (-74, 0.74, -2.05),
                       (94, 0.93, -2.0), (-94, 0.93, -2.2)):
        sx = 1 if a0 > 0 else -1
        ctrl = [surf(a0, 40, 0.02), surf(a0, 10, 0.05), surf(a0, -25, 0.065),
                (sx * xs, -0.63, -0.5), (sx * (xs + 0.04), -0.66, -1.2), (sx * xs, -0.64, -1.8),
                (sx * (xs + 0.03), -0.62, ln)]
        u, du = uvslice()
        part, ref = clump_part(ctrl, nb, sb, 0.17, 0.07, u, du, hang_side=(1, 0, 0),
                               wave_amp=0.07, wave_len=0.85, wave_phase=rnd.uniform(0, 6.28),
                               taper_start=0.72, flare=0.45)
        b.add(part, ref)
    # side-swept bangs
    for a0 in (-40, -28, -16, -4, 8, 20, 32, 44):
        outer = abs(a0) >= 28
        e_end = (rnd.uniform(-14, -4) if outer else rnd.uniform(9, 14))
        sweep = -11 if a0 > -30 else -4
        ctrl = []
        for s in (0, 0.33, 0.66, 1.0):
            ctrl.append(surf(a0 + sweep * s ** 1.3, lerp(36, e_end, s), 0.035 + 0.035 * s))
        u, du = uvslice()
        part, ref = clump_part(ctrl, nf, sf, 0.085 if not outer else 0.07, 0.028, u, du,
                               taper_start=0.45, tip_len=0.03, flare=0.25)
        b.add(part, ref)


# beanie --------------------------------------------------------------------
TILT = math.radians(18)
AX_K = Vector((0, math.sin(TILT), math.cos(TILT)))  # beanie axis, top tilted back
AX_J = Vector((0, math.cos(TILT), -math.sin(TILT)))  # points back
AX_I = Vector((1, 0, 0))
BEANIE_PROFILE = (
    # (phi from axis, offset above head, v)
    [(p, 0.10, 1.0 - 0.55 * p / 52.0) for p in (5, 10, 16, 22, 28, 34, 40, 46, 51)]
    + [(52.0, 0.105, 0.452), (52.6, 0.16, 0.448), (54.0, 0.172, 0.44)]
    + [(p, 0.175, 0.44 - 0.27 * (p - 54) / 26.8) for p in (58, 62, 66, 70, 74, 77)]
    + [(79.3, 0.168, 0.185), (80.4, 0.145, 0.172), (80.8, 0.11, 0.163), (80.3, 0.075, 0.157),
       (77.0, 0.055, 0.15)])


def beanie_dir(phi, psi):
    p, s = math.radians(phi), math.radians(psi)
    return (AX_K * math.cos(p) + (-AX_J * math.cos(s) + AX_I * math.sin(s)) * math.sin(p)).normalized()


DOME_TOP = 1.05  # apex height along the beanie axis


def _ring_pos(phi, psi, off):
    d = beanie_dir(phi, psi)
    return d * (head_r(d) + off)


def beanie_pos(phi, psi, off):
    if phi > 52.0 or off > 0.11:  # cuff, lip and tuck rows hug the head
        return _ring_pos(phi, psi, off)
    # body: elliptic dome from the cuff-top ring up to the apex, slouching backwards
    q_pt = _ring_pos(52.0, psi, 0.105)
    hq = q_pt.dot(AX_K)
    q = q_pt - AX_K * hq
    tp = math.radians(90.0 * phi / 52.0)
    back = (1 - math.cos(math.radians(psi))) / 2
    bulge = 1 + (0.12 + 0.30 * back) * math.sin(2 * tp) ** 1.2
    p = AX_K * (hq + (DOME_TOP - hq) * math.cos(tp)) + q * math.sin(tp) * bulge
    p += AX_J * 0.16 * math.cos(tp) ** 2  # whole crown leans back
    p += Vector((0, 0.35, -0.9)) * (0.10 * back ** 1.5 * math.sin(2 * tp) ** 2)  # soft droop
    return p


def beanie_parts(b, lod=1.0):
    cols = 40 if lod >= 1 else 24
    prof = BEANIE_PROFILE
    rows = list(range(len(prof)))

    def pos(r, psi):
        if r < 0:  # top pole
            return beanie_pos(0, 0, 0.10)
        phi, off, _ = prof[r]
        return beanie_pos(phi, psi, off)

    def uv(r, psi, psic):
        v = 1.0 if r < 0 else prof[r][2]
        base = -180.0 if psic < 0 else 0.0
        return (0.504 + 0.492 * min(max((psi - base) / 180.0, 0), 1), v)

    # rows go from top (phi small) to bottom; reverse so bottom->top for grid_part
    rows_rev = rows[::-1]
    b.add(grid_part(cols, rows_rev, pos, uv, top=-1))

    # strawberry + flower patch on the cuff (character's left-front)
    phi_p, psi_p, off = 66.5, 30.0, 0.175
    P = beanie_pos(phi_p, psi_p, off)
    up = (beanie_pos(phi_p - 1, psi_p, off) - beanie_pos(phi_p + 1, psi_p, off)).normalized()
    side = (beanie_pos(phi_p, psi_p + 1, off) - beanie_pos(phi_p, psi_p - 1, off)).normalized()
    n = side.cross(up).normalized()
    if n.dot(beanie_dir(phi_p, psi_p)) < 0:
        n = -n
    up = (up - n * up.dot(n)).normalized()
    right = up.cross(n).normalized()
    seg = 12 if lod >= 1 else 10

    def straw_shape(lx, ly, lz):
        f = 0.62 + 0.38 * (ly + 1) / 2
        return lx * f, ly * (1.12 if ly < 0 else 1.0), lz * f

    k = 1.55  # patch scale
    sc = P + n * 0.016
    b.add(ellipsoid_part(sc, right * 0.07 * k, up * 0.08 * k, n * 0.035 * k, seg, 8, STRAW_RECT, straw_shape),
          lambda c: sc)
    top = sc + up * 0.075 * k + n * 0.014 * k
    for ang in (-62, -31, 0, 31, 62):
        d = (up * math.cos(math.radians(ang)) + right * math.sin(math.radians(ang))).normalized()
        perp = n.cross(d).normalized()
        lc = top + d * 0.024 * k + n * 0.01
        b.add(ellipsoid_part(lc, perp * 0.012 * k, d * 0.027 * k, n * 0.008 * k, 6, 4,
                             (LEAF_RECT[0] + 0.01, 0.01, 0.08, 0.13)), lambda c, lc=lc: lc)
    fc = sc + right * 0.06 * k - up * 0.065 * k + n * 0.03 * k
    for i in range(5):
        ang = math.radians(i * 72 + 18)
        d = (up * math.cos(ang) + right * math.sin(ang)).normalized()
        perp = n.cross(d).normalized()
        pc = fc + d * 0.016 * k
        b.add(ellipsoid_part(pc, perp * 0.011 * k, d * 0.016 * k, n * 0.006 * k, 6, 4,
                             (PETAL_RECT[0] + 0.01, 0.01, 0.08, 0.13)), lambda c, pc=pc: pc)
    cc = fc + n * 0.008
    b.add(ellipsoid_part(cc, right * 0.009 * k, up * 0.009 * k, n * 0.008 * k, 6, 4,
                         (YELLOW_RECT[0] + 0.01, 0.01, 0.08, 0.13)), lambda c: cc)


# --------------------------------------------------------------------------- clothing templates
def make_clothing(shirt_path, pants_path):
    W, H = 585, 559
    TORSO = {"U": (231, 8, 128, 64), "L": (165, 74, 64, 128), "F": (231, 74, 128, 128),
             "R": (361, 74, 64, 128), "B": (427, 74, 128, 128), "D": (231, 204, 128, 64)}
    RLIMB = {"U": (217, 289, 64, 64), "L": (19, 355, 64, 128), "B": (85, 355, 64, 128),
             "R": (151, 355, 64, 128), "F": (217, 355, 64, 128), "D": (217, 485, 64, 64)}
    LLIMB = {"U": (308, 289, 64, 64), "F": (308, 355, 64, 128), "L": (374, 355, 64, 128),
             "B": (440, 355, 64, 128), "R": (506, 355, 64, 128), "D": (308, 485, 64, 64)}

    def knit_fill(arr, rect, rgb, period=6, horiz=False):
        x, y, w, h = rect
        yy, xx = np.mgrid[0:h, 0:w]
        t = (yy if horiz else xx) % period / period
        b = 0.9 + 0.1 * np.sin(np.pi * t) + RNG.normal(0, 0.025, (h, w))
        arr[y:y + h, x:x + w, :3] = np.clip(c3(rgb) * b[..., None], 0, 1)
        arr[y:y + h, x:x + w, 3] = 1

    def clear(arr, x, y, w, h):
        arr[y:y + h, x:x + w, 3] = 0

    def bow(draw, cx, cy, s, col=(238, 140, 168), dark=(205, 105, 135)):
        draw.polygon([(cx, cy), (cx - 2.2 * s, cy - 1.3 * s), (cx - 2.2 * s, cy + 1.3 * s)], fill=col, outline=dark)
        draw.polygon([(cx, cy), (cx + 2.2 * s, cy - 1.3 * s), (cx + 2.2 * s, cy + 1.3 * s)], fill=col, outline=dark)
        draw.polygon([(cx - 0.4 * s, cy), (cx - 1.3 * s, cy + 2.6 * s), (cx - 0.5 * s, cy + 2.4 * s)], fill=col)
        draw.polygon([(cx + 0.4 * s, cy), (cx + 1.3 * s, cy + 2.6 * s), (cx + 0.5 * s, cy + 2.4 * s)], fill=col)
        draw.ellipse([cx - 0.6 * s, cy - 0.6 * s, cx + 0.6 * s, cy + 0.6 * s], fill=dark)

    def lace(draw, x0, x1, y, r=3, col=(255, 252, 250, 255)):
        for cx in range(x0 + r, x1, 2 * r):
            draw.ellipse([cx - r, y - r, cx + r, y + r], fill=col)
            draw.ellipse([cx - 1, y - 1, cx + 1, y + 1], fill=(235, 215, 220, 255))

    # ---- shirt: oversized off-shoulder cream sweater over a pink tube top
    sh = np.zeros((H, W, 4))
    for rect in list(TORSO.values()) + list(RLIMB.values()) + list(LLIMB.values()):
        knit_fill(sh, rect, CREAM)
    clear(sh, *TORSO["U"])
    for f in ("F", "B", "L", "R"):  # bare shoulders / chest top
        x, y, w, h = TORSO[f]
        clear(sh, x, y, w, 16)
    for limb in (RLIMB, LLIMB):
        clear(sh, *limb["U"])
        for f in ("F", "B", "L", "R"):
            x, y, w, h = limb[f]
            clear(sh, x, y, w, 10)
            knit_fill(sh, (x, y + h - 22, w, 22), (236, 228, 214), period=4, horiz=True)  # cuff
    x, y, w, h = TORSO["F"]
    knit_fill(sh, (x + 34, y + 16, 60, h - 16), (250, 206, 216), period=4, horiz=True)  # pink top
    im = Image.fromarray((sh * 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    lace(d, x + 34, x + 94, y + 18)
    lace(d, x + 34, x + 94, y + 102)
    bow(d, x + 64, y + 30, 6)
    bow(d, x + 64, y + 104, 4)
    for xx in (x + 33, x + 94):  # cardigan edges
        d.line([(xx, y + 16), (xx, y + h)], fill=(225, 215, 198, 255), width=2)
    im.save(shirt_path)

    # ---- pants: pink ruffled skirt, bare thighs, white leg warmers with bows
    pa = np.zeros((H, W, 4))
    for f in ("L", "F", "R", "B", "D"):
        knit_fill(pa, TORSO[f], (246, 192, 204), period=10)
    for limb in (RLIMB, LLIMB):
        for f in ("F", "B", "L", "R"):
            x, y, w, h = limb[f]
            knit_fill(pa, (x, y, w, 26), (246, 192, 204), period=10)
            knit_fill(pa, (x, y + 62, w, h - 62), (250, 247, 243), period=12, horiz=True)
            knit_fill(pa, (x, y + 62, w, 8), (240, 236, 230), period=3)
            knit_fill(pa, (x, y + h - 12, w, 12), (246, 205, 214), period=5)  # shoes
        knit_fill(pa, limb["D"], (238, 190, 200), period=6)
    im = Image.fromarray((pa * 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    for f in ("L", "F", "R", "B"):
        x, y, w, h = TORSO[f]
        lace(d, x, x + w, y + h - 4)
    for limb in (RLIMB, LLIMB):
        for f in ("F", "B", "L", "R"):
            x, y, w, h = limb[f]
            lace(d, x, x + w, y + 27)
        x, y, w, h = limb["F"]
        bow(d, x + 32, y + 70, 5)
    im.save(pants_path)


# --------------------------------------------------------------------------- scene
def reset_scene():
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
    else:  # inside a running Blender: build in a fresh scene, keep the user's file intact
        scene = bpy.data.scenes.new("StrawberrySet")
        try:
            bpy.context.window.scene = scene
        except AttributeError:
            scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.01
    scene.unit_settings.length_unit = "CENTIMETERS"
    return scene


def bbox(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def roblox_data(ob, tris):
    mn, mx = bbox(ob)
    c, s = (mn + mx) / 2, mx - mn
    # Blender (x, y, z) -> Roblox (-x, z, y): Blender -Y front == Roblox -Z front
    return {"center": [round(-c.x, 4), round(c.z, 4), round(c.y, 4)],
            "size": [round(s.x, 4), round(s.z, 4), round(s.y, 4)],
            "tris": tris}


def export_fbx(ob, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"},
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False, bake_anim=False)


def preview_body(coll):
    mats = {k: color_material("prev_" + k, v) for k, v in
            {"cream": CREAM, "skin": SKIN, "pink": (246, 192, 204), "white": (250, 247, 243),
             "top": (250, 206, 216), "bow": (238, 140, 168)}.items()}

    def box(name, center, size, mat, bevel=0.06):
        me = bpy.data.meshes.new(name)
        hx, hy, hz = (s / 2 for s in size)
        v = [(x * hx, y * hy, z * hz) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        me.from_pydata(v, [], f)
        me.materials.append(mats[mat])
        ob = bpy.data.objects.new(name, me)
        ob.location = center
        coll.objects.link(ob)
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments = bevel, 3
        return ob

    # Roblox R15 blocky proportions (head centre at origin)
    box("UpperTorso", (0, 0, -1.3), (2.0, 1.0, 1.6), "cream")
    box("Chest", (0, -0.03, -0.62), (2.02, 1.02, 0.28), "skin", 0.03)
    box("TubeTop", (0, -0.47, -1.15), (0.9, 0.1, 1.1), "top", 0.03)
    box("LowerTorso", (0, 0, -2.3), (2.25, 1.2, 0.5), "pink")
    for sx in (-1, 1):
        box("Arm", (sx * 1.55, 0, -1.55), (1.1, 1.1, 2.1), "cream")
        box("Hand", (sx * 1.5, 0, -2.6), (0.85, 0.85, 0.12), "skin", 0.03)
        box("Thigh", (sx * 0.5, 0, -2.85), (0.94, 0.94, 0.6), "skin")
        box("Skirt", (sx * 0.5, 0, -2.62), (1.1, 1.15, 0.3), "pink", 0.04)
        box("Warmer", (sx * 0.5, 0, -3.85), (0.98, 1.02, 1.4), "white")
        box("Bow", (sx * 0.5, -0.56, -3.25), (0.32, 0.06, 0.16), "bow", 0.02)


def setup_render(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(os.environ.get("SB_SAMPLES", "64"))
    try:
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("pink")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.98, 0.78, 0.82, 1)
    bg.inputs["Strength"].default_value = 0.7
    scene.world = world

    def light(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, -0.8)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(ob)

    light("Key", (-4, -6, 4), 900, 4)
    light("Fill", (5, -5, 1), 350, 5, (1, 0.9, 0.93))
    light("Rim", (2, 6, 4), 700, 3)
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def render_view(scene, cam, path, a, e, dist, target, lens=50):
    loc = Vector(target) + ang_dir(a, e) * dist
    cam.location = loc
    cam.rotation_euler = (Vector(target) - loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def write_roblox_data(data):
    path = os.path.join(RBX_DIR, "StrawberryGirl_Builder.lua")
    if not os.path.exists(path):
        return
    lines = ["local MESH_DATA = {"]
    for name, d in data.items():
        lines.append('\t%s = { center = Vector3.new(%s), size = Vector3.new(%s), tris = %d },'
                     % (name, ", ".join(map(str, d["center"])), ", ".join(map(str, d["size"])), d["tris"]))
    lines.append("}")
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"(-- BEGIN GENERATED MESH DATA\n).*?(\n-- END GENERATED MESH DATA)",
                 lambda m: m.group(1) + "\n".join(lines) + m.group(2), src, flags=re.S)
    open(path, "w", encoding="utf-8").write(src)


def main():
    scene = reset_scene()
    atlas = make_atlas(os.path.join(TEX_DIR, "SB_HairBeanie_Atlas.png"))
    head_tex = make_head_texture(os.path.join(TEX_DIR, "SB_Head_Face.png"))
    make_face_decal(os.path.join(TEX_DIR, "SB_FaceDecal.png"))
    make_clothing(os.path.join(TEX_DIR, "SB_Shirt_Template.png"), os.path.join(TEX_DIR, "SB_Pants_Template.png"))

    m_atlas = image_material("SB_HairBeanie", atlas, rough=0.65, sheen=0.3)
    m_head = image_material("SB_Head", head_tex, rough=0.55)

    head, head_tris = build_head(m_head)
    hb = MeshBuilder()
    hair_parts(hb)
    hair = hb.to_object("SB_Hair", m_atlas)
    bb = MeshBuilder()
    beanie_parts(bb)
    beanie = bb.to_object("SB_Beanie", m_atlas)
    cb = MeshBuilder()
    hair_parts(cb, lod=0.5)
    beanie_parts(cb, lod=0.5)
    combo = cb.to_object("SB_HairBeanieCombo", m_atlas)
    combo.hide_render = True
    combo.location.x = 4.0  # keep it beside the set in the .blend

    data = {}
    for ob, tris in ((head, head_tris), (hair, hb.tris()), (beanie, bb.tris()), (combo, cb.tris())):
        if ob is combo:
            ob.location.x = 0.0
            bpy.context.view_layer.update()
        data[ob.name] = roblox_data(ob, tris)
        export_fbx(ob, os.path.join(EXP_DIR, ob.name + ".fbx"))
        print("%-20s tris=%5d  size(studs, Roblox XYZ)=%s" % (ob.name, tris, data[ob.name]["size"]))
    combo.location.x = 4.0
    json.dump(data, open(os.path.join(EXP_DIR, "mesh_data.json"), "w"), indent=2)
    write_roblox_data(data)

    body = bpy.data.collections.new("PreviewBody_NotForExport")
    scene.collection.children.link(body)
    preview_body(body)

    if DO_RENDER:
        cam = setup_render(scene)
        views = {"01_portrait": (-22, 6, 6.2, (0, 0, -0.45)), "02_face": (0, 2, 3.4, (0, 0, -0.05)),
                 "03_back": (180, 8, 9.5, (0, 0, -1.2)), "04_fullbody": (-15, 4, 14.5, (0, 0, -1.9)),
                 "05_side": (90, 4, 9.5, (0, 0, -1.2)), "06_beanie": (-35, 25, 4.0, (0, 0.1, 0.45))}
        only = os.environ.get("SB_VIEWS")
        for name, (a, e, dist, target) in views.items():
            if not only or name[:2] in only.split(","):
                render_view(scene, cam, os.path.join(PREV_DIR, name + ".png"), a, e, dist, target)

    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXP_DIR, "StrawberrySet.blend"), compress=True, copy=True)
    print("done ->", OUT_DIR)


if __name__ == "__main__":
    main()

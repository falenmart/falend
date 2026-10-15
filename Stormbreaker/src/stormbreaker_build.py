"""
Stormbreaker (Fırtınakıran) - Roblox için balta/çekiç modeli.

Tamamen prosedürel: geometri, UV, PBR dokular (renk / normal / pürüzlülük / metallik),
render ve dışa aktarma bu script ile yapılır.

Çalıştırma (bpy modülü olan python 3.13):
    python3.13 stormbreaker_build.py -- <çıktı_kök_klasörü> [--fast] [--no-gif]

Çıktılar:
    Blender/Stormbreaker.blend             (dokular içine paketli)
    Roblox/Stormbreaker.fbx                (Studio 3D Importer, 2 MeshPart: Head + Handle)
    Roblox/Stormbreaker.glb                (PBR dokular gömülü)
    Roblox/Textures/*_1024.png             (SurfaceAppearance haritaları)
    Textures/*.png                         (2048 kaynak dokular)
    Previews/*.png, Previews/turntable.gif

Eksenler (Blender): sap +Z yönünde, ağız -X, çekiç +X, kalınlık Y. 1 birim = 1 stud.
"""
import math
import os
import sys
import time

import bpy  # noqa: I001  (bmesh, bpy yüklendikten sonra içe aktarılabilir)
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageFilter
from scipy import ndimage

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
NO_GIF = "--no-gif" in ARGS
POS = [a for a in ARGS if not a.startswith("--")]
ROOT = os.path.abspath(POS[0] if POS else ".")
TEX = 1024 if FAST else 2048
RBX_TEX = 1024

DIRS = {k: os.path.join(ROOT, k) for k in ("Blender", "Roblox", "Textures", "Previews")}
DIRS["RobloxTex"] = os.path.join(ROOT, "Roblox", "Textures")
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


# =============================================================== gürültü
_rng = np.random.default_rng(1337)
_PERM = np.tile(_rng.permutation(256).astype(np.int32), 2)
_VAL = _rng.random(256).astype(np.float32)


def _vnoise3(x, y, z):
    xi = np.floor(x)
    yi = np.floor(y)
    zi = np.floor(z)
    xf = (x - xi).astype(np.float32)
    yf = (y - yi).astype(np.float32)
    zf = (z - zi).astype(np.float32)
    xi = xi.astype(np.int32) & 255
    yi = yi.astype(np.int32) & 255
    zi = zi.astype(np.int32) & 255
    x1 = (xi + 1) & 255
    y1 = (yi + 1) & 255
    z1 = (zi + 1) & 255
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    w = zf * zf * (3 - 2 * zf)
    px0 = _PERM[xi]
    px1 = _PERM[x1]
    p00 = _PERM[px0 + yi]
    p01 = _PERM[px0 + y1]
    p10 = _PERM[px1 + yi]
    p11 = _PERM[px1 + y1]

    def h(p, zz):
        return _VAL[_PERM[p + zz]]

    a = h(p00, zi) + (h(p10, zi) - h(p00, zi)) * u
    b = h(p01, zi) + (h(p11, zi) - h(p01, zi)) * u
    c = h(p00, z1) + (h(p10, z1) - h(p00, z1)) * u
    d = h(p01, z1) + (h(p11, z1) - h(p01, z1)) * u
    e = a + (b - a) * v
    f = c + (d - c) * v
    return e + (f - e) * w


def vnoise3(x, y, z):
    x, y, z = np.broadcast_arrays(np.asarray(x, np.float32), np.asarray(y, np.float32), np.asarray(z, np.float32))
    shape = x.shape
    x, y, z = x.ravel(), y.ravel(), z.ravel()
    out = np.empty(x.size, np.float32)
    step = 1 << 20
    for i in range(0, x.size, step):
        out[i:i + step] = _vnoise3(x[i:i + step], y[i:i + step], z[i:i + step])
    return out.reshape(shape)


def fbm(x, y, z, octaves=4, lac=2.0, gain=0.5):
    total = 0.0
    amp = 1.0
    norm = 0.0
    f = 1.0
    for o in range(octaves):
        off = 31.7 * o
        total = total + amp * vnoise3(x * f + off, y * f - off * 0.7, z * f + off * 1.3)
        norm += amp
        amp *= gain
        f *= lac
    return total / norm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def save_img(arr, path, srgb=False, size=None):
    """arr: (H,W) veya (H,W,3), satır 0 = UV v=0 (alt). PNG'de üst satır v=1 olduğundan çevrilir."""
    a = np.asarray(arr, np.float32)
    if srgb:
        a = lin2srgb(a)
    a = np.flipud(np.clip(a, 0, 1))
    img = Image.fromarray((a * 255 + 0.5).astype(np.uint8))
    if size and size != img.size[0]:
        img = img.resize((size, size), Image.LANCZOS)
    img.save(path)
    return path


def height_to_normal(h, strength):
    """Tanjant uzayı normal haritası (OpenGL, +Y yukarı). h satır=v, sütun=u."""
    dv, du = np.gradient(h.astype(np.float32))
    nx = -du * strength
    ny = -dv * strength
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5


# =============================================================== yardımcılar
def catmull(points, n):
    P = np.asarray(points, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(P) - 3
    out = []
    for k in range(n):
        s = k / (n - 1) * segs
        i = min(int(s), segs - 1)
        t = s - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)


def arc_fraction(pts):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    return d / max(d[-1], 1e-9), d[-1]


def end_taper(s, L, a, b, floor=0.08):
    """Uçlarda yuvarlatma: s 0..1, a/b stud cinsinden yuvarlama uzunluğu."""
    d0 = s * L
    d1 = (1 - s) * L
    t0 = np.sqrt(np.clip(d0 / a, 0, 1) * (2 - np.clip(d0 / a, 0, 1))) if a > 0 else 1.0
    t1 = np.sqrt(np.clip(d1 / b, 0, 1) * (2 - np.clip(d1 / b, 0, 1))) if b > 0 else 1.0
    return np.maximum(t0 * t1, floor)


def build_object(name, verts, faces, face_uvs, smooth, face_ints=None, vert_floats=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    uvl = me.uv_layers.new(name="UVMap")
    flat = [uv for fu in face_uvs for uv in fu]
    uvl.data.foreach_set("uv", np.asarray(flat, np.float32).ravel())
    if face_ints:
        for k, vals in face_ints.items():
            at = me.attributes.new(k, "INT", "FACE")
            at.data.foreach_set("value", np.asarray(vals, np.int32))
    if vert_floats:
        for k, vals in vert_floats.items():
            at = me.attributes.new(k, "FLOAT", "POINT")
            at.data.foreach_set("value", np.asarray(vals, np.float32))
    me.validate(clean_customdata=False)
    me.update()
    me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# =============================================================== ölçüler
ZH = 4.15  # baş merkezinin yüksekliği (sapın dibi z=0)


def C(z):
    """Sapın hafif organik eğrili eksen çizgisi."""
    z = np.asarray(z, float)
    x = 0.032 * np.sin(1.35 * z + 0.4) - 0.032 * math.sin(0.4) + 0.012 * np.sin(3.1 * z)
    y = 0.022 * np.sin(1.05 * z + 1.9) - 0.022 * math.sin(1.9)
    return np.stack([x, y, z], -1)


_RZ = [0.0, 0.35, 0.9, 1.6, 2.4, 3.1, 3.6, ZH - 0.3, ZH + 0.5]
_RR = [0.118, 0.112, 0.082, 0.076, 0.079, 0.081, 0.095, 0.118, 0.112]


def R(z):
    return np.interp(z, _RZ, _RR)


HC = C(ZH)  # başın dünya konumu

# ============================================================ SAP (ağaç kökü)
class Tube:
    def __init__(self, name, pts, radii, K, noise=0.13, nfreq=7.0, cap0=True, cap1=True, seed=0):
        self.name = name
        self.pts = np.asarray(pts, float)
        self.radii = np.asarray(radii, float)
        self.K = K
        self.noise = noise
        self.nfreq = nfreq
        self.cap0 = cap0
        self.cap1 = cap1
        self.seed = seed
        s, L = arc_fraction(self.pts)
        self.s = s
        self.L = L
        self.rmean = float(np.mean(self.radii))


def handle_tubes():
    rng = np.random.default_rng(42)
    tubes = []

    # çekirdek gövde
    zz = np.linspace(0.06, ZH + 0.47, 60)
    pts = C(zz)
    s, L = arc_fraction(pts)
    tubes.append(Tube("core", pts, R(zz) * 0.74 * end_taper(s, L, 0.08, 0.07), 12, noise=0.10, seed=1))

    # ana lifler: gövdenin etrafında burulan kökler
    for i in range(8):
        r = rng.random(4)
        phase = 2 * math.pi * i / 8 + r[0] * 0.5
        rate = 0.27 + 0.07 * r[1]
        if i in (2, 6):
            rate = -0.12
        z0 = 0.0 + 0.13 * r[2]
        z1 = ZH - 0.25 + 0.45 * r[3]
        zz = np.linspace(z0, z1, 64)
        ang = phase + 2 * math.pi * rate * zz + 0.25 * np.sin(zz * 2.1 + i)
        flare = 0.10 * np.clip((0.48 - zz) / 0.48, 0, 1) ** 1.4
        ro = R(zz) * 0.84 + flare
        pts = C(zz) + np.stack([ro * np.cos(ang), ro * np.sin(ang), np.zeros_like(zz)], -1)
        pts[:, 2] -= 0.03 * (flare / 0.10) ** 2  # parmak uçları biraz aşağı kıvrılır
        s, L = arc_fraction(pts)
        rad = (0.031 + 0.011 * r[0]) * (R(zz) / 0.08) ** 0.6 * (1 + 0.6 * flare / 0.10)
        rad *= end_taper(s, L, 0.05, 0.12, floor=0.45)
        tubes.append(Tube(f"strand{i}", pts, rad, 8, noise=0.2, seed=10 + i))

    # başın altındaki sargı (yaka)
    for i in range(3):
        r = rng.random(3)
        s_ = np.linspace(0, 1, 40)
        zz = ZH - 0.78 + 0.52 * s_ + 0.05 * r[0]
        d = 1 if i != 1 else -1
        ang = r[1] * 6.28 + d * 2 * math.pi * (1.7 + 0.3 * r[2]) * s_
        ro = R(zz) * 0.8 + 0.03
        pts = C(zz) + np.stack([ro * np.cos(ang), ro * np.sin(ang), np.zeros_like(zz)], -1)
        s, L = arc_fraction(pts)
        tubes.append(Tube(f"collar{i}", pts, 0.045 * end_taper(s, L, 0.08, 0.1), 8, noise=0.2, seed=30 + i))

    # başı sapa bağlayan sarmaşıklar: başın ekseni (X) etrafında sarmal sarılır,
    # yanakların (±Y) üstünden, üstten ve alttan geçer; ağız ve çekiçle çakışmaz
    for i in range(5):
        r = rng.random(3)
        s_ = np.linspace(0, 1, 46)
        d = 1 if i % 2 == 0 else -1
        xa, xb = (-0.29, 0.13) if i % 2 == 0 else (0.13, -0.29)
        x = xa + (xb - xa) * s_ + 0.02 * np.sin(s_ * 9 + i)
        ang = i * 2 * math.pi / 5 + r[0] + d * 2 * math.pi * (1.35 + 0.25 * r[1]) * s_
        y = 0.205 * np.cos(ang)
        z = 0.335 * np.sin(ang)
        helix = np.stack([x, y, z], -1)
        sy = 1 if y[0] >= 0 else -1
        start = np.array([0.0, sy * 0.07, -0.7 - 0.08 * r[2]])
        ey = 1 if y[-1] >= 0 else -1
        end = np.array([x[-1] * 0.5, ey * 0.06, z[-1] * 0.6])
        ctrl = np.vstack([start, (start + helix[0]) / 2 + [0, sy * 0.07, 0], helix[::3], end])
        pts = catmull(ctrl, 60) + HC
        s, L = arc_fraction(pts)
        rr = (0.046 - 0.006 * r[2]) * end_taper(s, L, 0.1, 0.1)
        tubes.append(Tube(f"wrap{i}", pts, rr, 8, noise=0.2, seed=40 + i))

    # tepedeki düğüm
    for i in range(2):
        s_ = np.linspace(0, 1, 30)
        zz = ZH + 0.24 + 0.22 * s_
        ang = i * math.pi + 2 * math.pi * 1.25 * s_ * (1 if i == 0 else -1)
        ro = 0.085 + 0.02 * np.sin(s_ * 3.1)
        pts = C(zz) + np.stack([ro * np.cos(ang), ro * np.sin(ang), np.zeros_like(zz)], -1)
        s, L = arc_fraction(pts)
        tubes.append(Tube(f"top{i}", pts, 0.042 * end_taper(s, L, 0.06, 0.09), 8, noise=0.2, seed=50 + i))

    # dipteki kök parmakları
    for i, a in enumerate((0.4, 2.5, 4.4)):
        d = np.array([math.cos(a), math.sin(a), 0.0])
        ctrl = [C(0.32) + d * 0.06, C(0.15) + d * 0.17 + [0, 0, -0.02], C(0.02) + d * 0.22 + [0, 0, -0.05],
                C(-0.03) + d * 0.25 + [0, 0, -0.06]]
        pts = catmull(ctrl, 18)
        s, L = arc_fraction(pts)
        rr = (0.056 - 0.016 * s) * end_taper(s, L, 0.03, 0.04, floor=0.5)
        tubes.append(Tube(f"finger{i}", pts, rr, 7, noise=0.2, seed=60 + i))

    # gövdeden çıkan kırık dal çıkıntıları
    for i, (zb, a) in enumerate(((0.78, 0.9), (0.98, 4.0))):
        d = np.array([math.cos(a), math.sin(a), 0.0])
        ctrl = [C(zb) + d * 0.04, C(zb + 0.12) + d * R(zb) * 1.1, C(zb + 0.3) + d * (R(zb) + 0.06)]
        pts = catmull(ctrl, 16)
        s, L = arc_fraction(pts)
        rr = (0.04 - 0.026 * s) * end_taper(s, L, 0.02, 0.025, floor=0.25)
        tubes.append(Tube(f"twig{i}", pts, rr, 7, noise=0.2, seed=70 + i))
    return tubes


def tube_geometry(t: Tube, rect, verts, faces, uvs):
    pts, radii, K = t.pts, t.radii, t.K
    N = len(pts)
    T = np.gradient(pts, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n0 = np.cross(T[0], ref)
    n0 /= np.linalg.norm(n0)
    nrm = [n0]
    for i in range(1, N):
        n = nrm[-1] - np.dot(nrm[-1], T[i]) * T[i]
        nrm.append(n / np.linalg.norm(n))
    nrm = np.array(nrm)
    bin_ = np.cross(T, nrm)
    ang = 2 * np.pi * np.arange(K) / K
    radial = np.cos(ang)[None, :, None] * nrm[:, None, :] + np.sin(ang)[None, :, None] * bin_[:, None, :]
    ring = pts[:, None, :] + radii[:, None, None] * radial
    q = ring * t.nfreq + t.seed * 3.1
    n1 = fbm(q[..., 0], q[..., 1], q[..., 2], 3)
    q2 = ring * t.nfreq * 4 + 50 + t.seed
    n2 = vnoise3(q2[..., 0], q2[..., 1], q2[..., 2])
    disp = 1 + t.noise * (n1 - 0.5) * 2.2 + 0.05 * (n2 - 0.5) * 2
    ring = pts[:, None, :] + radii[:, None, None] * radial * disp[..., None]

    base = len(verts)
    verts.extend(ring.reshape(-1, 3))
    u0, v0, u1, v1 = rect
    U = u0 + t.s * (u1 - u0)
    V = v0 + np.arange(K + 1) / K * (v1 - v0)
    for i in range(N - 1):
        for k in range(K):
            a = base + i * K + k
            b = base + i * K + (k + 1) % K
            c = base + (i + 1) * K + (k + 1) % K
            d = base + (i + 1) * K + k
            faces.append((a, d, c, b))
            uvs.append(((U[i], V[k]), (U[i + 1], V[k]), (U[i + 1], V[k + 1]), (U[i], V[k + 1])))
    if t.cap0:
        pole = len(verts)
        verts.append(pts[0] - T[0] * radii[0] * 0.6)
        for k in range(K):
            a = base + k
            b = base + (k + 1) % K
            faces.append((pole, a, b))
            uvs.append(((u0, (V[k] + V[k + 1]) / 2), (U[0], V[k]), (U[0], V[k + 1])))
    if t.cap1:
        pole = len(verts)
        verts.append(pts[-1] + T[-1] * radii[-1] * 0.6)
        last = base + (N - 1) * K
        for k in range(K):
            a = last + k
            b = last + (k + 1) % K
            faces.append((a, pole, b))
            uvs.append(((U[-1], V[k]), (u1, (V[k] + V[k + 1]) / 2), (U[-1], V[k + 1])))


def build_handle():
    tubes = handle_tubes()
    # atlas: her tüp bir yatay şerit; yükseklik çevre uzunluğuyla orantılı
    pad = 6
    weights = np.array([max(t.rmean, 0.03) for t in tubes])
    usable = TEX - pad * 2 * len(tubes)
    heights = np.maximum(np.floor(usable * weights / weights.sum()).astype(int), 24)
    while heights.sum() > usable:
        heights[np.argmax(heights)] -= 1
    verts, faces, uvs = [], [], []
    strips = []
    y = 0
    for t, h in zip(tubes, heights):
        y_in0 = y + pad
        y_in1 = y_in0 + h
        rect = (2 / TEX, y_in0 / TEX, 1 - 2 / TEX, y_in1 / TEX)
        tube_geometry(t, rect, verts, faces, uvs)
        strips.append((t, y, y_in0, y_in1, y_in1 + pad))
        y = y_in1 + pad
    ob = build_object("Stormbreaker_Handle", verts, faces, uvs, smooth=True)
    fix_normals(ob)
    return ob, strips


def handle_textures(strips):
    log("sap dokuları...")
    H = W = TEX
    col = np.zeros((H, W, 3), np.float32)
    height = np.zeros((H, W), np.float32)
    rough = np.zeros((H, W), np.float32)
    cols = (np.arange(W, dtype=np.float32) + 0.5) / W
    s_px = []
    for t, ya, y0, y1, yb in strips:
        rows = np.arange(ya, yb, dtype=np.float32) + 0.5
        theta = 2 * np.pi * (rows - y0) / (y1 - y0)
        S, TH = np.meshgrid(cols, theta)
        A = S * t.L + t.seed * 1.7
        rr = max(t.rmean, 0.035)
        # tahta damarı: sap boyunca uzayan çizgiler, alanı hafifçe bükülmüş
        warp = fbm(A * 0.9, np.cos(TH) * 3, np.sin(TH) * 3 + t.seed, 3)
        THw = TH + (warp - 0.5) * 2.6
        cx = np.cos(THw) * rr
        cy = np.sin(THw) * rr
        streak = fbm(A * 3.0, cx * 75, cy * 75 + t.seed, 4)
        fib = vnoise3(A * 9.0, cx * 230 + 7, cy * 230)
        fib = 1 - np.abs(2 * fib - 1)
        crev = smoothstep(0.40, 0.25, streak)
        cracks = smoothstep(0.80, 0.9, vnoise3(A * 22, cx * 14, cy * 14 + 9)) * smoothstep(0.55, 0.65, streak)
        big = fbm(A * 1.2 + 40, np.cos(TH) * 2, np.sin(TH) * 2, 3)
        hgt = 0.65 * streak + 0.22 * fib - 0.55 * crev - 0.25 * cracks
        hgt = hgt + 0.08 * fbm(A * 30, cx * 160, cy * 160, 2)
        hn = np.clip((hgt - 0.05) / 0.75, 0, 1)
        dark = np.array([0.008, 0.0045, 0.0028], np.float32)
        mid = np.array([0.036, 0.019, 0.010], np.float32)
        light = np.array([0.115, 0.064, 0.033], np.float32)
        c = np.where(hn[..., None] < 0.5, dark + (mid - dark) * (hn[..., None] * 2), mid + (light - mid) * ((hn[..., None] - 0.5) * 2))
        c = c * (0.72 + 0.6 * big[..., None])
        # yıpranmış, gri-kahve çıkıntılar
        weather = smoothstep(0.6, 0.85, fib * streak * 1.6)[..., None] * 0.35
        c = c * (1 - weather) + np.array([0.13, 0.09, 0.06], np.float32) * weather
        col[ya:yb] = c
        height[ya:yb] = hgt
        rough[ya:yb] = 0.72 + 0.2 * (1 - hn) - 0.1 * weather[..., 0]
        s_px.append(((t.L / W) + (2 * np.pi * rr / (y1 - y0))) / 2)
    texel = float(np.mean(s_px))
    nmap = height_to_normal(height, 0.03 / texel)
    out = {}
    for name, arr, srgb in (("Handle_Color", col, True), ("Handle_Normal", nmap, False),
                            ("Handle_Roughness", rough, False)):
        out[name] = save_img(arr, os.path.join(DIRS["Textures"], name + ".png"), srgb)
        save_img(arr, os.path.join(DIRS["RobloxTex"], name + "_1024.png"), srgb, RBX_TEX)
    out["Handle_Metalness"] = save_img(np.zeros((64, 64)), os.path.join(DIRS["Textures"], "Handle_Metalness.png"))
    save_img(np.zeros((64, 64)), os.path.join(DIRS["RobloxTex"], "Handle_Metalness_1024.png"))
    return out


# ============================================================ BAŞ (metal)
CHEEK, BEVEL, RIM, PLATE, HAMMER, CHAMFER, FACE, BLOCK, EDGE, PLATEWALL = range(10)

NT = np.array([-0.26, 0.24])
NB = np.array([-0.26, -0.21])
E0, E1, E2 = np.array([-1.22, 0.60]), np.array([-1.64, -0.10]), np.array([-1.02, -1.04])
UB = 0.6  # yanağın bittiği, keskin ağız şevinin başladığı yer


def blade_pt(u, t):
    n = NT + (NB - NT) * t
    e = (1 - t) ** 2 * E0 + 2 * (1 - t) * t * E1 + t * t * E2
    if t < 0.45:
        p = 1 + 0.55 * ((0.45 - t) / 0.45) ** 2
    else:
        p = 1 + 1.45 * ((t - 0.45) / 0.55) ** 2
    return np.array([n[0] + (e[0] - n[0]) * u, n[1] + (e[1] - n[1]) * u ** p])


def blade_h(u):
    if u <= UB:
        return 0.055 + 0.01 * max(0.0, 1 - u / 0.1)
    return 0.006 + 0.049 * ((1 - u) / (1 - UB)) ** 1.15


class HeadAcc:
    def __init__(self):
        self.v, self.f, self.ids, self.bu = [], [], [], []

    def vert(self, p, bu=-1.0):
        self.v.append(tuple(p))
        self.bu.append(bu)
        return len(self.v) - 1

    def face(self, idx, fid):
        self.f.append(tuple(idx))
        self.ids.append(fid)


def build_blade(acc: HeadAcc):
    US = list(np.linspace(0, UB, 9)) + list(np.linspace(UB, 1, 10))[1:]
    TS = np.linspace(0, 1, 44)
    V = {}
    for si, s in enumerate((1, -1)):
        for i, u in enumerate(US):
            for j, t in enumerate(TS):
                x, z = blade_pt(u, t)
                V[si, i, j] = acc.vert((x, s * blade_h(u), z), u)
    nU, nT = len(US), len(TS)
    for si in (0, 1):
        for i in range(nU - 1):
            fid = BEVEL if US[i] >= UB - 1e-6 else CHEEK
            for j in range(nT - 1):
                acc.face((V[si, i, j], V[si, i + 1, j], V[si, i + 1, j + 1], V[si, i, j + 1]), fid)
    for i in range(nU - 1):
        for j in (0, nT - 1):
            acc.face((V[0, i, j], V[0, i + 1, j], V[1, i + 1, j], V[1, i, j]), RIM)
    for j in range(nT - 1):
        acc.face((V[0, nU - 1, j], V[0, nU - 1, j + 1], V[1, nU - 1, j + 1], V[1, nU - 1, j]), EDGE)
        acc.face((V[0, 0, j], V[0, 0, j + 1], V[1, 0, j + 1], V[1, 0, j]), BLOCK)


def resample_poly(poly, step=0.03):
    out = []
    n = len(poly)
    for k in range(n):
        a = np.array(poly[k], float)
        b = np.array(poly[(k + 1) % n], float)
        m = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for q in range(m):
            out.append(a + (b - a) * q / m)
    return out


def inset_poly(P, d):
    P = np.asarray(P)
    n = len(P)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    sgn = 1 if area > 0 else -1
    out = []
    for k in range(n):
        p0, p1, p2 = P[k - 1], P[k], P[(k + 1) % n]
        e1 = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
        e2 = (p2 - p1) / (np.linalg.norm(p2 - p1) + 1e-9)
        n1 = sgn * np.array([-e1[1], e1[0]])
        n2 = sgn * np.array([-e2[1], e2[0]])
        bis = n1 + n2
        bis /= np.linalg.norm(bis) + 1e-9
        out.append(p1 + bis * d / max(np.dot(bis, n1), 0.35))
    return np.array(out)


PLATES = [
    # üst kenar boyunca uzanan bant
    [(0.0, 0.035), (0.30, 0.04), (0.56, 0.06), (0.47, 0.115), (0.25, 0.13), (0.0, 0.145)],
    # ağıza doğru bakan ok/şerit (chevron)
    [(0.0, 0.215), (0.30, 0.33), (0.53, 0.47), (0.30, 0.62), (0.0, 0.79), (0.0, 0.66), (0.24, 0.535),
     (0.33, 0.47), (0.24, 0.40), (0.0, 0.345)],
    # sakal kısmında alt kenar şeridi
    [(0.08, 0.90), (0.3, 0.915), (0.5, 0.94), (0.42, 0.965), (0.2, 0.965), (0.08, 0.955)],
]


def build_plates(acc: HeadAcc):
    h0 = 0.055
    for poly in PLATES:
        pts = resample_poly(poly, 0.035)
        xz = np.array([blade_pt(u, t) for u, t in pts])
        top = inset_poly(xz, 0.013)
        for s in (1, -1):
            b_idx = [acc.vert((p[0], s * (h0 - 0.004), p[1])) for p in xz]
            t_idx = [acc.vert((p[0], s * (h0 + 0.017), p[1])) for p in top]
            n = len(xz)
            for k in range(n):
                acc.face((b_idx[k], b_idx[(k + 1) % n], t_idx[(k + 1) % n], t_idx[k]), PLATEWALL)
            acc.face(t_idx, PLATE)
            acc.face(list(reversed(b_idx)), BLOCK)


def chamfer_octagon(c=0.2):
    r = 1 / math.cos(math.radians(22.5))
    base = [np.array([r * math.cos(math.radians(22.5 + 45 * k)), r * math.sin(math.radians(22.5 + 45 * k))]) for k in range(8)]
    out = []
    for k in range(8):
        v, pv, nv = base[k], base[k - 1], base[(k + 1) % 8]
        out.append(v + c * (pv - v))
        out.append(v + c * (nv - v))
    return out  # (z, y) çiftleri; çift indeks->tek indeks kenarı pah (chamfer)


HAMMER_SECTIONS = [(-0.34, .27, .15), (0.20, .27, .15), (0.20, .20, .15), (0.40, .20, .16), (0.72, .29, .23),
                   (0.72, .32, .25), (0.86, .32, .25), (0.90, .27, .21), (0.90, .22, .17), (0.935, .21, .16)]


def build_hammer(acc: HeadAcc):
    prof = chamfer_octagon(0.2)
    rings = []
    for x, rz, ry in HAMMER_SECTIONS:
        rings.append([acc.vert((x, p[1] * ry, p[0] * rz)) for p in prof])
    m = len(prof)
    for a in range(len(rings) - 1):
        xa, xb = HAMMER_SECTIONS[a][0], HAMMER_SECTIONS[a + 1][0]
        for k in range(m):
            if xb <= 0.2 + 1e-6:
                fid = BLOCK
            elif abs(xa - xb) < 1e-6:
                fid = HAMMER
            else:
                fid = CHAMFER if k % 2 == 0 else HAMMER
            acc.face((rings[a][k], rings[a][(k + 1) % m], rings[a + 1][(k + 1) % m], rings[a + 1][k]), fid)
    acc.face(list(reversed(rings[0])), BLOCK)
    acc.face(rings[-1], FACE)


def build_head():
    acc = HeadAcc()
    build_blade(acc)
    build_plates(acc)
    build_hammer(acc)
    me = bpy.data.meshes.new("Stormbreaker_Head")
    me.from_pydata(acc.v, [], acc.f)
    at = me.attributes.new("fid", "INT", "FACE")
    at.data.foreach_set("value", np.asarray(acc.ids, np.int32))
    bt = me.attributes.new("bu", "FLOAT", "POINT")
    bt.data.foreach_set("value", np.asarray(acc.bu, np.float32))
    me.update()
    ob = bpy.data.objects.new("Stormbreaker_Head", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(HC)
    fix_normals(ob)
    # UV: smart project + paketleme
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.scene.objects:
        o.select_set(o == ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(38), island_margin=0.006, area_weight=0.0)
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    # üçgenle (Roblox zaten üçgenler; fid / bu korunur)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def rasterize(ob, res):
    me = ob.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tri_loops = np.zeros(nt * 3, np.int32)
    me.loop_triangles.foreach_get("loops", tri_loops)
    tri_verts = np.zeros(nt * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tri_verts)
    tri_poly = np.zeros(nt, np.int32)
    me.loop_triangles.foreach_get("polygon_index", tri_poly)
    uv = np.zeros(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    pn = np.zeros(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pn = pn.reshape(-1, 3)
    fid = np.zeros(len(me.polygons), np.int32)
    me.attributes["fid"].data.foreach_get("value", fid)
    bu = np.zeros(len(me.vertices), np.float32)
    me.attributes["bu"].data.foreach_get("value", bu)

    TUV = uv[tri_loops].reshape(nt, 3, 2) * res - 0.5
    TP = co[tri_verts].reshape(nt, 3, 3)
    TB = bu[tri_verts].reshape(nt, 3)
    # dokusal yoğunluk (stud / piksel)
    a3 = 0.5 * np.linalg.norm(np.cross(TP[:, 1] - TP[:, 0], TP[:, 2] - TP[:, 0]), axis=1).sum()
    e1 = TUV[:, 1] - TUV[:, 0]
    e2 = TUV[:, 2] - TUV[:, 0]
    a2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum()
    texel = math.sqrt(a3 / a2)

    P = np.zeros((res, res, 3), np.float32)
    Nn = np.zeros((res, res, 3), np.float32)
    F = np.full((res, res), -1, np.int32)
    B = np.full((res, res), -1, np.float32)
    for t in range(nt):
        q = TUV[t]
        x0 = max(int(math.floor(q[:, 0].min())), 0)
        x1 = min(int(math.ceil(q[:, 0].max())), res - 1)
        y0 = max(int(math.floor(q[:, 1].min())), 0)
        y1 = min(int(math.ceil(q[:, 1].max())), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1, dtype=np.float32), np.arange(y0, y1 + 1, dtype=np.float32))
        (ax, ay), (bx, by), (cx, cy) = q
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        w2 = 1 - w0 - w1
        eps = -0.6 / max(abs(den) ** 0.5, 1)
        ins = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not ins.any():
            continue
        yy = ys[ins].astype(int)
        xx = xs[ins].astype(int)
        W = np.stack([w0[ins], w1[ins], w2[ins]], -1)
        P[yy, xx] = W @ TP[t]
        Nn[yy, xx] = pn[tri_poly[t]]
        F[yy, xx] = fid[tri_poly[t]]
        B[yy, xx] = W @ TB[t]
    mask = F >= 0
    idx = ndimage.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    P = P[idx[0], idx[1]]
    Nn = Nn[idx[0], idx[1]]
    F = F[idx[0], idx[1]]
    B = B[idx[0], idx[1]]
    return P, Nn, F, B, mask, texel


def head_textures(ob):
    log("baş dokuları: rasterize...")
    P, Nn, F, B, mask, texel = rasterize(ob, TEX)
    log(f"  texel={texel:.5f} stud/px, kaplama={mask.mean() * 100:.1f}%")
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    pat = fbm(x * 2.4, y * 2.4, z * 2.4, 5)
    blot = fbm(x * 0.8 + 5, y * 0.8, z * 0.8, 3)
    hamm = fbm(x * 15, y * 15, z * 15, 3)
    fine = vnoise3(x * 90, y * 90, z * 90)
    g = 0.30 * (0.62 + 0.7 * pat) * (0.75 + 0.4 * smoothstep(0.3, 0.7, blot))
    rough = 0.36 + 0.28 * (1 - pat)
    hgt = 0.22 * hamm + 0.1 * fine + 0.25 * fbm(x * 40, y * 40, z * 40, 2)

    # çizikler
    rng = np.random.default_rng(5)
    sc = np.zeros_like(x)
    for k in range(9):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        e = np.cross(d, rng.normal(size=3))
        e /= np.linalg.norm(e)
        f = np.cross(d, e)
        a = x * d[0] + y * d[1] + z * d[2]
        b = x * e[0] + y * e[1] + z * e[2]
        c = x * f[0] + y * f[1] + z * f[2]
        n_ = vnoise3(a * 1.6 + k * 7, b * 70, c * 70)
        line = np.clip(1 - np.abs(n_ - 0.5) * 26, 0, 1)
        gate = smoothstep(0.5, 0.7, vnoise3(a * 2.5 + k, b * 2.5, c * 2.5 + 3))
        sc = np.maximum(sc, line * gate)
    g = g + 0.12 * sc
    rough = rough - 0.12 * sc
    hgt = hgt - 0.5 * sc

    # ağız şevi: fırçalanmış, daha parlak
    bev = (F == BEVEL) | (F == EDGE)
    phi = np.arctan2(z + 0.15, x + 0.45)
    rad = np.hypot(z + 0.15, x + 0.45)
    br = vnoise3(phi * 160, rad * 2.2, y * 4) * 0.6 + vnoise3(phi * 420, rad * 4, y * 8 + 3) * 0.4
    edge = smoothstep(0.85, 1.0, B)
    g = np.where(bev, 0.40 * (0.8 + 0.4 * pat) + 0.035 * (br - 0.5) + 0.12 * edge + 0.1 * sc, g)
    rough = np.where(bev, 0.24 + 0.05 * br - 0.06 * edge + 0.1 * (1 - pat), rough)
    hgt = np.where(bev, 0.05 * br + 0.08 * hamm - 0.5 * sc, hgt)
    # yanak/şev sınırındaki oyma çizgi
    groove = (F == CHEEK) & (B > UB - 0.028)
    g = np.where(groove, g * 0.45, g)
    hgt = np.where(groove, hgt - 0.9, hgt)
    # bölgelere göre ayar
    g = np.where(F == PLATE, g * 0.82, g)
    g = np.where(F == PLATEWALL, 0.45 + 0.1 * pat, g)
    rough = np.where(F == PLATEWALL, 0.25, rough)
    g = np.where(F == RIM, 0.42 + 0.12 * pat, g)
    rough = np.where(F == RIM, 0.28, rough)
    g = np.where(F == CHAMFER, 0.44 + 0.12 * pat + 0.06 * sc, g)
    rough = np.where(F == CHAMFER, 0.26, rough)
    g = np.where(F == BLOCK, g * 0.62, g)
    rough = np.where(F == BLOCK, rough + 0.12, rough)
    # çekiç yüzü: dairesel fırçalama
    fa = np.arctan2(y, z)
    fr = np.hypot(y, z)
    fb = vnoise3(fr * 180, fa * 2, x)
    g = np.where(F == FACE, 0.4 + 0.03 * (fb - 0.5) + 0.08 * pat + 0.1 * sc, g)
    rough = np.where(F == FACE, 0.24 + 0.1 * fb, rough)
    hgt = np.where(F == FACE, 0.07 * fb + 0.15 * hamm, hgt)
    # çekiç uzunluğu boyunca ince oluklar (görseldeki yivler)
    on_ham = F == HAMMER
    rib = 0.5 + 0.5 * np.cos((np.arctan2(y, z) * 8 * 3))
    hgt = np.where(on_ham & (x > 0.42) & (x < 0.71), hgt - 0.6 * smoothstep(0.85, 1.0, rib), hgt)

    rough = np.clip(rough, 0.12, 0.9)
    tint = np.array([0.97, 1.0, 1.04], np.float32)
    col = np.clip(g, 0, 1)[..., None] * tint
    metal = np.where(F == BLOCK, 0.85, 1.0).astype(np.float32)
    nmap = height_to_normal(hgt, 0.0022 / texel)
    out = {}
    for name, arr, srgb in (("Head_Color", col, True), ("Head_Normal", nmap, False),
                            ("Head_Roughness", rough, False), ("Head_Metalness", metal, False)):
        out[name] = save_img(arr, os.path.join(DIRS["Textures"], name + ".png"), srgb)
        save_img(arr, os.path.join(DIRS["RobloxTex"], name + "_1024.png"), srgb, RBX_TEX)
    return out


# ============================================================ malzemeler
def make_material(name, tex):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    prefix = name.split("_")[-1]

    def img(key, non_color, x):
        im = bpy.data.images.load(tex[f"{prefix}_{key}"])
        if non_color:
            im.colorspace_settings.name = "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = im
        node.location = (x, 0)
        return node

    c = img("Color", False, -600)
    nt.links.new(c.outputs["Color"], bsdf.inputs["Base Color"])
    r = img("Roughness", True, -600)
    nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
    m = img("Metalness", True, -600)
    nt.links.new(m.outputs["Color"], bsdf.inputs["Metallic"])
    n = img("Normal", True, -800)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ============================================================ sahne & render
def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    world = bpy.data.worlds.new("Studio")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.03, 0.03, 0.035, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.42, 0.43, 0.45, 1)
    e = cr.elements.new(0.5)
    e.color = (0.12, 0.12, 0.125, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.9

    def area(name, loc, size, power, color=(1, 1, 1), size_y=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = power
        ld.color = color
        ld.shape = "RECTANGLE"
        ld.size = size
        ld.size_y = size_y or size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector((0, 0, 2.2)) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return lo

    area("Key", (-5.5, -7.0, 7.5), 4.0, 1400, (1.0, 0.97, 0.93))
    area("Rim", (6.0, 6.0, 6.5), 3.0, 1000, (0.85, 0.9, 1.0))
    area("Fill", (6.0, -6.0, 1.0), 5.0, 380)
    area("Top", (0.0, -1.0, 10.0), 6.0, 380, size_y=2.0)

    cam_d = bpy.data.cameras.new("Cam")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("Cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0, -12, 2.3)
    cam.rotation_euler = (math.radians(90), 0, 0)
    return cam


def frame_camera(cam, objs, margin=1.1, aspect=None):
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    pts = []
    for o in objs:
        mw = o.matrix_world
        co = np.zeros(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)[::3]
        for v in co:
            pts.append(inv @ (mw @ Vector(v)))
    pts = np.array([[p.x, p.y] for p in pts])
    mn, mx = pts.min(0), pts.max(0)
    cx, cy = (mn + mx) / 2
    w, h = mx - mn
    ar = sc.render.resolution_x / sc.render.resolution_y
    cam.data.ortho_scale = (max(w, h * ar) if ar >= 1 else max(h, w / ar)) * margin
    cam.location = cam.matrix_world @ Vector((cx, cy, 0))


def render(path, res, samples):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def composite_bg(src, dst, bg=(112, 112, 112)):
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    v = np.clip(1.06 - 0.16 * r ** 2, 0.8, 1.06)
    base = (np.array(bg, np.float32)[None, None, :] * v[..., None]).clip(0, 255).astype(np.uint8)
    b = Image.fromarray(base, "RGB").convert("RGBA")
    # yumuşak gölge hissi için hafif dış parıltı
    alpha = im.split()[3].filter(ImageFilter.GaussianBlur(18))
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * 0.22)))
    b = Image.alpha_composite(b, shadow)
    b = Image.alpha_composite(b, im)
    b.convert("RGB").save(dst)
    return dst


def pose_rig(pivot, rot_matrix):
    pivot.matrix_world = Matrix.Translation((0, 0, 2.2)) @ rot_matrix @ Matrix.Translation((0, 0, -2.2))


def R3(axis, deg):
    return Matrix.Rotation(math.radians(deg), 4, axis)


# ============================================================ dışa aktarma
def export_all(head, handle):
    bpy.ops.object.select_all(action="DESELECT")
    for o in (head, handle):
        o.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(DIRS["Roblox"], "Stormbreaker.fbx"),
        use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="Z", axis_up="Y",
        bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type="FACE",
        add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)
    try:
        bpy.ops.export_scene.gltf(filepath=os.path.join(DIRS["Roblox"], "Stormbreaker.glb"),
                                  export_format="GLB", use_selection=True, export_yup=True,
                                  export_apply=True)
    except Exception as ex:  # glTF eklentisi yoksa FBX yeterli
        log("GLB atlandı:", ex)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    log("sap geometrisi...")
    handle, strips = build_handle()
    log("baş geometrisi...")
    head = build_head()
    for o in (handle, head):
        log(f"  {o.name}: {len(o.data.vertices)} vertex, {sum(len(p.vertices) - 2 for p in o.data.polygons)} üçgen")

    tex = {}
    tex.update(handle_textures(strips))
    tex.update(head_textures(head))
    head.data.materials.append(make_material("Stormbreaker_Head", tex))
    handle.data.materials.append(make_material("Stormbreaker_Handle", tex))

    # dışa aktarma (sahne ışıkları/kamera eklenmeden önce, nötr pozda)
    export_all(head, handle)
    log("FBX/GLB yazıldı")

    cam = setup_scene()
    pivot = bpy.data.objects.new("AxePivot", None)
    bpy.context.scene.collection.objects.link(pivot)
    head.parent = pivot
    handle.parent = pivot
    objs = (head, handle)

    for img in bpy.data.images:
        if img.source == "FILE":
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIRS["Blender"], "Stormbreaker.blend"), compress=True)
    log(".blend kaydedildi")

    S = 40 if FAST else 160
    views = [
        ("Stormbreaker_front", R3("X", 6) @ R3("Y", -27) @ R3("Z", 14), (1150, 1380), 1.08),
        ("Stormbreaker_back", R3("X", 8) @ R3("Y", 27) @ R3("Z", 200), (1150, 1380), 1.08),
        ("Stormbreaker_hammer", R3("X", 10) @ R3("Y", -18) @ R3("Z", -58), (1150, 1380), 1.08),
    ]
    for name, rot, res, margin in views:
        pose_rig(pivot, rot)
        bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = res
        frame_camera(cam, objs, margin)
        raw = render(os.path.join(DIRS["Previews"], name + "_alpha.png"), res, S)
        composite_bg(raw, os.path.join(DIRS["Previews"], name + ".png"))
        log("render:", name)

    # yakın plan: baş
    pose_rig(pivot, R3("X", 6) @ R3("Y", -27) @ R3("Z", 22))
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = (1400, 1000)
    frame_camera(cam, (head,), 1.12)
    cam.data.ortho_scale *= 1.0
    raw = render(os.path.join(DIRS["Previews"], "Stormbreaker_closeup_alpha.png"), (1400, 1000), S)
    composite_bg(raw, os.path.join(DIRS["Previews"], "Stormbreaker_closeup.png"))
    log("render: closeup")

    if not NO_GIF:
        frames = []
        n = 12 if FAST else 36
        tmp = os.path.join(DIRS["Previews"], "_turn.png")
        for i in range(n):
            pose_rig(pivot, R3("X", 4) @ R3("Y", -14) @ R3("Z", 360 * i / n))
            bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = (440, 560)
            if i == 0:
                frame_camera(cam, objs, 1.25)
            render(tmp, (440, 560), 12 if FAST else 24)
            composite_bg(tmp, tmp + ".jpg.png")
            frames.append(Image.open(tmp + ".jpg.png").convert("P", palette=Image.ADAPTIVE, colors=200))
        frames[0].save(os.path.join(DIRS["Previews"], "Stormbreaker_turntable.gif"), save_all=True,
                       append_images=frames[1:], duration=70, loop=0)
        for f in (tmp, tmp + ".jpg.png"):
            os.remove(f)
        log("turntable gif")
    log("bitti")


main()

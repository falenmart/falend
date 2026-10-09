"""BAKAN - karanlik oda canavari.

6 stud capinda, havada suzulen duzensiz goz kumesi: ortada buyuk bir goz
(beyaz, kirmizi damarli, siyah iris) ve cevresinde 15 kucuk goz; aralarinda
koyu mor-siyah, puruzsuz kutle. Irisler ayri obje (oyuncuyu takip eder).
Etrafinda yavasca donen 3 ince kara halka, hafif mor Neon parilti.

Calistir:  python bakan.py [--preview]
"""

import math
import os
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monster_lib as ml  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "Bakan"))

DIAMETER = 6.0      # goz kumesinin capi (stud)
CENTER_Z = 5.0      # suzulme yuksekligi (merkez)
MASS_R = 2.3        # olcekleme oncesi kutle yaricapi
SMALL_EYES = 15


# ------------------------------------------------------------- vein texture

def vein_texture(path, w=1024, h=512, seed=3):
    """Beyaz goz aki + arkadan irise dogru uzanan kirmizi damarlar.
    UV kure: v=1 kutbu irisin oldugu on taraf."""
    rnd = random.Random(seed)
    img = np.zeros((h, w, 3), dtype=np.float32)
    v = np.linspace(0, 1, h)[:, None]
    base = np.array([0.93, 0.90, 0.86], dtype=np.float32)
    back = np.array([0.80, 0.55, 0.55], dtype=np.float32)
    k = np.clip(1 - v / 0.45, 0, 1) ** 1.5
    img[:] = base * (1 - k[..., None]) + back * k[..., None]
    alpha = np.zeros((h, w), dtype=np.float32)

    def stamp(x, y, r, a):
        x0, x1 = int(x - r - 2), int(x + r + 3)
        y0, y1 = max(int(y - r - 2), 0), min(int(y + r + 3), h)
        if y0 >= y1:
            return
        ys = np.arange(y0, y1)[:, None]
        xs = np.arange(x0, x1)[None, :]
        d = np.sqrt((xs - x) ** 2 + (ys - y) ** 2)
        val = np.clip(r + 0.8 - d, 0, 1) * a
        cols = np.mod(np.arange(x0, x1), w)
        sub = alpha[y0:y1][:, cols]
        alpha[y0:y1, cols] = np.maximum(sub, val)

    def vein(x, y, ang, r, depth):
        while y < h * 0.80 and r > 0.35:
            # thinner / fainter as it approaches the iris; u stretches near the pole
            vv = y / h
            stretch = 1 / max(math.sin(math.pi * vv), 0.25)
            step = 2.0
            ang += rnd.uniform(-0.35, 0.35)
            ang = 0.85 * ang + 0.15 * (math.pi / 2)
            x += math.cos(ang) * step * stretch
            y += math.sin(ang) * step
            stamp(x, y, r, min(1.0, 0.55 + r * 0.25))
            r *= 0.993
            if depth < 3 and rnd.random() < 0.025:
                vein(x, y, ang + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.0), r * 0.7, depth + 1)

    for _ in range(46):
        vein(rnd.uniform(0, w), rnd.uniform(0, h * 0.3), math.pi / 2 + rnd.uniform(-0.5, 0.5),
             rnd.uniform(1.3, 2.6), 0)
    red = np.array([0.55, 0.02, 0.03], dtype=np.float32)
    img = img * (1 - alpha[..., None]) + red * alpha[..., None]
    rgba = np.concatenate([img, np.ones((h, w, 1), dtype=np.float32)], axis=2)
    im = bpy.data.images.new("BakanGozDamar", w, h)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return im


# ------------------------------------------------------------- geometry

def mass_radius(n):
    """Kutlenin kaba (goz kapaksiz) yaricapi n yonunde."""
    lumps = noise.fractal(n * 1.1 + Vector((3.1, 0.7, 5.2)), 0.5, 2.0, 3)
    return MASS_R * (1 + 0.15 * lumps)


def eye_sphere(name, center, r, gaze, col, mat):
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=18, radius=r, calc_uvs=True)
    q = Vector((0, 0, 1)).rotation_difference(gaze)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(center) @ q.to_matrix().to_4x4(), verts=bm.verts)
    return ml.mesh_object(name, bm, col=col, mat=mat)


def iris_cap(name, center, r, gaze, angle, col, mat, rings=6, segs=28):
    """Goz kuresine oturan siyah iris kapagi (ince kabuk)."""
    bm = bmesh.new()
    q = Vector((0, 0, 1)).rotation_difference(gaze).to_matrix()
    rr = r * 1.012
    tip = bm.verts.new(center + q @ Vector((0, 0, rr)))
    rows = []
    for i in range(1, rings + 1):
        th = angle * i / rings
        row = []
        for j in range(segs):
            ph = 2 * math.pi * j / segs
            p = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))) * rr
            row.append(bm.verts.new(center + q @ p))
        rows.append(row)
    for j in range(segs):
        bm.faces.new((tip, rows[0][j], rows[0][(j + 1) % segs]))
    for i in range(rings - 1):
        for j in range(segs):
            a, b = rows[i][j], rows[i][(j + 1) % segs]
            c, d = rows[i + 1][(j + 1) % segs], rows[i + 1][j]
            bm.faces.new((a, d, c, b))
    obj = ml.mesh_object(name, bm, col=col, mat=mat)
    ml.solidify(obj, r * 0.025, -1.0)
    ml.set_smooth(obj)
    return obj


def ring(name, major, minor, tilt, beads, seed, col, mat, segs=120, sides=8):
    rnd = random.Random(seed)
    bead_u = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(beads))
    bm = bmesh.new()
    grid = []
    for i in range(segs):
        u = 2 * math.pi * i / segs
        rm = major * (1 + 0.025 * noise.noise(Vector((math.cos(u) * 2, math.sin(u) * 2, seed))))
        r = minor
        for bu in bead_u:
            du = math.atan2(math.sin(u - bu), math.cos(u - bu))
            r += minor * 1.6 * math.exp(-(du / 0.045) ** 2)
        cu, su = math.cos(u), math.sin(u)
        row = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            p = Vector(((rm + r * math.cos(a)) * cu, (rm + r * math.cos(a)) * su, r * math.sin(a)))
            row.append(bm.verts.new(p))
        grid.append(row)
    for i in range(segs):
        for k in range(sides):
            a, b = grid[i][k], grid[i][(k + 1) % sides]
            c, d = grid[(i + 1) % segs][(k + 1) % sides], grid[(i + 1) % segs][k]
            bm.faces.new((a, b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=Euler(tilt).to_matrix().to_4x4(), verts=bm.verts)
    return ml.mesh_object(name, bm, col=col, mat=mat)


def place_eyes(rnd):
    """(yon, yaricap) listesi: once ana goz, sonra 15 kucuk goz."""
    main_dir = Vector((0, -1, 0.12)).normalized()
    eyes = [(main_dir, 1.18)]
    radii = sorted((rnd.uniform(0.28, 0.72) for _ in range(SMALL_EYES)), reverse=True)
    for r in radii:
        for _ in range(4000):
            n = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
            if rnd.random() > 0.15 + 0.85 * max(0.0, -n.y + 0.3):
                continue
            a_new = math.asin(min(r / MASS_R, 0.99))
            ok = True
            for d, r2 in eyes:
                a2 = math.asin(min(r2 / MASS_R, 0.99))
                if n.angle(d) < (a_new + a2) * 1.12 + math.radians(3):
                    ok = False
                    break
            if ok:
                eyes.append((n, r))
                break
        else:
            raise RuntimeError("could not place eye")
    return eyes


def build(col):
    rnd = random.Random(7)
    os.makedirs(OUT, exist_ok=True)
    tex = vein_texture(os.path.join(OUT, "BakanGozDamar.png"))
    sclera = ml.material("Bakan_GozAki", (0.92, 0.88, 0.85), roughness=0.18, coat=0.6, image=tex)
    iris_m = ml.material("Bakan_Iris", (0.004, 0.003, 0.004), roughness=0.12, coat=1.0)
    flesh = ml.material("Bakan_Kutle", (0.011, 0.0025, 0.018), roughness=0.4, coat=0.25, specular=0.45)
    ring_m = ml.material("Bakan_Halka", (0.006, 0.006, 0.008), roughness=0.35, metallic=0.6)
    glow = ml.glow_material("Bakan_MorNeon", (0.55, 0.12, 1.0), 3.0, alpha=0.6, edge_soft=0.3, rim=True)

    eyes = place_eyes(rnd)
    eye_objs, iris_objs, eye_data = [], [], []
    for i, (n, r) in enumerate(eyes):
        d = mass_radius(n) - (0.30 if i == 0 else 0.12) * r
        c = n * d
        tilt = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        gaze = n if i == 0 else (n + (tilt - n * tilt.dot(n)).normalized() * rnd.uniform(0.15, 0.45)).normalized()
        name = "AnaGoz" if i == 0 else f"KucukGoz{i}"
        iname = "AnaIris" if i == 0 else f"Iris{i}"
        eye_objs.append(eye_sphere(name, c, r, gaze, col, sclera))
        iris_objs.append(iris_cap(iname, c, r, gaze, math.radians(25 if i == 0 else 30), col, iris_m))
        eye_data.append((n, r, d))

    # ---- Kutle: lumpy sphere + eyelid ridges hugging each eye
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    for v in bm.verts:
        n = v.co.normalized()
        rad = mass_radius(n)
        for (en, er, ed) in eye_data:
            ang = n.angle(en)
            # angle where the eye sphere meets the mass surface (approx.)
            hole = math.asin(min(er * 0.97 / max(rad, 1e-3), 0.99))
            rad += (0.22 if er > 1 else 0.13) * er * math.exp(-((ang - hole * 1.05) / (hole * 0.22)) ** 2)
            if ang < hole:
                rad -= 0.15 * er * (1 - ang / hole)
        v.co = n * rad
    kutle = ml.mesh_object("Kutle", bm, col=col, mat=flesh)
    ml.decimate(kutle, 9000)
    ml.set_smooth(kutle)

    # ---- Parilti: hafif mor Neon hale (kutleden biraz buyuk, yari saydam)
    parilti = kutle.copy()
    parilti.data = kutle.data.copy()
    parilti.name = "Parilti"
    parilti.data.name = "Parilti"
    col.objects.link(parilti)
    for v in parilti.data.vertices:
        v.co += v.normal * 0.09
    parilti.data.materials.clear()
    parilti.data.materials.append(glow)
    ml.decimate(parilti, 4000)
    ml.set_smooth(parilti)

    # ---- Halkalar
    halkalar = [
        ring("Halka1", 3.35, 0.07, (math.radians(72), math.radians(8), 0), 4, 1, col, ring_m),
        ring("Halka2", 3.60, 0.065, (math.radians(-28), math.radians(58), 0), 5, 2, col, ring_m),
        ring("Halka3", 3.85, 0.06, (math.radians(12), math.radians(-35), math.radians(40)), 3, 3, col, ring_m),
    ]

    cluster = [kutle] + eye_objs + iris_objs
    parts = cluster + [parilti] + halkalar
    lo, hi = ml.world_bounds(cluster)
    size = max(hi - lo)
    s = DIAMETER / size
    mid = (lo + hi) / 2
    norm = Matrix.Translation((0, 0, CENTER_Z)) @ Matrix.Scale(s, 4) @ Matrix.Translation(-mid)
    for o in parts:
        o.data.transform(norm)
    # rings must be concentric with the root (they spin around it in Roblox)
    for h in halkalar:
        lo_h, hi_h = ml.world_bounds([h])
        h.data.transform(Matrix.Translation(Vector((0, 0, CENTER_Z)) - (lo_h + hi_h) / 2))

    root = ml.make_root(col, (0, 0, CENTER_Z), size=(1.0, 1.0, 1.0))
    ordered = ([kutle] + [eye_objs[0], iris_objs[0]]
               + eye_objs[1:] + iris_objs[1:] + [parilti] + halkalar)
    ml.finalize_parts(ordered, root)
    return [root] + ordered


def main():
    preview = "--preview" in sys.argv
    scene = ml.reset_scene()
    col = ml.collection("Bakan")
    parts = build(col)
    for o in parts:
        print(f"{o.name:10s} tris={ml.tri_count(o)}")
    cl = [o for o in parts if o.name.startswith(("Kutle", "AnaGoz", "Kucuk", "AnaIris", "Iris"))]
    lo, hi = ml.world_bounds(cl)
    print("cluster bounds", tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi))
    lo, hi = ml.world_bounds(parts[1:])
    print("all bounds", tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi))

    if not preview:
        ml.export(OUT, "Bakan", parts)
        ml.save_blend(os.path.join(OUT, "Bakan.blend"))

    st = ml.studio(scene)
    ml.area_light("Ana", (-6, -9, 11), (0, 0, 5), 900, 5, (1.0, 0.96, 0.92), col=st)
    ml.area_light("ArkaSol", (-7, 7, 9), (0, 0, 5), 1300, 3, (0.75, 0.7, 1.0), col=st)
    ml.area_light("ArkaSag", (7, 8, 8), (0, 0, 5), 1300, 3, (0.75, 0.7, 1.0), col=st)
    ml.area_light("Dolgu", (7, -8, 3), (0, 0, 5), 160, 6, (0.8, 0.85, 1.0), col=st)
    mor = ml.point_light("MorIsik", (0, 0, 5.0), 400, (0.6, 0.2, 1.0), radius=1.5, col=st)
    mor.data.use_shadow = False  # Roblox PointLight gibi: kutlenin icinden disari sizar
    ml.glare_compositor(scene)

    renders = os.path.join(OUT, "renders")
    os.makedirs(renders, exist_ok=True)
    smp = 24 if preview else 64
    res = (625, 500) if preview else (1250, 1000)
    views = {
        "1_on": ((-3.5, -17, 6.0), (0, 0, 5.0), 50),
        "2_yan": ((17, -4, 7.0), (0, 0, 5.0), 50),
        "3_ust_capraz": ((10, 12, 12), (0, 0, 5.0), 50),
        "4_ana_goz_yakin": ((-1.6, -8.0, 6.0), (0, -1.5, 5.3), 70),
    }
    for name, (loc, tgt, lens) in views.items():
        cam = ml.camera("Cam_" + name, loc, tgt, lens)
        ml.render(scene, cam, os.path.join(renders, f"Bakan_{name}.png"), res, smp)

    ml.roblox_dummy((6.0, 0.5, 0), col=st)
    cam = ml.camera("Cam_olcek", (3.0, -22, 5.5), (3.0, 0, 4.2), 50)
    ml.render(scene, cam, os.path.join(renders, "Bakan_5_olcek.png"), res, smp)


if __name__ == "__main__":
    main()

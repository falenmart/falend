"""GERI DONEN - Fisilti'nin gelismis hali.

10 stud boyunda, iki kafali (biri ileri biri geri bakar), koyu bordo-siyah
govde ve catlaklarindan sizan turuncu Neon isik. Dort ince eklemli kol,
alt kisim kuyruk gibi incelen dort duman seridi.

Calistir:  python geri_donen.py [--preview]
"""

import math
import os
import sys

import bpy  # noqa: F401  (must come first: provides mathutils)
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monster_lib as ml  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "GeriDonen"))

HEIGHT = 10.0
HOVER = 0.5


def skull(co, rz):
    x, y, z = co
    if z < 0:
        k = -z / rz
        x *= 1 - 0.35 * k
        y *= 1 - 0.05 * k
        z *= 1 + 0.15 * k      # sivri, uzun cene
    if y > 0:
        y *= 1.18
    return Vector((x, y, z))


def head_cutters(col):
    """Goz cukurlari + yirtik dikey agiz (kafa yerel koordinatlari, -Y = yuz)."""
    return [
        ml.ellipsoid("_cut_gozL", (0.14, -0.45, 0.08), (0.095, 0.30, 0.105), 20, 14, col=col),
        ml.ellipsoid("_cut_gozR", (-0.14, -0.45, 0.08), (0.095, 0.30, 0.105), 20, 14, col=col),
        ml.ellipsoid("_cut_agiz1", (0.0, -0.45, -0.20), (0.045, 0.30, 0.22), 20, 14, col=col),
        ml.ellipsoid("_cut_agiz2", (0.03, -0.42, -0.42), (0.035, 0.30, 0.12), 20, 14, col=col),
    ]


def head_glows(m, i):
    """Cukurlarin icinde parlayan turuncu isik (Catlaklar parcasina katilir)."""
    out = []
    for k, (c, r) in enumerate((((0.14, -0.27, 0.08), (0.075, 0.07, 0.08)),
                                ((-0.14, -0.27, 0.08), (0.075, 0.07, 0.08)),
                                ((0.0, -0.30, -0.25), (0.035, 0.08, 0.30)))):
        g = ml.ellipsoid(f"_glow{i}_{k}", c, r, 16, 10)
        g.data.transform(m)
        out.append(g)
    return out


def build(col):
    flesh = ml.material("GeriDonen_Bordo", (0.024, 0.0018, 0.004), roughness=0.42, specular=0.45)
    smoke = ml.material("GeriDonen_Duman", (0.012, 0.0012, 0.0025), roughness=0.6, specular=0.3)
    neon = ml.glow_material("GeriDonen_TuruncuNeon", (1.0, 0.32, 0.04), 6.0)

    # ------------------------------------------------------------ Govde
    el = [
        {"co": (0, 0, 3.70), "size": (0.42, 0.40, 0.50)},    # kuyruk koku
        {"co": (0, 0, 4.30), "size": (0.60, 0.50, 0.55)},    # pelvis
        {"co": (0, 0, 5.15), "size": (0.44, 0.38, 0.62)},    # bel
        {"co": (0, 0, 6.30), "size": (0.80, 0.58, 0.92)},    # gogus kafesi
        {"co": (0, 0, 7.22), "size": (1.02, 0.50, 0.42)},    # omuz kemeri
        {"co": (0.98, 0, 7.36), "r": 0.34},
        {"co": (-0.98, 0, 7.36), "r": 0.34},
        {"co": (0.82, 0.25, 6.92), "r": 0.26},
        {"co": (-0.82, 0.25, 6.92), "r": 0.26},
        {"co": (0, 0, 7.85), "size": (0.40, 0.36, 0.36)},    # boyun kok
    ]
    for sy in (-1, 1):                                         # catal boyun
        for k in range(5):
            t = k / 4
            el.append({"co": (0, sy * (0.12 + 0.55 * t), 8.0 + 0.62 * t), "r": 0.22 - 0.05 * t})
    for k in range(10):                                        # omurga cikintilari
        z = 4.55 + k * 0.33
        yb = 0.36 + 0.2 * math.exp(-((z - 6.3) / 0.8) ** 2)
        el.append({"co": (0, yb + 0.04, z), "r": 0.10, "stiff": 1.6})
    for k in range(4):                                         # kaburgalar
        z = 5.75 + 0.3 * k
        for a in range(-5, 6):
            ang = math.radians(a * 13)
            rx_, ry_ = 0.74 - 0.04 * k, 0.56
            el.append({"co": (math.sin(ang) * rx_, -math.cos(ang) * ry_, z - abs(a) * 0.035),
                       "r": 0.075, "stiff": 1.4})
    govde = ml.metaball_object("Govde", el, resolution=0.045, col=col, mat=flesh)
    ml.decimate(govde, 9000)
    ml.displace_noise(govde, 0.025, 3.0, seed=21)
    ml.set_smooth(govde)

    # ------------------------------------------------------------- Kafalar
    rx, ry, rz = 0.39, 0.47, 0.60
    heads = []
    mats = []
    for name, sy in (("BasOn", -1), ("BasArka", 1)):
        h = ml.ellipsoid(name, (0, 0, 0), (rx, ry, rz), 40, 28, col=col, mat=flesh,
                         deform=lambda c: skull(c, rz))
        yaw = 0.0 if sy < 0 else math.pi
        m = (Matrix.Translation((0, 0.86 * sy, 9.15))
             @ Euler((0, 0, yaw)).to_matrix().to_4x4()
             @ Euler((math.radians(12), 0, 0)).to_matrix().to_4x4())
        for c in head_cutters(col):
            ml.boolean(h, c)
            ml.remove(c)
        h.data.transform(m)
        ml.displace_noise(h, 0.015, 4.0, seed=30 + sy)
        heads.append(h)
        mats.append(m)

    # ------------------------------------------------------------- Kollar
    def arm(name, sx, sy, z0, reach):
        s = Vector((0.95 * sx, 0.18 * sy, z0))
        j1 = s + Vector((0.45 * sx, 0.55 * sy, -0.70)) * reach
        j2 = j1 + Vector((0.28 * sx, 0.60 * sy, -0.95)) * reach
        w = j2 + Vector((0.02 * sx, 0.30 * sy, -1.05)) * reach
        pts = [s, s.lerp(j1, 0.5), j1, j1.lerp(j2, 0.5), j2, j2.lerp(w, 0.5), w]
        rad = [0.24, 0.09, 0.15, 0.08, 0.13, 0.065, 0.095]
        edges = [(i, i + 1) for i in range(6)]
        # joint spikes (pointing up/outwards, against the bend)
        for j, ln in ((2, 0.32), (4, 0.26)):
            base = pts[j]
            tip = base + Vector((0.12 * sx, -0.22 * sy, 0.18)) * (ln / 0.3)
            pts.append(tip)
            rad.append(0.012)
            edges.append((j, len(pts) - 1))
        # three long claws
        for k, spread in enumerate((-0.12, 0.0, 0.12)):
            side = Vector((spread, spread * 0.4 * sy, 0))
            a = w + Vector((0.0, 0.12 * sy, -0.12)) + side
            b = a + Vector((0.0, 0.22 * sy, -0.45)) + side * 0.6
            c = b + Vector((-0.05 * sx, 0.28 * sy, -0.32)) + side * 0.3
            i0 = len(pts)
            pts += [a, b, c]
            rad += [0.04, 0.03, 0.006]
            edges += [(6, i0), (i0, i0 + 1), (i0 + 1, i0 + 2)]
        o = ml.skin_object(name, [tuple(p) for p in pts], edges, rad, col=col, mat=flesh, subdiv=2)
        ml.decimate(o, 5000)
        ml.displace_noise(o, 0.01, 5.0, seed=sx * 3 + sy)
        return o

    kollar = [
        arm("Kol1", 1, -1, 7.55, 1.0),     # on-sol
        arm("Kol2", -1, -1, 7.55, 1.0),    # on-sag
        arm("Kol3", 1, 1, 7.05, 0.92),     # arka-sol
        arm("Kol4", -1, 1, 7.05, 0.92),    # arka-sag
    ]

    # ------------------------------------------------------------- Kuyruk
    kuyruk = []
    specs = [(45, 1.00, 0.00, 41), (135, 0.92, 0.25, 42), (225, 1.05, 0.10, 43), (315, 0.88, 0.35, 44)]
    for i, (a0, ln, lift, seed) in enumerate(specs, start=1):
        a = math.radians(a0)
        pts = []
        for k, z in enumerate((4.35, 3.40, 2.55, 1.75, 1.05, 0.45)):
            ang = a + k * 0.55
            rr = (0.26, 0.42, 0.52, 0.60, 0.70, 0.82)[k]
            zz = 4.35 - (4.35 - z) * ln + lift * (k / 5)
            pts.append((rr * math.cos(ang), rr * math.sin(ang), zz))
        o = ml.tube(f"Kuyruk{i}", pts, [0.46, 0.34, 0.24, 0.15, 0.07, 0.004],
                    samples=40, sides=12, flat=0.45, twist=math.radians(160 + 30 * i),
                    wobble=0.08, seed=seed, col=col, mat=smoke)
        ml.subsurf(o, 1)
        ml.displace_noise(o, 0.03, 3.0, seed=seed)
        kuyruk.append(o)

    # ---------------------------------------------------------- Catlaklar
    pieces = [ml.surface_cracks("_crk_body", govde, 20, seed=7, steps=(8, 18), step_len=0.13,
                                radius=0.034, branch_prob=0.12, lift=0.0, sides=6,
                                region=lambda p: 4.3 < p.z < 8.2)]
    for i, h in enumerate(heads):
        eyes = [mats[i] @ Vector((sx * 0.14, -0.40, 0.08)) for sx in (1, -1)]
        pieces.append(ml.surface_cracks(
            f"_crk_head{i}", h, 7, seed=50 + i, steps=(4, 9), step_len=0.08, radius=0.022,
            branch_prob=0.15, lift=0.0, sides=5,
            region=lambda p, e=eyes: any(0.13 < (p - q).length < 0.22 for q in e)))
        pieces += head_glows(mats[i], i)
    for i, k in enumerate(kollar):
        pieces.append(ml.surface_cracks(f"_crk_{k.name}", k, 2, seed=60 + i, steps=(4, 7),
                                        step_len=0.08, radius=0.02, branch_prob=0.0, lift=0.0, sides=5,
                                        region=lambda p: p.z > 5.5))
    catlak = ml.join("Catlaklar", pieces, col=col, mat=neon)
    ml.set_smooth(catlak)

    parts = [govde] + heads + kollar + kuyruk + [catlak]

    lo, hi = ml.world_bounds(parts)
    s = HEIGHT / (hi.z - lo.z)
    norm = Matrix.Translation((0, 0, HOVER)) @ Matrix.Scale(s, 4) @ Matrix.Translation((0, 0, -lo.z))
    for o in parts:
        o.data.transform(norm)

    root = ml.make_root(col, (0, 0, HOVER + HEIGHT * 0.58), size=(2.0, 1.0, 2.0))
    ml.finalize_parts(parts, root)
    return [root] + parts


def main():
    preview = "--preview" in sys.argv
    scene = ml.reset_scene()
    col = ml.collection("GeriDonen")
    parts = build(col)
    for o in parts:
        print(f"{o.name:10s} tris={ml.tri_count(o)}")
    lo, hi = ml.world_bounds(parts[1:])
    print("bounds", tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi))

    if not preview:
        ml.export(OUT, "GeriDonen", parts)
        ml.save_blend(os.path.join(OUT, "GeriDonen.blend"))

    st = ml.studio(scene)
    ml.area_light("Ana", (-6, -9, 12), (0, 0, 6), 1100, 5, (1.0, 0.95, 0.9), col=st)
    ml.area_light("ArkaSol", (-7, 7, 9), (0, 0, 6), 1500, 3, (0.7, 0.75, 1.0), col=st)
    ml.area_light("ArkaSag", (7, 8, 9), (0, 0, 6), 1500, 3, (0.7, 0.75, 1.0), col=st)
    ml.area_light("Dolgu", (7, -8, 3), (0, 0, 5), 200, 6, (0.8, 0.85, 1.0), col=st)
    ml.point_light("CatlakIsik", (0, -1.6, 6.5), 25, (1.0, 0.4, 0.1), col=st)
    ml.point_light("CatlakIsik2", (0, 1.6, 6.5), 25, (1.0, 0.4, 0.1), col=st)
    ml.glare_compositor(scene)

    renders = os.path.join(OUT, "renders")
    os.makedirs(renders, exist_ok=True)
    smp = 24 if preview else 64
    res = (500, 625) if preview else (1000, 1250)
    views = {
        "1_on_capraz": ((-10, -16, 7.0), (0, 0, 5.6), 50),
        "2_yan": ((20, 0, 6.2), (0, 0, 5.6), 50),
        "3_arka_capraz": ((10, 16, 7.0), (0, 0, 5.6), 50),
        "4_kafalar_yakin": ((-2.6, -7.0, 9.5), (0, -0.5, 9.2), 60),
    }
    for name, (loc, tgt, lens) in views.items():
        cam = ml.camera("Cam_" + name, loc, tgt, lens)
        ml.render(scene, cam, os.path.join(renders, f"GeriDonen_{name}.png"), res, smp)

    ml.roblox_dummy((4.6, 0.5, 0), col=st)
    cam = ml.camera("Cam_olcek", (2.3, -23, 6.2), (2.3, 0, 5.2), 50)
    ml.render(scene, cam, os.path.join(renders, "GeriDonen_5_olcek.png"), res, smp)


if __name__ == "__main__":
    main()

"""FISILTI - ana koridor canavari.

9 stud boyunda, ince/uzun, one egik, dizlere kadar uzanan kollar, yuz yerine
parlayan bulanik beyaz oval (iki bos goz cukuru + dikey kirmizi agiz yarigi),
duman gibi dalgalanan yirtik pelerin seritleri. Yerden 1 stud yukarida suzulur.

Calistir:  python fisilti.py [--preview]
"""

import math
import os
import sys

import bpy  # noqa: F401  (must come first: provides mathutils)
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monster_lib as ml  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "Fisilti"))

HEIGHT = 9.0   # boy (stud)
HOVER = 1.0    # yerden yukseklik (stud)


def head_shape(co, rz):
    """Uzun, cenesi daralan, arkasi siskin kafa."""
    x, y, z = co
    if z < 0:
        k = -z / rz
        x *= 1 - 0.28 * k
        y *= 1 - 0.12 * k
    if y > 0:
        y *= 1.12
        z *= 1.04
    return Vector((x, y, z))


def build(col):
    black = ml.material("Fisilti_MatSiyah", (0.008, 0.008, 0.009), roughness=0.72, specular=0.3)
    cloth = ml.material("Fisilti_Pelerin", (0.006, 0.006, 0.007), roughness=0.8, specular=0.3)
    face_mat = ml.glow_material("Fisilti_YuzNeon", (0.92, 0.94, 1.0), 1.6, alpha=0.82, edge_soft=0.75)
    mouth_mat = ml.glow_material("Fisilti_AgizNeon", (0.95, 0.2, 0.17), 6.0)

    # ------------------------------------------------------------ Govde
    # skeleton (x, y, z); -Y is front. Lean forward ~20 degrees.
    v = [
        (0.00, 0.05, 5.00),   # 0 pelvis
        (0.00, -0.05, 5.90),  # 1 waist
        (0.00, -0.30, 6.80),  # 2 lower chest
        (0.00, -0.62, 7.60),  # 3 upper chest
        (0.00, -0.98, 8.15),  # 4 neck base
        (0.00, -1.22, 8.55),  # 5 neck top
        (0.74, -0.66, 7.72),  # 6 L shoulder
        (-0.74, -0.66, 7.72),  # 7 R shoulder
        (0.28, 0.05, 4.80),   # 8 L hip
        (0.36, -0.28, 3.10),  # 9 L knee
        (0.34, 0.08, 1.55),   # 10 L ankle
        (0.36, -0.12, 1.00),  # 11 L toe (pointed down)
        (-0.28, 0.05, 4.80),  # 12 R hip
        (-0.38, -0.22, 3.05),  # 13 R knee
        (-0.33, 0.12, 1.60),  # 14 R ankle
        (-0.35, -0.05, 1.08),  # 15 R toe
    ]
    e = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (3, 6), (3, 7),
         (0, 8), (8, 9), (9, 10), (10, 11), (0, 12), (12, 13), (13, 14), (14, 15)]
    r = [(0.40, 0.30), (0.30, 0.24), (0.46, 0.30), (0.52, 0.30), (0.19, 0.19),
         (0.15, 0.15), 0.19, 0.19,
         0.20, 0.12, 0.075, 0.025,
         0.20, 0.12, 0.075, 0.025]
    govde = ml.skin_object("Govde", v, e, r, col=col, mat=black, subdiv=2)
    ml.displace_noise(govde, 0.03, 2.5, seed=1)

    # -------------------------------------------------------------- Bas
    rx, ry, rz = 0.46, 0.52, 0.68
    bas = ml.ellipsoid("Bas", (0, 0, 0), (rx, ry, rz), 40, 28, col=col, mat=black,
                       deform=lambda c: head_shape(c, rz))
    # goz cukurlari + agiz oyugu (kafa yerel koordinatlari, -Y = yuz)
    eye_l = ml.ellipsoid("_cut_eyeL", (0.135, -0.50, 0.11), (0.075, 0.32, 0.10), 24, 16, col=col,
                         rot=Euler((0, math.radians(-15), 0)))
    eye_r = ml.ellipsoid("_cut_eyeR", (-0.135, -0.50, 0.11), (0.075, 0.32, 0.10), 24, 16, col=col,
                         rot=Euler((0, math.radians(15), 0)))
    mouth_cut = ml.ellipsoid("_cut_mouth", (0, -0.47, -0.25), (0.032, 0.24, 0.29), 24, 16, col=col)
    for c in (eye_l, eye_r, mouth_cut):
        ml.boolean(bas, c)

    # ------------------------------------------------------------- Yuz
    yuz = ml.ellipsoid("Yuz", (0, 0, 0), (rx + 0.035, ry + 0.035, rz + 0.035), 48, 32,
                       col=col, mat=face_mat, deform=lambda c: head_shape(c, rz + 0.035))
    ml.solidify(yuz, 0.025, 1.0)
    oval = ml.tube("_cut_oval", [(0, -1.6, -0.06), (0, 0.0, -0.06)], [1.0, 1.0],
                   samples=2, sides=48, col=col, up_hint=Vector((0, 0, 1)))
    oval.data.transform(Matrix.Translation((0, 0, -0.06)) @ Matrix.Diagonal((0.29, 1, 0.47, 1))
                        @ Matrix.Translation((0, 0, 0.06)))
    ml.boolean(yuz, oval, 'INTERSECT')
    for c in (eye_l, eye_r, mouth_cut):
        ml.boolean(yuz, c)
    for c in (eye_l, eye_r, mouth_cut, oval):
        ml.remove(c)

    # ------------------------------------------------------------- Agiz
    agiz = ml.ellipsoid("Agiz", (0, -0.39, -0.25), (0.03, 0.09, 0.27), 20, 16,
                        col=col, mat=mouth_mat)

    # place head: forward of the neck, tilted down a little
    hm = Matrix.Translation((0, -1.55, 9.12)) @ Euler((math.radians(14), 0, 0)).to_matrix().to_4x4()
    for o in (bas, yuz, agiz):
        o.data.transform(hm)

    # ------------------------------------------------------------ Kollar
    def arm(name, sx):
        pts = [
            (0.70 * sx, -0.66, 7.70),  # 0 shoulder
            (0.98 * sx, -0.80, 6.70),  # 1
            (1.10 * sx, -0.92, 5.70),  # 2 elbow
            (1.13 * sx, -1.02, 4.70),  # 3
            (1.09 * sx, -1.10, 3.78),  # 4 wrist
            (1.07 * sx, -1.13, 3.55),  # 5 palm
        ]
        rad = [0.17, 0.115, 0.10, 0.085, 0.065, (0.11, 0.05)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
        palm = Vector(pts[5])
        inward = Vector((-sx, 0, 0))
        for i, spread in enumerate((-0.11, -0.04, 0.04, 0.11)):
            ln = 0.42 + (0.06 if i in (1, 2) else 0.0)
            b = palm + Vector((0, spread, -0.12))
            m = b + Vector((0, spread * 0.5, -ln)) + inward * 0.04
            t = m + Vector((0, spread * 0.4 - 0.05, -ln * 0.9)) + inward * 0.12
            base = len(pts)
            pts += [tuple(b), tuple(m), tuple(t)]
            rad += [0.035, 0.026, 0.008]
            edges += [(5, base), (base, base + 1), (base + 1, base + 2)]
        b = palm + Vector((0, -0.12, -0.02)) + inward * 0.03
        t = b + Vector((0, -0.10, -0.38)) + inward * 0.1
        base = len(pts)
        pts += [tuple(b), tuple(t)]
        rad += [0.035, 0.008]
        edges += [(5, base), (base, base + 1)]
        o = ml.skin_object(name, pts, edges, rad, col=col, mat=black, subdiv=2)
        ml.decimate(o, 6000)
        ml.displace_noise(o, 0.012, 4.0, seed=3 + sx)
        return o

    sol = arm("SolKol", 1)    # karakterin solu (+X)
    sag = arm("SagKol", -1)

    # ---------------------------------------------------------- Pelerin
    strips = [
        # (points, w0, w1, side_hint, seed)
        ([(0.42, -0.30, 7.75), (0.80, 0.15, 6.60), (0.92, 0.75, 5.10), (1.02, 1.35, 3.50), (1.08, 1.95, 2.30)],
         0.75, 0.45, (1, -0.2, 0), 11),
        ([(-0.42, -0.30, 7.75), (-0.82, 0.12, 6.55), (-0.95, 0.70, 5.00), (-1.05, 1.25, 3.60), (-1.12, 1.80, 2.50)],
         0.75, 0.45, (1, 0.2, 0), 12),
        ([(0.18, -0.30, 7.40), (0.25, 0.45, 6.20), (0.30, 1.25, 4.70), (0.34, 1.95, 3.30), (0.38, 2.65, 2.30)],
         0.65, 0.35, (1, 0, 0), 13),
        ([(-0.18, -0.30, 7.30), (-0.24, 0.50, 6.00), (-0.30, 1.30, 4.40), (-0.36, 2.05, 3.10), (-0.42, 2.80, 2.10)],
         0.65, 0.30, (1, 0, 0), 14),
        ([(0.30, 0.10, 5.40), (0.62, 0.38, 4.40), (0.74, 0.80, 3.25), (0.82, 1.25, 2.10), (0.86, 1.65, 1.30)],
         0.55, 0.30, (1, -0.5, 0), 15),
        ([(-0.30, 0.10, 5.40), (-0.62, 0.40, 4.35), (-0.75, 0.85, 3.15), (-0.83, 1.30, 2.05), (-0.88, 1.75, 1.25)],
         0.55, 0.30, (1, 0.5, 0), 16),
    ]
    pelerin = []
    for i, (pts, w0, w1, side, seed) in enumerate(strips, start=1):
        pelerin.append(ml.ribbon(f"Pelerin{i}", pts, w0 * 0.6, w1, side_hint=Vector(side), seed=seed,
                                 wave_amp=0.2, wave_freq=1.4, col=col, mat=cloth,
                                 fingers=3, split=0.38, bulge=1.8,
                                 twist=math.radians(50 if i % 2 else -50)))

    parts = [govde, bas, yuz, agiz, sol, sag] + pelerin

    # normalise: exactly HEIGHT tall, lowest point HOVER studs above the floor
    lo, hi = ml.world_bounds(parts)
    s = HEIGHT / (hi.z - lo.z)
    norm = Matrix.Translation((0, 0, HOVER)) @ Matrix.Scale(s, 4) @ Matrix.Translation((0, 0, -lo.z))
    for o in parts:
        o.data.transform(norm)

    root = ml.make_root(col, (0, -0.25, 1 + HEIGHT * 0.5), size=(2.0, 1.0, 2.0))
    ml.finalize_parts(parts, root)
    return [root] + parts


def main():
    preview = "--preview" in sys.argv
    scene = ml.reset_scene()
    col = ml.collection("Fisilti")
    parts = build(col)
    for o in parts:
        print(f"{o.name:10s} tris={ml.tri_count(o)}")
    lo, hi = ml.world_bounds(parts[1:])
    print("bounds", tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi))

    if not preview:
        ml.export(OUT, "Fisilti", parts)
        ml.save_blend(os.path.join(OUT, "Fisilti.blend"))

    st = ml.studio(scene)
    ml.area_light("Ana", (-6, -9, 12), (0, 0, 6), 900, 5, (1.0, 0.97, 0.93), col=st)
    ml.area_light("ArkaSol", (-7, 7, 9), (0, 0, 6), 1600, 3, (0.65, 0.75, 1.0), col=st)
    ml.area_light("ArkaSag", (7, 8, 9), (0, 0, 6), 1600, 3, (0.65, 0.75, 1.0), col=st)
    ml.area_light("Dolgu", (7, -8, 3), (0, 0, 5), 160, 6, (0.8, 0.85, 1.0), col=st)
    ml.glare_compositor(scene)

    renders = os.path.join(OUT, "renders")
    os.makedirs(renders, exist_ok=True)
    smp = 24 if preview else 64
    res = (500, 625) if preview else (1000, 1250)
    views = {
        "1_on_capraz": ((-9, -15, 7.0), (0, -0.4, 5.4), 50),
        "2_yan": ((19, -0.6, 6.0), (0, -0.4, 5.4), 50),
        "3_arka_capraz": ((9, 15, 7.0), (0, 0.3, 5.2), 50),
        "4_yuz_yakin": ((-1.2, -6.2, 9.6), (0, -1.6, 9.1), 70),
    }
    for name, (loc, tgt, lens) in views.items():
        cam = ml.camera("Cam_" + name, loc, tgt, lens)
        ml.render(scene, cam, os.path.join(renders, f"Fisilti_{name}.png"), res, smp)

    ref = ml.roblox_dummy((4.2, 0.5, 0), col=st)
    cam = ml.camera("Cam_olcek", (2.0, -22, 6.0), (2.0, 0, 5.0), 50)
    ml.render(scene, cam, os.path.join(renders, "Fisilti_5_olcek.png"), res, smp)


if __name__ == "__main__":
    main()

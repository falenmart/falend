"""
Kızıl Kemik İblisi (boss) - Blender'da model + rig + animasyon.

Referans görsel: beyaz kemik maske (tek siyah göz, boynuzlar, dişli ağız), arkasında kırmızı/beyaz diken
taç, bordo yırtık pelerin, kırmızı kaslı omuzlar, omuzlardan yere uzanan dev beyaz bıçak kollar, yere basan
ince kemik ön kollar ve pençeler.

Her rig parçası ayrı (rigid) bir mesh; kemiğin başı Roblox Motor6D pivotunda. Çıktılar:
  Blender/YamiBoss.blend                 (model + rig + Action'lar + exporter)
  Blender/Meshes/YamiBoss_Parts.fbx      (Studio 3D Importer için, parçalar "Boss_<Parça>")
  roblox/shared/BossRigData.luau         (pivot/merkez/boyut/renk tablosu - Roblox tarafı bunu kullanır)
  roblox/shared/Animations/Boss_*.rbxmx  (KeyframeSequence'lar)
  Previews/boss_*.png / .gif

Usage: python boss_build.py -- <blender_dir> <roblox_shared_dir> <preview_dir>
"""
import math
import os
import random
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anim_core as ac  # noqa: E402
import build_vfx  # noqa: E402
import roblox_anim_export as rax  # noqa: E402

FPS = 60
M = rax.M

# ------------------------------------------------------------------ palet (doku atlası)
PALETTE = [
    (236, 232, 222),  # 0 kemik beyazı
    (205, 18, 22),    # 1 kırmızı
    (70, 9, 24),      # 2 bordo pelerin
    (10, 10, 12),     # 3 siyah
    (118, 8, 14),     # 4 koyu kırmızı
    (2, 2, 2),        # 5 göz
    (170, 20, 30),    # 6 ağız içi
    (190, 186, 178),  # 7 gri kemik
]


def pal_uv(i):
    return (((i % 4) + 0.5) / 4.0, 1.0 - ((i // 4) + 0.5) / 4.0)


def make_palette(path):
    from PIL import Image
    img = Image.new("RGB", (256, 256))
    px = img.load()
    for i, c in enumerate(PALETTE):
        cx, cy = (i % 4) * 64, (i // 4) * 64
        for x in range(cx, cx + 64):
            for y in range(cy, cy + 64):
                px[x, y] = c
    img.save(path)


# ------------------------------------------------------------------ primitifler (Roblox ekseni)

class Acc:
    def __init__(self):
        self.verts, self.faces, self.uvs = [], [], []

    def v(self, p, ci):
        self.verts.append(tuple(float(x) for x in p))
        self.uvs.append(pal_uv(ci))
        return len(self.verts) - 1


def _basis(direction):
    d = ac.norm(direction)
    ref = np.array([0, 1, 0]) if abs(d[1]) < 0.9 else np.array([1, 0, 0])
    a = ac.norm(np.cross(d, ref))
    b = np.cross(d, a)
    return d, a, b


def ellipsoid(acc, c, r, ci, rot=None, segs=16, rings=10):
    c = np.asarray(c, float)
    R = np.eye(3) if rot is None else np.asarray(rot)
    top = acc.v(c + R @ np.array([0, r[1], 0]), ci)
    bot = acc.v(c + R @ np.array([0, -r[1], 0]), ci)
    ringsi = []
    for i in range(1, rings):
        th = math.pi * i / rings
        ring = []
        for k in range(segs):
            ph = 2 * math.pi * k / segs
            p = np.array([math.sin(th) * math.cos(ph) * r[0], math.cos(th) * r[1], math.sin(th) * math.sin(ph) * r[2]])
            ring.append(acc.v(c + R @ p, ci))
        ringsi.append(ring)
    for k in range(segs):
        k2 = (k + 1) % segs
        acc.faces.append((top, ringsi[0][k2], ringsi[0][k]))
        acc.faces.append((bot, ringsi[-1][k], ringsi[-1][k2]))
    for i in range(len(ringsi) - 1):
        a, b = ringsi[i], ringsi[i + 1]
        for k in range(segs):
            k2 = (k + 1) % segs
            acc.faces.append((a[k], a[k2], b[k2], b[k]))


def tube(acc, pts, ci, segs=10, cap=True):
    """pts: [(pos, radius)] - kapalı boru (kemik)."""
    rings = []
    for i, (p, r) in enumerate(pts):
        p = np.asarray(p, float)
        if i < len(pts) - 1:
            d = np.asarray(pts[i + 1][0], float) - p
        else:
            d = p - np.asarray(pts[i - 1][0], float)
        _, a, b = _basis(d)
        rings.append([acc.v(p + (math.cos(2 * math.pi * k / segs) * a + math.sin(2 * math.pi * k / segs) * b) * r, ci)
                      for k in range(segs)])
    for i in range(len(rings) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            acc.faces.append((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    if cap:
        for ring, p in ((rings[0], pts[0][0]), (rings[-1], pts[-1][0])):
            c = acc.v(p, ci)
            for k in range(segs):
                acc.faces.append((c, ring[(k + 1) % segs], ring[k]))


def spike(acc, base, direction, length, radius, ci, segs=8, flat=1.0):
    base = np.asarray(base, float)
    d, a, b = _basis(direction)
    tip = acc.v(base + d * length, ci)
    ring = [acc.v(base + (math.cos(2 * math.pi * k / segs) * a + math.sin(2 * math.pi * k / segs) * b * flat) * radius, ci)
            for k in range(segs)]
    c = acc.v(base, ci)
    for k in range(segs):
        k2 = (k + 1) % segs
        acc.faces.append((ring[k], ring[k2], tip))
        acc.faces.append((c, ring[k2], ring[k]))


def box(acc, c, size, ci, rot=None):
    c = np.asarray(c, float)
    R = np.eye(3) if rot is None else np.asarray(rot)
    hs = np.asarray(size, float) / 2
    ids = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            for dz in (-1, 1):
                ids.append(acc.v(c + R @ (hs * np.array([dx, dy, dz])), ci))
    for q in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
        acc.faces.append(tuple(ids[i] for i in q))


def blade(acc, p0, p1, w0, w1, thick, up, ci, stations=10, curve=0.0):
    """Yassı, sivrilen bıçak (p0 -> p1). up: bıçak düzleminin 'genişlik' yönü ipucu."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = ac.norm(p1 - p0)
    wdir = ac.norm(np.asarray(up, float) - np.dot(up, d) * d)
    ndir = np.cross(d, wdir)
    rings = []
    for i in range(stations + 1):
        t = i / stations
        c = p0 + (p1 - p0) * t + wdir * curve * math.sin(math.pi * t)
        w = (w0 + (w1 - w0) * t) / 2
        th = thick * (1 - 0.7 * t) / 2
        pts = [c + wdir * w, c + ndir * th, c - wdir * w * 0.85, c - ndir * th]
        rings.append([acc.v(p, ci) for p in pts])
    for i in range(stations):
        for k in range(4):
            k2 = (k + 1) % 4
            acc.faces.append((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    acc.faces.append(tuple(reversed(rings[0])))
    acc.faces.append(tuple(rings[-1]))
    return d, wdir, ndir


def mirror(p):
    return (-p[0], p[1], p[2])


# ------------------------------------------------------------------ rig tanımı
# (parça, ebeveyn, pivot) - Roblox koordinatı, zemin y=0, boss -Z'ye bakar
RIG = [
    ("Pelvis", "HumanoidRootPart", (0, 6.0, 0.4)),
    ("Chest", "Pelvis", (0, 9.2, 0.0)),
    ("Head", "Chest", (0, 12.2, -2.6)),
    ("Crown", "Chest", (0, 12.6, -0.6)),
    ("ShoulderR", "Chest", (2.8, 11.6, -1.4)),
    ("ShoulderL", "Chest", (-2.8, 11.6, -1.4)),
    ("BladeR", "ShoulderR", (6.3, 11.4, -1.6)),
    ("BladeL", "ShoulderL", (-6.3, 11.4, -1.6)),
    ("BladeTipR", "BladeR", (11.4, 6.6, -3.2)),
    ("BladeTipL", "BladeL", (-11.4, 6.6, -3.2)),
    ("ArmR", "Chest", (2.3, 10.4, -2.6)),
    ("ArmL", "Chest", (-2.3, 10.4, -2.6)),
    ("ForearmR", "ArmR", (3.2, 5.9, -5.2)),
    ("ForearmL", "ArmL", (-3.2, 5.9, -5.2)),
    ("ClawR", "ForearmR", (3.4, 1.25, -6.2)),
    ("ClawL", "ForearmL", (-3.4, 1.25, -6.2)),
]
PIVOT = {n: np.array(p, float) for n, _, p in RIG}
PARENT = {n: par for n, par, _ in RIG}
HRP_CENTER = np.array([0, 8.0, 0])
HRP_SIZE = (6, 8, 6)
PIVOT["HumanoidRootPart"] = HRP_CENTER
PART_STYLE = {  # yedek (mesh yokken) Roblox görünümü: şekil, renk indeksi, materyal
    "Pelvis": ("Ball", 2, "Fabric"), "Chest": ("Ball", 2, "Fabric"), "Head": ("Ball", 0, "SmoothPlastic"),
    "Crown": ("Spikes", 1, "SmoothPlastic"), "ShoulderR": ("Ball", 1, "SmoothPlastic"),
    "ShoulderL": ("Ball", 1, "SmoothPlastic"), "BladeR": ("Blade", 0, "SmoothPlastic"),
    "BladeL": ("Blade", 0, "SmoothPlastic"), "BladeTipR": ("Blade", 0, "SmoothPlastic"),
    "BladeTipL": ("Blade", 0, "SmoothPlastic"), "ArmR": ("Bone", 0, "SmoothPlastic"),
    "ArmL": ("Bone", 0, "SmoothPlastic"), "ForearmR": ("Bone", 0, "SmoothPlastic"),
    "ForearmL": ("Bone", 0, "SmoothPlastic"), "ClawR": ("Ball", 0, "SmoothPlastic"),
    "ClawL": ("Ball", 0, "SmoothPlastic"),
}


def build_part_meshes():
    rnd = random.Random(11)
    acc = {n: Acc() for n, _, _ in RIG}

    # -------- pelerin (Pelvis): yırtık uçlu çan
    a = acc["Pelvis"]
    segs, rows = 40, 9
    rings = []
    for i in range(rows + 1):
        t = i / rows
        y = 0.15 + t * 8.6
        rad = 3.0 + (1 - t) ** 1.6 * 5.2
        ring = []
        for k in range(segs):
            ph = 2 * math.pi * k / segs
            fold = 1 + 0.07 * math.sin(ph * 7 + t * 3) + 0.04 * math.sin(ph * 13)
            yy = y
            if i == 0:  # yırtık etek
                yy = 0.15 + (0.9 if k % 2 else 0.0) * rnd.uniform(0.3, 1.0)
                fold *= rnd.uniform(1.0, 1.12)
            ring.append(a.v((math.cos(ph) * rad * fold, yy, 0.6 + math.sin(ph) * rad * fold * 0.92), 2))
        rings.append(ring)
    for i in range(rows):
        for k in range(segs):
            k2 = (k + 1) % segs
            a.faces.append((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    for ring, yc in ((rings[0], 0.2), (rings[-1], 8.75)):
        c = a.v((0, yc, 0.6), 2)
        for k in range(segs):
            a.faces.append((c, ring[(k + 1) % segs], ring[k]))
    for k in range(10):  # yerde sürünen yırtık parçalar
        ph = rnd.uniform(0, 2 * math.pi)
        r0 = 7.6
        spike(a, (math.cos(ph) * r0, 0.15, 0.6 + math.sin(ph) * r0), (math.cos(ph), -0.05, math.sin(ph)),
              rnd.uniform(1.2, 2.6), 0.6, 2, segs=4, flat=0.25)

    # -------- göğüs / başlık (Chest): pelerinin üst kısmı + kemik boyun
    a = acc["Chest"]
    tube(a, [((0, 8.6, 0.4), 3.3), ((0, 10.4, -0.2), 3.0), ((0, 11.9, -0.9), 2.4), ((0, 12.9, -1.4), 1.6)], 2, segs=18)
    tube(a, [((0, 11.6, -1.6), 0.7), ((0, 12.3, -2.6), 0.55)], 7, segs=8)
    for s in (1, -1):  # kaburgalar (pelerinin açık yerinde)
        for j in range(3):
            tube(a, [((0.2 * s, 10.6 - j * 0.55, -2.6), 0.13), ((1.1 * s, 10.4 - j * 0.55, -2.5), 0.12),
                     ((1.7 * s, 10.1 - j * 0.55, -2.0), 0.1)], 0, segs=6)

    # -------- kafa / maske (Head)
    a = acc["Head"]
    hc = np.array([0, 12.7, -3.9])
    ellipsoid(a, hc, (1.25, 1.45, 1.15), 0)
    ellipsoid(a, hc + np.array([0, -0.95, -0.55]), (0.95, 0.7, 0.8), 0)            # çene
    box(a, hc + np.array([0, -0.95, -1.2]), (1.15, 0.42, 0.25), 6)                  # ağız
    for i in range(6):                                                               # dişler
        x = -0.48 + i * 0.19
        spike(a, hc + np.array([x, -0.75, -1.32]), (0, -1, -0.15), 0.32, 0.07, 0, segs=4)
        spike(a, hc + np.array([x + 0.09, -1.16, -1.3]), (0, 1, -0.15), 0.26, 0.06, 0, segs=4)
    ellipsoid(a, hc + np.array([0, 0.35, -1.12]), (0.3, 0.3, 0.12), 5)              # tek göz
    for s in (1, -1):
        for j in range(3):                                                           # siyah çizgiler
            box(a, hc + np.array([0.55 * s, 0.05 - j * 0.22, -1.02]), (0.42, 0.07, 0.08), 3,
                rot=ac.euler3(0, 0, 18 * s))
        spike(a, hc + np.array([0.45 * s, 1.15, 0.0]), (0.25 * s, 1, 0.15), 2.4, 0.3, 0, segs=7)    # boynuz
        spike(a, hc + np.array([1.1 * s, 0.45, 0.0]), (1, 0.45, 0.25), 2.0, 0.33, 0, segs=7, flat=0.6)  # kulak
        box(a, hc + np.array([0.35 * s, 0.75, -1.05]), (0.5, 0.06, 0.06), 6, rot=ac.euler3(0, 0, -20 * s))
    spike(a, hc + np.array([0, 1.2, -0.35]), (0, 1, -0.1), 1.5, 0.22, 0, segs=6)    # orta boynuz
    spike(a, hc + np.array([0, -1.45, -0.7]), (0, -1, -0.25), 2.0, 0.3, 0, segs=6)   # sakal dikeni
    for i, vtx in enumerate(a.verts):  # maskeyi biraz büyüt (referanstaki oran)
        a.verts[i] = tuple(hc + (np.array(vtx) - hc) * 1.3)

    # -------- taç (Crown): kırmızı/beyaz diken yelpazesi
    a = acc["Crown"]
    cc = np.array([0, 13.0, -0.2])
    n = 13
    for i in range(n):
        ang = math.radians(-82 + 164 * i / (n - 1))
        d = np.array([math.sin(ang), math.cos(ang), 0.28])
        length = 4.2 + 2.6 * math.cos(ang) ** 2 + rnd.uniform(-0.4, 0.4)
        ci = 1 if i % 2 == 0 else 0
        spike(a, cc + d * 1.2, d, length, 1.35 if ci == 1 else 1.0, ci, segs=4, flat=0.22)
        if ci == 0:
            spike(a, cc + d * 1.6 + np.array([0, 0, 0.12]), d, length * 0.8, 0.45, 1, segs=4, flat=0.2)
    ellipsoid(a, cc, (1.6, 1.2, 0.8), 4)

    # -------- omuzlar (kaslı kırmızı)
    for name, s in (("ShoulderR", 1), ("ShoulderL", -1)):
        a = acc[name]
        for c, r in [((4.3, 12.2, -1.4), (2.0, 1.6, 1.7)), ((5.3, 11.3, -1.1), (1.6, 1.4, 1.5)),
                     ((3.6, 11.0, -2.2), (1.3, 1.2, 1.1)), ((5.0, 12.6, -0.4), (1.2, 1.0, 1.1)),
                     ((6.2, 11.6, -1.7), (1.1, 1.2, 1.1))]:
            p = (c[0] * s, c[1], c[2])
            ellipsoid(a, p, r, 1 if rnd.random() < 0.6 else 4, segs=14, rings=9)

    # -------- bıçak kollar
    for s, up, low in ((1, "BladeR", "BladeTipR"), (-1, "BladeL", "BladeTipL")):
        a = acc[up]
        p0, p1 = PIVOT[up], PIVOT[low]
        hint = np.array([0.0, 0.3, -1.0])
        d, wdir, ndir = blade(a, p0 + (p1 - p0) * -0.05, p1 + (p1 - p0) * 0.08, 3.0, 3.8, 1.0, hint, 0)
        for j in range(3):  # bıçak yüzeyinde siyah şeritler
            t0, t1 = 0.12 + j * 0.3, 0.3 + j * 0.3
            c0 = p0 + (p1 - p0) * t0 + ndir * 0.36 - wdir * 0.2
            c1 = p0 + (p1 - p0) * t1 + ndir * 0.3 + wdir * 0.35
            blade(a, c0, c1, 0.28, 0.08, 0.12, ndir, 3, stations=3)
            blade(a, c0 - ndir * 0.72, c1 - ndir * 0.6, 0.28, 0.08, 0.12, ndir, 3, stations=3)
        for j in range(2):
            t = 0.35 + j * 0.3
            c = p0 + (p1 - p0) * t + wdir * 0.5
            spike(a, c, (p1 - p0), 1.4, 0.16, 1, segs=4, flat=0.3)
        a = acc[low]
        q0 = PIVOT[low]
        q1 = np.array([16.6 * s, 0.6, -5.6])
        blade(a, q0, q1, 3.8, 0.05, 0.85, hint, 0, stations=12, curve=0.6)
        for j in range(3):
            t = 0.15 + j * 0.25
            c = q0 + (q1 - q0) * t
            spike(a, c + np.array([0, 0.15, -0.35]), (q1 - q0), 1.6 - j * 0.3, 0.17, 1 if j != 1 else 3, segs=4, flat=0.3)

    # -------- ince kemik ön kollar + pençeler
    for s, arm, fore, claw in ((1, "ArmR", "ForearmR", "ClawR"), (-1, "ArmL", "ForearmL", "ClawL")):
        pa, pf, pc = PIVOT[arm], PIVOT[fore], PIVOT[claw]
        tube(acc[arm], [(pa, 0.42), ((pa + pf) / 2, 0.32), (pf, 0.38)], 0, segs=9)
        ellipsoid(acc[arm], pf, (0.48, 0.48, 0.48), 7, segs=10, rings=7)
        tube(acc[fore], [(pf, 0.33), ((pf + pc) / 2, 0.26), (pc, 0.3)], 0, segs=9)
        a = acc[claw]
        ellipsoid(a, pc + np.array([0, -0.45, -0.35]), (0.75, 0.38, 0.65), 0, segs=10, rings=7)
        for k in range(4):
            ang = math.radians(-40 + 27 * k) * s
            d = np.array([math.sin(ang), -0.55, -math.cos(ang)])
            spike(a, pc + np.array([math.sin(ang) * 0.5, -0.55, -0.6 - math.cos(ang) * 0.3]), d, 1.3, 0.17, 0, segs=5)
        spike(a, pc + np.array([0.55 * s, -0.5, 0.1]), (0.5 * s, -0.6, 0.6), 0.9, 0.15, 0, segs=5)
    return acc


# ------------------------------------------------------------------ animasyonlar (FK, derece)
# Her anahtar: {parça: (rx, ry, rz)} veya Pelvis için (dx, dy, dz, rx, ry, rz)
def K(**kw):
    return kw


BOSS_ANIMS = [
    {"name": "Boss_Idle", "priority": "Idle", "loop": True, "keys": [
        (0.0, K()),
        (1.2, K(Pelvis=(0, 0.18, 0, 0, 0, 0), Chest=(-3, 0, 0), Head=(5, 0, 4), Crown=(-5, 0, 0),
                BladeR=(0, 0, 4), BladeL=(0, 0, -4), ShoulderR=(0, 0, 3), ShoulderL=(0, 0, -3))),
        (2.4, K()),
    ], "markers": {}},
    {"name": "Boss_Walk", "priority": "Movement", "loop": True, "keys": [
        (0.0, K(Pelvis=(0, -0.3, 0, 0, 4, 3), Chest=(0, -5, 0), ArmR=(-24, 0, 0), ForearmR=(10, 0, 0),
                ArmL=(22, 0, 0), ForearmL=(-12, 0, 0), BladeR=(9, 0, 5), BladeL=(-9, 0, -5), Head=(0, 4, 0))),
        (0.3, K(Pelvis=(0, 0.25, 0, 0, 0, 0), ArmR=(2, 0, 0), ForearmR=(-8, 0, 0), ArmL=(-2, 0, 0),
                ForearmL=(-30, 0, 0), ClawL=(25, 0, 0))),
        (0.6, K(Pelvis=(0, -0.3, 0, 0, -4, -3), Chest=(0, 5, 0), ArmR=(22, 0, 0), ForearmR=(-12, 0, 0),
                ArmL=(-24, 0, 0), ForearmL=(10, 0, 0), BladeR=(-9, 0, 5), BladeL=(9, 0, -5), Head=(0, -4, 0))),
        (0.9, K(Pelvis=(0, 0.25, 0, 0, 0, 0), ArmR=(-2, 0, 0), ForearmR=(-30, 0, 0), ClawR=(25, 0, 0),
                ArmL=(2, 0, 0), ForearmL=(-8, 0, 0))),
        (1.2, K(Pelvis=(0, -0.3, 0, 0, 4, 3), Chest=(0, -5, 0), ArmR=(-24, 0, 0), ForearmR=(10, 0, 0),
                ArmL=(22, 0, 0), ForearmL=(-12, 0, 0), BladeR=(9, 0, 5), BladeL=(-9, 0, -5), Head=(0, 4, 0))),
    ], "markers": {}},
    {"name": "Boss_Slash", "priority": "Action", "loop": False, "keys": [
        (0.0, K()),
        (0.5, K(Chest=(-4, -22, 0), Head=(0, 18, 0), ShoulderR=(0, -42, 14), BladeR=(0, -10, 32),
                BladeTipR=(0, 0, 12), ShoulderL=(0, -10, 0), Pelvis=(0, -0.3, 0.6, 0, -8, 0))),
        (0.65, K(Chest=(6, 26, 0), Head=(0, -12, 0), ShoulderR=(15, 70, -10), BladeR=(0, 15, 5),
                 BladeTipR=(0, 0, 6), ShoulderL=(0, 12, 0), Pelvis=(0, -0.6, -1.4, 0, 12, 0))),
        (0.95, K(Chest=(6, 30, 0), Head=(0, -14, 0), ShoulderR=(16, 76, -11), BladeR=(0, 18, 4),
                 BladeTipR=(0, 0, 4), ShoulderL=(0, 14, 0), Pelvis=(0, -0.6, -1.4, 0, 14, 0))),
        (1.5, K()),
    ], "markers": {"Hit": 0.62}},
    {"name": "Boss_Slam", "priority": "Action", "loop": False, "keys": [
        (0.0, K()),
        (0.8, K(Pelvis=(0, 1.0, 0.8, 0, 0, 0), Chest=(-18, 0, 0), Head=(-16, 0, 0), Crown=(-12, 0, 0),
                ShoulderR=(-20, 0, 34), BladeR=(-10, 0, 62), BladeTipR=(0, 0, 38),
                ShoulderL=(-20, 0, -34), BladeL=(-10, 0, -62), BladeTipL=(0, 0, -38))),
        (1.0, K(Pelvis=(0, -1.1, -1.6, 0, 0, 0), Chest=(10, 0, 0), Head=(10, 0, 0), Crown=(8, 0, 0),
                ShoulderR=(10, 45, -5), BladeR=(0, 0, -10), BladeTipR=(0, 0, -8),
                ShoulderL=(10, -45, 5), BladeL=(0, 0, 10), BladeTipL=(0, 0, 8))),
        (1.4, K(Pelvis=(0, -1.0, -1.6, 0, 0, 0), Chest=(9, 0, 0), Head=(8, 0, 0),
                ShoulderR=(9, 44, -5), BladeR=(0, 0, -10), BladeTipR=(0, 0, -8),
                ShoulderL=(9, -44, 5), BladeL=(0, 0, 10), BladeTipL=(0, 0, 8))),
        (2.0, K()),
    ], "markers": {"Hit": 1.0}},
    {"name": "Boss_Roar", "priority": "Action", "loop": False, "keys": [
        (0.0, K()),
        (0.6, K(Chest=(-20, 0, 0), Head=(-32, 0, 0), Crown=(-16, 0, 0), ShoulderR=(-6, 0, 16),
                ShoulderL=(-6, 0, -16), BladeR=(0, 0, 46), BladeL=(0, 0, -46), Pelvis=(0, 0.6, 0.4, 0, 0, 0))),
        (0.72, K(Chest=(-22, 0, 2), Head=(-34, 0, -4), Crown=(-18, 0, 0), ShoulderR=(-6, 0, 18),
                 ShoulderL=(-6, 0, -18), BladeR=(0, 0, 50), BladeL=(0, 0, -50), Pelvis=(0, 0.6, 0.4, 0, 0, 0))),
        (0.84, K(Chest=(-21, 0, -2), Head=(-33, 0, 4), Crown=(-17, 0, 0), ShoulderR=(-6, 0, 17),
                 ShoulderL=(-6, 0, -17), BladeR=(0, 0, 48), BladeL=(0, 0, -48), Pelvis=(0, 0.6, 0.4, 0, 0, 0))),
        (1.3, K(Chest=(-18, 0, 0), Head=(-28, 0, 0), Crown=(-14, 0, 0), ShoulderR=(-6, 0, 14),
                ShoulderL=(-6, 0, -14), BladeR=(0, 0, 40), BladeL=(0, 0, -40), Pelvis=(0, 0.5, 0.4, 0, 0, 0))),
        (1.8, K()),
    ], "markers": {"Burst": 0.75}},
    {"name": "Boss_Lunge", "priority": "Action", "loop": False, "keys": [
        (0.0, K()),
        (0.4, K(Pelvis=(0, -1.3, 1.2, 0, 0, 0), Chest=(26, 0, 0), Head=(-10, 0, 0),
                ShoulderR=(0, -34, 6), ShoulderL=(0, 34, -6), BladeR=(0, -12, 18), BladeL=(0, 12, -18),
                ArmR=(-20, 0, 0), ArmL=(-20, 0, 0))),
        (0.7, K(Pelvis=(0, -0.4, -2.6, 0, 0, 0), Chest=(14, 0, 0), Head=(-4, 0, 0),
                ShoulderR=(8, 46, 0), ShoulderL=(8, -46, 0), BladeR=(0, 18, 8), BladeL=(0, -18, -8),
                ArmR=(30, 0, 0), ArmL=(30, 0, 0))),
        (1.0, K(Pelvis=(0, -0.4, -2.6, 0, 0, 0), Chest=(14, 0, 0), ShoulderR=(8, 50, 0), ShoulderL=(8, -50, 0),
                BladeR=(0, 20, 8), BladeL=(0, -20, -8), ArmR=(28, 0, 0), ArmL=(28, 0, 0))),
        (1.4, K()),
    ], "markers": {"Lunge": 0.42, "Hit": 0.7}},
    {"name": "Boss_Death", "priority": "Action4", "loop": False, "keys": [
        (0.0, K()),
        (0.8, K(Pelvis=(0, -2.4, 0, 0, 0, 0), Chest=(38, 0, 0), Head=(30, 0, 0), Crown=(20, 0, 0),
                BladeR=(0, 0, -25), BladeL=(0, 0, 25), ArmR=(25, 0, 10), ArmL=(25, 0, -10))),
        (2.2, K(Pelvis=(0, -3.9, 0, 8, 0, 6), Chest=(56, 0, 10), Head=(42, 10, 0), Crown=(30, 0, 0),
                BladeR=(0, 0, -40), BladeL=(0, 0, 32), ArmR=(55, 0, 25), ArmL=(55, 0, -25),
                ForearmR=(-40, 0, 0), ForearmL=(-40, 0, 0))),
    ], "markers": {}},
]


def transform_for(part, val):
    if part == "Pelvis" and len(val) == 6:
        return ac.T(val[0], val[1], val[2]) @ ac.M4(ac.euler3(val[3], val[4], val[5]))
    return ac.M4(ac.euler3(*val))


# ------------------------------------------------------------------ Blender

def rb_vec(p):
    return Vector((-p[0], p[2], p[1]))


def rb_mat(m4):
    return M @ Matrix([list(r) for r in m4]) @ M


def build_armature():
    arm_data = bpy.data.armatures.new("YamiBossRig")
    arm_obj = bpy.data.objects.new("YamiBossRig", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    hrp = eb.new("HumanoidRootPart")
    hrp.head = rb_vec(HRP_CENTER)
    hrp.tail = rb_vec(HRP_CENTER + np.array([0, 0, -2.0]))
    children = {}
    for n, par, _ in RIG:
        children.setdefault(par, []).append(n)
    for n, par, p in RIG:
        b = eb.new(n)
        head = np.array(p, float)
        kids = children.get(n)
        if kids:
            tail = PIVOT[kids[0]]
        else:
            tail = head + np.array([0, -1.0, -0.6])
        if np.linalg.norm(tail - head) < 0.2:
            tail = head + np.array([0, 1.0, 0])
        b.head = rb_vec(head)
        b.tail = rb_vec(tail)
    for n, par, _ in RIG:
        eb[n].parent = eb[par]
        eb[n].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_data.display_type = "STICK"
    arm_obj.show_in_front = True
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm_obj


def basis_for(arm_obj, part, tr4):
    A = arm_obj.data.bones[part].matrix_local
    Tj = ac.T(*PIVOT[part])
    D = rb_mat(Tj @ tr4 @ np.linalg.inv(Tj))
    return A.inverted() @ D @ A


EASE = {"default": ("BEZIER", "AUTO")}


def build_action(arm_obj, anim):
    action = bpy.data.actions.new(anim["name"])
    action.use_fake_user = True
    action["roblox_priority"] = anim["priority"]
    action["roblox_loop"] = bool(anim["loop"])
    rax.assign_action(arm_obj, action)
    parts = [n for n, _, _ in RIG]
    prev = {}
    for t, keys in anim["keys"]:
        frame = round(t * FPS)
        for part in parts:
            val = keys.get(part, (0, 0, 0, 0, 0, 0) if part == "Pelvis" else (0, 0, 0))
            B = basis_for(arm_obj, part, transform_for(part, val))
            loc, rot, _ = B.decompose()
            if part in prev and prev[part].dot(rot) < 0:
                rot = -rot
            prev[part] = rot
            pb = arm_obj.pose.bones[part]
            pb.rotation_quaternion = rot
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if part == "Pelvis":
                pb.location = loc
                pb.keyframe_insert("location", frame=frame)
    for fc in rax.action_fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"
        fc.update()
    for mname, t in anim["markers"].items():
        mk = action.pose_markers.new(mname)
        mk.frame = round(t * FPS)
    return action


def reset_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)


def write_rig_luau(path, bboxes):
    def v3(p):
        return f"Vector3.new({p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f})"

    lines = [
        "-- OTOMATİK ÜRETİLDİ (src/blender/boss_build.py). Elle değiştirme; Blender script'ini tekrar çalıştır.",
        "-- Kızıl Kemik İblisi rig verisi: Roblox koordinatı, zemin y=0, boss -Z'ye bakar.",
        "return {",
        f"\tRootCenter = {v3(HRP_CENTER)},",
        f"\tRootSize = {v3(HRP_SIZE)},",
        f"\tHipHeight = {HRP_CENTER[1] - HRP_SIZE[1] / 2:.4f},",
        "\tPalette = {",
    ]
    for c in PALETTE:
        lines.append(f"\t\tColor3.fromRGB({c[0]}, {c[1]}, {c[2]}),")
    lines.append("\t},")
    lines.append("\tParts = {")
    for n, par, p in RIG:
        lo, hi = bboxes[n]
        center = (lo + hi) / 2
        size = hi - lo
        shape, ci, mat = PART_STYLE[n]
        lines.append(
            f'\t\t{{ Name = "{n}", Parent = "{par}", Pivot = {v3(p)}, Center = {v3(center)}, '
            f'Size = {v3(size)}, Shape = "{shape}", Color = {ci + 1}, Material = "{mat}" }},'
        )
    lines.append("\t},")
    lines.append("}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def render_still(path, res=(900, 700), samples=24):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def setup_scene():
    sc = bpy.context.scene
    world = bpy.data.worlds.new("BossWorld")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.33, 0.33, 0.36, 1)
    gme = bpy.data.meshes.new("Ground")
    s = 40
    gme.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("Ground", gme)
    gme.materials.append(build_vfx.make_flat_material("GroundMat", (0.28, 0.28, 0.3), 1.0))
    sc.collection.objects.link(g)
    cam_data = bpy.data.cameras.new("BossCam")
    cam_data.lens = 32
    cam = bpy.data.objects.new("BossCam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = rb_vec((7, 9.5, -27))
    cam.rotation_euler = (rb_vec((0, 7.5, -2)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.2
    sun = bpy.data.objects.new("Sun", sun_data)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(35), math.radians(-25), math.radians(20))
    rim = bpy.data.lights.new("Rim", "AREA")
    rim.energy = 3000
    rim.size = 10
    rim.color = (1.0, 0.25, 0.2)
    ro = bpy.data.objects.new("Rim", rim)
    sc.collection.objects.link(ro)
    ro.location = rb_vec((0, 14, 12))
    ro.rotation_euler = (rb_vec((0, 8, 0)) - ro.location).to_track_quat("-Z", "Y").to_euler()
    return [g, cam, ro, sun]


def render_gif(arm_obj, action, path, fps_out=12, res=(420, 330)):
    from PIL import Image
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = 10
    reset_pose(arm_obj)
    rax.assign_action(arm_obj, action)
    f0, f1 = action.frame_range
    frames = []
    tmp = path + ".frame.png"
    f = f0
    while f <= f1 + 1e-6:
        sc.frame_set(int(round(f)))
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        frames.append(Image.open(tmp).convert("RGB").copy())
        f += FPS / fps_out
    os.remove(tmp)
    pal = [fr.convert("P", palette=Image.ADAPTIVE, colors=128) for fr in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / fps_out), loop=0)


def main(blend_dir, shared_dir, preview_dir):
    blend_dir, shared_dir, preview_dir = (os.path.abspath(p) for p in (blend_dir, shared_dir, preview_dir))
    build_vfx.reset_scene()
    sc = bpy.context.scene
    sc.render.fps = FPS
    tex_dir = os.path.join(blend_dir, "Textures")
    os.makedirs(tex_dir, exist_ok=True)
    pal_path = os.path.join(tex_dir, "T_BossPalette.png")
    make_palette(pal_path)
    mat = build_vfx.make_image_material("M_BossPalette", pal_path, alpha=False, roughness=0.55)
    # palet dokusu keskin kalsın
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE":
            node.interpolation = "Closest"

    arm_obj = build_armature()
    accs = build_part_meshes()
    objs = {}
    bboxes = {}
    for n, _, _ in RIG:
        a = accs[n]
        vs = np.array(a.verts)
        bboxes[n] = (vs.min(axis=0), vs.max(axis=0))
        o = build_vfx.build_object("Boss_" + n, a.verts, a.faces, a.uvs, smooth=n in ("Pelvis", "Chest", "Head", "ShoulderR", "ShoulderL"), material=mat)
        vg = o.vertex_groups.new(name=n)
        vg.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
        mod = o.modifiers.new("Armature", "ARMATURE")
        mod.object = arm_obj
        o.parent = arm_obj
        objs[n] = o
    write_rig_luau(os.path.join(shared_dir, "BossRigData.luau"), bboxes)

    # FBX: her parça kendi bbox merkezinde (Roblox MeshPart'ı zaten merkeze alır)
    fbx_objs = list(objs.values())
    for o in fbx_objs:
        o.modifiers["Armature"].show_viewport = False
        o.modifiers["Armature"].show_render = False
    build_vfx.export_fbx(fbx_objs, os.path.join(blend_dir, "Meshes", "YamiBoss_Parts.fbx"))
    for o in fbx_objs:
        o.modifiers["Armature"].show_viewport = True
        o.modifiers["Armature"].show_render = True

    actions = []
    for anim in BOSS_ANIMS:
        reset_pose(arm_obj)
        actions.append(build_action(arm_obj, anim))
    results = rax.export_all(arm_obj, os.path.join(shared_dir, "Animations"))
    for path, nk, parts in results:
        print(f"exported {os.path.basename(path)}: {nk} keyframes, {len(parts)} joints")

    txt = bpy.data.texts.new("roblox_anim_export.py")
    with open(os.path.join(HERE, "roblox_anim_export.py"), encoding="utf-8") as fh:
        txt.write(fh.read())

    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        extra = setup_scene()
        reset_pose(arm_obj)
        idle = bpy.data.actions["Boss_Idle"]
        rax.assign_action(arm_obj, idle)
        sc.frame_set(0)
        render_still(os.path.join(preview_dir, "boss_model.png"))
        for name in ("Boss_Walk", "Boss_Slam", "Boss_Slash", "Boss_Roar", "Boss_Lunge"):
            render_gif(arm_obj, bpy.data.actions[name], os.path.join(preview_dir, f"anim_{name}.gif"))
            print("gif", name)
        for o in extra:
            bpy.data.objects.remove(o, do_unlink=True)

    reset_pose(arm_obj)
    rax.assign_action(arm_obj, bpy.data.actions["Boss_Idle"])
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(blend_dir, "YamiBoss.blend"), compress=True)
    print("saved boss blend")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv[0], argv[1], argv[2] if len(argv) > 2 else None)

"""Tiny software renderer (PIL) for quick pose checks of the R15 rig + katana."""
import math

import numpy as np
from PIL import Image, ImageDraw

import anim_core as ac

COLORS = {
    "Head": (232, 196, 160), "UpperTorso": (60, 60, 66), "LowerTorso": (40, 40, 44),
    "RightUpperArm": (225, 188, 152), "RightLowerArm": (225, 188, 152), "RightHand": (215, 178, 142),
    "LeftUpperArm": (205, 170, 138), "LeftLowerArm": (205, 170, 138), "LeftHand": (195, 160, 128),
    "RightUpperLeg": (30, 30, 34), "RightLowerLeg": (30, 30, 34), "RightFoot": (20, 20, 22),
    "LeftUpperLeg": (24, 24, 28), "LeftLowerLeg": (24, 24, 28), "LeftFoot": (16, 16, 18),
}


def box_faces(m, size, color):
    sx, sy, sz = (s / 2 for s in size)
    c = [np.array([dx * sx, dy * sy, dz * sz, 1.0]) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    w = [(m @ p)[:3] for p in c]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [([w[i] for i in q], color) for q in quads]


def katana_faces(km):
    faces = []
    faces += box_faces(km @ ac.T(0, 0.02, -2.26), (0.07, 0.22, 3.4), (90, 140, 230))   # blade
    faces += box_faces(km @ ac.T(0, -0.1, -2.26), (0.08, 0.04, 3.4), (240, 240, 120))  # edge marker
    faces += box_faces(km @ ac.T(0, 0, -0.53), (0.5, 0.58, 0.06), (35, 35, 38))        # tsuba
    faces += box_faces(km @ ac.T(0, 0, 0.13), (0.19, 0.25, 1.27), (15, 15, 15))        # grip
    return faces


class Cam:
    def __init__(self, pos, target, fov=40, size=(320, 320)):
        self.pos = np.asarray(pos, float)
        f = ac.norm(np.asarray(target, float) - self.pos)
        r = ac.norm(np.cross(f, [0, 1, 0]))
        u = np.cross(r, f)
        self.r, self.u, self.f = r, u, f
        self.size = size
        self.k = (size[1] / 2) / math.tan(math.radians(fov) / 2)

    def project(self, p):
        d = np.asarray(p) - self.pos
        z = float(np.dot(d, self.f))
        x = float(np.dot(d, self.r))
        y = float(np.dot(d, self.u))
        z = max(z, 0.05)
        return (self.size[0] / 2 + x * self.k / z, self.size[1] / 2 - y * self.k / z), z


def render(transforms, cams, root_offset=(0, 0, 0), label=None, size=(320, 320)):
    world = ac.fk(transforms, hrp=ac.T(*root_offset) @ ac.HRP_REST)
    faces = []
    for part, color in COLORS.items():
        faces += box_faces(world[part], ac.PART_SIZES[part], color)
    faces += katana_faces(world["RightHand"] @ ac.KATANA_IN_HAND)
    faces += box_faces(world["Head"] @ ac.T(0, 0.05, -0.65), (0.3, 0.25, 0.2), (200, 60, 60))  # nose = facing
    light = ac.norm(np.array([0.4, 0.8, -0.45]))
    tiles = []
    for cam in cams:
        img = Image.new("RGB", size, (214, 218, 226))
        dr = ImageDraw.Draw(img)
        for gx in range(-6, 7):  # ground grid
            a, _ = cam.project((gx, 0, -6))
            b, _ = cam.project((gx, 0, 6))
            dr.line([a, b], fill=(190, 194, 202))
            a, _ = cam.project((-6, 0, gx))
            b, _ = cam.project((6, 0, gx))
            dr.line([a, b], fill=(190, 194, 202))
        items = []
        for pts, color in faces:
            n = ac.norm(np.cross(pts[1] - pts[0], pts[3] - pts[0]))
            centre = sum(pts) / 4
            if np.dot(n, centre - cam.pos) > 0:
                n = -n
            proj = [cam.project(p) for p in pts]
            depth = float(np.dot(centre - cam.pos, cam.f))
            shade = 0.55 + 0.45 * max(0.0, float(np.dot(n, light)))
            items.append((depth, [p[0] for p in proj], tuple(int(c * shade) for c in color)))
        for depth, poly, col in sorted(items, key=lambda x: -x[0]):
            dr.polygon(poly, fill=col, outline=(15, 15, 18))
        tiles.append(img)
    sheet = Image.new("RGB", (size[0] * len(tiles), size[1] + (18 if label else 0)), (30, 30, 34))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * size[0], 18 if label else 0))
    if label:
        ImageDraw.Draw(sheet).text((6, 3), label, fill=(240, 240, 240))
    return sheet


def default_cams(size=(300, 300)):
    """front-left 3/4 (sees the sword arm from the front), right side, behind-above (player view)."""
    return [Cam((-5.5, 4.2, -9.5), (0, 2.5, -0.8), size=size),
            Cam((11.0, 3.0, -0.6), (0, 2.4, -0.6), size=size),
            Cam((2.5, 8.5, 9.5), (0, 2.6, -1.5), size=size)]


def contact_sheet(rows, path):
    """rows: list of PIL images (same width)."""
    w = max(r.width for r in rows)
    h = sum(r.height for r in rows)
    out = Image.new("RGB", (w, h), (20, 20, 24))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    out.save(path)

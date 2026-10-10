"""Kagune mesh'lerini (.obj) üretir. Mesh'ler X ekseni boyunca uzanır, sınır kutusu ~1x1x1.
Kullanım: python3 make_kagune_meshes.py <çıkış_klasörü>"""
import math, sys, os
import numpy as np

def write_obj(path, verts, faces):
    verts = np.array(verts, dtype=float)
    # sınır kutusunu [-0.5, 0.5] aralığına oturt
    mn, mx = verts.min(0), verts.max(0)
    verts = (verts - (mn + mx) / 2) / (mx - mn)
    normals = np.zeros_like(verts)
    for a, b, c in faces:
        n = np.cross(verts[b] - verts[a], verts[c] - verts[a])
        normals[a] += n; normals[b] += n; normals[c] += n
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    with open(path, 'w') as f:
        f.write(f'# {os.path.basename(path)} - kagune mesh\n')
        for v in verts: f.write('v %.5f %.5f %.5f\n' % tuple(v))
        for n in normals: f.write('vn %.5f %.5f %.5f\n' % tuple(n))
        for a, b, c in faces: f.write(f'f {a+1}//{a+1} {b+1}//{b+1} {c+1}//{c+1}\n')
    return verts, faces

def tube(nx, na, radius_fn, center_fn, cap_start=True, apex=False):
    verts, faces = [], []
    for i in range(nx):
        x = i / (nx - 1) - 0.5
        cy, cz = center_fn(x)
        for j in range(na):
            th = 2 * math.pi * j / na
            r = radius_fn(x, th)
            verts.append((x, cy + r * math.cos(th), cz + r * math.sin(th)))
    for i in range(nx - 1):
        for j in range(na):
            a = i * na + j; b = i * na + (j + 1) % na
            c = (i + 1) * na + j; d = (i + 1) * na + (j + 1) % na
            faces += [(a, c, b), (b, c, d)]
    if cap_start:
        verts.append((-0.5, *center_fn(-0.5))); ci = len(verts) - 1
        for j in range(na): faces.append((ci, j, (j + 1) % na))
    last = (nx - 1) * na
    if apex:
        verts.append((0.56, *center_fn(0.5))); ai = len(verts) - 1
        for j in range(na): faces.append((last + j, ai, last + (j + 1) % na))
    else:
        verts.append((0.5, *center_fn(0.5))); ci = len(verts) - 1
        for j in range(na): faces.append((last + j, ci, last + (j + 1) % na))
    return verts, faces

def segment_radius(x, th):
    t = x + 0.5
    r = 0.42 * (0.86 + 0.14 * math.sin(math.pi * t))      # ortası şişkin halka
    r *= 1 + 0.07 * math.cos(6 * th)                        # boyuna sırtlar
    scale = max(0.0, math.cos(th)) ** 6 * (t ** 1.5) * (1 - t) * 1.1  # üstte geriye bakan pul
    return r + 0.35 * scale

def tip_radius(x, th):
    t = x + 0.5
    r = 0.5 * (1 - t) ** 1.35 + 0.01
    r *= 1 + 0.08 * math.cos(6 * th)
    return r

out = sys.argv[1] if len(sys.argv) > 1 else '.'
seg = write_obj(os.path.join(out, 'KaguneSegment.obj'), *tube(18, 24, segment_radius, lambda x: (0, 0)))
tip = write_obj(os.path.join(out, 'KaguneTip.obj'), *tube(22, 24, tip_radius, lambda x: (0.12 * (x + 0.5) ** 2, 0), apex=True))

if len(sys.argv) > 2:  # önizleme resmi
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(10, 4.5), facecolor='#111')
    for k, (title, (v, f)) in enumerate([('KaguneSegment', seg), ('KaguneTip', tip)]):
        ax = fig.add_subplot(1, 2, k + 1, projection='3d', facecolor='#111')
        tris = [[v[a], v[b], v[c]] for a, b, c in f]
        light = np.array([0.4, 0.8, 0.5]); light /= np.linalg.norm(light)
        cols = []
        for tr in tris:
            n = np.cross(tr[1] - tr[0], tr[2] - tr[0]); n /= max(np.linalg.norm(n), 1e-9)
            s = 0.25 + 0.75 * max(0, n @ light)
            cols.append((0.75 * s + 0.1, 0.06 * s, 0.08 * s))
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolor='none'))
        ax.set_xlim(-0.6, 0.6); ax.set_ylim(-0.6, 0.6); ax.set_zlim(-0.6, 0.6)
        ax.view_init(18, -60); ax.set_axis_off(); ax.set_title(title, color='white')
    plt.tight_layout(); plt.savefig(sys.argv[2], dpi=110, facecolor='#111')

"""
Yami Skills - VFX mesh builder (Blender 4.x / 5.x, runs headless or from Blender's Text Editor).

Builds every VFX mesh used by the Roblox scripts, assigns materials/textures,
saves YamiVFX.blend, exports one FBX per mesh + a combined FBX, and renders a preview.

All geometry is authored in ROBLOX coordinates (studs, X right, Y up, -Z forward) and
converted to Blender with rb() -> Blender (-x, z, y). With Roblox's recommended FBX export
settings (Forward: Z, Up: Y, Apply Scalings: FBX Unit Scale) the meshes import into Studio
with exactly the orientation/scale they were authored in.

Usage:
    blender -b -P build_vfx.py -- <out_dir>
    python build_vfx.py <out_dir>          (with the `bpy` pip module)
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vfx_textures  # noqa: E402


def rb(p):
    """Roblox (x, y, z) -> Blender (x, y, z)."""
    return (-p[0], p[2], p[1])


# ------------------------------------------------------------------ scene setup

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "NONE"
    sc.unit_settings.scale_length = 1.0
    return sc


def make_image_material(name, image_path, alpha=True, roughness=0.6, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    img = bpy.data.images.load(image_path, check_existing=True)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (-400, 200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_flat_material(name, color, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def build_object(name, verts_rb, faces, uvs=None, smooth=False, material=None, recalc=True):
    """verts_rb in Roblox coords, faces = index tuples, uvs = per-vertex (u, v)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([rb(v) for v in verts_rb], [], faces)
    me.validate(clean_customdata=False)
    if uvs is not None:
        layer = me.uv_layers.new(name="UVMap")
        for loop in me.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index]
    for p in me.polygons:
        p.use_smooth = smooth
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if material is not None:
        me.materials.append(material)
    return obj


def pivot_fix(verts, faces, uvs, at, uv=(0.0005, 0.0005), size=0.004):
    """Adds a microscopic triangle so the mesh bounding box is centred where we want.
    Roblox re-centres MeshParts on their bounding box, so this keeps the pivot."""
    i = len(verts)
    x, y, z = at
    verts += [(x + size, y, z), (x - size, y, z), (x, y + size, z)]
    uvs += [uv, uv, uv]
    faces.append((i, i + 1, i + 2))


# --------------------------------------------------------------------- meshes

def mesh_slash_arc(mat):
    """Crescent slash. Circle centre at origin, lies flat (XZ plane), bulges toward -Z (forward).
    u: tail (left, -100deg) -> head (right, +100deg); v: inner -> outer edge."""
    R, span, N, M, W, H = 5.0, math.radians(200), 72, 6, 1.5, 0.12
    verts, faces, uvs = [], [], []

    def prof(u):
        return max(0.02, W * math.sin(math.pi * (u ** 0.85)) ** 0.75)

    def idx(side, i, j):
        return side * (N + 1) * (M + 1) + i * (M + 1) + j

    for side, ysign in ((0, 1.0), (1, -1.0)):
        for i in range(N + 1):
            u = i / N
            th = -span / 2 + u * span
            t = prof(u)
            r_in, r_out = R - 0.78 * t, R + 0.22 * t
            d = (math.sin(th), -math.cos(th))
            h = H * 0.5 * (t / W)
            for j in range(M + 1):
                v = j / M
                r = r_in + (r_out - r_in) * v
                hh = h * math.sqrt(max(0.0, 1 - (2 * v - 1) ** 2)) + 0.004
                verts.append((d[0] * r, ysign * hh, d[1] * r))
                uvs.append((u, v))
    for i in range(N):
        for j in range(M):
            faces.append((idx(0, i, j), idx(0, i + 1, j), idx(0, i + 1, j + 1), idx(0, i, j + 1)))
            faces.append((idx(1, i, j + 1), idx(1, i + 1, j + 1), idx(1, i + 1, j), idx(1, i, j)))
    for i in range(N):  # inner + outer walls
        faces.append((idx(0, i, 0), idx(1, i, 0), idx(1, i + 1, 0), idx(0, i + 1, 0)))
        faces.append((idx(0, i + 1, M), idx(1, i + 1, M), idx(1, i, M), idx(0, i, M)))
    for j in range(M):  # end caps
        faces.append((idx(0, 0, j + 1), idx(1, 0, j + 1), idx(1, 0, j), idx(0, 0, j)))
        faces.append((idx(0, N, j), idx(1, N, j), idx(1, N, j + 1), idx(0, N, j + 1)))
    pivot_fix(verts, faces, uvs, (0.0, 0.0, R + 0.22 * W))
    return build_object("SlashArc", verts, faces, uvs, smooth=True, material=mat)


def mesh_dimension_rift(mat):
    """Long jagged lens - the 'cut in space'. Length along X (100 studs), opening along Y,
    paper thin along Z. Scaled at runtime (length and opening animate separately)."""
    L, N, HMAX = 100.0, 520, 1.5
    rnd = random.Random(1337)
    spikes = [(rnd.uniform(-L / 2, L / 2), rnd.uniform(0.5, 2.6), rnd.uniform(0.15, 0.95), rnd.choice((1, -1)))
              for _ in range(48)]

    def jag(x, side):
        s = 0.0
        for cx, wdt, amp, sd in spikes:
            if sd != side:
                continue
            d = abs(x - cx) / wdt
            if d < 1:
                s += amp * (1 - d)
        s += 0.12 * math.sin(x * 2.7 + side) + 0.08 * math.sin(x * 7.3 + 2 * side)
        return max(-0.6, s)

    verts, faces, uvs = [], [], []
    for i in range(N + 1):
        u = i / N
        x = -L / 2 + u * L
        k = max(0.0, 1 - (2 * x / L) ** 2)
        hh = HMAX * k ** 1.15 + 0.01
        yt = hh * (1 + jag(x, 1))
        yb = -hh * (1 + jag(x, -1))
        zt = 0.18 * (hh / HMAX) ** 0.6 + 0.01
        verts += [(x, yt, 0.0), (x, 0.0, zt), (x, yb, 0.0), (x, 0.0, -zt)]
        uvs += [(u, 1.0), (u, 0.5), (u, 0.0), (u, 0.5)]
    for i in range(N):
        a, b = 4 * i, 4 * (i + 1)
        for q in range(4):
            q2 = (q + 1) % 4
            faces.append((a + q, b + q, b + q2, a + q2))
    faces.append((0, 1, 2, 3))
    e = 4 * N
    faces.append((e + 3, e + 2, e + 1, e))
    return build_object("DimensionRift", verts, faces, uvs, smooth=True, material=mat)


def mesh_shock_ring(mat):
    """Flat ring (shockwave) on the ground plane, slightly cone shaped, radius 1 (scaled at runtime)."""
    N, M, rin = 96, 4, 0.7
    verts, faces, uvs = [], [], []

    def idx(side, i, j):
        return side * (N + 1) * (M + 1) + i * (M + 1) + j

    for side, off in ((0, 0.015), (1, -0.015)):
        for i in range(N + 1):
            a = 2 * math.pi * i / N
            for j in range(M + 1):
                v = j / M
                r = rin + (1 - rin) * v
                y = 0.15 * v + off
                verts.append((math.cos(a) * r, y, math.sin(a) * r))
                uvs.append((i / N, v))
    for i in range(N):
        for j in range(M):
            faces.append((idx(0, i, j), idx(0, i, j + 1), idx(0, i + 1, j + 1), idx(0, i + 1, j)))
            faces.append((idx(1, i, j), idx(1, i + 1, j), idx(1, i + 1, j + 1), idx(1, i, j + 1)))
        faces.append((idx(0, i, 0), idx(0, i + 1, 0), idx(1, i + 1, 0), idx(1, i, 0)))
        faces.append((idx(0, i, M), idx(1, i, M), idx(1, i + 1, M), idx(0, i + 1, M)))
    return build_object("ShockRing", verts, faces, uvs, smooth=True, material=mat)


def mesh_swirl(mat):
    """Helical dark wind ribbon for charge-ups. Double sided (two opposite layers)."""
    N, turns = 160, 1.15
    verts, faces, uvs = [], [], []
    for i in range(N + 1):
        u = i / N
        phi = 2 * math.pi * turns * u
        r = 1.6 - 0.8 * u
        yc = 0.4 + 2.2 * u
        hb = 0.35 * math.sin(math.pi * u) ** 0.6 + 0.02
        c, s = math.cos(phi), math.sin(phi)
        verts += [(c * r, yc - hb, s * r), (c * r, yc + hb, s * r)]
        uvs += [(u, 0.0), (u, 1.0)]
    n0 = len(verts)
    verts += list(verts)
    uvs += list(uvs)
    for i in range(N):
        a, b = 2 * i, 2 * (i + 1)
        faces.append((a, b, b + 1, a + 1))
        faces.append((n0 + a + 1, n0 + b + 1, n0 + b, n0 + a))
    return build_object("Swirl", verts, faces, uvs, smooth=True, material=mat, recalc=False)


def mesh_cocoon(mat):
    """Black Cocoon shell: lumpy sphere with thorny spikes, radius ~1."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    rnd = random.Random(7)
    spikes = []
    for _ in range(46):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        spikes.append((v, rnd.uniform(0.18, 0.55), math.radians(rnd.uniform(6, 11))))
    for vert in bm.verts:
        n = vert.co.normalized()
        r = 1.0 + 0.07 * noise.noise(n * 2.6) + 0.03 * noise.noise(n * 7.0)
        for d, h, ang in spikes:
            a = n.angle(d)
            if a < ang:
                r += h * (1 - a / ang) ** 2.2
        vert.co = n * r
    me = bpy.data.meshes.new("Cocoon")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new("Cocoon", me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def mesh_rock(name, seed, mat):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1 if seed % 2 else 2, radius=1.0)
    rnd = random.Random(seed)
    sx, sy, sz = rnd.uniform(0.8, 1.2), rnd.uniform(0.6, 0.95), rnd.uniform(0.8, 1.2)
    for vert in bm.verts:
        n = vert.co.normalized()
        r = 1.0 + rnd.uniform(-0.18, 0.18) + 0.15 * noise.noise(n * 1.7 + Vector((seed, 0, 0)))
        co = n * r
        co.x *= sx
        co.y *= sz
        co.z *= sy
        co.z = max(co.z, -0.55 * sy)
        vert.co = co
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def mesh_shard(mat):
    """Thin crystal shard used for 'space cracking' around the rift. Length 1 along Z."""
    verts = [(0, 0, -0.5), (0, 0, 0.5), (0.06, 0, 0.1), (-0.06, 0, 0.1), (0, 0.02, 0.1), (0, -0.02, 0.1)]
    faces = [(0, 4, 2), (0, 3, 4), (0, 5, 3), (0, 2, 5), (1, 2, 4), (1, 4, 3), (1, 3, 5), (1, 5, 2)]
    return build_object("Shard", verts, faces, None, smooth=False, material=mat)


def mesh_impact_star(mat):
    """Flat 8-point manga impact star (faces +Z / -Z). Radius 1."""
    rnd = random.Random(99)
    outline = []
    for k in range(16):
        a = k * math.pi / 8
        r = rnd.uniform(0.75, 1.0) if k % 2 == 0 else rnd.uniform(0.14, 0.22)
        outline.append((math.cos(a) * r, math.sin(a) * r))
    verts = [(0, 0, 0.025), (0, 0, -0.025)]
    for x, y in outline:
        verts.append((x, y, 0.0))
    faces = []
    n = len(outline)
    for k in range(n):
        a, b = 2 + k, 2 + (k + 1) % n
        faces.append((0, a, b))
        faces.append((1, b, a))
    return build_object("ImpactStar", verts, faces, None, smooth=False, material=mat)


# -------------------------------------------------------------- katana + saya

UV_A = (0.0, 0.5, 0.5, 1.0)     # blade
UV_B = (0.5, 1.0, 0.5, 1.0)     # grip wrap
UV_C = (0.0, 0.25, 0.25, 0.5)   # gold
UV_D = (0.25, 0.5, 0.25, 0.5)   # dark iron
UV_E = (0.5, 1.0, 0.0, 0.5)     # black lacquer


def uv_in(rect, u, v, pad=0.04):
    u0, u1, v0, v1 = rect
    pu, pv = (u1 - u0) * pad, (v1 - v0) * pad
    return (u0 + pu + (u1 - u0 - 2 * pu) * u, v0 + pv + (v1 - v0 - 2 * pv) * v)


class MeshAccum:
    def __init__(self):
        self.verts, self.faces, self.uvs = [], [], []

    def add_v(self, p, uv):
        self.verts.append(tuple(p))
        self.uvs.append(uv)
        return len(self.verts) - 1


def sori(z_abs, start, length, amount=0.16):
    s = min(max((z_abs - start) / length, 0.0), 1.0)
    return amount * s * s


def add_oval_tube(acc, stations, segs, rect, cap0=True, cap1=True):
    """stations: list of (z, cy, rx, ry). Tube along Z with oval cross sections."""
    rings = []
    for si, (z, cy, rx, ry) in enumerate(stations):
        u = si / max(1, len(stations) - 1)
        ring = []
        for k in range(segs + 1):
            a = 2 * math.pi * k / segs
            p = (math.cos(a) * rx, cy + math.sin(a) * ry, z)
            ring.append(acc.add_v(p, uv_in(rect, u, k / segs)))
        rings.append(ring)
    for si in range(len(rings) - 1):
        r0, r1 = rings[si], rings[si + 1]
        for k in range(segs):
            acc.faces.append((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    for cap, (ring, st) in ((cap0, (rings[0], stations[0])), (cap1, (rings[-1], stations[-1]))):
        if not cap:
            continue
        z, cy = st[0], st[1]
        c = acc.add_v((0, cy, z), uv_in(rect, 0.5, 0.5))
        for k in range(segs):
            acc.faces.append((c, ring[k + 1], ring[k]))


def add_box(acc, center, size, rect):
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    corners = [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    ids = [acc.add_v(p, uv_in(rect, (i % 2), (i // 4))) for i, p in enumerate(corners)]
    # corner index = dx*4 + dy*2 + dz  (dx,dy,dz in {0,1})
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for q in quads:
        acc.faces.append(tuple(ids[i] for i in q))


def add_blade(acc, z0=-0.56, length=3.4, base_w=0.22, stations=60):
    """Curved katana blade along -Z. Edge faces -Y, spine faces +Y. Ends in a point."""
    rings = []
    for i in range(stations):
        s = i / (stations - 1)
        z = z0 - s * length
        c = sori(abs(z), abs(z0), length)
        w = base_w - 0.05 * s
        spine = c + w / 2
        edge = c - w / 2
        if s > 0.86:  # kissaki: edge sweeps up to meet the spine
            k = (s - 0.86) / 0.14
            edge = edge + (spine - edge) * (k ** 1.7)
            spine = spine - 0.015 * k
        ridge = spine - (spine - edge) * 0.3
        th = 0.034 * (1 - 0.55 * s)
        pts = [(0, spine + 0.008, z), (th, spine, z), (th * 1.25, ridge, z), (0, edge, z),
               (-th * 1.25, ridge, z), (-th, spine, z)]
        vs = [1.0, 0.95, 0.7, 0.0, 0.7, 0.95]
        rings.append([acc.add_v(p, uv_in(UV_A, s, vv)) for p, vv in zip(pts, vs)])
    tip_z = z0 - length - 0.02
    tip_c = sori(abs(tip_z), abs(z0), length) + base_w / 2 - 0.05 - 0.02
    tip = acc.add_v((0, tip_c, tip_z), uv_in(UV_A, 1.0, 0.5))
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(6):
            k2 = (k + 1) % 6
            acc.faces.append((r0[k], r1[k], r1[k2], r0[k2]))
    last = rings[-1]
    for k in range(6):
        acc.faces.append((last[k], tip, last[(k + 1) % 6]))
    first = rings[0]
    acc.faces.append(tuple(reversed(first)))


def mesh_katana(mat):
    """Yami's katana. Origin = grip point (centre of the fist). Blade along -Z, edge -Y.
    Weld it to RightHand with CFrame.new(0, -0.1, 0) (see KatanaService.lua)."""
    acc = MeshAccum()
    add_blade(acc)
    add_box(acc, (0, 0.0, -0.63), (0.1, 0.25, 0.14), UV_C)                       # habaki
    add_oval_tube(acc, [(-0.56, 0, 0.27, 0.31), (-0.50, 0, 0.27, 0.31)], 32, UV_D)  # tsuba
    add_oval_tube(acc, [(-0.50, 0, 0.105, 0.135), (-0.45, 0, 0.105, 0.135)], 16, UV_D)  # fuchi
    grip = [(-0.45 + t * (0.72 + 0.45) / 8, 0, 0.095 - 0.006 * math.sin(math.pi * t / 8), 0.125)
            for t in range(9)]
    add_oval_tube(acc, grip, 16, UV_B)                   # tsuka
    add_oval_tube(acc, [(0.72, 0, 0.105, 0.135), (0.8, 0, 0.1, 0.13), (0.82, 0, 0.07, 0.09)], 16, UV_D)
    pivot_fix(acc.verts, acc.faces, acc.uvs, (0, 0, 3.98), uv=uv_in(UV_E, 0.5, 0.5))
    return build_object("Katana", acc.verts, acc.faces, acc.uvs, smooth=True, material=mat)


def mesh_saya(mat):
    """Black lacquered sheath. Origin = mouth (koiguchi). Extends along -Z, same curve as blade."""
    acc = MeshAccum()
    L = 3.6
    st = []
    for i in range(25):
        s = i / 24
        z = -s * L
        cy = 0.16 * s * s
        rx = 0.085 - 0.012 * s
        ry = 0.155 - 0.03 * s
        st.append((z, cy, rx, ry))
    add_oval_tube(acc, st, 16, UV_E)
    add_oval_tube(acc, [(0.0, 0, 0.098, 0.168), (-0.08, 0, 0.098, 0.168)], 16, UV_D)       # koiguchi
    z_end = -L
    add_oval_tube(acc, [(z_end, 0.16, 0.074, 0.126), (z_end - 0.07, 0.165, 0.074, 0.12),
                        (z_end - 0.1, 0.17, 0.03, 0.05)], 16, UV_D)                       # kojiri
    pivot_fix(acc.verts, acc.faces, acc.uvs, (0, 0, L + 0.1), uv=uv_in(UV_E, 0.5, 0.5))
    return build_object("KatanaSaya", acc.verts, acc.faces, acc.uvs, smooth=True, material=mat)


# ------------------------------------------------------------------- export

def export_fbx(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="Z",
        axis_up="Y",
        bake_space_transform=True,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
    )


def render_preview(objs, path, cam_loc, cam_target, res=(1600, 900), samples=48, ortho=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("PreviewWorld") if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.78, 0.79, 0.82, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    cam_data = bpy.data.cameras.new("PreviewCam")
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = cam_loc
    direction = Vector(cam_target) - Vector(cam_loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in (cam, sun):
        bpy.data.objects.remove(o, do_unlink=True)


def main(out_root):
    out_root = os.path.abspath(out_root)
    tex_dir = os.path.join(out_root, "Textures")
    mesh_dir = os.path.join(out_root, "Meshes")
    os.makedirs(mesh_dir, exist_ok=True)
    tex = vfx_textures.build_all(tex_dir)

    reset_scene()
    m_slash = make_image_material("M_SlashArc", tex["T_SlashArc.png"], roughness=1.0)
    m_ring = make_image_material("M_ShockRing", tex["T_ShockRing.png"], roughness=1.0)
    m_swirl = make_image_material("M_Swirl", tex["T_Swirl.png"], roughness=1.0)
    m_katana = make_image_material("M_Katana", tex["T_Katana.png"], alpha=False, roughness=0.35, metallic=0.6)
    m_black = make_flat_material("M_YamiBlack", (0.0, 0.0, 0.0), roughness=0.9)
    m_rock = make_flat_material("M_Rock", (0.35, 0.33, 0.31), roughness=1.0)

    objs = {
        "SlashArc": mesh_slash_arc(m_slash),
        "DimensionRift": mesh_dimension_rift(m_black),
        "ShockRing": mesh_shock_ring(m_ring),
        "Swirl": mesh_swirl(m_swirl),
        "Cocoon": mesh_cocoon(m_black),
        "Rock1": mesh_rock("Rock1", 1, m_rock),
        "Rock2": mesh_rock("Rock2", 2, m_rock),
        "Rock3": mesh_rock("Rock3", 3, m_rock),
        "Shard": mesh_shard(m_black),
        "ImpactStar": mesh_impact_star(m_black),
        "Katana": mesh_katana(m_katana),
        "KatanaSaya": mesh_saya(m_katana),
    }

    # individual FBX files (object at origin)
    for name, o in objs.items():
        o.location = (0, 0, 0)
        export_fbx([o], os.path.join(mesh_dir, f"{name}.fbx"))

    # combined FBX: simple spread so the Studio import looks tidy (positions don't matter in
    # Roblox: MeshParts are re-centred and the scripts place/scale them at runtime)
    for k, (name, o) in enumerate(objs.items()):
        o.location = ((k % 6) * 12.0 - 30.0, (k // 6) * 12.0, 0.0)
    objs["DimensionRift"].location = (0.0, 40.0, 0.0)
    export_fbx(list(objs.values()), os.path.join(mesh_dir, "YamiVFX_AllMeshes.fbx"))

    # display layout for the .blend file and the preview render (Blender coordinates)
    display = {
        "DimensionRift": ((0, 9, 3.2), (0, 0, 0), 0.13),
        "SlashArc": ((-11, 1.5, 1.2), (0, 0, 0), 0.75),
        "ShockRing": ((-4.2, 0, 0.3), (0, 0, 0), 1.8),
        "Swirl": ((0, 0, 0), (0, 0, 0), 1.1),
        "Cocoon": ((4.6, 0, 1.4), (0, 0, 0), 1.3),
        "ImpactStar": ((9.6, 0.5, 1.5), (math.radians(-70), 0, 0), 1.3),
        "Rock1": ((-9, -6.5, 0.6), (0, 0, 0), 0.9),
        "Rock2": ((-6.3, -6.5, 0.6), (0, 0, 0.6), 0.9),
        "Rock3": ((-3.6, -6.5, 0.6), (0, 0, 1.2), 0.9),
        "Shard": ((-1.0, -6.5, 1.2), (math.radians(60), 0, 0), 2.5),
        "Katana": ((5.0, -6.0, 0.6), (0, 0, math.radians(90)), 1.25),
        "KatanaSaya": ((5.0, -8.0, 0.4), (0, 0, math.radians(90)), 1.25),
    }
    for name, (loc, rot, scl) in display.items():
        o = objs[name]
        o.location = loc
        o.rotation_euler = rot
        o.scale = (scl, scl, scl)

    blend_path = os.path.join(out_root, "YamiVFX.blend")
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    return objs


if __name__ == "__main__":
    argv = sys.argv
    out = argv[argv.index("--") + 1] if "--" in argv else (argv[1] if len(argv) > 1 else os.getcwd())
    preview = argv[argv.index("--") + 2] if "--" in argv and len(argv) > argv.index("--") + 2 else None
    objs = main(out)
    if preview:
        render_preview(list(objs.values()), preview, cam_loc=(0, -31, 19), cam_target=(-0.5, 0.0, 0.8), samples=40)
    print("VFX build OK ->", out)

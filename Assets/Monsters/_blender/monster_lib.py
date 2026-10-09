"""Shared helpers for building the Roblox monsters procedurally in Blender.

Convention: 1 Blender unit = 1 Roblox stud, Z is up, the monster's front faces -Y.
Every part is its own mesh object (object name == mesh name) so the Roblox
3D Importer turns each one into a separately named MeshPart.
"""

import math
import os
import random

import bpy  # noqa: F401  (must come first: provides mathutils/bmesh)
import bmesh
from mathutils import Matrix, Vector, noise
from mathutils.bvhtree import BVHTree


# ---------------------------------------------------------------- scene setup

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'NONE'
    scene.unit_settings.scale_length = 1.0
    return scene


def collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


# ------------------------------------------------------------------ materials

def material(name, color, roughness=0.6, emission=None, strength=0.0,
             alpha=1.0, metallic=0.0, coat=0.0, image=None, specular=0.5):
    """Principled material. `color`/`emission` are linear RGB tuples."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Specular IOR Level"].default_value = specular
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = 'BLENDED'
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.location = (-400, 200)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    mat.diffuse_color = (*color, alpha)
    return mat


def glow_material(name, color, strength, alpha=1.0, edge_soft=0.0, rim=False):
    """Emissive 'Neon' look. edge_soft > 0 fades the emission out towards
    grazing angles, which reads as a blurred/haze glow in renders; rim=True
    does the opposite (transparent centre, glowing silhouette = aura)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1.0)
    emit.inputs["Strength"].default_value = strength
    shader = emit.outputs[0]
    if alpha < 1.0 or edge_soft > 0.0:
        transp = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        fac_socket = mix.inputs["Fac"]
        if edge_soft > 0.0:
            lw = nt.nodes.new("ShaderNodeLayerWeight")
            lw.inputs["Blend"].default_value = edge_soft
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = 'MULTIPLY_ADD'
            inv.inputs[1].default_value = alpha if rim else -alpha
            inv.inputs[2].default_value = 0.0 if rim else alpha
            facing = lw.outputs["Facing"]
            if rim:  # concentrate the aura on the silhouette
                pw = nt.nodes.new("ShaderNodeMath")
                pw.operation = 'POWER'
                pw.inputs[1].default_value = 3.0
                nt.links.new(facing, pw.inputs[0])
                facing = pw.outputs[0]
            nt.links.new(facing, inv.inputs[0])
            nt.links.new(inv.outputs[0], fac_socket)
        else:
            fac_socket.default_value = alpha
        nt.links.new(transp.outputs[0], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        shader = mix.outputs[0]
        mat.surface_render_method = 'BLENDED'
    nt.links.new(shader, out.inputs["Surface"])
    mat.diffuse_color = (*color, alpha)
    return mat


# ----------------------------------------------------------- object plumbing

def mesh_object(name, bm=None, mesh=None, col=None, mat=None, smooth=True):
    if mesh is None:
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
    mesh.name = name
    obj = bpy.data.objects.new(name, mesh)
    (col or bpy.context.scene.collection).objects.link(obj)
    if mat is not None:
        mesh.materials.clear()
        mesh.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = smooth
    return obj


def bake_modifiers(obj):
    """Apply the whole modifier stack (no bpy.ops needed)."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = new
    new.materials.clear()
    for m in old.materials:
        new.materials.append(m)
    bpy.data.meshes.remove(old)
    new.name = obj.name
    return obj


def remove(obj):
    me = obj.data
    bpy.data.objects.remove(obj)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def boolean(target, cutter, op='DIFFERENCE'):
    """Boolean with fallbacks: the exact solver occasionally returns an empty
    mesh on near-degenerate overlaps, so retry with other solvers / a tiny
    nudge of the cutter instead of silently losing the part."""
    before = len(target.data.vertices)
    backup = target.data.copy()
    attempts = [('EXACT', 1.0), ('MANIFOLD', 1.0), ('EXACT', 1.004), ('FLOAT', 1.0)]
    for solver, nudge in attempts:
        if nudge != 1.0:
            cutter.scale = (nudge, nudge, nudge)
        mod = target.modifiers.new("bool", 'BOOLEAN')
        mod.operation = op
        mod.solver = solver
        mod.object = cutter
        try:
            bake_modifiers(target)
        except Exception:
            target.modifiers.clear()
        ok = len(target.data.vertices) >= max(8, before * 0.5 if op != 'INTERSECT' else 8)
        if ok:
            break
        old = target.data
        target.data = backup.copy()
        bpy.data.meshes.remove(old)
    else:
        raise RuntimeError(f"boolean failed: {target.name} - {cutter.name}")
    cutter.scale = (1, 1, 1)
    bpy.data.meshes.remove(backup)
    return target


def set_smooth(obj, smooth=True):
    for p in obj.data.polygons:
        p.use_smooth = smooth


def origin_to_center(obj):
    me = obj.data
    if not me.vertices:
        return obj
    xs = [v.co for v in me.vertices]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    c = (lo + hi) / 2
    me.transform(Matrix.Translation(-c))
    obj.location = obj.matrix_world @ c
    bpy.context.view_layer.update()
    return obj


def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def decimate(obj, max_tris):
    tris = tri_count(obj)
    if tris <= max_tris:
        return obj
    mod = obj.modifiers.new("dec", 'DECIMATE')
    mod.ratio = max_tris / tris * 0.97
    bake_modifiers(obj)
    return obj


def solidify(obj, thickness, offset=0.0):
    mod = obj.modifiers.new("solid", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    bake_modifiers(obj)
    return obj


def subsurf(obj, levels=1):
    mod = obj.modifiers.new("sub", 'SUBSURF')
    mod.levels = levels
    mod.render_levels = levels
    bake_modifiers(obj)
    return obj


def displace_noise(obj, amp, scale, seed=0.0, octaves=3, axis_weight=None):
    """Push vertices along their normals by fractal noise."""
    me = obj.data
    me.update()
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    for v in me.vertices:
        p = v.co * scale + off
        n = noise.fractal(p, 0.6, 2.0, octaves)
        w = 1.0 if axis_weight is None else axis_weight(v.co)
        v.co += v.normal * n * amp * w
    me.update()
    return obj


# --------------------------------------------------------- shape generators

def ellipsoid(name, center, radii, segments=32, rings=20, col=None, mat=None,
              rot=None, deform=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=1.0)
    for v in bm.verts:
        co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
        if deform is not None:
            co = deform(co)
        v.co = co
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ (rot.to_matrix() if hasattr(rot, "to_matrix") else rot).to_4x4()
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return mesh_object(name, bm, col=col, mat=mat)


def skin_object(name, verts, edges, radii, col=None, mat=None, subdiv=2,
                smooth_branch=0.6):
    """Organic limb/torso from a vertex skeleton using the Skin modifier."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) for v in verts], edges, [])
    obj = mesh_object(name, mesh=me, col=col, mat=mat)
    mod = obj.modifiers.new("skin", 'SKIN')
    mod.branch_smoothing = smooth_branch
    sv = me.skin_vertices[0].data
    for i, r in enumerate(radii):
        r = r if isinstance(r, (tuple, list)) else (r, r)
        sv[i].radius = r
        sv[i].use_root = (i == 0)
    if subdiv:
        s = obj.modifiers.new("sub", 'SUBSURF')
        s.levels = subdiv
        s.render_levels = subdiv
    bake_modifiers(obj)
    set_smooth(obj)
    return obj


MB_FACTOR = 0.575  # visible radius / metaball radius (stiffness 2, threshold 0.6)


def metaball_object(name, elements, resolution=0.05, col=None, mat=None):
    """Blobby organic mesh. `elements`: dicts with co, r (visible radius) or
    size (visible x/y/z radii for an ellipsoid) and optional rot (Quaternion)."""
    mb = bpy.data.metaballs.new(name + "_mb")
    mb.resolution = resolution
    mb.render_resolution = resolution
    mb.threshold = 0.6
    for el in elements:
        if "size" in el:
            e = mb.elements.new(type='ELLIPSOID')
            sx, sy, sz = el["size"]
            base = max(sx, sy, sz)
            e.radius = base / MB_FACTOR
            e.size_x, e.size_y, e.size_z = sx / base, sy / base, sz / base
        else:
            e = mb.elements.new(type='BALL')
            e.radius = el["r"] / MB_FACTOR
        e.co = el["co"]
        e.stiffness = el.get("stiff", 2.0)
        if "rot" in el:
            e.rotation = el["rot"]
    mo = bpy.data.objects.new(name + "_mbobj", mb)
    bpy.context.scene.collection.objects.link(mo)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(mo.evaluated_get(dg))
    bpy.data.objects.remove(mo)
    bpy.data.metaballs.remove(mb)
    return mesh_object(name, mesh=me, col=col, mat=mat)


def catmull(points, samples):
    """Resample a polyline with a Catmull-Rom spline -> `samples` points."""
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return pts
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    seg = len(pts) - 1
    out = []
    for i in range(samples):
        t = i / (samples - 1) * seg
        k = min(int(t), seg - 1)
        u = t - k
        p0, p1, p2, p3 = ext[k], ext[k + 1], ext[k + 2], ext[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u
                          + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def frames(path, up_hint=Vector((0, 0, 1))):
    """Parallel-transport frames (tangent, side, normal) along a path."""
    tans = []
    for i in range(len(path)):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        tans.append((b - a).normalized())
    side = up_hint.cross(tans[0])
    if side.length < 1e-4:
        side = Vector((1, 0, 0)).cross(tans[0])
    side.normalize()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            side = side - t * side.dot(t)
            if side.length < 1e-6:
                side = out[-1][1]
            side.normalize()
        out.append((t, side, t.cross(side).normalized()))
    return out


def tube(name, points, radii, samples=24, sides=8, flat=1.0, twist=0.0,
         col=None, mat=None, up_hint=Vector((0, 0, 1)), wobble=0.0, seed=0.0,
         cap_start=True):
    """Tube along a smoothed path. `radii` is a list matching `points` or a
    callable r(t). The last ring collapses to a point when its radius is ~0."""
    path = catmull(points, samples)
    fr = frames(path, up_hint)
    if callable(radii):
        rad = [radii(i / (samples - 1)) for i in range(samples)]
    else:
        rr = catmull([(r, 0, 0) for r in radii], samples)
        rad = [max(p.x, 0.0) for p in rr]
    bm = bmesh.new()
    rings = []
    for i, (p, (t, s, n)) in enumerate(zip(path, fr)):
        u = i / (samples - 1)
        ang0 = twist * u
        ring = []
        r = rad[i]
        if wobble:
            p = p + (s * noise.noise(Vector((u * 4, seed, 0)))
                     + n * noise.noise(Vector((u * 4, seed, 5)))) * wobble
        for k in range(sides):
            a = 2 * math.pi * k / sides + ang0
            off = s * math.cos(a) * r + n * math.sin(a) * r * flat
            ring.append(bm.verts.new(p + off))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            a, b = rings[i][k], rings[i][(k + 1) % sides]
            c, d = rings[i + 1][(k + 1) % sides], rings[i + 1][k]
            bm.faces.new((a, b, c, d))
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, col=col, mat=mat)


def ribbon(name, points, width0, width1, length_jitter=0.35, cols=9,
           rows=30, side_hint=Vector((1, 0, 0)), wave_amp=0.12, wave_freq=2.0,
           tear_prob=0.05, thickness=0.035, seed=1, col=None, mat=None,
           fingers=3, split=0.45, bulge=1.3, twist=0.0):
    """Torn cloth / smoke strip that follows `points`, with a ragged hem,
    jagged sides, ripples and a few tears. Solidified so it is two-sided."""
    rnd = random.Random(seed)
    path = catmull(points, 64)
    seglen = [0.0]
    for a, b in zip(path, path[1:]):
        seglen.append(seglen[-1] + (b - a).length)
    total = seglen[-1]

    def at(t):
        d = t * total
        for i in range(1, len(seglen)):
            if seglen[i] >= d:
                f = (d - seglen[i - 1]) / max(seglen[i] - seglen[i - 1], 1e-6)
                return path[i - 1].lerp(path[i], f), (path[i] - path[i - 1]).normalized()
        return path[-1], (path[-1] - path[-2]).normalized()

    # The strip is one sheet down to `split`, then tears into `fingers`
    # tendrils of different lengths that each taper to a point.
    per = max(2, cols // fingers)
    total_cols = per * fingers
    rs = max(2, int(rows * split))
    lens = [max(split + 0.12, 1.0 - rnd.random() * length_jitter) for _ in range(fingers)]

    def width(t):
        if t < 0.4:
            return width0 + (width0 * bulge - width0) * (t / 0.4)
        return width0 * bulge + (width1 - width0 * bulge) * ((t - 0.4) / 0.6)

    bm = bmesh.new()
    sheets = []
    for f in range(fingers):
        s_fc = -1 + 2 * (f * per + per / 2) / total_cols
        drift = rnd.uniform(-0.35, 0.35)
        grid = []
        for j in range(per + 1):
            s_g = -1 + 2 * (f * per + j) / total_cols
            column = []
            for r in range(rows):
                if r <= rs:
                    t = split * r / rs
                    b = 0.0
                else:
                    b = (r - rs) / (rows - 1 - rs)
                    t = split + (lens[f] - split) * b
                s = s_fc + (s_g - s_fc) * (1 - b) ** 0.9
                s += (s_fc * 0.35 + drift) * b
                p, tan = at(t)
                side = side_hint - tan * side_hint.dot(tan)
                side.normalize()
                side = Matrix.Rotation(twist * t, 3, tan) @ side
                nrm = tan.cross(side).normalized()
                w = width(t) * (1 + 0.2 * noise.noise(Vector((t * 3, seed, 0.5))))
                if s_g in (-1.0, 1.0):
                    s += 0.16 * noise.noise(Vector((t * 9, seed * 3.1, s_g))) * (0.3 + t)
                ripple = math.sin(2 * math.pi * (t * wave_freq + s_g * 0.25) + seed)
                ripple += 0.5 * noise.noise(Vector((t * 5, s_g * 2, seed)))
                ripple += 0.8 * b * noise.noise(Vector((t * 4, f * 1.7, seed + 9)))
                ripple *= wave_amp * (0.3 + t)
                column.append(bm.verts.new(p + side * s * w / 2 + nrm * ripple))
            grid.append(column)
        sheets.append(grid)
        for j in range(per):
            for r in range(rows - 1):
                if r > rs and rnd.random() < tear_prob:
                    continue
                bm.faces.new((grid[j][r], grid[j + 1][r], grid[j + 1][r + 1], grid[j][r + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    obj = mesh_object(name, bm, col=col, mat=mat)
    solidify(obj, thickness, 0.0)
    set_smooth(obj)
    return obj


def surface_cracks(name, target, count, seed, steps=(8, 18), step_len=0.12,
                   radius=0.035, branch_prob=0.12, region=None, bias=None,
                   col=None, mat=None, lift=0.012, sides=5):
    """Random-walk crack lines glued onto `target`'s surface, merged into a
    single tube mesh (used for glowing neon cracks)."""
    rnd = random.Random(seed)
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(target, dg)
    me = target.data
    mw = target.matrix_world
    candidates = [mw @ v.co for v in me.vertices
                  if region is None or region(mw @ v.co)]
    bm = bmesh.new()

    def walk(start, direction, n, r0):
        pts = []
        p = start
        d = direction
        for _ in range(n):
            loc, nrm, _, _ = bvh.find_nearest(p)
            if loc is None:
                break
            d = d - nrm * d.dot(nrm)
            if d.length < 1e-5:
                break
            d.normalize()
            pts.append((loc + nrm * lift, nrm.copy()))
            jitter = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
            d = (d + jitter * 0.55).normalized()
            if bias is not None:
                d = (d + bias * 0.25).normalized()
            p = loc + d * step_len
        return pts

    def emit(pts, r0):
        if len(pts) < 3:
            return
        n = len(pts)
        rings = []
        for i, (p, nrm) in enumerate(pts):
            a = pts[max(i - 1, 0)][0]
            b = pts[min(i + 1, n - 1)][0]
            t = (b - a).normalized()
            s = nrm.cross(t).normalized()
            u = i / (n - 1)
            r = r0 * (0.25 + 0.75 * math.sin(math.pi * u) ** 0.6)
            r *= 0.8 + 0.4 * rnd.random()
            ring = []
            for k in range(sides):
                ang = 2 * math.pi * k / sides
                ring.append(bm.verts.new(p + (s * math.cos(ang) + nrm * math.sin(ang) * 0.6) * r))
            rings.append(ring)
        for i in range(n - 1):
            for k in range(sides):
                bm.faces.new((rings[i][k], rings[i][(k + 1) % sides],
                              rings[i + 1][(k + 1) % sides], rings[i + 1][k]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])

    for _ in range(count):
        start = rnd.choice(candidates)
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1.5, 1.5))).normalized()
        n = rnd.randint(*steps)
        main = walk(start, d, n, radius)
        emit(main, radius)
        for i in range(2, len(main) - 2):
            if rnd.random() < branch_prob:
                bd = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
                br = walk(main[i][0], bd, rnd.randint(3, max(4, n // 2)), radius * 0.6)
                emit(br, radius * 0.6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_object(name, bm, col=col, mat=mat)
    return obj


def project_points(obj, points, lift=0.0):
    """Snap points onto the surface of `obj` (plus `lift` along the normal)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(obj, dg)
    mw = obj.matrix_world
    inv = mw.inverted()
    out = []
    for p in points:
        loc, nrm, _, _ = bvh.find_nearest(inv @ Vector(p))
        out.append(mw @ (loc + nrm * lift))
    return out


def join(name, objs, col=None, mat=None):
    """Merge several objects into one mesh object (world space)."""
    bm = bmesh.new()
    for o in objs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        remove(o)
    return mesh_object(name, bm, col=col, mat=mat)


# ------------------------------------------------------------------- export

def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = mw
    bpy.context.view_layer.update()


def make_root(name_col, center, size=(2.0, 1.0, 2.0)):
    """Invisible 'Root' part (becomes the PrimaryPart in Roblox)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    mat = material("Root_Gorunmez", (0.2, 0.6, 1.0), alpha=0.15)
    obj = mesh_object("Root", bm, col=name_col, mat=mat, smooth=False)
    obj.location = Vector(center)
    bpy.context.view_layer.update()
    obj.hide_render = True
    obj.display_type = 'WIRE'
    return obj


def finalize_parts(parts, root):
    for o in parts:
        if o is root:
            continue
        origin_to_center(o)
        parent_keep(o, root)


def export(folder, base, objs):
    os.makedirs(folder, exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    fbx = os.path.join(folder, base + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True, object_types={'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
        axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
        mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False,
        path_mode='COPY', embed_textures=True)
    return fbx


def save_blend(path):
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)


# ------------------------------------------------------------------- render

def studio(scene, floor_color=(0.045, 0.047, 0.055), world=(0.012, 0.013, 0.018)):
    scene.render.engine = 'CYCLES'
    cy = scene.cycles
    cy.device = 'CPU'
    cy.samples = 96
    cy.use_adaptive_sampling = True
    cy.max_bounces = 6
    try:
        cy.use_denoising = True
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'

    w = bpy.data.worlds.new("World")
    scene.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*world, 1)
    bg.inputs["Strength"].default_value = 1.0

    col = collection("Studio")
    # cyclorama floor with a 2-stud checker for scale reading
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    floor = mesh_object("Zemin", bm, col=col, smooth=False)
    fm = bpy.data.materials.new("ZeminMat")
    nt = fm.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 40.0  # 80 stud plane / 40 = 2 stud cells
    chk.inputs["Color1"].default_value = (*floor_color, 1)
    chk.inputs["Color2"].default_value = tuple(c * 1.35 for c in floor_color) + (1,)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["UV"], chk.inputs["Vector"])
    nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    floor.data.materials.append(fm)
    floor.data.uv_layers.new()
    floor.data.uv_layers[0].data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])

    # backdrop wall far behind
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    wall = mesh_object("Fon", bm, col=col, smooth=False)
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall.location = (0, 22, 20)
    wm = material("FonMat", (0.03, 0.032, 0.04), roughness=0.9)
    wall.data.materials.append(wm)
    return col


def area_light(name, loc, target, energy, size, color=(1, 1, 1), col=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    (col or bpy.context.scene.collection).objects.link(lo)
    lo.location = loc
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return lo


def point_light(name, loc, energy, color, radius=0.2, col=None):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    lo = bpy.data.objects.new(name, ld)
    (col or bpy.context.scene.collection).objects.link(lo)
    lo.location = loc
    return lo


def camera(name, loc, target, lens=50):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 500
    co = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    d = Vector(target) - Vector(loc)
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return co


def glare_compositor(scene, threshold=0.8, size=0.7, strength=0.8):
    tree = bpy.data.node_groups.new("Kompozit", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = tree.nodes.new("CompositorNodeRLayers")
    gl = tree.nodes.new("CompositorNodeGlare")
    out = tree.nodes.new("NodeGroupOutput")
    try:
        gl.inputs["Type"].default_value = 'Bloom'
    except Exception:
        pass
    gl.inputs["Threshold"].default_value = threshold
    gl.inputs["Size"].default_value = size
    gl.inputs["Strength"].default_value = strength
    tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
    tree.links.new(gl.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = tree


def render(scene, cam, path, res=(1000, 1250), samples=None):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    if samples:
        scene.cycles.samples = samples
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def roblox_dummy(loc, col=None):
    """Classic R6 'noob' (~5 studs tall) placed next to a monster for scale."""
    yellow = material("Referans_Sari", (0.91, 0.61, 0.03), roughness=0.5)
    blue = material("Referans_Mavi", (0.004, 0.14, 0.41), roughness=0.5)
    green = material("Referans_Yesil", (0.37, 0.51, 0.06), roughness=0.5)
    x, y, z = loc
    blocks = [
        ("Ref_SolBacak", (x + 0.5, y, z + 1.0), (1, 1, 2), green),
        ("Ref_SagBacak", (x - 0.5, y, z + 1.0), (1, 1, 2), green),
        ("Ref_Govde", (x, y, z + 3.0), (2, 1, 2), blue),
        ("Ref_SolKol", (x + 1.5, y, z + 3.0), (1, 1, 2), yellow),
        ("Ref_SagKol", (x - 1.5, y, z + 3.0), (1, 1, 2), yellow),
    ]
    objs = []
    for n, c, s, m in blocks:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
        objs.append(mesh_object(n, bm, col=col, mat=m, smooth=False))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.6, radius2=0.6, depth=1.2)
    bmesh.ops.translate(bm, vec=Vector((x, y, z + 4.6)), verts=bm.verts)
    objs.append(mesh_object("Ref_Bas", bm, col=col, mat=yellow))
    return objs

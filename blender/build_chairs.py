"""
Anime koltuklari - Blender uretici script (Roblox uyumlu)

Calistirma:
  - Blender icinde: Scripting sekmesi > bu dosyayi ac > Run Script
  - Komut satirindan: blender --background --python blender/build_chairs.py
  - Ya da bpy modulu ile: python3 blender/build_chairs.py

Ciktilar (blender/export/):
  - <Koltuk>.fbx      -> Roblox Studio 3D Importer ile ice aktarilir
  - AnimeChairs.blend -> 4 koltuk yan yana, onizleme animasyonlariyla
  - renders/*.png     -> onizleme goruntuleri (--render ile)

Olcek: 1 Blender birimi = 1 Roblox stud. Oturma yuksekligi ~2 stud.
Animasyonlu parcalar ayri objeler; Roblox'ta script ile hareket ettirilir.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(HERE, "export")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")

# Roblox MeshPart siniri 20.000 ucgen; guvenli payla kontrol edilir.
TRI_LIMIT = 20000


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 120


_materials = {}


def mat(name, color, metallic=0.0, roughness=0.5, emission=0.0, alpha=1.0):
    """Principled malzeme. emission > 0 olanlar Roblox'ta Neon yapilacak."""
    if name in _materials:
        return _materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    rgba = (*color, 1.0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    m.diffuse_color = rgba
    _materials[name] = m
    return m


def link(obj, coll):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)


def new_obj(name, bm, coll, material, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    if material:
        me.materials.append(material)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return obj


def box(name, coll, material, size, loc=(0, 0, 0), bevel=0.0, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    obj = new_obj(name, bm, coll, material)
    obj.location = loc
    obj.rotation_euler = rot
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    return obj


def cyl(name, coll, material, r, depth, loc=(0, 0, 0), rot=(0, 0, 0),
        verts=24, r2=None, bevel=0.0, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=r, radius2=r if r2 is None else r2,
                          depth=depth)
    obj = new_obj(name, bm, coll, material, smooth=smooth)
    obj.location = loc
    obj.rotation_euler = rot
    if smooth:
        _autosmooth(obj)
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    return obj


def sphere(name, coll, material, r, loc=(0, 0, 0), seg=24, rings=12,
           scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    obj = new_obj(name, bm, coll, material, smooth=True)
    obj.location = loc
    obj.scale = scale
    return obj


def torus(name, coll, material, R, r, loc=(0, 0, 0), rot=(0, 0, 0),
          major=48, minor=12, arc=2 * math.pi):
    """Torus (ya da arc < 2pi ise yay)."""
    bm = bmesh.new()
    closed = arc >= 2 * math.pi - 1e-6
    steps = major if closed else major + 1
    rings = []
    for i in range(steps):
        a = arc * i / major
        c = Vector((math.cos(a) * R, math.sin(a) * R, 0))
        out = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for j in range(minor):
            b = 2 * math.pi * j / minor
            p = c + out * (math.cos(b) * r) + Vector((0, 0, math.sin(b) * r))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    n = len(rings)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for j in range(minor):
            k = (j + 1) % minor
            bm.faces.new((a[j], b[j], b[k], a[k]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_obj(name, bm, coll, material, smooth=True)
    obj.location = loc
    obj.rotation_euler = rot
    return obj


def prism(name, coll, material, pts, depth, loc=(0, 0, 0), rot=(0, 0, 0),
          bevel=0.0):
    """2B cokgeni (XZ duzleminde) Y yonunde kalinlastirir."""
    bm = bmesh.new()
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in pts]
    back = [bm.verts.new((x, depth / 2, z)) for x, z in pts]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_obj(name, bm, coll, material)
    obj.location = loc
    obj.rotation_euler = rot
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    return obj


def leaf_points(length, width, n=14):
    """Yaprak/kanat bicimi icin sivri uclu kontur (XZ)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((width * math.sin(math.pi * t) * (1 - 0.35 * t),
                    length * t))
    for i in range(n - 1, 0, -1):
        t = i / n
        pts.append((-width * math.sin(math.pi * t) * (1 - 0.35 * t),
                    length * t))
    return pts


def _autosmooth(obj):
    # Duz yuzeyleri keskin tutmak icin kenar bolme
    mod = obj.modifiers.new("EdgeSplit", "EDGE_SPLIT")
    mod.split_angle = math.radians(40)


def set_origin(obj, world_point):
    """Objeyi yerinde birakarak pivotunu world_point'e tasir (mentese icin)."""
    bpy.context.view_layer.update()
    mw = obj.matrix_world.copy()
    local = mw.inverted() @ Vector(world_point)
    obj.data.transform(Matrix.Translation(-local))
    obj.matrix_world = mw @ Matrix.Translation(local)


def join(objs, name, pivot=None):
    """Objeleri (modifier'lari islenmis halde) tek objede birlestirir."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    for ob in objs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.transform(ob.matrix_world)
        base = len(mats)
        mats.extend(me.materials)
        for p in me.polygons:
            p.material_index += base
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    colls = list(objs[0].users_collection)
    for ob in objs:
        old = ob.data
        bpy.data.objects.remove(ob)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m_ in mats:
        me.materials.append(m_)
    obj = bpy.data.objects.new(name, me)
    for c in colls:
        c.objects.link(obj)
    if pivot is not None:
        me.transform(Matrix.Translation(-Vector(pivot)))
        obj.location = pivot
    return obj


def bake_modifiers(coll):
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in list(coll.objects):
        if obj.type != "MESH" or not obj.modifiers:
            continue
        ev = obj.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        old = obj.data
        obj.modifiers.clear()
        obj.data = me
        me.name = obj.name
        bpy.data.meshes.remove(old)


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def mirror_x(obj, coll, name):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    dup.location.x = -obj.location.x
    dup.rotation_euler.y = -obj.rotation_euler.y
    dup.rotation_euler.z = -obj.rotation_euler.z
    dup.scale.x = -obj.scale.x
    coll.objects.link(dup)
    return dup


def apply_negative_scale(coll):
    """FBX/Roblox icin negatif olcekleri mesh'e uygula."""
    import mathutils
    for obj in coll.objects:
        if obj.type == "MESH" and any(s < 0 for s in obj.scale):
            sm = mathutils.Matrix.Diagonal((*obj.scale, 1.0))
            obj.data.transform(sm)
            if obj.scale.x * obj.scale.y * obj.scale.z < 0:
                obj.data.flip_normals()
            obj.scale = (1, 1, 1)


def key_rot(obj, frame, rot):
    obj.rotation_euler = rot
    obj.keyframe_insert("rotation_euler", frame=frame)


def key_loc(obj, frame, loc):
    obj.location = loc
    obj.keyframe_insert("location", frame=frame)


def key_scale(obj, frame, s):
    obj.scale = s
    obj.keyframe_insert("scale", frame=frame)


def cyclic(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:  # Blender 4.4+ katmanli action
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        if not any(m.type == "CYCLES" for m in fc.modifiers):
            fc.modifiers.new("CYCLES")
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# ---------------------------------------------------------------------------
# Ortak malzemeler
# ---------------------------------------------------------------------------

def materials():
    return {
        "wood_dark": mat("WoodDark", (0.23, 0.11, 0.05), roughness=0.7),
        "wood": mat("Wood", (0.45, 0.25, 0.11), roughness=0.65),
        "wood_light": mat("WoodLight", (0.66, 0.45, 0.25), roughness=0.6),
        "red": mat("HokageRed", (0.62, 0.06, 0.04), roughness=0.45),
        "white": mat("ClothWhite", (0.92, 0.9, 0.85), roughness=0.8),
        "gold": mat("Gold", (0.95, 0.68, 0.2), metallic=1.0, roughness=0.25),
        "steel": mat("Steel", (0.55, 0.57, 0.6), metallic=1.0, roughness=0.3),
        "steel_dark": mat("SteelDark", (0.12, 0.13, 0.15), metallic=0.9,
                          roughness=0.35),
        "stone": mat("Stone", (0.35, 0.33, 0.31), roughness=0.9),
        "leather": mat("Leather", (0.25, 0.14, 0.08), roughness=0.55),
        "rope": mat("Rope", (0.7, 0.58, 0.38), roughness=0.95),
        "black": mat("Black", (0.03, 0.03, 0.03), roughness=0.6),
        "green_cloak": mat("CloakGreen", (0.08, 0.25, 0.12), roughness=0.8),
        "orange": mat("Orange", (0.95, 0.42, 0.05), roughness=0.5),
        # Neon (Roblox'ta Material = Neon)
        "neon_chakra": mat("Neon_Chakra", (0.1, 0.55, 1.0), emission=6.0),
        "neon_fire": mat("Neon_Fire", (1.0, 0.35, 0.05), emission=6.0),
        "neon_ki": mat("Neon_Ki", (1.0, 0.82, 0.1), emission=8.0),
        "neon_lantern": mat("Neon_Lantern", (1.0, 0.65, 0.25), emission=5.0),
        "neon_alarm": mat("Neon_Alarm", (1.0, 0.05, 0.03), emission=8.0),
        "neon_teal": mat("Neon_Teal", (0.1, 1.0, 0.8), emission=4.0),
        # Yari saydam aura (Roblox'ta Neon + Transparency ~0.7)
        "neon_aura": mat("Neon_Aura", (1.0, 0.85, 0.2), emission=1.5,
                         alpha=0.15),
        "wing_blue": mat("WingBlue", (0.12, 0.25, 0.6), roughness=0.5),
    }


# ---------------------------------------------------------------------------
# 1) Hokage Tahti (Naruto esintili)
# ---------------------------------------------------------------------------

def build_hokage(coll, M):
    # Uc kademeli yuvarlak platform
    cyl("Platform_Base", coll, M["stone"], 4.2, 0.4, (0, 0, 0.2), verts=48,
        bevel=0.05)
    cyl("Platform_Mid", coll, M["wood_dark"], 3.5, 0.3, (0, 0, 0.55),
        verts=48, bevel=0.04)
    cyl("Platform_Top", coll, M["red"], 3.0, 0.15, (0, 0, 0.775), verts=48)

    # Oturak (Roblox'ta buraya Seat parcasi konur)
    box("Seat", coll, M["red"], (2.4, 2.2, 0.45), (0, 0, 2.0), bevel=0.12)
    box("Seat_Frame", coll, M["wood_dark"], (2.7, 2.5, 0.5), (0, 0, 1.6),
        bevel=0.06)
    for i, (x, y) in enumerate([(-1.15, -1.05), (1.15, -1.05),
                                (-1.15, 1.05), (1.15, 1.05)]):
        cyl(f"Leg_{i + 1}", coll, M["wood_dark"], 0.18, 0.8, (x, y, 1.15),
            verts=12, r2=0.14)

    # Uzun, ust kismi kemerli sirtlik
    back_pts = [(-1.4, 0), (1.4, 0), (1.4, 4.2)]
    for i in range(1, 16):
        a = math.pi * i / 16
        back_pts.append((1.4 * math.cos(a), 4.2 + 1.0 * math.sin(a)))
    back_pts.append((-1.4, 4.2))
    prism("Back", coll, M["wood_dark"], back_pts, 0.35, (0, 1.25, 1.8),
          bevel=0.05)
    inner = [(x * 0.82, 0.25 + z * 0.86) for x, z in back_pts]
    prism("Back_Cushion", coll, M["red"], inner, 0.2, (0, 1.05, 1.8),
          bevel=0.05)

    # Altin cerceve yayi
    torus("Back_Trim", coll, M["gold"], 1.42, 0.07, (0, 1.05, 6.0),
          rot=(math.pi / 2, 0, 0), major=32, minor=8, arc=math.pi)

    # Amblem: genel yaprak + girdap (resmi logo degil)
    torus("Emblem_Ring", coll, M["gold"], 0.62, 0.06, (0, 0.92, 4.7),
          rot=(math.pi / 2, 0, 0), major=40, minor=8)
    torus("Emblem_Swirl", coll, M["gold"], 0.32, 0.05, (0, 0.92, 4.7),
          rot=(math.pi / 2, 0, 0), major=24, minor=8, arc=1.6 * math.pi)
    prism("Emblem_Leaf", coll, M["gold"], leaf_points(0.55, 0.22), 0.06,
          (0, 0.92, 4.95), rot=(0, math.radians(-35), 0))

    # Kolcaklar
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        box(f"Armrest_{s}", coll, M["wood_dark"], (0.45, 2.4, 0.3),
            (side * 1.45, -0.05, 2.75), bevel=0.08)
        cyl(f"Armrest_Post_{s}", coll, M["wood_dark"], 0.14, 1.0,
            (side * 1.45, -0.95, 2.2), verts=12)
        sphere(f"Armrest_Knob_{s}", coll, M["gold"], 0.22,
               (side * 1.45, -1.25, 2.95), seg=16, rings=8)

    # Yanlarda kagit fenerler (Neon)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        x = side * 3.2
        cyl(f"LanternPole_{s}", coll, M["wood_dark"], 0.08, 3.2,
            (x, 0.8, 2.2), verts=10)
        cyl(f"Lantern_Glow_{s}", coll, M["neon_lantern"], 0.38, 0.8,
            (x, 0.8, 4.1), verts=16, r2=0.32)
        cyl(f"Lantern_Cap_{s}", coll, M["black"], 0.42, 0.1,
            (x, 0.8, 4.55), verts=16)
        cyl(f"Lantern_Bottom_{s}", coll, M["black"], 0.36, 0.08,
            (x, 0.8, 3.68), verts=16)

    # Arkadaki ates dili (Neon) - Roblox'ta tween ile titrer
    for i, (x, h, w, tilt) in enumerate([(-2.3, 4.0, 0.55, 18),
                                         (0, 7.6, 0.8, 0),
                                         (2.3, 4.0, 0.55, -18),
                                         (-1.7, 5.6, 0.65, 10),
                                         (1.7, 5.6, 0.65, -10)]):
        prism(f"Flame_{i + 1}", coll, M["neon_fire"], leaf_points(h, w),
              0.1, (x, 1.75 + i * 0.04, 0.8),
              rot=(0, math.radians(tilt), 0))

    # Chakra halkalari (Neon) - oturunca buyuyup yayilir
    for i, r in enumerate((3.6, 4.0)):
        torus(f"ChakraRing_{i + 1}", coll, M["neon_chakra"], r, 0.06,
              (0, 0, 0.45 + i * 0.05), major=64, minor=6)

    # Sapka (dekor, tahtin kenarinda)
    cyl("Hat_Brim", coll, M["white"], 0.75, 0.08, (2.25, -1.3, 0.92),
        verts=24)
    cyl("Hat_Top", coll, M["white"], 0.55, 0.45, (2.25, -1.3, 1.17),
        verts=24, r2=0.08)
    cyl("Hat_Band", coll, M["red"], 0.56, 0.12, (2.25, -1.3, 1.02),
        verts=24, r2=0.5)


def anim_hokage(coll):
    o = coll.objects
    for name in ("ChakraRing_1", "ChakraRing_2"):
        r = o[name]
        key_scale(r, 1, (0.6, 0.6, 1))
        key_scale(r, 60, (1.15, 1.15, 1))
        key_scale(r, 61, (0.6, 0.6, 1))
        cyclic(r)
        key_rot(r, 1, (0, 0, 0))
        key_rot(r, 120, (0, 0, math.pi * (2 if name.endswith("1") else -2)))
        cyclic(r)
    for i in range(1, 6):
        f = o[f"Flame_{i}"]
        key_scale(f, 1, (1, 1, 1))
        key_scale(f, 10 + i * 3, (1.1, 1, 1.18))
        key_scale(f, 40, (1, 1, 1))
        cyclic(f)


# ---------------------------------------------------------------------------
# 2) Gravite Egitim Koltugu (Dragon Ball esintili)
# ---------------------------------------------------------------------------

def build_dbz(coll, M):
    cyl("Platform", coll, M["steel_dark"], 4.0, 0.5, (0, 0, 0.25),
        verts=48, bevel=0.06)
    cyl("Platform_Ring", coll, M["steel"], 4.05, 0.12, (0, 0, 0.55),
        verts=48, r2=3.6)
    torus("Floor_Glow", coll, M["neon_ki"], 2.8, 0.05, (0, 0, 0.53),
          major=64, minor=6)

    # Catlak parcalari - oturunca yukari firlar (Roblox'ta tween)
    import random
    rnd = random.Random(7)
    for i in range(10):
        a = 2 * math.pi * i / 10 + rnd.uniform(-0.2, 0.2)
        d = rnd.uniform(2.0, 3.4)
        pts = [(rnd.uniform(-0.45, -0.2), 0), (rnd.uniform(0.2, 0.45), 0),
               (rnd.uniform(0.15, 0.35), rnd.uniform(0.4, 0.7)),
               (rnd.uniform(-0.3, 0.0), rnd.uniform(0.5, 0.8))]
        prism(f"Debris_{i + 1}", coll, M["stone"], pts, 0.18,
              (math.cos(a) * d, math.sin(a) * d, 0.55),
              rot=(math.radians(90) + rnd.uniform(-0.3, 0.3), 0, a),
              bevel=0.03)

    # Kapsul govdeli koltuk
    cyl("Pedestal", coll, M["steel"], 0.55, 1.2, (0, 0, 1.1), verts=24,
        r2=0.4, bevel=0.03)
    sphere("Seat", coll, M["orange"], 1.25, (0, 0, 2.05),
           scale=(1.0, 0.95, 0.32), seg=32, rings=16)
    box("Back", coll, M["orange"], (2.2, 0.5, 3.0), (0, 1.0, 3.4),
        bevel=0.35)
    box("Back_Plate", coll, M["steel_dark"], (2.5, 0.25, 3.3),
        (0, 1.3, 3.4), bevel=0.15)
    box("Back_Stripe", coll, M["steel"], (0.25, 0.12, 2.8),
        (0, 0.74, 3.5), bevel=0.05)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        box(f"Armrest_{s}", coll, M["steel_dark"], (0.5, 2.0, 0.35),
            (side * 1.35, 0.0, 2.7), bevel=0.12)
        box(f"Armrest_Pad_{s}", coll, M["orange"], (0.4, 1.6, 0.12),
            (side * 1.35, 0.0, 2.92), bevel=0.04)
        cyl(f"Armrest_Light_{s}", coll, M["neon_ki"], 0.06, 1.4,
            (side * 1.62, 0.0, 2.7), rot=(math.pi / 2, 0, 0), verts=8)

    # Arkadaki ki cekirdegi (Neon) + yorunge halkalari
    sphere("KiCore", coll, M["neon_ki"], 0.55, (0, 2.2, 4.6), seg=24,
           rings=12)
    torus("KiOrbit_1", coll, M["gold"], 0.95, 0.05, (0, 2.2, 4.6),
          rot=(math.radians(70), 0, 0), major=40, minor=6)
    torus("KiOrbit_2", coll, M["gold"], 1.15, 0.05, (0, 2.2, 4.6),
          rot=(math.radians(110), math.radians(40), 0), major=40, minor=6)
    cyl("Core_Arm", coll, M["steel_dark"], 0.12, 1.1, (0, 1.8, 4.0),
        rot=(math.radians(-50), 0, 0), verts=10)

    # Dort gravite direkleri
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        x, y = math.cos(a) * 3.3, math.sin(a) * 3.3
        cyl(f"Pylon_{i + 1}", coll, M["steel_dark"], 0.28, 2.6,
            (x, y, 1.8), verts=8, r2=0.18, smooth=False, bevel=0.03)
        sphere(f"Pylon_Orb_{i + 1}", coll, M["neon_ki"], 0.22,
               (x, y, 3.25), seg=16, rings=8)

    # Aura kabugu (Neon, yari saydam - Roblox'ta Transparency 0.6)
    sphere("Aura", coll, M["neon_aura"], 1.6, (0, 0.1, 3.0),
           scale=(1.0, 0.85, 1.6), seg=24, rings=12)


def anim_dbz(coll):
    o = coll.objects
    for i in range(1, 11):
        d = o[f"Debris_{i}"]
        base = d.location.copy()
        key_loc(d, 1, base)
        key_loc(d, 30, base + Vector((0, 0, 1.2 + (i % 3) * 0.5)))
        key_loc(d, 90, base + Vector((0, 0, 1.6 + (i % 3) * 0.5)))
        key_loc(d, 120, base)
        cyclic(d)
    for name, axis in (("KiOrbit_1", 2), ("KiOrbit_2", 1)):
        r = o[name]
        rot0 = r.rotation_euler.copy()
        key_rot(r, 1, rot0)
        rot1 = rot0.copy()
        rot1[axis] += 2 * math.pi
        key_rot(r, 60, rot1)
        cyclic(r)
    a = o["Aura"]
    key_scale(a, 1, (1.0, 0.85, 1.6))
    key_scale(a, 15, (1.08, 0.92, 1.7))
    key_scale(a, 30, (1.0, 0.85, 1.6))
    cyclic(a)


# ---------------------------------------------------------------------------
# 3) Kaptan Koltugu (One Piece esintili)
# ---------------------------------------------------------------------------

def build_pirate(coll, M):
    # Guverte tahtalari
    for i in range(9):
        box(f"Deck_{i + 1}", coll,
            M["wood"] if i % 2 else M["wood_light"],
            (0.78, 7.0, 0.25), (-3.2 + i * 0.8, 0, 0.125), bevel=0.03)
    for side in (-1, 1):
        box(f"Deck_Rail_{'L' if side < 0 else 'R'}", coll, M["wood_dark"],
            (7.3, 0.3, 0.3), (0, side * 3.6, 0.15), bevel=0.04)

    # Fici govdeli koltuk
    cyl("Barrel", coll, M["wood"], 1.25, 1.6, (0, 0, 1.05), verts=24,
        r2=1.25)
    for z in (0.45, 1.05, 1.65):
        torus(f"Barrel_Band_{int(z * 100)}", coll, M["steel_dark"], 1.27,
              0.05, (0, 0, z), major=40, minor=6)
    cyl("Seat", coll, M["leather"], 1.3, 0.3, (0, 0, 2.0), verts=32,
        bevel=0.1)

    # Yari dairesel sirtlik
    torus("Back", coll, M["wood_dark"], 1.15, 0.22, (0, 0, 3.0),
          rot=(0, 0, 0), major=24, minor=10, arc=math.pi)
    o = coll.objects["Back"]
    o.scale = (1, 1, 6.0)
    torus("Back_Top", coll, M["wood_dark"], 1.15, 0.2, (0, 0, 4.3),
          major=24, minor=10, arc=math.pi)
    for i in range(5):
        a = math.pi * (i + 0.5) / 5
        cyl(f"Back_Spindle_{i + 1}", coll, M["wood_light"], 0.07, 1.2,
            (math.cos(a) * 1.15, math.sin(a) * 1.15, 3.6), verts=8)
    for name in ("Back", "Back_Top", *[f"Back_Spindle_{i + 1}"
                                       for i in range(5)]):
        ob = coll.objects[name]
        x, y, z = ob.location
        ob.location = (x, y + 0.15, z)
        if name.startswith("Back"):
            ob.rotation_euler.z += 0
    coll.objects["Back"].location.z = 2.35

    # Direk + bayrak (bayrak dalgalanir)
    cyl("Mast", coll, M["wood_dark"], 0.18, 8.0, (-2.6, 2.2, 4.25),
        verts=16, r2=0.12)
    sphere("Mast_Top", coll, M["gold"], 0.22, (-2.6, 2.2, 8.35),
           seg=16, rings=8)
    cyl("Yard", coll, M["wood_dark"], 0.08, 2.8, (-1.3, 2.2, 7.6),
        rot=(0, math.pi / 2, 0), verts=10)
    # Bayrak: bolunmus duzlem, pivot direkte
    bm = bmesh.new()
    nx, nz = 12, 8
    W, H = 2.6, 1.8
    vs = [[bm.verts.new((i / nx * W, 0, -j / nz * H)) for j in range(nz + 1)]
          for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1],
                          vs[i][j + 1]))
    flag = new_obj("Flag", bm, coll, M["black"], smooth=True)
    flag.location = (-2.5, 2.2, 7.5)
    # Kumas dalgasi sekle islenir (Roblox mesh deforme edemez; bayrak
    # orada direk etrafinda sallanir)
    for v in flag.data.vertices:
        v.co.y = math.sin(v.co.x * 2.4) * 0.12 * (v.co.x / W)
    sol = flag.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.04
    # Genel kafatasi amblemi (resmi logo degil); bayraga birlestirilir
    cx, cz, fy = -1.2, 6.55, 2.2 - 0.2
    emblem = [
        cyl("Flag_Skull", coll, M["white"], 0.32, 0.05, (cx, fy, cz),
            rot=(math.pi / 2, 0, 0), verts=20, smooth=False),
        box("Flag_Jaw", coll, M["white"], (0.34, 0.05, 0.22),
            (cx, fy, cz - 0.3)),
        box("Flag_Bone_1", coll, M["white"], (1.3, 0.05, 0.12),
            (cx, fy + 0.01, cz - 0.15), rot=(0, math.radians(35), 0)),
        box("Flag_Bone_2", coll, M["white"], (1.3, 0.05, 0.12),
            (cx, fy + 0.01, cz - 0.15), rot=(0, math.radians(-35), 0)),
        box("Flag_HatBrim", coll, M["wood_light"], (1.05, 0.05, 0.1),
            (cx, fy - 0.01, cz + 0.22)),
        prism("Flag_HatCrown", coll, M["wood_light"],
              [(-0.3, 0), (0.3, 0), (0.25, 0.25), (-0.25, 0.25)], 0.05,
              (cx, fy - 0.01, cz + 0.27)),
        box("Flag_HatBand", coll, M["red"], (0.6, 0.06, 0.08),
            (cx, fy - 0.02, cz + 0.31)),
    ]
    join([flag] + emblem, "Flag", pivot=(-2.5, 2.2, 7.5))

    # Dumen (yanda, doner)
    parts = [
        torus("Wheel_Rim", coll, M["wood"], 0.9, 0.08, (2.6, -1.2, 2.2),
              rot=(math.pi / 2, 0, math.pi / 2), major=40, minor=8),
        cyl("Wheel_Hub", coll, M["gold"], 0.18, 0.3, (2.6, -1.2, 2.2),
            rot=(0, math.pi / 2, 0), verts=16),
    ]
    for i in range(8):
        a = math.pi * i / 4
        parts.append(cyl(f"Wheel_Spoke_{i + 1}", coll, M["wood_light"],
                         0.05, 1.5,
                         (2.6, -1.2 + math.cos(a) * 0.75,
                          2.2 + math.sin(a) * 0.75),
                         rot=(a + math.pi / 2, 0, 0), verts=8))
    join(parts, "Wheel", pivot=(2.6, -1.2, 2.2))
    cyl("Wheel_Stand", coll, M["wood_dark"], 0.22, 1.9, (2.85, -1.2, 1.15),
        verts=12)

    # Fener (Neon)
    cyl("Lantern_Post", coll, M["wood_dark"], 0.08, 2.6, (2.6, 2.4, 1.55),
        verts=10)
    cyl("Lantern_Glow", coll, M["neon_lantern"], 0.28, 0.6,
        (2.6, 2.4, 3.15), verts=12)
    cyl("Lantern_Cap", coll, M["steel_dark"], 0.36, 0.25, (2.6, 2.4, 3.55),
        verts=12, r2=0.05)

    # Halat yumagi + hasir sapka (dekor)
    for k in range(3):
        torus(f"Rope_Coil_{k + 1}", coll, M["rope"], 0.55 - k * 0.12, 0.08,
              (-2.6, -2.2, 0.33 + k * 0.14), major=28, minor=6)
    cyl("StrawHat_Brim", coll, M["wood_light"], 0.65, 0.06,
        (1.0, -1.0, 2.2), verts=24, rot=(math.radians(-12), 0, 0))
    cyl("StrawHat_Top", coll, M["wood_light"], 0.38, 0.32,
        (1.0, -1.0, 2.38), verts=24, r2=0.34, rot=(math.radians(-12), 0, 0))
    cyl("StrawHat_Band", coll, M["red"], 0.395, 0.1,
        (1.0, -1.0, 2.28), verts=24, rot=(math.radians(-12), 0, 0))


def anim_pirate(coll):
    o = coll.objects
    f = o["Flag"]
    for fr, deg in ((1, -12), (30, 12), (60, -12)):
        key_rot(f, fr, (0, 0, math.radians(deg)))
    cyclic(f)
    w = o["Wheel"]
    for fr, deg in ((1, 0), (60, 45), (120, 0)):
        key_rot(w, fr, (math.radians(deg), 0, 0))


# ---------------------------------------------------------------------------
# 4) Komuta Koltugu (Attack on Titan esintili)
# ---------------------------------------------------------------------------

def build_aot(coll, M):
    # Tas kale platformu + basamak
    box("Platform", coll, M["stone"], (7.0, 6.0, 0.6), (0, 0.3, 0.3),
        bevel=0.08)
    box("Step", coll, M["stone"], (4.0, 1.0, 0.3), (0, -3.2, 0.15),
        bevel=0.06)
    for i in range(7):
        box(f"Battlement_{i + 1}", coll, M["stone"], (0.6, 0.6, 0.9),
            (-3.0 + i, 3.0, 1.05), bevel=0.05)

    # Agir metal koltuk
    box("Seat", coll, M["leather"], (2.3, 2.1, 0.4), (0, 0, 2.0),
        bevel=0.12)
    box("Seat_Base", coll, M["steel_dark"], (2.6, 2.4, 1.3), (0, 0, 1.2),
        bevel=0.1)
    box("Back", coll, M["steel_dark"], (2.6, 0.45, 3.6), (0, 1.15, 3.8),
        bevel=0.12)
    box("Back_Cushion", coll, M["leather"], (2.0, 0.2, 3.0), (0, 0.85, 3.7),
        bevel=0.08)
    for k, z in enumerate((2.6, 3.4, 4.2, 5.0)):
        box(f"Back_Rivet_Row_{k + 1}", coll, M["steel"], (2.2, 0.05, 0.06),
            (0, 0.73, z))

    # Pelerin (sirtlikten sarkar)
    pts = [(-1.3, 0), (1.3, 0), (1.5, -3.2), (0.7, -3.0), (0, -3.3),
           (-0.7, -3.0), (-1.5, -3.2)]
    prism("Cloak", coll, M["green_cloak"], pts, 0.08, (0, 1.45, 5.5),
          bevel=0.02)

    # Kolcaklar + 3D manevra gaz tupleri
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        box(f"Armrest_{s}", coll, M["steel_dark"], (0.5, 2.3, 0.35),
            (side * 1.5, 0.0, 2.75), bevel=0.1)
        cyl(f"GasTank_{s}", coll, M["steel"], 0.32, 1.8,
            (side * 1.95, 0.4, 1.6), rot=(math.radians(15), 0, 0),
            verts=16, bevel=0.02)
        sphere(f"GasTank_Cap_{s}", coll, M["steel"], 0.32,
               (side * 1.95, 0.64, 2.47), seg=16, rings=8)
        box(f"Blade_Case_{s}", coll, M["steel_dark"], (0.35, 1.6, 0.5),
            (side * 1.95, -0.6, 1.0), bevel=0.06)
        for b in range(3):
            box(f"Blade_{s}_{b + 1}", coll, M["steel"], (0.04, 1.4, 0.2),
                (side * (1.85 + b * 0.09), -0.6, 1.4), bevel=0.01)

    # Kanatlar: mentese sirtlikta, Roblox'ta HingeConstraint/Tween ile acilir
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        feathers = []
        hinge = (side * 1.2, 1.55, 5.2)
        for k in range(6):
            length = 3.8 - k * 0.4
            f = prism(f"Wing_{s}_F{k + 1}", coll,
                      M["white"] if k % 2 == 0 else M["wing_blue"],
                      leaf_points(length, 0.34, n=10), 0.08,
                      (hinge[0], hinge[1] + k * 0.03, hinge[2]),
                      rot=(0, side * math.radians(20 + k * 17), 0))
            feathers.append(f)
        feathers.append(sphere(f"Wing_{s}_Joint", coll, M["steel"], 0.25,
                               hinge, seg=16, rings=8))
        join(feathers, f"Wing_{s}", pivot=hinge)

    # Alarm lambasi (Neon) - kirmizi yanip soner
    cyl("Alarm_Post", coll, M["steel_dark"], 0.1, 3.6, (2.8, 2.2, 2.4),
        verts=10)
    cyl("Alarm_Base", coll, M["steel_dark"], 0.35, 0.2, (2.8, 2.2, 4.25),
        verts=16)
    sphere("Alarm_Light", coll, M["neon_alarm"], 0.33, (2.8, 2.2, 4.4),
           scale=(1, 1, 1.2), seg=16, rings=8)
    torus("Alarm_Cage", coll, M["steel"], 0.36, 0.03, (2.8, 2.2, 4.45),
          major=24, minor=6)

    # Isaret fisegi (dekor) ve harita masasi
    box("MapTable", coll, M["wood"], (1.6, 1.0, 0.1), (-2.7, -1.4, 1.75),
        bevel=0.03)
    box("MapTable_Leg", coll, M["wood_dark"], (0.2, 0.2, 1.1),
        (-2.7, -1.4, 1.15))
    box("Map", coll, M["white"], (1.3, 0.75, 0.02), (-2.7, -1.4, 1.81))
    cyl("Flare_Gun", coll, M["steel_dark"], 0.06, 0.6, (-2.4, -1.2, 1.88),
        rot=(0, math.pi / 2, 0.3), verts=10)


def anim_aot(coll):
    o = coll.objects
    for s, side in (("L", -1), ("R", 1)):
        w = o[f"Wing_{s}"]
        r0 = w.rotation_euler.copy()
        closed = r0.copy()
        closed.z = side * math.radians(80)
        key_rot(w, 1, closed)
        key_rot(w, 30, r0)
        key_rot(w, 90, r0)
        key_rot(w, 120, closed)
    a = o["Alarm_Light"]
    for fr, sc in ((1, 1.0), (8, 1.2), (15, 1.0)):
        key_scale(a, fr, (sc, sc, sc * 1.2))
    cyclic(a)


# ---------------------------------------------------------------------------
# Dis aktarma ve ana akis
# ---------------------------------------------------------------------------

CHAIRS = [
    ("HokageThrone", build_hokage, anim_hokage),
    ("GravityTrainingChair", build_dbz, anim_dbz),
    ("PirateCaptainChair", build_pirate, anim_pirate),
    ("ScoutCommandChair", build_aot, anim_aot),
]


def export_fbx(coll, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in coll.objects:
        ob.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        bake_anim=False,
        path_mode="COPY",
    )


def setup_preview(scene):
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.02, 0.025, 0.04, 1)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    def light(name, kind, loc, energy, rot=(0, 0, 0), size=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        if size:
            ld.size = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)

    light("Key", "AREA", (8, -10, 14), 3000, (math.radians(50), 0,
                                               math.radians(35)), 8)
    light("Rim", "AREA", (-8, 10, 10), 1500, (math.radians(-55), 0,
                                              math.radians(200)), 6)
    light("Sun", "SUN", (0, 0, 20), 1.5, (math.radians(30), 0,
                                         math.radians(20)))
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 40
    scene.collection.objects.link(cam)
    scene.camera = cam
    floor = bpy.data.objects.new("PreviewFloor", bpy.data.meshes.new("F"))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    bm.to_mesh(floor.data)
    bm.free()
    floor.data.materials.append(mat("Floor", (0.06, 0.06, 0.08),
                                    roughness=0.4))
    scene.collection.objects.link(floor)
    return cam


def aim(cam, target, dist, height, angle):
    t = Vector(target)
    cam.location = t + Vector((math.sin(angle) * dist,
                               -math.cos(angle) * dist, height))
    d = t - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render(scene, cam, offsets, frame=45):
    os.makedirs(RENDER_DIR, exist_ok=True)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.view_settings.look = "AgX - Medium High Contrast" \
        if "AgX - Medium High Contrast" in [
            i.name for i in bpy.types.ColorManagedViewSettings.bl_rna
            .properties["look"].enum_items] else "None"
    scene.frame_set(frame)
    for name, x in offsets:
        aim(cam, (x, 0, 3.0), 13, 4.5, math.radians(-30))
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.ops.render.render(write_still=True)
    aim(cam, (offsets[-1][1] / 2, 0, 3.0), 34, 10, math.radians(-20))
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 700
    cam.data.lens = 32
    scene.render.filepath = os.path.join(RENDER_DIR, "AllChairs.png")
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else \
        sys.argv[1:]
    do_render = "--render" in argv

    reset_scene()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    scene = bpy.context.scene
    M = materials()
    offsets = []
    spacing = 11.0

    for idx, (name, build, animate) in enumerate(CHAIRS):
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)
        build(coll, M)
        apply_negative_scale(coll)

        # FBX: dalga modifier'i dahil, animasyonsuz, merkezde
        export_fbx(coll, os.path.join(EXPORT_DIR, f"{name}.fbx"))

        # Ucgen kontrolu (Roblox MeshPart siniri)
        dg = bpy.context.evaluated_depsgraph_get()
        total = 0
        for ob in coll.objects:
            me = ob.evaluated_get(dg).to_mesh()
            tris = sum(len(p.vertices) - 2 for p in me.polygons)
            ob.evaluated_get(dg).to_mesh_clear()
            total += tris
            if tris > TRI_LIMIT:
                raise RuntimeError(f"{ob.name}: {tris} ucgen > {TRI_LIMIT}")
        print(f"[OK] {name}: {len(coll.objects)} parca, {total} ucgen")

        animate(coll)
        # Blender'da isimler geneldir: sonraki koltuk "Seat", "Back" vb.
        # isimleri temiz kullanabilsin diye bu koltugun objelerini onekle.
        for ob in coll.objects:
            ob.name = f"{name}.{ob.name}"
        x = idx * spacing
        offsets.append((name, x))
        for ob in coll.objects:
            if ob.parent is None:
                if ob.animation_data and ob.animation_data.action:
                    _shift_location_keys(ob, x)
                ob.location.x += x

    cam = setup_preview(scene)
    aim(cam, (offsets[-1][1] / 2, 0, 3.0), 34, 10, math.radians(-20))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPORT_DIR,
                                                      "AnimeChairs.blend"))
    if do_render:
        render(scene, cam, offsets)
    print("Bitti:", EXPORT_DIR)


def _shift_location_keys(ob, dx):
    ad = ob.animation_data
    try:
        curves = list(ad.action.fcurves)
    except AttributeError:
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        if fc.data_path == "location" and fc.array_index == 0:
            for kp in fc.keyframe_points:
                kp.co.y += dx
                kp.handle_left.y += dx
                kp.handle_right.y += dx


if __name__ == "__main__":
    main()

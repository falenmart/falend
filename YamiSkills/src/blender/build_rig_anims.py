"""
Yami Skills - builds the R15 rig + katana in Blender, creates one Action per animation from
anim_library.py, saves YamiRig_Animations.blend and exports Roblox KeyframeSequences (.rbxmx).

Usage:
    python build_rig_anims.py -- <blender_out_dir> <rbxmx_out_dir> [<gif_preview_dir>]
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

import anim_core as ac  # noqa: E402
import anim_library as al  # noqa: E402
import build_vfx  # noqa: E402
import roblox_anim_export as rax  # noqa: E402

FPS = 60
M = rax.M


def rb_vec(p):
    return Vector((-p[0], p[2], p[1]))


def rb_mat(m4):
    """Roblox 4x4 (numpy) -> Blender Matrix (same object expressed in Blender axes)."""
    return M @ Matrix([list(r) for r in m4]) @ M


BONE_TAIL = {
    "HumanoidRootPart": (0, 3.0, -0.8),
    "LowerTorso": (0, 2.4, 0), "UpperTorso": (0, 4.0, 0), "Head": (0, 5.1, 0),
    "RightUpperArm": None, "RightLowerArm": None, "RightHand": "hand",
    "LeftUpperArm": None, "LeftLowerArm": None, "LeftHand": "hand",
    "RightUpperLeg": None, "RightLowerLeg": None, "RightFoot": "foot",
    "LeftUpperLeg": None, "LeftLowerLeg": None, "LeftFoot": "foot",
}
CHILD_OF = {"RightUpperArm": "RightLowerArm", "RightLowerArm": "RightHand", "LeftUpperArm": "LeftLowerArm",
            "LeftLowerArm": "LeftHand", "RightUpperLeg": "RightLowerLeg", "RightLowerLeg": "RightFoot",
            "LeftUpperLeg": "LeftLowerLeg", "LeftLowerLeg": "LeftFoot"}


def pivot(part):
    if part == "HumanoidRootPart":
        return ac.REST["HumanoidRootPart"][:3, 3]
    return ac.joint_pivot_rest(part)


def build_armature():
    arm_data = bpy.data.armatures.new("YamiRig")
    arm_obj = bpy.data.objects.new("YamiRig", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    order = ["HumanoidRootPart"] + [j[2] for j in ac.JOINTS]
    for part in order:
        b = eb.new(part)
        head = pivot(part)
        tail_spec = BONE_TAIL[part]
        if tail_spec is None:
            tail = pivot(CHILD_OF[part])
        elif tail_spec == "hand":
            tail = head + np.array([0, -0.32, 0])
        elif tail_spec == "foot":
            tail = head + np.array([0, -0.12, -0.55])
        else:
            tail = np.array(tail_spec, float)
        b.head = rb_vec(head)
        b.tail = rb_vec(tail)
        b.roll = 0.0
    for _, p0, p1, _, _ in ac.JOINTS:
        eb[p1].parent = eb[p0]
        eb[p1].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_data.display_type = "STICK"
    arm_obj.show_in_front = True
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm_obj


def material(name, rgb, rough=0.7):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*rgb, 1)
    return m


def build_body(arm_obj):
    mats = {
        "skin": material("Skin", (0.78, 0.6, 0.47)),
        "shirt": material("Shirt", (0.07, 0.07, 0.08)),
        "pants": material("Pants", (0.03, 0.03, 0.035)),
        "head": material("HeadMat", (0.78, 0.6, 0.47)),
        "hair": material("Hair", (0.02, 0.02, 0.02)),
    }
    part_mat = {"Head": "head", "UpperTorso": "shirt", "LowerTorso": "pants",
                "RightUpperArm": "skin", "RightLowerArm": "skin", "RightHand": "skin",
                "LeftUpperArm": "skin", "LeftLowerArm": "skin", "LeftHand": "skin",
                "RightUpperLeg": "pants", "RightLowerLeg": "pants", "RightFoot": "pants",
                "LeftUpperLeg": "pants", "LeftLowerLeg": "pants", "LeftFoot": "pants"}
    verts, faces, face_mat, vgroups = [], [], [], {}
    mat_names = list(mats.keys())

    def add_box(part, center_m4, size, mat_key):
        sx, sy, sz = (s / 2 for s in size)
        base = len(verts)
        for dx in (-1, 1):
            for dy in (-1, 1):
                for dz in (-1, 1):
                    p = center_m4 @ np.array([dx * sx, dy * sy, dz * sz, 1.0])
                    verts.append(rb_vec(p[:3]))
        vgroups.setdefault(part, []).extend(range(base, base + 8))
        for q in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            faces.append(tuple(base + i for i in q))
            face_mat.append(mat_names.index(mat_key))

    for part, mk in part_mat.items():
        size = ac.PART_SIZES[part]
        if part == "Head":
            size = (1.05, 1.15, 1.05)
        add_box(part, ac.REST[part], size, mk)
    # Yami-ish spiky hair + headband hint so facing is readable in previews
    head = ac.REST["Head"]
    add_box("Head", head @ ac.T(0, 0.62, 0.05), (1.15, 0.25, 1.15), "hair")
    for i, (x, z) in enumerate([(-0.35, 0.3), (0.0, 0.42), (0.35, 0.3), (-0.2, -0.1), (0.25, -0.05)]):
        add_box("Head", head @ ac.T(x, 0.82, z) @ ac.M4(ac.euler3(25 if z > 0 else -15, 0, 15 * (i - 2))),
                (0.3, 0.35, 0.3), "hair")
    add_box("Head", head @ ac.T(0, 0.05, -0.53), (0.7, 0.12, 0.05), "hair")  # eyes band (facing marker)

    me = bpy.data.meshes.new("YamiBody")
    me.from_pydata(verts, [], faces)
    for m in mats.values():
        me.materials.append(m)
    for poly, mi in zip(me.polygons, face_mat):
        poly.material_index = mi
    me.validate()
    body = bpy.data.objects.new("YamiBody", me)
    bpy.context.scene.collection.objects.link(body)
    for part, idxs in vgroups.items():
        vg = body.vertex_groups.new(name=part)
        vg.add(idxs, 1.0, "REPLACE")
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    body.parent = arm_obj
    return body


def bind_rigid(obj, arm_obj, bone, roblox_world_m4):
    """Bake obj (authored at its own origin, Roblox axes) to the rest transform and skin it 100% to bone."""
    obj.data.transform(rb_mat(roblox_world_m4))
    obj.matrix_world = Matrix.Identity(4)
    vg = obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    obj.parent = arm_obj


def build_katana(arm_obj, tex_dir):
    kat_mat = build_vfx.make_image_material("M_Katana", os.path.join(tex_dir, "T_Katana.png"), alpha=False,
                                            roughness=0.35, metallic=0.6)
    katana = build_vfx.mesh_katana(kat_mat)
    saya = build_vfx.mesh_saya(kat_mat)
    bind_rigid(katana, arm_obj, "RightHand", ac.REST["RightHand"] @ ac.KATANA_IN_HAND)
    bind_rigid(saya, arm_obj, "LowerTorso", ac.REST["LowerTorso"] @ ac.SAYA_IN_LOWERTORSO)
    return katana, saya


EASE = {
    "smooth": ("BEZIER", "AUTO"), "hold": ("BEZIER", "AUTO"), "linear": ("LINEAR", "AUTO"),
    "in": ("QUAD", "EASE_IN"), "out": ("QUART", "EASE_OUT"), "snap": ("EXPO", "EASE_OUT"),
}


def basis_from_transform(arm_obj, part, tr4):
    bone = arm_obj.data.bones[part]
    A = bone.matrix_local
    pj = pivot(part)
    Tj = ac.T(*pj)
    D_r = Tj @ tr4 @ np.linalg.inv(Tj)
    D_b = rb_mat(D_r)
    return A.inverted() @ D_b @ A


def build_action(arm_obj, anim):
    action = bpy.data.actions.new(anim["name"])
    action.use_fake_user = True
    action["roblox_priority"] = anim["priority"]
    action["roblox_loop"] = bool(anim["loop"])
    rax.assign_action(arm_obj, action)
    parts = anim["parts"] or ac.ANIMATED_PARTS
    prev_q = {}
    key_frames = []
    warnings = []
    for t, spec, ease in anim["keys"]:
        frame = round(t * FPS)
        key_frames.append((frame, ease))
        tr, warns = ac.build_pose(spec, f"{anim['name']}@{t}")
        warnings += warns
        for part in parts:
            B = basis_from_transform(arm_obj, part, tr.get(part, np.eye(4)))
            loc, rot, _ = B.decompose()
            if part in prev_q and prev_q[part].dot(rot) < 0:
                rot = -rot
            prev_q[part] = rot
            pb = arm_obj.pose.bones[part]
            pb.rotation_quaternion = rot
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if part == "LowerTorso":
                pb.location = loc
                pb.keyframe_insert("location", frame=frame)
    ease_at = dict(key_frames)
    for fc in rax.action_fcurves(action):
        for kp in fc.keyframe_points:
            interp, easing = EASE.get(ease_at.get(round(kp.co.x), "smooth"), EASE["smooth"])
            kp.interpolation = interp
            kp.easing = easing
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"
        if anim["loop"] and hasattr(fc, "modifiers"):
            pass  # loop handled by Roblox (KeyframeSequence.Loop)
        fc.update()
    for name, t in anim["markers"].items():
        mk = action.pose_markers.new(name)
        mk.frame = round(t * FPS)
    return action, warnings


def reset_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)


def setup_preview_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 10
    sc.cycles.use_denoising = True
    sc.render.resolution_x = 420
    sc.render.resolution_y = 420
    world = bpy.data.worlds.new("PreviewWorld")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.64, 0.69, 1)
    ground_me = bpy.data.meshes.new("Ground")
    s = 14
    ground_me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("Ground", ground_me)
    ground_me.materials.append(material("GroundMat", (0.42, 0.43, 0.45), 1.0))
    sc.collection.objects.link(ground)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 42
    cam = bpy.data.objects.new("Cam", cam_data)
    sc.collection.objects.link(cam)
    # 3/4 showcase view from the front-right (character faces Roblox -Z = Blender -Y)
    cam.location = rb_vec((5.6, 4.3, -7.0))
    target = rb_vec((-0.2, 2.3, -1.1))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.5
    sun = bpy.data.objects.new("Sun", sun_data)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(40), math.radians(-20), math.radians(-35))
    return cam, ground, sun


def render_gif(arm_obj, action, path, fps_out=15):
    from PIL import Image
    sc = bpy.context.scene
    reset_pose(arm_obj)
    rax.assign_action(arm_obj, action)
    f0, f1 = action.frame_range
    frames = []
    step = FPS / fps_out
    f = f0
    tmp = path + ".frame.png"
    while f <= f1 + 1e-6:
        sc.frame_set(int(round(f)))
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        frames.append(Image.open(tmp).convert("RGB").copy())
        f += step
    if os.path.exists(tmp):
        os.remove(tmp)
    pal = [fr.convert("P", palette=Image.ADAPTIVE, colors=128) for fr in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / fps_out), loop=0)
    return len(frames)


def main(blend_dir, rbxmx_dir, gif_dir=None):
    blend_dir = os.path.abspath(blend_dir)
    rbxmx_dir = os.path.abspath(rbxmx_dir)
    build_vfx.reset_scene()
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    tex_dir = os.path.join(blend_dir, "Textures")
    if not os.path.exists(os.path.join(tex_dir, "T_Katana.png")):
        import vfx_textures
        vfx_textures.build_all(tex_dir)
    arm_obj = build_armature()
    build_body(arm_obj)
    build_katana(arm_obj, tex_dir)

    all_warn = []
    actions = []
    for anim in al.ALL:
        reset_pose(arm_obj)
        action, warns = build_action(arm_obj, anim)
        actions.append(action)
        all_warn += warns
    for w in all_warn:
        print("WARN", w)

    # Bind exporter as a text block inside the .blend so users can re-export after editing
    txt = bpy.data.texts.new("roblox_anim_export.py")
    with open(os.path.join(HERE, "roblox_anim_export.py"), encoding="utf-8") as fh:
        txt.write(fh.read())

    results = rax.export_all(arm_obj, rbxmx_dir)
    for path, n, parts in results:
        print(f"exported {os.path.basename(path)}: {n} keyframes, {len(parts)} joints")

    show = bpy.data.actions.get("DimensionSlash")
    rax.assign_action(arm_obj, show)
    sc.frame_start = 0
    sc.frame_end = int(show.frame_range[1])
    sc.frame_set(0)

    if gif_dir:
        os.makedirs(gif_dir, exist_ok=True)
        cam, ground, sun = setup_preview_scene()
        for action in actions:
            n = render_gif(arm_obj, action, os.path.join(gif_dir, f"anim_{action.name}.gif"))
            print("gif", action.name, n, "frames")
        for o in (cam, ground, sun):
            bpy.data.objects.remove(o, do_unlink=True)
        rax.assign_action(arm_obj, show)

    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(blend_dir, "YamiRig_Animations.blend"), compress=True)
    print("saved", os.path.join(blend_dir, "YamiRig_Animations.blend"))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv[0], argv[1], argv[2] if len(argv) > 2 else None)

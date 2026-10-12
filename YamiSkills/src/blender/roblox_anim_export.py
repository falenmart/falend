"""
Roblox KeyframeSequence exporter for the YamiRig armature (Blender 4.x / 5.x).

Run it from Blender's Text Editor (Run Script) after editing animations in YamiRig_Animations.blend:
every Action that has a "roblox_priority" custom property is exported as <ActionName>.rbxmx
next to the .blend file (folder "RobloxAnimations"). Drag the .rbxmx into Roblox Studio
(or put it in ReplicatedStorage.YamiSkills.Animations, replacing the old one).

Math: each bone's head sits on the Roblox joint pivot. For a joint with rest pivot p (Roblox space)
    Pose.CFrame = Motor6D.Transform = T(p)^-1 * M * (A * B * A^-1) * M * T(p)
where A = bone.matrix_local, B = pose_bone.matrix_basis and M maps Roblox <-> Blender axes
(Blender (x, y, z) = Roblox (-x, z, y); M is its own inverse).
"""
import math
import os
import xml.sax.saxutils as su

import bpy
from mathutils import Matrix, Vector

M = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

HIERARCHY = [  # (part, parent part)
    ("LowerTorso", "HumanoidRootPart"), ("UpperTorso", "LowerTorso"), ("Head", "UpperTorso"),
    ("RightUpperArm", "UpperTorso"), ("RightLowerArm", "RightUpperArm"), ("RightHand", "RightLowerArm"),
    ("LeftUpperArm", "UpperTorso"), ("LeftLowerArm", "LeftUpperArm"), ("LeftHand", "LeftLowerArm"),
    ("RightUpperLeg", "LowerTorso"), ("RightLowerLeg", "RightUpperLeg"), ("RightFoot", "RightLowerLeg"),
    ("LeftUpperLeg", "LowerTorso"), ("LeftLowerLeg", "LeftUpperLeg"), ("LeftFoot", "LeftLowerLeg"),
]
PARTS = [p for p, _ in HIERARCHY]
CHILDREN = {}
for _p, _parent in HIERARCHY:
    CHILDREN.setdefault(_parent, []).append(_p)
PRIORITY = {"Idle": 0, "Movement": 1, "Action": 2, "Action2": 3, "Action3": 4, "Action4": 5, "Core": 1000}


def action_fcurves(action):
    try:
        return list(action.fcurves)
    except AttributeError:
        pass
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out.extend(cb.fcurves)
    return out


def assign_action(obj, action):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if hasattr(obj.animation_data, "action_slot") and getattr(action, "slots", None):
        if len(action.slots) and obj.animation_data.action_slot is None:
            obj.animation_data.action_slot = action.slots[0]


def animated_bones(action):
    names = set()
    for fc in action_fcurves(action):
        dp = fc.data_path
        if dp.startswith('pose.bones["'):
            names.add(dp.split('"')[1])
    return names


def joint_transform(arm_obj, part):
    bone = arm_obj.data.bones[part]
    pb = arm_obj.pose.bones[part]
    A = bone.matrix_local
    D = A @ pb.matrix_basis @ A.inverted()
    head_r = M @ Vector((*bone.head_local, 1.0))
    Tj = Matrix.Translation(head_r.xyz)
    return Tj.inverted() @ M @ D @ M @ Tj


def fmt(x):
    if abs(x) < 1e-7:
        x = 0.0
    return repr(round(float(x), 6))


def cframe_xml(m, indent):
    r = m.to_3x3()
    t = m.translation
    vals = [("X", t.x), ("Y", t.y), ("Z", t.z)]
    for i in range(3):
        for j in range(3):
            vals.append((f"R{i}{j}", r[i][j]))
    inner = "".join(f"<{k}>{fmt(v)}</{k}>" for k, v in vals)
    return f'{indent}<CoordinateFrame name="CFrame">{inner}</CoordinateFrame>\n'


class RefGen:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"RBX{self.n:08X}"


def rig_hierarchy(arm_obj):
    """(part, parent) pairs from the armature bone tree (root bone = HumanoidRootPart)."""
    pairs = []
    for b in arm_obj.data.bones:
        if b.parent is not None:
            pairs.append((b.name, b.parent.name))
    return pairs


def pose_xml(part, cframes, animated, needed, ref, indent, children=None):
    weight = 1.0 if part in animated else 0.0
    cf = cframes.get(part, Matrix.Identity(4)) if weight > 0 else Matrix.Identity(4)
    s = f'{indent}<Item class="Pose" referent="{ref()}">\n'
    s += f"{indent}\t<Properties>\n"
    s += f'{indent}\t\t<string name="Name">{part}</string>\n'
    s += cframe_xml(cf, indent + "\t\t")
    s += f'{indent}\t\t<token name="EasingDirection">0</token>\n'
    s += f'{indent}\t\t<token name="EasingStyle">0</token>\n'
    s += f'{indent}\t\t<float name="Weight">{fmt(weight)}</float>\n'
    s += f"{indent}\t</Properties>\n"
    for child in (children or CHILDREN).get(part, []):
        if child in needed:
            s += pose_xml(child, cframes, animated, needed, ref, indent + "\t", children)
    s += f"{indent}</Item>\n"
    return s


def export_action(arm_obj, action, out_dir, sample_fps=30):
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    assign_action(arm_obj, action)
    hierarchy = rig_hierarchy(arm_obj)
    parent_of = dict(hierarchy)
    children = {}
    for _p, _par in hierarchy:
        children.setdefault(_par, []).append(_p)
    animated = animated_bones(action) & set(parent_of)
    needed = set()
    for p in animated:  # every ancestor of an animated part must exist as a (weight 0) pose
        cur = p
        while cur is not None:
            needed.add(cur)
            cur = parent_of.get(cur)
    f0, f1 = action.frame_range
    step = fps / sample_fps
    frames = set()
    f = f0
    while f < f1 - 1e-6:
        frames.add(round(f, 4))
        f += step
    frames.add(round(f1, 4))
    for fc in action_fcurves(action):
        for kp in fc.keyframe_points:
            frames.add(round(kp.co.x, 4))
    markers = {}
    for mk in getattr(action, "pose_markers", []):
        frames.add(float(mk.frame))
        markers.setdefault(round(float(mk.frame), 4), []).append(mk.name)
    frames = sorted(x for x in frames if f0 - 1e-6 <= x <= f1 + 1e-6)

    ref = RefGen()
    name = action.name
    loop = bool(action.get("roblox_loop", False))
    prio = PRIORITY.get(action.get("roblox_priority", "Action"), 2)
    out = ['<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">\n',
           "\t<External>null</External>\n\t<External>nil</External>\n",
           f'\t<Item class="KeyframeSequence" referent="{ref()}">\n',
           "\t\t<Properties>\n",
           f'\t\t\t<string name="Name">{su.escape(name)}</string>\n',
           f'\t\t\t<bool name="Loop">{"true" if loop else "false"}</bool>\n',
           f'\t\t\t<token name="Priority">{prio}</token>\n',
           "\t\t</Properties>\n"]
    for fr in frames:
        whole = math.floor(fr)
        scene.frame_set(int(whole), subframe=float(fr - whole))
        cframes = {p: joint_transform(arm_obj, p) for p in animated}
        t = (fr - f0) / fps
        out.append(f'\t\t<Item class="Keyframe" referent="{ref()}">\n')
        out.append(f'\t\t\t<Properties>\n\t\t\t\t<string name="Name">Keyframe</string>\n'
                   f'\t\t\t\t<float name="Time">{fmt(t)}</float>\n\t\t\t</Properties>\n')
        out.append(pose_xml("HumanoidRootPart", cframes, animated, needed | {"HumanoidRootPart"}, ref, "\t\t\t", children))
        for mname in markers.get(round(fr, 4), []):
            out.append(f'\t\t\t<Item class="KeyframeMarker" referent="{ref()}">\n'
                       f'\t\t\t\t<Properties>\n\t\t\t\t\t<string name="Name">{su.escape(mname)}</string>\n'
                       f'\t\t\t\t\t<string name="Value"></string>\n\t\t\t\t</Properties>\n\t\t\t</Item>\n')
        out.append("\t\t</Item>\n")
    out.append("\t</Item>\n</roblox>\n")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.rbxmx")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(out))
    return path, len(frames), sorted(animated)


def export_all(arm_obj, out_dir, sample_fps=30):
    results = []
    prev = arm_obj.animation_data.action if arm_obj.animation_data else None
    for action in bpy.data.actions:
        if "roblox_priority" not in action:
            continue
        results.append(export_action(arm_obj, action, out_dir, sample_fps))
    if prev is not None:
        assign_action(arm_obj, prev)
    return results


if __name__ == "__main__":
    rig = bpy.data.objects.get("YamiRig") or bpy.data.objects.get("YamiBossRig")
    if rig is None:
        raise SystemExit("YamiRig / YamiBossRig armature not found")
    base = bpy.path.abspath("//") or os.getcwd()
    for path, n, parts in export_all(rig, os.path.join(base, "RobloxAnimations")):
        print(f"exported {path} ({n} keyframes, {len(parts)} joints)")

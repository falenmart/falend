"""
Yami Skills - animation authoring core (pure numpy, no Blender needed).

* R15 (block rig) definition in ROBLOX space (studs, X right, Y up, -Z forward, ground y = 0).
* Forward kinematics with Roblox Motor6D semantics:
      Part1 = Part0 * C0 * Transform * C1^-1
* Two-bone IK for the sword arm (grip position + blade/edge direction), the free arm and the legs.
* Conversion of joint Transforms <-> Blender pose-bone matrix_basis (see blender_bridge in build script).

A KeyframeSequence Pose.CFrame is exactly the Motor6D.Transform computed here.
"""
import math

import numpy as np

# ----------------------------------------------------------------- matrices


def T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def R3x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def R3y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def R3z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def euler3(rx, ry, rz):
    """Degrees. Same as Roblox CFrame.Angles(rx, ry, rz) = Rx * Ry * Rz."""
    return R3x(math.radians(rx)) @ R3y(math.radians(ry)) @ R3z(math.radians(rz))


def M4(r3=None, p=(0, 0, 0)):
    m = np.eye(4)
    if r3 is not None:
        m[:3, :3] = r3
    m[:3, 3] = p
    return m


def inv(m):
    return np.linalg.inv(m)


def norm(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def axis_angle3(axis, ang):
    x, y, z = norm(axis)
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ])


def rot_between(a, b):
    a, b = norm(a), norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        if c > 0:
            return np.eye(3)
        perp = norm(np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]))
        return axis_angle3(perp, math.pi)
    return axis_angle3(v, math.atan2(np.linalg.norm(v), c))


def rot_angle(r3):
    return math.acos(max(-1.0, min(1.0, (np.trace(r3) - 1) / 2)))


def angle_between(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return math.acos(max(-1.0, min(1.0, float(np.dot(a, b) / (na * nb)))))


def frame_from(blade, edge):
    """Hand rotation whose -Z = blade direction and -Y = edge direction (orthogonalised)."""
    b = norm(blade)
    e = np.asarray(edge, dtype=float)
    e = norm(e - np.dot(e, b) * b)
    z = -b
    y = -e
    x = np.cross(y, z)
    return np.column_stack([x, y, z])


# ------------------------------------------------------------------ R15 rig

PART_SIZES = {
    "HumanoidRootPart": (2, 2, 1),
    "LowerTorso": (2, 0.4, 1),
    "UpperTorso": (2, 1.6, 1),
    "Head": (1.2, 1.2, 1.2),
    "RightUpperArm": (1, 1.169, 1), "RightLowerArm": (1, 1.052, 1), "RightHand": (1, 0.3, 1),
    "LeftUpperArm": (1, 1.169, 1), "LeftLowerArm": (1, 1.052, 1), "LeftHand": (1, 0.3, 1),
    "RightUpperLeg": (1, 1.217, 1), "RightLowerLeg": (1, 1.193, 1), "RightFoot": (1, 0.3, 1),
    "LeftUpperLeg": (1, 1.217, 1), "LeftLowerLeg": (1, 1.193, 1), "LeftFoot": (1, 0.3, 1),
}

# (motor name, part0, part1, C0 position in part0, C1 position in part1) - hierarchy order
JOINTS = [
    ("Root", "HumanoidRootPart", "LowerTorso", (0, -1, 0), (0, -0.2, 0)),
    ("Waist", "LowerTorso", "UpperTorso", (0, 0.2, 0), (0, -0.8, 0)),
    ("Neck", "UpperTorso", "Head", (0, 0.8, 0), (0, -0.5, 0)),
    ("RightShoulder", "UpperTorso", "RightUpperArm", (1, 0.563, 0), (-0.5, 0.42, 0)),
    ("RightElbow", "RightUpperArm", "RightLowerArm", (0, -0.334, 0), (0, 0.261, 0)),
    ("RightWrist", "RightLowerArm", "RightHand", (0, -0.501, 0), (0, 0.125, 0)),
    ("LeftShoulder", "UpperTorso", "LeftUpperArm", (-1, 0.563, 0), (0.5, 0.42, 0)),
    ("LeftElbow", "LeftUpperArm", "LeftLowerArm", (0, -0.334, 0), (0, 0.261, 0)),
    ("LeftWrist", "LeftLowerArm", "LeftHand", (0, -0.501, 0), (0, 0.125, 0)),
    ("RightHip", "LowerTorso", "RightUpperLeg", (0.5, -0.2, 0), (0, 0.42, 0)),
    ("RightKnee", "RightUpperLeg", "RightLowerLeg", (0, -0.409, 0), (0, 0.4, 0)),
    ("RightAnkle", "RightLowerLeg", "RightFoot", (0, -0.548, 0), (0, 0.1, 0)),
    ("LeftHip", "LowerTorso", "LeftUpperLeg", (-0.5, -0.2, 0), (0, 0.42, 0)),
    ("LeftKnee", "LeftUpperLeg", "LeftLowerLeg", (0, -0.409, 0), (0, 0.4, 0)),
    ("LeftAnkle", "LeftLowerLeg", "LeftFoot", (0, -0.548, 0), (0, 0.1, 0)),
]
JOINT_BY_PART = {j[2]: j for j in JOINTS}
PARENT = {j[2]: j[1] for j in JOINTS}
ANIMATED_PARTS = [j[2] for j in JOINTS]
HRP_REST = T(0, 3.0, 0)

# katana grip offset inside the RightHand part (blade along hand -Z, edge along hand -Y)
GRIP_IN_HAND = np.array([0.0, -0.1, 0.0])
KATANA_IN_HAND = T(0, -0.1, 0)
# sheath (saya) frame inside LowerTorso: mouth at the left hip, pointing back/down, edge up
_saya_dir = norm((-0.12, -0.42, 0.9))
_saya_up = norm(np.array((0.0, -1.0, 0.0)) - np.dot((0.0, -1.0, 0.0), _saya_dir) * _saya_dir)
SAYA_IN_LOWERTORSO = M4(np.column_stack([np.cross(_saya_up, -_saya_dir), _saya_up, -_saya_dir]),
                        (-1.08, 0.05, -0.42))


def fk(transforms=None, hrp=HRP_REST):
    transforms = transforms or {}
    world = {"HumanoidRootPart": hrp}
    for _, p0, p1, c0, c1 in JOINTS:
        tr = transforms.get(p1, np.eye(4))
        world[p1] = world[p0] @ T(*c0) @ tr @ inv(T(*c1))
    return world


REST = fk()


def joint_pivot_rest(part1):
    _, p0, _, c0, _ = JOINT_BY_PART[part1]
    return (REST[p0] @ T(*c0))[:3, 3]


# -------------------------------------------------------------------- IK

def _two_bone_angle(u0, f0, d, hinge_sign):
    """Hinge (about local X) angle so that |u0 + Rx(a) f0| = d. Returns (angle, reached)."""
    a2 = float(np.dot(u0, u0) + np.dot(f0, f0))
    k = 2 * float(u0[1] * f0[1] + u0[2] * f0[2])  # u0 . Rx(a) f0 at a = 0
    # general: u0 . Rx(a) f0 = (u0y f0y + u0z f0z) cos a + (u0z f0y - u0y f0z) sin a ; f0z = 0, u0z = 0 here
    c = (d * d - a2) / k
    reached = -1.0 <= c <= 1.0
    c = max(-1.0, min(1.0, c))
    return hinge_sign * math.acos(c), reached


def swing_twist_y(r3):
    """Split a rotation into swing (bend of the local Y axis) and twist (about Y). Degrees."""
    y = r3 @ np.array([0.0, 1.0, 0.0])
    swing = math.degrees(math.acos(max(-1.0, min(1.0, y[1]))))
    sw = rot_between([0, 1, 0], y)
    tw = sw.T @ r3
    twist = math.degrees(math.atan2(tw[0, 2], tw[0, 0]))
    return swing, twist


def solve_arm(side, world, grip_w, blade_w=None, edge_hint=None, pole_w=None, edge_weight=0.6,
              pole_weight=0.5, roll_steps=48, twist_steps=96):
    """Sword/free arm IK.
    grip_w : world position of the grip point (centre of the fist)
    blade_w: desired direction of the hand's -Z axis (the katana blade). None = free hand.
    edge_hint: preferred direction of the hand's -Y axis (cutting edge); solver may roll the
               hand around the blade to keep the wrist natural.
    Returns ({UpperArm, LowerArm, Hand: 4x4 Transforms}, info)."""
    pre = "Right" if side == "R" else "Left"
    _, _, _, sh_c0, sh_c1 = JOINT_BY_PART[pre + "UpperArm"]
    _, _, _, el_c0, el_c1 = JOINT_BY_PART[pre + "LowerArm"]
    _, _, _, wr_c0, wr_c1 = JOINT_BY_PART[pre + "Hand"]
    ut = world["UpperTorso"]
    R_ut = ut[:3, :3]
    S = (ut @ T(*sh_c0))[:3, 3]
    u0 = np.array(el_c0, float) - np.array(sh_c1, float)
    f0 = np.array(wr_c0, float) - np.array(el_c1, float)
    off = np.array(wr_c1, float) - GRIP_IN_HAND           # grip -> wrist pivot, hand space
    max_reach = float(np.linalg.norm(u0 + f0)) * 0.995
    G = np.asarray(grip_w, float)
    pole_ut = R_ut.T @ np.asarray(pole_w if pole_w is not None else (0.6 if side == "R" else -0.6, -0.6, 0.5), float)

    candidates = []
    if blade_w is None:
        candidates.append(None)
    else:
        b = norm(blade_w)
        ref = np.array([0.0, 1.0, 0.0]) if abs(b[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
        p1 = norm(np.cross(b, ref))
        p2 = np.cross(b, p1)
        for k in range(roll_steps):
            a = 2 * math.pi * k / roll_steps
            e = math.cos(a) * p1 + math.sin(a) * p2
            candidates.append(frame_from(b, e))

    best = None
    for R_hand in candidates:
        if R_hand is None:
            W = G + R_ut @ np.array([0.0, 0.225, 0.0])
        else:
            W = G + R_hand @ off
        t_ut = R_ut.T @ (W - S)
        d = float(np.linalg.norm(t_ut))
        reached = d <= max_reach
        if not reached:
            t_ut = t_ut / d * max_reach
            d = max_reach
        theta, _ = _two_bone_angle(u0, f0, d, +1.0)
        R_e = R3x(theta)
        w_loc = u0 + R_e @ f0
        axis = norm(t_ut)
        R_align = rot_between(w_loc, t_ut)
        for k in range(twist_steps):
            psi = 2 * math.pi * k / twist_steps
            R_s = axis_angle3(axis, psi) @ R_align
            elbow = R_s @ u0
            ev = elbow - np.dot(elbow, axis) * axis
            pv = pole_ut - np.dot(pole_ut, axis) * axis
            cost = pole_weight * math.radians(math.degrees(angle_between(ev, pv)))
            if R_hand is None:
                R_w = np.eye(3)
            else:
                R_w = (R_ut @ R_s @ R_e).T @ R_hand
                swing, twist = swing_twist_y(R_w)
                cost += math.radians(swing + 2.5 * max(0.0, swing - 55.0) + 0.35 * abs(twist))
                if edge_hint is not None:
                    cost += edge_weight * angle_between(-R_hand[:, 1], np.asarray(edge_hint, float))
            if best is None or cost < best[0]:
                best = (cost, R_s, R_e, R_w, reached, d)
    _, R_s, R_e, R_w, reached, d = best
    out = {pre + "UpperArm": M4(R_s), pre + "LowerArm": M4(R_e), pre + "Hand": M4(R_w)}
    swing, twist = swing_twist_y(R_w)
    info = {"reached": reached, "dist": d, "wrist_swing": swing, "wrist_twist": twist}
    return out, info


def solve_leg(side, world, ankle_w, foot_yaw=0.0, foot_pitch=0.0, pole_w=None):
    pre = "Right" if side == "R" else "Left"
    _, _, _, hp_c0, hp_c1 = JOINT_BY_PART[pre + "UpperLeg"]
    _, _, _, kn_c0, kn_c1 = JOINT_BY_PART[pre + "LowerLeg"]
    _, _, _, an_c0, an_c1 = JOINT_BY_PART[pre + "Foot"]
    lt = world["LowerTorso"]
    R_lt = lt[:3, :3]
    H = (lt @ T(*hp_c0))[:3, 3]
    u0 = np.array(kn_c0, float) - np.array(hp_c1, float)
    f0 = np.array(an_c0, float) - np.array(kn_c1, float)
    t_lt = R_lt.T @ (np.asarray(ankle_w, float) - H)
    d = float(np.linalg.norm(t_lt))
    phi, reached = _two_bone_angle(u0, f0, d, -1.0)
    R_k = R3x(phi)
    w_loc = u0 + R_k @ f0
    axis = norm(t_lt)
    R_align = rot_between(w_loc, t_lt)
    R_foot = R3y(math.radians(foot_yaw)) @ R3x(math.radians(foot_pitch))
    if pole_w is None:
        pole_w = R3y(math.radians(foot_yaw)) @ np.array([0.0, 0.0, -1.0])
    pole_lt = R_lt.T @ np.asarray(pole_w, float)
    best = None
    for k in range(240):
        psi = 2 * math.pi * k / 240
        R_h = axis_angle3(axis, psi) @ R_align
        knee_dir = R_h @ R3x(0) @ np.array([0.0, 0.0, -1.0])  # knee cap faces local -Z
        kv = knee_dir - np.dot(knee_dir, axis) * axis
        pv = pole_lt - np.dot(pole_lt, axis) * axis
        R_a = (R_lt @ R_h @ R_k).T @ R_foot
        cost = angle_between(kv, pv) + 0.15 * rot_angle(R_a)
        if best is None or cost < best[0]:
            best = (cost, R_h, R_a)
    _, R_h, R_a = best
    out = {pre + "UpperLeg": M4(R_h), pre + "LowerLeg": M4(R_k), pre + "Foot": M4(R_a)}
    return out, {"reached": reached, "dist": d}


# --------------------------------------------------------------- pose specs

def build_pose(spec, name="?"):
    """spec keys (all optional):
      root: (dx, dy, dz, rx, ry, rz)         LowerTorso Transform (offset studs + Euler deg)
      waist / neck: (rx, ry, rz)
      r_arm / l_arm: dict(hand=(x,y,z), blade=(..), edge=(..), pole=(..), space='torso'|'world')
                     or dict(fk=((rx,ry,rz) shoulder, (..) elbow, (..) wrist))
      r_leg / l_leg: dict(foot=(x, y, z) world ankle pos, yaw=deg, pitch=deg, pole=(..))
                     or dict(fk=(hip, knee, ankle))
    Returns {part1: 4x4 Transform}, warnings."""
    tr = {}
    warns = []
    r = spec.get("root", (0, 0, 0, 0, 0, 0))
    tr["LowerTorso"] = T(r[0], r[1], r[2]) @ M4(euler3(r[3], r[4], r[5]))
    tr["UpperTorso"] = M4(euler3(*spec.get("waist", (0, 0, 0))))
    tr["Head"] = M4(euler3(*spec.get("neck", (0, 0, 0))))
    world = fk(tr)

    for side, key in (("R", "r_arm"), ("L", "l_arm")):
        pre = "Right" if side == "R" else "Left"
        arm = spec.get(key)
        if arm is None:
            arm = {"fk": ((0, 0, 0), (0, 0, 0), (0, 0, 0))}
        if "fk" in arm:
            s, e, w = arm["fk"]
            tr[pre + "UpperArm"] = M4(euler3(*s))
            tr[pre + "LowerArm"] = M4(euler3(*e))
            tr[pre + "Hand"] = M4(euler3(*w))
            continue
        ut = world["UpperTorso"]
        R_ut = ut[:3, :3]
        torso = arm.get("space", "torso") == "torso"

        dirs_world = arm.get("dir_space", "torso") == "world"

        def to_w(v, is_point=False):
            if v is None:
                return None
            v = np.asarray(v, float)
            if not torso or (dirs_world and not is_point):
                return v
            return (ut @ np.array([*v, 1.0]))[:3] if is_point else R_ut @ v

        default_pole = (0.6 if side == "R" else -0.6, -0.6, 0.5)
        out, info = solve_arm(side, world, to_w(arm["hand"], True), to_w(arm.get("blade")),
                              to_w(arm.get("edge")), to_w(arm.get("pole", default_pole)),
                              edge_weight=arm.get("edge_weight", 0.6), pole_weight=arm.get("pole_weight", 0.5))
        if not info["reached"]:
            warns.append(f"{name}: {key} target out of reach (d={info['dist']:.2f})")
        if info["wrist_swing"] > 75:
            warns.append(f"{name}: {key} wrist bend {info['wrist_swing']:.0f} deg")
        tr.update(out)

    for side, key in (("R", "r_leg"), ("L", "l_leg")):
        pre = "Right" if side == "R" else "Left"
        leg = spec.get(key)
        if leg is None:
            rest_ankle = joint_pivot_rest(pre + "Foot")
            leg = {"foot": tuple(rest_ankle)}
        if "fk" in leg:
            h, k, a = leg["fk"]
            tr[pre + "UpperLeg"] = M4(euler3(*h))
            tr[pre + "LowerLeg"] = M4(euler3(*k))
            tr[pre + "Foot"] = M4(euler3(*a))
            continue
        out, info = solve_leg(side, world, leg["foot"], leg.get("yaw", 0.0), leg.get("pitch", 0.0), leg.get("pole"))
        if not info["reached"]:
            warns.append(f"{name}: {key} foot out of reach (d={info['dist']:.2f})")
        tr.update(out)
    return tr, warns


def grip_world(transforms):
    """World matrix of the katana frame (for previews / sanity checks)."""
    w = fk(transforms)
    return w["RightHand"] @ KATANA_IN_HAND

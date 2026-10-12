"""
Yami Skills - animation definitions (Black Clover / Yami Sukehiro moveset).

Every animation is a list of keys: (time_seconds, pose_spec, ease_of_next_segment).
pose_spec format: see anim_core.build_pose. Sword arm targets are in UPPER TORSO space
(origin = UpperTorso centre, X right, Y up, -Z forward) so body twists carry the sword.
blade = direction the blade points, edge = direction the cutting edge faces.

Easing names (segment that STARTS at the key):
  'smooth' bezier ease in/out, 'linear', 'in' (accelerate), 'out' (decelerate),
  'snap' (very fast start, long settle), 'hold' (stay until next key, smooth).

Markers: {'Name': time} -> KeyframeMarkers in the exported KeyframeSequence.
Joint masks: 'parts' limits which joints the animation drives (others are left to walk/idle).
"""
from copy import deepcopy

# ----------------------------------------------------------------- building blocks

ARM_PARTS = ["RightUpperArm", "RightLowerArm", "RightHand"]
UPPER_PARTS = ["UpperTorso", "Head", "RightUpperArm", "RightLowerArm", "RightHand",
               "LeftUpperArm", "LeftLowerArm", "LeftHand"]

LEGS_NEUTRAL = {"r_leg": {"foot": (0.5, 0.223, 0.0)}, "l_leg": {"foot": (-0.5, 0.223, 0.0)}}

R_HOLD = {"hand": (1.45, -1.0, -0.4), "blade": (0.05, -0.3, -0.95), "edge": (0, -1, 0)}
R_READY = {"hand": (1.1, -0.45, -0.95), "blade": (0.1, 0.6, -0.79), "edge": (0, -0.6, -0.8)}
L_REST = {"fk": ((0, 0, -4), (6, 0, 0), (0, 0, 0))}
L_READY = {"hand": (-1.2, -0.75, -0.45), "blade": (0, -0.3, -0.95), "edge": (0, -1, 0), "wrist_weight": 0.6}


def pose(**kw):
    p = {"root": (0, 0, 0, 0, 0, 0), "waist": (0, 0, 0), "neck": (0, 0, 0),
         "r_arm": dict(R_HOLD), "l_arm": dict(L_REST)}
    p.update(deepcopy(LEGS_NEUTRAL))
    p.update(deepcopy(kw))
    return p


def ready(**kw):
    p = pose(root=(0, -0.2, 0, 0, -12, 0), waist=(-2, 8, 0), neck=(0, 4, 0),
             r_arm=dict(R_READY), l_arm=dict(L_READY),
             r_leg={"foot": (0.72, 0.223, 0.42), "yaw": -20},
             l_leg={"foot": (-0.5, 0.223, -0.45), "yaw": 5})
    p.update(deepcopy(kw))
    return p


def neutral(**kw):
    return pose(**kw)


def with_(base, **kw):
    p = deepcopy(base)
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(p.get(k), dict) and not v.get("_replace"):
            p[k].update(v)
        else:
            p[k] = v
    return p


# ======================================================================= HOLD
HOLD = {
    "name": "Hold", "priority": "Idle", "loop": True, "parts": ARM_PARTS,
    "keys": [
        (0.0, pose(), "smooth"),
        (1.0, pose(r_arm=dict(R_HOLD, hand=(1.45, -1.04, -0.38), blade=(0.05, -0.36, -0.93))), "smooth"),
        (2.0, pose(), "smooth"),
    ],
    "markers": {},
}

# ====================================================================== EQUIP
# right hand crosses to the left hip, grabs the handle (katana jumps from saya to hand),
# draws it forward with a flourish and settles into the hold.
EQUIP = {
    "name": "Equip", "priority": "Action", "loop": False, "parts": UPPER_PARTS,
    "keys": [
        (0.0, pose(), "smooth"),
        (0.14, pose(waist=(-10, 22, 0), neck=(6, -10, 0),
                    r_arm={"hand": (-0.5, -0.95, -0.62), "blade": (-0.12, -0.42, 0.9), "edge": (0, 1, 0),
                           "pole": (1, -0.2, -0.2)},
                    l_arm={"hand": (-1.15, -1.05, -0.3), "blade": (0.2, -0.3, 0.93), "edge": (0, -1, 0),
                           "wrist_weight": 0.5}), "out"),
        (0.3, pose(waist=(-4, -14, 0), neck=(0, 8, 0),
                   r_arm={"hand": (1.25, 0.05, -1.05), "blade": (0.62, 0.3, -0.72), "edge": (0, -1, 0.2)},
                   l_arm=dict(L_REST)), "smooth"),
        (0.5, pose(), "smooth"),
    ],
    "markers": {"Grab": 0.14},
}

# ======================================================================= M1s
M1_1 = {  # diagonal down-left slash
    "name": "M1_1", "priority": "Action", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "in"),
        (0.09, ready(root=(0, -0.22, 0.05, 0, -24, 0), waist=(4, -20, 0), neck=(0, 18, 0),
                     r_arm={"hand": (1.15, 0.85, -0.35), "blade": (0.3, 0.75, 0.6), "edge": (0, 0.6, -0.8),
                            "pole": (1, 0.2, 0.3)}), "linear"),
        (0.14, ready(root=(0, -0.3, -0.1, -4, -4, 0), waist=(-4, 4, 0),
                     r_arm={"hand": (0.65, 0.25, -1.45), "blade": (-0.25, 0.45, -0.86), "edge": (-0.5, -0.5, -0.4),
                            "pole": (1, -0.3, 0.2)},
                     l_leg={"foot": (-0.55, 0.223, -0.75), "yaw": 5}), "out"),
        (0.2, ready(root=(0, -0.4, -0.2, -8, 18, 0), waist=(-10, 22, 0), neck=(0, -14, 0),
                    r_arm={"hand": (-0.45, -0.75, -1.05), "blade": (-0.6, -0.55, -0.58), "edge": (-0.4, -0.5, 0.4),
                           "pole": (0.8, 0.3, 0.4)},
                    l_arm={"hand": (-1.35, -0.55, 0.25), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)},
                    l_leg={"foot": (-0.6, 0.223, -0.8), "yaw": 10}), "smooth"),
        (0.32, ready(root=(0, -0.38, -0.2, -6, 20, 0), waist=(-8, 24, 0), neck=(0, -14, 0),
                     r_arm={"hand": (-0.55, -0.85, -0.95), "blade": (-0.65, -0.6, -0.45), "edge": (-0.3, -0.5, 0.5),
                            "pole": (0.8, 0.3, 0.4)},
                     l_arm={"hand": (-1.35, -0.6, 0.25), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)},
                     l_leg={"foot": (-0.6, 0.223, -0.8), "yaw": 10}), "smooth"),
        (0.5, neutral(), "smooth"),
    ],
    "markers": {"Hit": 0.15},
}

M1_2 = {  # horizontal backhand left -> right
    "name": "M1_2", "priority": "Action", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "in"),
        (0.09, ready(root=(0, -0.25, 0, 0, 22, 0), waist=(-2, 26, 0), neck=(0, -22, 0),
                     r_arm={"hand": (-0.55, -0.15, -0.85), "blade": (-0.8, 0.1, 0.6), "edge": (0.3, 0, -0.9),
                            "pole": (0.6, -0.5, -0.6)}), "linear"),
        (0.145, ready(root=(0, -0.3, -0.1, -3, 0, 0), waist=(-4, 0, 0),
                      r_arm={"hand": (0.55, -0.05, -1.5), "blade": (0.1, 0.05, -0.99), "edge": (1, 0, 0.1),
                             "pole": (1, -0.4, 0)}), "out"),
        (0.2, ready(root=(0, -0.32, -0.15, -4, -24, 0), waist=(-6, -26, 0), neck=(0, 20, 0),
                    r_arm={"hand": (1.6, -0.1, -0.55), "blade": (0.85, 0.05, 0.5), "edge": (-0.4, 0, 0.9),
                           "pole": (0.2, -0.8, 0.6)},
                    l_arm={"hand": (-1.0, -0.4, -0.9), "blade": (0.2, -0.2, -0.95), "edge": (0, -1, 0)},
                    r_leg={"foot": (0.8, 0.223, 0.45), "yaw": -30}), "smooth"),
        (0.32, ready(root=(0, -0.3, -0.15, -3, -28, 0), waist=(-5, -28, 0), neck=(0, 22, 0),
                     r_arm={"hand": (1.65, -0.2, -0.35), "blade": (0.8, -0.05, 0.6), "edge": (-0.5, 0, 0.8),
                            "pole": (0.2, -0.8, 0.6)},
                     l_arm={"hand": (-1.0, -0.45, -0.85), "blade": (0.2, -0.2, -0.95), "edge": (0, -1, 0)},
                     r_leg={"foot": (0.8, 0.223, 0.45), "yaw": -30}), "smooth"),
        (0.5, neutral(), "smooth"),
    ],
    "markers": {"Hit": 0.15},
}

M1_3 = {  # rising slash low-left -> high-right
    "name": "M1_3", "priority": "Action", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "in"),
        (0.09, ready(root=(0, -0.45, 0, -6, 18, 0), waist=(-10, 18, 0), neck=(4, -10, 0),
                     r_arm={"hand": (-0.25, -0.95, -0.85), "blade": (-0.55, -0.6, -0.58), "edge": (0.4, 0.6, -0.5),
                            "pole": (0.9, -0.2, 0.3)}), "linear"),
        (0.145, ready(root=(0, -0.3, -0.1, -2, 0, 0), waist=(-2, 0, 0),
                      r_arm={"hand": (0.6, -0.1, -1.5), "blade": (0.0, 0.1, -1.0), "edge": (0.3, 0.95, 0),
                             "pole": (1, -0.5, 0.2)}), "out"),
        (0.2, ready(root=(0, -0.05, -0.1, 4, -20, 0), waist=(8, -20, 0), neck=(-8, 16, 0),
                    r_arm={"hand": (1.3, 0.95, -0.65), "blade": (0.45, 0.75, 0.48), "edge": (0.2, 0.4, -0.9),
                           "pole": (1, -0.3, 0.3)},
                    l_arm={"hand": (-1.2, -0.7, 0.1), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)}), "smooth"),
        (0.32, ready(root=(0, -0.08, -0.1, 3, -22, 0), waist=(7, -22, 0), neck=(-8, 16, 0),
                     r_arm={"hand": (1.35, 1.0, -0.55), "blade": (0.5, 0.78, 0.38), "edge": (0.2, 0.35, -0.9),
                            "pole": (1, -0.3, 0.3)},
                     l_arm={"hand": (-1.2, -0.7, 0.1), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)}), "smooth"),
        (0.5, neutral(), "smooth"),
    ],
    "markers": {"Hit": 0.15},
}

M1_4 = {  # jumping overhead slam (finisher)
    "name": "M1_4", "priority": "Action", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "in"),
        (0.13, ready(root=(0, 0.05, 0.15, 10, -8, 0), waist=(14, 4, 0), neck=(-12, 0, 0),
                     r_arm={"hand": (0.35, 1.45, 0.05), "blade": (0.0, 0.4, 0.92), "edge": (0, 0.92, -0.4),
                            "pole": (1, 0.3, 0)},
                     l_arm={"hand": (0.1, 1.3, 0.15), "blade": (0, 0.4, 0.92), "edge": (0, 0.9, -0.4),
                            "pole": (-1, 0.3, 0)},
                     r_leg={"foot": (0.7, 0.223, 0.55), "yaw": -15, "pitch": -15},
                     l_leg={"foot": (-0.45, 0.223, -0.6), "yaw": 0}), "in"),
        (0.19, ready(root=(0, -0.35, -0.3, -12, -4, 0), waist=(-8, 0, 0), neck=(4, 0, 0),
                     r_arm={"hand": (0.35, 0.95, -1.2), "blade": (0.0, 0.5, -0.87), "edge": (0, -0.87, -0.5),
                            "pole": (1, -0.2, 0.2)},
                     l_arm={"hand": (0.15, 0.85, -1.05), "blade": (0, 0.5, -0.87), "edge": (0, -0.87, -0.5),
                            "pole": (-1, -0.2, 0.2)},
                     l_leg={"foot": (-0.55, 0.223, -1.0), "yaw": 0}), "out"),
        (0.25, ready(root=(0, -0.75, -0.5, -22, 0, 0), waist=(-20, 0, 0), neck=(14, 0, 0),
                     r_arm={"hand": (0.35, -0.45, -1.45), "blade": (0.0, -0.5, -0.87), "edge": (0, -0.87, 0.5),
                            "dir_space": "world", "pole": (1, -0.2, 0.4)},
                     l_arm={"hand": (0.12, -0.35, -1.3), "blade": (0, -0.5, -0.87), "edge": (0, -0.87, 0.5),
                            "dir_space": "world", "pole": (-1, -0.2, 0.4)},
                     r_leg={"foot": (0.75, 0.223, 0.85), "yaw": -10, "pitch": -25},
                     l_leg={"foot": (-0.55, 0.223, -1.05), "yaw": 0}), "smooth"),
        (0.45, ready(root=(0, -0.7, -0.5, -20, 0, 0), waist=(-18, 0, 0), neck=(12, 0, 0),
                     r_arm={"hand": (0.35, -0.5, -1.4), "blade": (0.0, -0.55, -0.83), "edge": (0, -0.83, 0.55),
                            "dir_space": "world", "pole": (1, -0.2, 0.4)},
                     l_arm={"hand": (0.12, -0.4, -1.25), "blade": (0, -0.55, -0.83), "edge": (0, -0.83, 0.55),
                            "dir_space": "world", "pole": (-1, -0.2, 0.4)},
                     r_leg={"foot": (0.75, 0.223, 0.85), "yaw": -10, "pitch": -25},
                     l_leg={"foot": (-0.55, 0.223, -1.05), "yaw": 0}), "smooth"),
        (0.7, neutral(), "smooth"),
    ],
    "markers": {"Hit": 0.25},
}

# ================================================================ BLACK MOON (Z)
BLACK_MOON = {
    "name": "BlackMoon", "priority": "Action2", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "smooth"),
        (0.28, ready(root=(0, -0.45, 0.1, 0, -32, 0), waist=(-4, -34, 0), neck=(0, 40, 0),
                     r_arm={"hand": (1.45, -0.35, 0.55), "blade": (0.62, 0.1, 0.78), "edge": (0.8, 0, -0.6),
                            "dir_space": "world", "pole": (0.5, -0.8, 0.4)},
                     l_arm={"hand": (-0.9, 0.25, -1.35), "blade": (0.1, 0.9, -0.3), "edge": (1, 0, 0),
                            "wrist_weight": 0.5},
                     r_leg={"foot": (1.0, 0.223, 0.75), "yaw": -40},
                     l_leg={"foot": (-0.75, 0.223, -0.75), "yaw": -10}), "in"),
        (0.34, ready(root=(0, -0.5, -0.05, -4, -6, 0), waist=(-6, -4, 0), neck=(0, 10, 0),
                     r_arm={"hand": (1.05, -0.1, -1.45), "blade": (0.55, 0.05, -0.83), "edge": (-0.8, 0, -0.55),
                            "dir_space": "world", "pole": (1, -0.4, 0.2)},
                     l_arm={"hand": (-1.2, -0.2, -0.6), "blade": (0, -0.3, -0.95), "edge": (0, -1, 0)},
                     r_leg={"foot": (1.0, 0.223, 0.75), "yaw": -40},
                     l_leg={"foot": (-0.8, 0.223, -0.85), "yaw": -5}), "out"),
        (0.41, ready(root=(0, -0.5, -0.2, -6, 30, 0), waist=(-6, 32, 0), neck=(0, -30, 0),
                     r_arm={"hand": (-0.75, -0.05, -1.15), "blade": (-0.9, 0.05, -0.42), "edge": (-0.4, 0, 0.9),
                            "dir_space": "world", "pole": (0.9, -0.3, 0.3)},
                     l_arm={"hand": (-1.35, -0.45, 0.45), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)},
                     r_leg={"foot": (0.85, 0.223, 0.55), "yaw": -30, "pitch": -10},
                     l_leg={"foot": (-0.8, 0.223, -0.9), "yaw": 15}), "smooth"),
        (0.6, ready(root=(0, -0.48, -0.2, -5, 38, 0), waist=(-5, 36, 0), neck=(0, -34, 0),
                    r_arm={"hand": (-1.05, -0.25, -0.35), "blade": (-0.85, -0.1, 0.5), "edge": (0.4, 0, 0.9),
                           "dir_space": "world", "pole": (0.9, -0.3, 0.3)},
                    l_arm={"hand": (-1.35, -0.5, 0.45), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)},
                    r_leg={"foot": (0.85, 0.223, 0.55), "yaw": -30, "pitch": -10},
                    l_leg={"foot": (-0.8, 0.223, -0.9), "yaw": 15}), "smooth"),
        (0.85, neutral(), "smooth"),
    ],
    "markers": {"Release": 0.37},
}

# =============================================================== DEATH THRUST (X)
_THRUST_POSE = dict(root=(0, -0.62, -0.45, -16, 12, 0), waist=(-6, 8, 0), neck=(14, -14, 0),
                    r_arm={"hand": (0.55, 0.25, -1.75), "blade": (0.0, 0.04, -1.0), "edge": (0.4, -0.9, 0),
                           "dir_space": "world", "pole": (1, -0.2, 0.3)},
                    l_arm={"hand": (-1.25, -0.75, 0.75), "blade": (0, -0.4, 0.9), "edge": (0, -1, 0)},
                    r_leg={"foot": (0.75, 0.223, 0.65), "yaw": -25, "pitch": -30},
                    l_leg={"foot": (-0.6, 0.223, -1.25), "yaw": 5})
DEATH_THRUST = {
    "name": "DeathThrust", "priority": "Action2", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "smooth"),
        (0.22, ready(root=(0, -0.5, 0.2, -4, -24, 0), waist=(-2, -10, 0), neck=(4, 30, 0),
                     r_arm={"hand": (1.35, -0.55, 0.55), "blade": (0.05, 0.05, -1.0), "edge": (0.4, -0.9, 0),
                            "dir_space": "world", "pole": (0.6, -0.4, 0.8)},
                     l_arm={"hand": (-0.75, 0.05, -1.4), "blade": (0.2, 0.7, -0.7), "edge": (1, 0, 0),
                            "wrist_weight": 0.5},
                     r_leg={"foot": (0.85, 0.223, 0.65), "yaw": -35},
                     l_leg={"foot": (-0.6, 0.223, -0.85), "yaw": 0}), "snap"),
        (0.3, ready(**_THRUST_POSE), "smooth"),
        (0.52, ready(**dict(_THRUST_POSE, root=(0, -0.6, -0.42, -14, 12, 0))), "smooth"),
        (0.8, neutral(), "smooth"),
    ],
    "markers": {"Dash": 0.24},
}

# =============================================================== BLACK COCOON (C)
_COCOON_HOLD = dict(root=(0, -0.55, 0.05, 6, 0, 0), waist=(-16, 0, 0), neck=(18, 0, 0),
                    r_arm={"hand": (0.45, -0.35, -1.0), "blade": (0.0, 1.0, -0.08), "edge": (0, 0, -1),
                           "pole": (1, -0.6, 0.2)},
                    l_arm={"hand": (-0.2, -0.25, -1.05), "blade": (0.6, 0.6, -0.5), "edge": (1, -0.3, 0),
                           "wrist_weight": 0.5},
                    r_leg={"foot": (0.75, 0.223, 0.2), "yaw": -10},
                    l_leg={"foot": (-0.75, 0.223, -0.2), "yaw": 10})
BLACK_COCOON = {
    "name": "BlackCocoon", "priority": "Action2", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "smooth"),
        (0.25, pose(**_COCOON_HOLD), "smooth"),
        (1.2, pose(**dict(_COCOON_HOLD, root=(0, -0.6, 0.05, 7, 0, 0), waist=(-18, 0, 0))), "smooth"),
        (2.2, pose(**dict(_COCOON_HOLD, root=(0, -0.66, 0.05, 8, 0, 0), waist=(-21, 0, 0))), "linear"),
        (2.27, pose(**dict(_COCOON_HOLD, root=(0, -0.68, 0.05, 8, 2, 0), waist=(-22, 2, 1))), "linear"),
        (2.34, pose(**dict(_COCOON_HOLD, root=(0, -0.7, 0.05, 8, -2, 0), waist=(-23, -2, -1))), "snap"),
        (2.45, pose(root=(0, -0.15, 0, -4, 0, 0), waist=(14, 0, 0), neck=(-14, 0, 0),
                    r_arm={"hand": (1.85, 0.35, -0.55), "blade": (0.8, 0.5, -0.33), "edge": (0.3, 0.2, 0.9),
                           "pole": (0.5, -0.8, 0.4)},
                    l_arm={"hand": (-1.85, 0.35, -0.55), "blade": (-0.3, 0.9, -0.3), "edge": (0, 0, 1),
                           "wrist_weight": 0.4},
                    r_leg={"foot": (0.9, 0.223, 0.25), "yaw": -15},
                    l_leg={"foot": (-0.9, 0.223, -0.25), "yaw": 15}), "smooth"),
        (2.85, pose(root=(0, -0.2, 0, -3, 0, 0), waist=(10, 0, 0), neck=(-10, 0, 0),
                    r_arm={"hand": (1.8, 0.2, -0.6), "blade": (0.8, 0.45, -0.38), "edge": (0.3, 0.2, 0.9),
                           "pole": (0.5, -0.8, 0.4)},
                    l_arm={"hand": (-1.8, 0.2, -0.6), "blade": (-0.3, 0.9, -0.3), "edge": (0, 0, 1),
                           "wrist_weight": 0.4},
                    r_leg={"foot": (0.9, 0.223, 0.25), "yaw": -15},
                    l_leg={"foot": (-0.9, 0.223, -0.25), "yaw": 15}), "smooth"),
        (3.2, neutral(), "smooth"),
    ],
    "markers": {"Shell": 0.2, "Burst": 2.45},
}

# ============================================================ DIMENSION SLASH (V)
# Iai stance: body turned right, katana low at the right hip pointing back (world space),
# left hand aimed at the target. Then one explosive right->left horizontal cut that ends
# with the blade fully extended to the left and the body twisted - the "cut through space".
_IAI = dict(root=(0, -0.8, 0.2, 4, -40, 0), waist=(-8, -16, 0), neck=(6, 50, 0),
            r_arm={"hand": (1.25, -0.8, 0.55), "blade": (0.35, -0.38, 0.86), "edge": (0, -1, 0),
                   "dir_space": "world", "pole": (0.6, -0.5, 0.6)},
            l_arm={"hand": (-0.9, 0.15, -1.4), "blade": (0.1, 0.8, -0.6), "edge": (1, 0, 0), "dir_space": "world"},
            r_leg={"foot": (1.0, 0.223, 0.8), "yaw": -55},
            l_leg={"foot": (-0.9, 0.223, -1.0), "yaw": -20})


def _iai(dy=0.0, ry=0.0, wx=0.0, hand_dz=0.0):
    p = deepcopy(_IAI)
    r = list(p["root"])
    r[1] += dy
    r[4] += ry
    p["root"] = tuple(r)
    w = list(p["waist"])
    w[0] += wx
    p["waist"] = tuple(w)
    h = list(p["r_arm"]["hand"])
    h[2] += hand_dz
    p["r_arm"]["hand"] = tuple(h)
    return ready(**p)


_DS_MID = dict(root=(0, -0.7, -0.15, -4, -4, 0), waist=(-6, -4, 0), neck=(0, 8, 0),
               r_arm={"hand": (1.1, -0.05, -1.55), "blade": (0.6, 0.05, -0.8), "edge": (-0.8, 0.1, -0.6),
                      "dir_space": "world", "pole": (1, -0.4, 0.1)},
               l_arm={"hand": (-1.2, -0.25, -0.4), "blade": (0, -0.3, -0.95), "edge": (0, -1, 0)},
               r_leg={"foot": (0.95, 0.223, 0.7), "yaw": -40, "pitch": -10},
               l_leg={"foot": (-0.9, 0.223, -1.1), "yaw": -5})
_DS_END = dict(root=(0, -0.62, -0.4, -6, 40, 0), waist=(-4, 26, 0), neck=(2, -40, 0),
               r_arm={"hand": (-0.6, -0.05, -1.25), "blade": (-0.92, 0.1, 0.38), "edge": (-0.3, 0, 0.95),
                      "dir_space": "world", "pole": (0.9, -0.3, 0.4)},
               l_arm={"hand": (-1.35, -0.45, 0.5), "blade": (0, -0.3, 0.95), "edge": (0, -1, 0)},
               r_leg={"foot": (0.8, 0.223, 0.45), "yaw": -25, "pitch": -25},
               l_leg={"foot": (-0.9, 0.223, -1.15), "yaw": 20})
DIMENSION_SLASH = {
    "name": "DimensionSlash", "priority": "Action3", "loop": False, "parts": None,
    "keys": [
        (0.0, ready(), "smooth"),
        (0.25, _iai(), "smooth"),
        (0.45, _iai(dy=-0.02, ry=1.0, wx=-0.5), "smooth"),
        (0.65, _iai(dy=-0.03, ry=-0.5, wx=-1.0, hand_dz=0.03), "smooth"),
        (0.85, _iai(dy=-0.04, ry=1.2, wx=-1.5, hand_dz=0.05), "smooth"),
        (1.0, _iai(dy=-0.05, ry=-1.0, wx=-2.0, hand_dz=0.08), "linear"),
        (1.06, _iai(dy=-0.06, ry=1.5, wx=-2.0, hand_dz=0.1), "linear"),
        (1.11, _iai(dy=-0.07, ry=-3.0, wx=-2.5, hand_dz=0.12), "snap"),
        (1.16, ready(**_DS_MID), "out"),
        (1.22, ready(**_DS_END), "smooth"),
        (1.9, ready(**dict(_DS_END, root=(0, -0.64, -0.4, -6, 41, 0))), "smooth"),
        (2.7, neutral(), "smooth"),
    ],
    "markers": {"Charge": 0.25, "Slash": 1.18},
}

# ============================================================== BLACK BLADE (F)
BLACK_BLADE = {
    "name": "BlackBlade", "priority": "Action2", "loop": False, "parts": UPPER_PARTS,
    "keys": [
        (0.0, pose(), "smooth"),
        (0.3, pose(waist=(-4, -10, 0), neck=(6, 6, 0),
                   r_arm={"hand": (0.35, -0.15, -1.05), "blade": (0.0, 1.0, -0.06), "edge": (-1, 0, 0),
                          "pole": (1, -0.6, 0.1)},
                   l_arm={"hand": (0.12, 0.3, -1.15), "blade": (0.5, 0.5, -0.7), "edge": (0, -0.5, -0.5),
                          "wrist_weight": 0.4}), "smooth"),
        (0.55, pose(waist=(-6, -12, 0), neck=(2, 8, 0),
                    r_arm={"hand": (0.35, -0.15, -1.05), "blade": (0.0, 1.0, -0.06), "edge": (-1, 0, 0),
                           "pole": (1, -0.6, 0.1)},
                    l_arm={"hand": (0.12, 1.15, -1.1), "blade": (0.5, 0.6, -0.6), "edge": (0, -0.5, -0.5),
                           "wrist_weight": 0.4}), "snap"),
        (0.72, pose(waist=(-2, -16, 0), neck=(0, 10, 0),
                    r_arm={"hand": (1.55, -0.55, -0.6), "blade": (0.45, -0.6, -0.66), "edge": (0.6, -0.4, 0.6),
                           "pole": (0.6, -0.6, 0.6)},
                    l_arm=dict(L_REST)), "smooth"),
        (1.0, pose(), "smooth"),
    ],
    "markers": {"Coat": 0.5},
}

ALL = [HOLD, EQUIP, M1_1, M1_2, M1_3, M1_4, BLACK_MOON, DEATH_THRUST, BLACK_COCOON, DIMENSION_SLASH, BLACK_BLADE]

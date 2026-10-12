"""
Generates Roblox XML models (.rbxmx) for the demo place:
  DemoArena.rbxmx   - ground, stone plaza, pillars, unanchored crates (Workspace)
  DemoAtmosphere.rbxmx - Atmosphere for Lighting
Usage: python make_demo_arena.py <out_dir>
"""
import math
import os
import random
import sys
import xml.sax.saxutils as su

MATERIAL = {"Plastic": 256, "SmoothPlastic": 272, "Wood": 512, "WoodPlanks": 528, "Slate": 800, "Concrete": 816,
            "Granite": 832, "Cobblestone": 880, "Rock": 896, "Grass": 1280, "Ground": 1360, "Basalt": 788}

_ref = [0]


def ref():
    _ref[0] += 1
    return f"RBXDEMO{_ref[0]:06d}"


def f(x):
    return repr(round(float(x), 5))


def cframe(pos, yaw=0.0, pitch=0.0, roll=0.0):
    # R = Ry(yaw) * Rx(pitch) * Rz(roll)  (degrees)
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cx, sx = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cz, sz = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

    def mm(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    r = mm(mm(ry, rx), rz)
    inner = f"<X>{f(pos[0])}</X><Y>{f(pos[1])}</Y><Z>{f(pos[2])}</Z>"
    for i in range(3):
        for j in range(3):
            inner += f"<R{i}{j}>{f(r[i][j])}</R{i}{j}>"
    return f'<CoordinateFrame name="CFrame">{inner}</CoordinateFrame>'


def color(rgb):
    r, g, b = rgb
    return f'<Color3uint8 name="Color3uint8">{(0xFF << 24) | (r << 16) | (g << 8) | b}</Color3uint8>'


def part(name, size, pos, rgb, material="SmoothPlastic", anchored=True, cls="Part", yaw=0, pitch=0, roll=0, extra=""):
    return (f'<Item class="{cls}" referent="{ref()}"><Properties>'
            f'<string name="Name">{su.escape(name)}</string>'
            f'<bool name="Anchored">{"true" if anchored else "false"}</bool>'
            f'<Vector3 name="size"><X>{f(size[0])}</X><Y>{f(size[1])}</Y><Z>{f(size[2])}</Z></Vector3>'
            f'{cframe(pos, yaw, pitch, roll)}{color(rgb)}'
            f'<token name="Material">{MATERIAL[material]}</token>'
            f'<token name="TopSurface">0</token><token name="BottomSurface">0</token>'
            f'{extra}</Properties></Item>')


def model(name, children):
    return (f'<Item class="Model" referent="{ref()}"><Properties><string name="Name">{su.escape(name)}</string>'
            f'</Properties>{"".join(children)}</Item>')


def wrap(item):
    return ('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
            f'<External>null</External><External>nil</External>{item}</roblox>')


def arena():
    rnd = random.Random(7)
    items = []
    items.append(part("Ground", (1024, 16, 1024), (0, -8, 0), (86, 120, 62), "Grass"))
    items.append(part("StonePlaza", (120, 1, 120), (0, 0.5, 0), (122, 120, 116), "Slate"))
    items.append(part("DarkPath", (24, 1.04, 260), (0, 0.52, -150), (70, 66, 62), "Cobblestone"))
    items.append(part("SpawnLocation", (12, 1, 12), (0, 1.5, 40), (20, 20, 22), "Slate", cls="SpawnLocation",
                      extra='<int name="Duration">0</int><bool name="Neutral">true</bool>'))
    # ring of pillars (anchored) around the plaza
    for i in range(10):
        a = i / 10 * math.tau
        pos = (math.cos(a) * 54, 9, math.sin(a) * 54)
        items.append(part(f"Pillar{i + 1}", (4, 18, 4), pos, (96, 94, 90), "Rock", yaw=math.degrees(a)))
        items.append(part(f"PillarCap{i + 1}", (6, 1.5, 6), (pos[0], 18.6, pos[2]), (80, 78, 74), "Rock", yaw=math.degrees(a)))
    # unanchored crates to fling with skills
    crates = []
    for i in range(18):
        x = rnd.uniform(-30, 30)
        z = rnd.uniform(-70, -15)
        s = rnd.choice([3, 3, 4, 5])
        crates.append(part(f"Crate{i + 1}", (s, s, s), (x, 1 + s / 2, z), (152, 112, 66), "WoodPlanks", anchored=False,
                           yaw=rnd.uniform(0, 90)))
    # stacked wall of crates far away (for Black Moon / Dimension Slash)
    for row in range(3):
        for col in range(7):
            crates.append(part(f"WallCrate{row}_{col}", (4, 4, 4), (-14 + col * 4.2, 3 + row * 4.05, -95), (140, 104, 62),
                               "WoodPlanks", anchored=False))
    items.append(model("Crates", crates))
    # scattered boulders (anchored decor)
    for i in range(14):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(70, 140)
        s = rnd.uniform(5, 12)
        items.append(part(f"Boulder{i + 1}", (s, s * 0.7, s * 1.1), (math.cos(a) * r, s * 0.25, math.sin(a) * r),
                          (104, 101, 96), "Rock", yaw=rnd.uniform(0, 180), pitch=rnd.uniform(-10, 10)))
    return wrap(model("DemoArena", items))


def atmosphere():
    return wrap(f'<Item class="Atmosphere" referent="{ref()}"><Properties><string name="Name">Atmosphere</string>'
                '<float name="Density">0.33</float><float name="Haze">1.4</float><float name="Glare">0.2</float>'
                '<Color3 name="Color"><R>0.78</R><G>0.75</G><B>0.82</B></Color3>'
                '<Color3 name="Decay"><R>0.36</R><G>0.33</G><B>0.42</B></Color3>'
                '</Properties></Item>')


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "DemoArena.rbxmx"), "w", encoding="utf-8") as fh:
        fh.write(arena())
    with open(os.path.join(out, "Atmosphere.rbxmx"), "w", encoding="utf-8") as fh:
        fh.write(atmosphere())
    print("ok")

"""
Yami Skills - procedural textures (numpy -> PNG).

All VFX textures are WHITE/BLACK + alpha so Roblox can tint them.
Mesh textures (slash, ring, swirl) are pure black with an alpha gradient.
Particle textures are white with alpha (Roblox ParticleEmitter.Color tints them black).

UV convention: arrays are built with row 0 = v=0 (bottom) and flipped before saving,
so that Blender UV (u, v) matches pixel (u*W, (1-v)*H) of the saved PNG.
"""
import math
import os

import numpy as np
from PIL import Image


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def value_noise_1d(x, seed=0, octaves=3):
    rng = np.random.default_rng(seed)
    table = rng.random(4096)
    out = np.zeros_like(x, dtype=np.float64)
    amp, freq, total = 1.0, 1.0, 0.0
    for _ in range(octaves):
        xf = x * freq
        i0 = np.floor(xf).astype(np.int64)
        f = xf - i0
        f = f * f * (3 - 2 * f)
        a = table[i0 % 4096]
        b = table[(i0 + 1) % 4096]
        out += amp * (a + (b - a) * f)
        total += amp
        amp *= 0.5
        freq *= 2.0
    return out / total


def value_noise_2d(x, y, seed=0, octaves=4):
    rng = np.random.default_rng(seed)
    table = rng.random((256, 256))
    out = np.zeros_like(x, dtype=np.float64)
    amp, freq, total = 1.0, 1.0, 0.0
    for _ in range(octaves):
        xf, yf = x * freq, y * freq
        x0 = np.floor(xf).astype(np.int64)
        y0 = np.floor(yf).astype(np.int64)
        fx = xf - x0
        fy = yf - y0
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        a = table[y0 % 256, x0 % 256]
        b = table[y0 % 256, (x0 + 1) % 256]
        c = table[(y0 + 1) % 256, x0 % 256]
        d = table[(y0 + 1) % 256, (x0 + 1) % 256]
        out += amp * ((a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy)
        total += amp
        amp *= 0.5
        freq *= 2.0
    return out / total


def uv_grid(w, h):
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    return np.meshgrid(u, v)  # (h, w), row 0 = v small (bottom)


def save_rgba(path, rgb, alpha):
    """rgb: (h,w,3) or tuple; alpha: (h,w). Rows are bottom-up, flipped on save."""
    h, w = alpha.shape
    if not isinstance(rgb, np.ndarray):
        rgb = np.ones((h, w, 3)) * np.array(rgb, dtype=np.float64)
    arr = np.concatenate([rgb, alpha[..., None]], axis=2)
    arr = np.flipud(np.clip(arr, 0, 1))
    Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA").save(path)


# ---------------------------------------------------------------- mesh textures

def tex_slash(path, rim=False):
    w, h = 1024, 256
    U, V = uv_grid(w, h)
    along = smoothstep(0.0, 0.32, U) * (1.0 - smoothstep(0.9, 1.0, U))
    across = np.power(V, 1.35)
    streak = 0.62 + 0.38 * value_noise_1d(V * 70.0 + U * 2.0, seed=3)
    wisps = smoothstep(0.25, 0.75, value_noise_2d(U * 18.0, V * 6.0, seed=5) + U * 0.9)
    alpha = np.clip(along * across * streak * wisps * 1.75, 0, 1)
    alpha *= 1.0 - smoothstep(0.985, 1.0, V)  # crisp but anti-aliased outer edge
    rgb = np.zeros((h, w, 3))
    if rim:
        rim_mask = smoothstep(0.90, 0.95, V) * (1 - smoothstep(0.975, 0.99, V)) * along
        rgb += rim_mask[..., None]
        alpha = np.maximum(alpha, rim_mask * 0.95)
    alpha[0:2, 0:2] = 0.0  # pivot-fix triangle samples this corner
    save_rgba(path, rgb, alpha)


def tex_ring(path):
    w, h = 1024, 128
    U, V = uv_grid(w, h)
    alpha = smoothstep(0.0, 0.45, V) * (1.0 - smoothstep(0.8, 1.0, V))
    alpha *= 0.7 + 0.3 * value_noise_1d(U * 90.0, seed=11)
    alpha = np.clip(alpha * 1.25, 0, 1)
    save_rgba(path, (0, 0, 0), alpha)


def tex_swirl(path):
    w, h = 1024, 256
    U, V = uv_grid(w, h)
    along = smoothstep(0.0, 0.18, U) * (1.0 - smoothstep(0.7, 1.0, U))
    across = np.power(np.sin(np.pi * V), 0.7)
    streak = 0.55 + 0.45 * value_noise_1d(V * 40.0 + U * 6.0, seed=21)
    alpha = np.clip(along * across * streak * 1.5, 0, 1)
    save_rgba(path, (0, 0, 0), alpha)


def tex_katana_atlas(path):
    """512x512 atlas. Regions in UV space (u0,u1,v0,v1):
    A blade   (0.0,0.5, 0.5,1.0)  u=along blade, v=edge(0)->spine(1)
    B grip    (0.5,1.0, 0.5,1.0)  u=along grip,  v=around
    C gold    (0.0,0.25,0.25,0.5)
    D iron    (0.25,0.5,0.25,0.5)
    E lacquer (0.5,1.0, 0.0,0.5)
    """
    w = h = 512
    U, V = uv_grid(w, h)
    rgb = np.zeros((h, w, 3))
    n = value_noise_2d(U * 64, V * 64, seed=7)

    # A blade
    m = (U < 0.5) & (V >= 0.5)
    lu = U / 0.5
    lv = (V - 0.5) / 0.5
    hamon_line = 0.28 + 0.06 * np.sin(lu * 38.0) + 0.03 * np.sin(lu * 97.0 + 1.3)
    hamon = 1.0 - smoothstep(hamon_line - 0.03, hamon_line + 0.03, lv)
    steel = np.stack([0.62 + 0.1 * lv, 0.64 + 0.1 * lv, 0.68 + 0.1 * lv], axis=-1)
    steel = steel * (1.0 - 0.35 * smoothstep(0.75, 1.0, lv))[..., None]
    white = np.array([0.93, 0.94, 0.97])
    blade = steel * (1 - hamon[..., None]) + white * hamon[..., None]
    blade *= (0.96 + 0.04 * n)[..., None]
    rgb[m] = blade[m]

    # B grip: black ito wrap with pale diamond windows
    m = (U >= 0.5) & (V >= 0.5)
    gu = (U - 0.5) / 0.5 * 7.0
    gv = (V - 0.5) / 0.5 * 2.0
    du = np.abs((gu % 1.0) - 0.5)
    dv = np.abs((gv % 1.0) - 0.5)
    diamond = (du + dv) < 0.32
    grip = np.where(diamond[..., None], np.array([0.86, 0.85, 0.80]), np.array([0.035, 0.035, 0.04]))
    grip = grip * (0.9 + 0.1 * n)[..., None]
    rgb[m] = grip[m]

    # C gold
    m = (U < 0.25) & (V >= 0.25) & (V < 0.5)
    rgb[m] = (np.array([0.80, 0.60, 0.22]) * (0.85 + 0.15 * n)[..., None])[m]

    # D dark iron
    m = (U >= 0.25) & (U < 0.5) & (V >= 0.25) & (V < 0.5)
    rgb[m] = (np.array([0.10, 0.10, 0.11]) * (0.8 + 0.4 * n)[..., None])[m]

    # E black lacquer
    m = (U >= 0.5) & (V < 0.5)
    rgb[m] = (np.array([0.025, 0.025, 0.03]) * (0.8 + 0.4 * n)[..., None])[m]

    # bottom-left quarter (unused) also dark
    m = (U < 0.5) & (V < 0.25)
    rgb[m] = np.array([0.05, 0.05, 0.05])
    save_rgba(path, rgb, np.ones((h, w)))


# ------------------------------------------------------------- particle textures

def _radial(w=512):
    U, V = uv_grid(w, w)
    x, y = U * 2 - 1, V * 2 - 1
    r = np.sqrt(x * x + y * y)
    a = np.arctan2(y, x)
    return x, y, r, a


def tex_p_inksmoke(path):
    x, y, r, a = _radial()
    n = value_noise_2d((x + 2) * 3.5, (y + 2) * 3.5, seed=31, octaves=5)
    edge = 0.55 + 0.35 * n
    alpha = 1.0 - smoothstep(edge - 0.25, edge, r)
    alpha *= 0.55 + 0.45 * value_noise_2d((x + 5) * 9, (y + 5) * 9, seed=32)
    save_rgba(path, (1, 1, 1), np.clip(alpha * 1.3, 0, 1))


def tex_p_streak(path):
    w = 512
    U, V = uv_grid(w, w)
    x = (U - 0.5) * 2
    along = np.sin(np.pi * V) ** 0.6
    core = np.exp(-(x / (0.08 * along + 1e-4)) ** 2)
    save_rgba(path, (1, 1, 1), np.clip(core * along, 0, 1))


def tex_p_crack(path):
    x, y, r, a = _radial()
    alpha = np.zeros_like(r)
    rng = np.random.default_rng(41)
    for _ in range(11):
        ang = rng.uniform(-math.pi, math.pi)
        wob = rng.uniform(2, 6)
        target = ang + 0.12 * np.sin(r * wob * 6)
        d = np.abs(np.angle(np.exp(1j * (a - target))))
        width = 0.035 * (1 - r) + 0.004
        line = 1 - smoothstep(width * 0.6, width, d * r + 1e-6)
        alpha = np.maximum(alpha, line * (1 - smoothstep(rng.uniform(0.6, 0.98), 1.0, r)))
    alpha = np.maximum(alpha, 1 - smoothstep(0.05, 0.12, r))
    save_rgba(path, (1, 1, 1), np.clip(alpha, 0, 1))


def tex_p_ring(path):
    x, y, r, a = _radial()
    ring = np.exp(-((r - 0.82) / 0.07) ** 2)
    ring *= 0.75 + 0.25 * value_noise_1d((a + math.pi) * 20, seed=51)
    save_rgba(path, (1, 1, 1), np.clip(ring * 1.2, 0, 1))


def tex_p_star(path):
    x, y, r, a = _radial()
    spikes = np.abs(np.cos(2 * a)) ** 40 * (1 - smoothstep(0.0, 1.0, r))
    spikes += np.abs(np.cos(2 * a + math.pi / 4)) ** 60 * (1 - smoothstep(0.0, 0.6, r)) * 0.6
    core = 1 - smoothstep(0.0, 0.18, r)
    save_rgba(path, (1, 1, 1), np.clip(spikes * 1.6 + core, 0, 1))


def tex_p_shards(path):
    w = 512
    U, V = uv_grid(w, w)
    alpha = np.zeros((w, w))
    rng = np.random.default_rng(61)
    for _ in range(7):
        cx, cy = rng.uniform(0.2, 0.8, 2)
        ang = rng.uniform(0, math.pi)
        length = rng.uniform(0.15, 0.4)
        width = rng.uniform(0.02, 0.05)
        dx, dy = U - cx, V - cy
        along = dx * math.cos(ang) + dy * math.sin(ang)
        perp = -dx * math.sin(ang) + dy * math.cos(ang)
        taper = width * (1 - np.abs(along) / length)
        inside = (np.abs(along) < length) & (np.abs(perp) < taper)
        alpha = np.maximum(alpha, inside.astype(np.float64))
    save_rgba(path, (1, 1, 1), alpha)


def build_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = {
        "T_SlashArc.png": lambda p: tex_slash(p, rim=False),
        "T_SlashArc_Rim.png": lambda p: tex_slash(p, rim=True),
        "T_ShockRing.png": tex_ring,
        "T_Swirl.png": tex_swirl,
        "T_Katana.png": tex_katana_atlas,
        "P_InkSmoke.png": tex_p_inksmoke,
        "P_Streak.png": tex_p_streak,
        "P_Crack.png": tex_p_crack,
        "P_Ring.png": tex_p_ring,
        "P_Star.png": tex_p_star,
        "P_Shards.png": tex_p_shards,
    }
    paths = {}
    for name, fn in files.items():
        p = os.path.join(out_dir, name)
        fn(p)
        paths[name] = p
    return paths


if __name__ == "__main__":
    import sys

    print(build_all(sys.argv[1] if len(sys.argv) > 1 else "."))

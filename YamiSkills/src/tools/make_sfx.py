"""
Procedural dark-magic sound effects for the Yami skill set (OGG Vorbis, 44.1 kHz).
Optional: upload them in Roblox (Asset Manager / Creator Hub) and put the IDs in Config.Sounds.
Usage: python make_sfx.py <out_dir>
"""
import os
import sys

import numpy as np
import soundfile as sf
from scipy import signal

SR = 44100
rng = np.random.default_rng(1919)


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_adsr(n, a, d, s_level, r, total):
    t = np.arange(n) / SR
    e = np.zeros(n)
    a_n = max(1, int(a * SR))
    d_n = max(1, int(d * SR))
    r_n = max(1, int(r * SR))
    e[:a_n] = np.linspace(0, 1, a_n)
    e[a_n:a_n + d_n] = np.linspace(1, s_level, min(d_n, max(0, n - a_n)))[: max(0, min(d_n, n - a_n))]
    sus_end = max(a_n + d_n, n - r_n)
    e[a_n + d_n:sus_end] = s_level
    e[sus_end:] = np.linspace(s_level, 0, n - sus_end)
    return e


def bandsweep(noise, f0, f1, q=2.0, steps=48):
    """Time-varying band-pass by processing short overlapping blocks."""
    n = len(noise)
    out = np.zeros(n)
    block = n // steps + 1
    win = np.hanning(block * 2)
    for i in range(steps):
        c = f0 * (f1 / f0) ** (i / max(1, steps - 1))
        lo, hi = max(20, c / (1 + 1 / q)), min(SR / 2 - 100, c * (1 + 1 / q))
        b, a = signal.butter(2, [lo, hi], btype="band", fs=SR)
        start = max(0, i * block - block // 2)
        seg = noise[start:start + block * 2]
        y = signal.lfilter(b, a, seg)
        w = win[: len(y)]
        out[start:start + len(y)] += y * w
    return out


def lowpass(x, fc, order=2):
    b, a = signal.butter(order, fc, btype="low", fs=SR)
    return signal.lfilter(b, a, x)


def highpass(x, fc, order=2):
    b, a = signal.butter(order, fc, btype="high", fs=SR)
    return signal.lfilter(b, a, x)


def normalize(x, peak=0.92):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def soft_clip(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def reverb(x, decay=1.6, mix=0.25):
    n = int(decay * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * (6.9 / decay))
    ir = lowpass(ir, 5000)
    wet = signal.fftconvolve(x, ir)
    wet = np.concatenate([wet, np.zeros(max(0, len(x) + n - len(wet)))])[: len(x) + n]
    dry = np.concatenate([x, np.zeros(n)])
    return dry * (1 - mix) + normalize(wet, np.max(np.abs(x)) + 1e-9) * mix


def stereo(x, width=0.15):
    d = int(0.012 * SR)
    left = x
    right = np.concatenate([np.zeros(d), x[:-d]]) * (1 - width) + x * width
    return np.stack([left, right], axis=1)


def whoosh(dur=0.36, f0=3800, f1=700, power=1.0):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    x = bandsweep(noise, f0, f1, q=1.6)
    t = np.arange(n) / n
    e = (t ** 0.35) * np.exp(-((t - 0.32) ** 2) / 0.045) + 0.0
    return normalize(x * e) * power


def shing(dur=0.5, base=2600):
    t = t_axis(dur)
    x = np.zeros_like(t)
    for k, mult in enumerate([1.0, 1.51, 2.27, 2.94, 3.81]):
        x += np.sin(2 * np.pi * base * mult * t + rng.uniform(0, 6)) * np.exp(-t * (9 + 5 * k)) / (1 + k)
    return normalize(x) * 0.5


def sub_boom(dur=1.6, f0=70, f1=28):
    t = t_axis(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 2.4)
    crack = highpass(rng.standard_normal(len(t)), 900) * np.exp(-t * 30)
    rumble = lowpass(rng.standard_normal(len(t)), 180) * np.exp(-t * 1.6) * 0.8
    return normalize(soft_clip(body * 1.2 + crack * 0.35 + rumble, 1.8))


def tear(dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / SR
    crackle = np.zeros(n)
    idx = rng.choice(n, size=int(n * 0.012), replace=False)
    crackle[idx] = rng.uniform(-1, 1, len(idx))
    crackle = highpass(signal.lfilter([1], [1, -0.6], crackle), 1200)
    rip = bandsweep(rng.standard_normal(n), 900, 5200, q=2.5) * np.exp(-t * 5)
    return normalize(soft_clip(crackle * 2.5 + rip, 2.5))


def make_slash():
    x = whoosh(0.34, 4200, 650) + shing(0.34, 3100)[: int(0.34 * SR)] * 0.35
    return stereo(normalize(x))


def make_heavy_slash():
    w = whoosh(0.6, 2600, 260, 1.0)
    s = shing(0.6, 2100)
    x = w + s * 0.3
    return stereo(normalize(reverb(x, 0.9, 0.18)))


def make_dash():
    x = whoosh(0.42, 1200, 5200) * 0.8 + whoosh(0.42, 5200, 900) * 0.4
    return stereo(normalize(x))


def make_hit():
    t = t_axis(0.3)
    f = 55 + 110 * np.exp(-t * 35)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    click = highpass(rng.standard_normal(len(t)), 2500) * np.exp(-t * 90)
    slice_ = bandsweep(rng.standard_normal(len(t)), 5000, 1500) * np.exp(-t * 25)
    return stereo(normalize(soft_clip(body * 1.3 + click * 0.5 + slice_ * 0.5, 2)))


def make_boom():
    return stereo(normalize(reverb(sub_boom(1.7), 1.8, 0.3)))


def make_rift():
    # reverse swell -> tear -> boom
    sw_n = int(0.55 * SR)
    swell = bandsweep(rng.standard_normal(sw_n), 300, 4500, q=1.2) * np.linspace(0, 1, sw_n) ** 2.5
    tr = tear(0.5)
    bm = sub_boom(2.2, 80, 24)
    total = np.zeros(sw_n + len(bm))
    total[:sw_n] += swell * 0.6
    total[sw_n - int(0.05 * SR): sw_n - int(0.05 * SR) + len(tr)] += tr * 0.9
    total[sw_n: sw_n + len(bm)] += bm
    return stereo(normalize(reverb(total, 2.4, 0.32)))


def make_charge():
    dur = 1.6
    t = t_axis(dur)
    drone = (np.sin(2 * np.pi * 46 * t) + 0.7 * np.sin(2 * np.pi * 46.8 * t) + 0.4 * np.sin(2 * np.pi * 92.5 * t))
    hiss = bandsweep(rng.standard_normal(len(t)), 400, 1800, q=1.0, steps=24) * (0.3 + 0.7 * t / dur)
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 3.0 * t)
    x = soft_clip(drone * 0.6 * lfo + hiss * 0.5, 1.6)
    fade = int(0.08 * SR)  # loop friendly
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return stereo(normalize(x, 0.8))


def make_cocoon():
    dur = 0.9
    t = t_axis(dur)
    swirl = bandsweep(rng.standard_normal(len(t)), 2400, 300, q=1.4) * np.sin(np.pi * t / dur) ** 0.6
    hum = np.sin(2 * np.pi * 70 * t) * np.exp(-((t - 0.6) ** 2) / 0.05) * 0.5
    return stereo(normalize(reverb(swirl + hum, 1.0, 0.25)))


def make_draw():
    dur = 0.55
    n = int(dur * SR)
    t = np.arange(n) / SR
    slide = bandsweep(rng.standard_normal(n), 3500, 7000, q=4) * np.clip(t / 0.25, 0, 1) * np.exp(-np.clip(t - 0.3, 0, None) * 14)
    ring = shing(dur, 3400)[:n]
    ring = np.concatenate([np.zeros(int(0.28 * SR)), ring])[:n]
    return stereo(normalize(slide * 0.7 + ring * 0.6))


SOUNDS = {
    "yami_slash.ogg": make_slash,
    "yami_heavy_slash.ogg": make_heavy_slash,
    "yami_dash.ogg": make_dash,
    "yami_hit.ogg": make_hit,
    "yami_boom.ogg": make_boom,
    "yami_dimension_rift.ogg": make_rift,
    "yami_charge_loop.ogg": make_charge,
    "yami_cocoon.ogg": make_cocoon,
    "yami_katana_draw.ogg": make_draw,
}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name, fn in SOUNDS.items():
        data = fn()
        sf.write(os.path.join(out, name), data.astype(np.float32), SR, format="OGG", subtype="VORBIS")
        print(name, f"{len(data) / SR:.2f}s")

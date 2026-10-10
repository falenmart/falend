"""Roblox T-shirt tasarımlarını üretir.

Çalıştırma:  python3 roblox-tisort/olustur.py
Çıktı: 512x512 şeffaf PNG'ler (Roblox'a doğrudan yüklenebilir) + önizleme.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2048           # çizim çözünürlüğü (sonra 512'ye küçültülür, kenarlar pürüzsüz olur)
OUT = 512
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"

INK = (27, 24, 48, 255)        # kalın kontur rengi: her renk tişört üstünde okunur
WHITE = (255, 255, 255, 255)


def new_layer():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def new_mask():
    return Image.new("L", (S, S), 0)


def dilate(mask, r):
    """Maskeyi r piksel genişletir (kontur için)."""
    blurred = mask.filter(ImageFilter.GaussianBlur(r / 2))
    return blurred.point(lambda v: 255 if v > 8 else 0)


def paint(canvas, mask, color, stroke=0, stroke_color=INK):
    """Maskeyi renkle doldurur; stroke>0 ise etrafına kalın kontur çizer."""
    if stroke:
        canvas.paste(Image.new("RGBA", (S, S), stroke_color), (0, 0), dilate(mask, stroke))
    if isinstance(color, Image.Image):
        canvas.paste(color, (0, 0), mask)
    else:
        canvas.paste(Image.new("RGBA", (S, S), color), (0, 0), mask)


def vgradient(top, bottom, y0=0, y1=S):
    g = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(g)
    for y in range(S):
        t = min(max((y - y0) / max(y1 - y0, 1), 0), 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line([(0, y), (S, y)], fill=c)
    return g


def heart_points(cx, cy, size, n=200):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 32, cy - y * size / 32))
    return pts


def star_points(cx, cy, r_out, r_in, n=4, rot=0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def sparkle(canvas, cx, cy, r, color=WHITE, stroke=22):
    m = new_mask()
    ImageDraw.Draw(m).polygon(star_points(cx, cy, r, r * 0.28), fill=255)
    paint(canvas, m, color, stroke)


def finish(canvas, name):
    img = canvas.resize((OUT, OUT), Image.LANCZOS)
    path = os.path.join(HERE, name)
    img.save(path, optimize=True)
    return img


# ---------------------------------------------------------------------------
# 1) SEVİMLİ KEDİ — kalpli kawaii kedi (her yaş, her cinsiyet)
# ---------------------------------------------------------------------------
def kedi():
    c = new_layer()

    # Kafa + kulaklar tek parça maske
    head = new_mask()
    d = ImageDraw.Draw(head)
    d.ellipse([330, 620, 1718, 1760], fill=255)
    d.polygon([(400, 980), (470, 330), (900, 700)], fill=255)      # sol kulak
    d.polygon([(1648, 980), (1578, 330), (1148, 700)], fill=255)   # sağ kulak
    head = head.filter(ImageFilter.GaussianBlur(18)).point(lambda v: 255 if v > 128 else 0)
    paint(c, head, (255, 247, 236, 255), stroke=70)

    # Kulak içleri
    inner = new_mask()
    d = ImageDraw.Draw(inner)
    d.polygon([(500, 870), (530, 480), (790, 720)], fill=255)
    d.polygon([(1548, 870), (1518, 480), (1258, 720)], fill=255)
    inner = inner.filter(ImageFilter.GaussianBlur(12)).point(lambda v: 255 if v > 128 else 0)
    paint(c, inner, (255, 160, 190, 255))

    # Turuncu tekir lekesi (alın)
    patch = new_mask()
    d = ImageDraw.Draw(patch)
    for x0 in (880, 990, 1100):
        d.rounded_rectangle([x0, 640, x0 + 70, 860], radius=35, fill=255)
    patch.paste(0, (0, 0), Image.eval(head, lambda v: 255 - v))
    paint(c, patch, (255, 170, 80, 255))

    # Yanak pembelikleri
    blush = new_mask()
    d = ImageDraw.Draw(blush)
    d.ellipse([470, 1290, 700, 1430], fill=255)
    d.ellipse([1348, 1290, 1578, 1430], fill=255)
    paint(c, blush, (255, 140, 170, 230))

    # Gözler (büyük, parlak)
    eyes = new_mask()
    d = ImageDraw.Draw(eyes)
    d.ellipse([640, 1000, 860, 1280], fill=255)
    d.ellipse([1188, 1000, 1408, 1280], fill=255)
    paint(c, eyes, INK)
    shine = new_mask()
    d = ImageDraw.Draw(shine)
    for ex in (640, 1188):
        d.ellipse([ex + 40, 1040, ex + 130, 1130], fill=255)
        d.ellipse([ex + 130, 1170, ex + 170, 1210], fill=255)
    paint(c, shine, WHITE)

    # Burun + "w" ağız
    nose = new_mask()
    ImageDraw.Draw(nose).polygon([(974, 1300), (1074, 1300), (1024, 1360)], fill=255)
    nose = nose.filter(ImageFilter.GaussianBlur(8)).point(lambda v: 255 if v > 100 else 0)
    paint(c, nose, (255, 120, 150, 255), stroke=18)
    d = ImageDraw.Draw(c)
    d.arc([904, 1320, 1028, 1440], start=20, end=160, fill=INK, width=30)
    d.arc([1020, 1320, 1144, 1440], start=20, end=160, fill=INK, width=30)

    # Bıyıklar
    for side in (-1, 1):
        for dy, ang in ((-30, -8), (40, 8)):
            x0 = 1024 + side * 470
            x1 = 1024 + side * 760
            y0 = 1330 + dy
            y1 = y0 + ang * 6
            d.line([(x0, y0), (x1, y1)], fill=INK, width=26)

    # Kalp
    h = new_mask()
    ImageDraw.Draw(h).polygon(heart_points(1640, 420, 520), fill=255)
    paint(c, h, vgradient((255, 90, 120), (230, 30, 80), 180, 700), stroke=55)
    hs = new_mask()
    ImageDraw.Draw(hs).ellipse([1500, 290, 1580, 370], fill=255)
    paint(c, hs, (255, 255, 255, 220))

    sparkle(c, 330, 330, 140, (255, 225, 90, 255))
    sparkle(c, 1820, 1500, 110, (130, 220, 255, 255))
    sparkle(c, 220, 1500, 80, (255, 255, 255, 255))
    return finish(c, "1_sevimli_kedi.png")


# ---------------------------------------------------------------------------
# 2) HAVALI SMILEY — piksel güneş gözlüklü gülen surat (klasik meme)
# ---------------------------------------------------------------------------
def smiley():
    c = new_layer()
    face = new_mask()
    ImageDraw.Draw(face).ellipse([224, 224, 1824, 1824], fill=255)
    paint(c, face, vgradient((255, 230, 70), (255, 170, 20), 224, 1824), stroke=80)

    # Üstte parlama
    gl = new_mask()
    ImageDraw.Draw(gl).ellipse([480, 360, 900, 560], fill=255)
    gl = gl.rotate(25, center=(690, 460))
    paint(c, gl, (255, 255, 255, 120))

    # Piksel güneş gözlüğü ("deal with it")
    px = 64
    pattern = [
        "XXXXXXXXXXXXXXXXXXXXXXXXX",
        "XXXXXXXXXXXXXXXXXXXXXXXXX",
        "..XWWXXXXXX...XWWXXXXXX..",
        "..XXWWXXXXX...XXWWXXXXX..",
        "..XXXXXXXXX...XXXXXXXXX..",
        "...XXXXXXX.....XXXXXXX...",
        "....XXXXX.......XXXXX....",
    ]
    ox = 1024 - len(pattern[0]) * px // 2
    oy = 760
    d = ImageDraw.Draw(c)
    for r, row in enumerate(pattern):
        for col, ch in enumerate(row):
            if ch == ".":
                continue
            color = WHITE if ch == "W" else INK
            d.rectangle([ox + col * px, oy + r * px, ox + (col + 1) * px - 1, oy + (r + 1) * px - 1], fill=color)

    # Kocaman gülüş
    mouth = new_mask()
    md = ImageDraw.Draw(mouth)
    md.chord([560, 1020, 1488, 1600], start=0, end=180, fill=255)
    paint(c, mouth, INK)
    tongue = new_mask()
    ImageDraw.Draw(tongue).ellipse([820, 1380, 1228, 1620], fill=255)
    tongue.paste(0, (0, 0), Image.eval(mouth, lambda v: 255 - v))
    paint(c, tongue, (255, 100, 120, 255))
    teeth = new_mask()
    ImageDraw.Draw(teeth).rectangle([600, 1310, 1448, 1380], fill=255)
    teeth.paste(0, (0, 0), Image.eval(mouth, lambda v: 255 - v))
    paint(c, teeth, WHITE)

    # Yanak
    blush = new_mask()
    bd = ImageDraw.Draw(blush)
    bd.ellipse([380, 1180, 560, 1290], fill=255)
    bd.ellipse([1488, 1180, 1668, 1290], fill=255)
    paint(c, blush, (255, 120, 90, 160))

    sparkle(c, 1800, 300, 150)
    sparkle(c, 1900, 620, 80, (255, 240, 120, 255))
    return finish(c, "2_havali_smiley.png")


# ---------------------------------------------------------------------------
# 3) GOOD VIBES — gökkuşağı yazı (estetik / "aesthetic" kitle)
# ---------------------------------------------------------------------------
def good_vibes():
    c = new_layer()

    def text_mask(txt, size, cy):
        m = new_mask()
        f = ImageFont.truetype(FONT, size)
        d = ImageDraw.Draw(m)
        w = d.textlength(txt, font=f)
        d.text((1024 - w / 2, cy), txt, font=f, fill=255, anchor="lm")
        return m

    rainbow = Image.new("RGBA", (S, S))
    rd = ImageDraw.Draw(rainbow)
    stops = [(255, 94, 120), (255, 160, 60), (255, 220, 70), (90, 220, 140), (80, 170, 255), (170, 110, 255)]
    for x in range(S):
        t = x / (S - 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2)
        f = t - i
        col = tuple(int(stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f) for k in range(3)) + (255,)
        rd.line([(x, 0), (x, S)], fill=col)

    good = text_mask("GOOD", 560, 720)
    vibes = text_mask("VIBES", 560, 1240)
    both = Image.new("L", (S, S), 0)
    both.paste(255, (0, 0), good)
    both.paste(255, (0, 0), vibes)

    # 3B gölge: aşağı-sağa kaydırılmış kopya
    shadow = Image.new("L", (S, S), 0)
    shadow.paste(both, (34, 34))
    paint(c, dilate(shadow, 60), INK)
    paint(c, both, rainbow, stroke=60)
    # Küçük kalp ve yıldızlar
    h = new_mask()
    ImageDraw.Draw(h).polygon(heart_points(1024, 1720, 300), fill=255)
    paint(c, h, (255, 90, 130, 255), stroke=45)
    sparkle(c, 260, 330, 150, (255, 225, 90, 255))
    sparkle(c, 1800, 360, 110, WHITE)
    sparkle(c, 1780, 1700, 130, (130, 220, 255, 255))
    sparkle(c, 290, 1690, 90, (200, 160, 255, 255))
    return finish(c, "3_good_vibes.png")


# ---------------------------------------------------------------------------
# Önizleme: blok Roblox avatarı üstünde 3 tasarım
# ---------------------------------------------------------------------------
def preview(designs):
    W, H = 1860, 760
    img = Image.new("RGBA", (W, H), (34, 36, 48, 255))
    d = ImageDraw.Draw(img)
    shirts = [(70, 70, 80), (240, 240, 245), (120, 180, 255)]
    labels = ["Sevimli Kedi", "Havalı Smiley", "Good Vibes"]
    lab_font = ImageFont.truetype(FONT, 40)
    skin = (255, 214, 120)
    pants = (40, 60, 120)
    for i, (des, shirt, lab) in enumerate(zip(designs, shirts, labels)):
        cx = 310 + i * 620
        # Kafa
        d.rounded_rectangle([cx - 70, 70, cx + 70, 200], radius=30, fill=skin, outline=(0, 0, 0), width=4)
        d.ellipse([cx - 35, 115, cx - 15, 140], fill=(0, 0, 0))
        d.ellipse([cx + 15, 115, cx + 35, 140], fill=(0, 0, 0))
        d.arc([cx - 35, 130, cx + 35, 175], start=20, end=160, fill=(0, 0, 0), width=5)
        # Gövde
        torso = [cx - 140, 210, cx + 140, 490]
        d.rectangle(torso, fill=shirt, outline=(0, 0, 0), width=4)
        # Kollar
        d.rectangle([cx - 285, 210, cx - 145, 490], fill=shirt, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 145, 210, cx + 285, 490], fill=shirt, outline=(0, 0, 0), width=4)
        d.rectangle([cx - 285, 440, cx - 145, 490], fill=skin, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 145, 440, cx + 285, 490], fill=skin, outline=(0, 0, 0), width=4)
        # Bacaklar
        d.rectangle([cx - 140, 495, cx - 3, 680], fill=pants, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 3, 495, cx + 140, 680], fill=pants, outline=(0, 0, 0), width=4)
        # T-shirt görseli gövde önünde
        t = des.resize((250, 250), Image.LANCZOS)
        img.alpha_composite(t, (cx - 125, 225))
        w = d.textlength(lab, font=lab_font)
        d.text((cx - w / 2, 700), lab, font=lab_font, fill=(255, 255, 255))
    img.convert("RGB").save(os.path.join(HERE, "onizleme.png"), optimize=True)


if __name__ == "__main__":
    designs = [kedi(), smiley(), good_vibes()]
    preview(designs)
    print("Tamam:", os.listdir(HERE))

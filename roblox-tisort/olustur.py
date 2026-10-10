"""Roblox T-shirt tasarımlarını üretir.

Çalıştırma:  python3 roblox-tisort/olustur.py
Çıktı: 512x512 şeffaf PNG'ler (Roblox'a doğrudan yüklenebilir) + önizleme.
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

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
        _over(canvas, dilate(mask, stroke), stroke_color)
    _over(canvas, mask, color)


def _over(canvas, mask, color):
    layer = color.copy() if isinstance(color, Image.Image) else Image.new("RGBA", (S, S), color)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    canvas.alpha_composite(layer)


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
# 4) KAWAII TAVŞAN — araştırmada sevimli hayvanlarda 1. sıra
# ---------------------------------------------------------------------------
def tavsan():
    c = new_layer()

    # Pastel yuvarlak arka plan (sticker görünümü, her gömlekte öne çıkar)
    bg = new_mask()
    ImageDraw.Draw(bg).ellipse([200, 520, 1848, 2000], fill=255)
    paint(c, bg, vgradient((255, 200, 225), (200, 180, 255), 520, 2000), stroke=60)

    def ear(cx, top, bottom, w, angle):
        m = new_mask()
        ImageDraw.Draw(m).ellipse([cx - w, top, cx + w, bottom], fill=255)
        return m.rotate(angle, center=(cx, bottom - 60), resample=Image.BICUBIC)

    ears = new_mask()
    ears.paste(255, (0, 0), ear(760, 120, 1050, 150, 10))
    ears.paste(255, (0, 0), ear(1288, 180, 1050, 150, -22))
    head = new_mask()
    ImageDraw.Draw(head).ellipse([430, 820, 1618, 1840], fill=255)
    body = Image.new("L", (S, S), 0)
    body.paste(255, (0, 0), ears)
    body.paste(255, (0, 0), head)
    paint(c, body, (255, 255, 255, 255), stroke=60)
    inner = new_mask()
    inner.paste(255, (0, 0), ear(760, 240, 980, 70, 10))
    inner.paste(255, (0, 0), ear(1288, 290, 980, 70, -22))
    paint(c, inner, (255, 170, 200, 255))
    # Kulaklarla kafa arasında ince ayrım çizgisi
    sep = dilate(head, 1)
    sep.paste(0, (0, 0), head)
    ImageDraw.Draw(c).arc([430, 820, 1618, 1840], start=225, end=315, fill=INK, width=28)

    # Fiyonk
    bow = new_mask()
    bd = ImageDraw.Draw(bow)
    bd.polygon([(1290, 760), (1100, 640), (1120, 900)], fill=255)
    bd.polygon([(1290, 760), (1480, 640), (1460, 900)], fill=255)
    bow = bow.filter(ImageFilter.GaussianBlur(14)).point(lambda v: 255 if v > 128 else 0)
    paint(c, bow, (255, 95, 150, 255), stroke=34)
    knot = new_mask()
    ImageDraw.Draw(knot).ellipse([1230, 700, 1350, 820], fill=255)
    paint(c, knot, (255, 140, 180, 255), stroke=26)

    # Işıltılı gözler
    eyes = new_mask()
    d = ImageDraw.Draw(eyes)
    d.ellipse([650, 1150, 880, 1430], fill=255)
    d.ellipse([1168, 1150, 1398, 1430], fill=255)
    paint(c, eyes, vgradient((40, 30, 70), (110, 70, 170), 1150, 1430))
    shine = new_mask()
    d = ImageDraw.Draw(shine)
    for ex in (650, 1168):
        d.ellipse([ex + 40, 1190, ex + 135, 1285], fill=255)
        d.ellipse([ex + 140, 1330, ex + 185, 1375], fill=255)
    paint(c, shine, WHITE)
    for ex in (650, 1168):
        sparkle(c, ex + 170, 1200, 50, WHITE, stroke=0)

    blush = new_mask()
    d = ImageDraw.Draw(blush)
    d.ellipse([520, 1440, 740, 1570], fill=255)
    d.ellipse([1308, 1440, 1528, 1570], fill=255)
    paint(c, blush, (255, 140, 175, 220))

    nose = new_mask()
    ImageDraw.Draw(nose).ellipse([984, 1430, 1064, 1490], fill=255)
    paint(c, nose, (255, 120, 160, 255), stroke=16)
    d = ImageDraw.Draw(c)
    d.line([(1024, 1495), (1024, 1540)], fill=INK, width=24)
    d.arc([934, 1470, 1028, 1580], start=10, end=150, fill=INK, width=24)
    d.arc([1020, 1470, 1114, 1580], start=30, end=170, fill=INK, width=24)

    h = new_mask()
    ImageDraw.Draw(h).polygon(heart_points(330, 700, 260), fill=255)
    paint(c, h, (255, 90, 130, 255), stroke=40)
    sparkle(c, 1800, 420, 130, (255, 225, 90, 255))
    sparkle(c, 220, 1100, 80, WHITE)
    sparkle(c, 1850, 1250, 90, (130, 220, 255, 255))
    return finish(c, "4_kawaii_tavsan.png")


# ---------------------------------------------------------------------------
# 5) Y2K PİKSEL KALP — neon parıltılı 8-bit kalp (Y2K / piksel trendi)
# ---------------------------------------------------------------------------
def piksel_kalp():
    c = new_layer()
    pattern = [
        "..OOO...OOO..",
        ".OWWPO.OPPPO.",
        "OWWPPPOPPPPMO",
        "OWPPPPPPPPPMO",
        "OPPPPPPPPPPMO",
        "OPPPPPPPPPMMO",
        ".OPPPPPPPMMO.",
        "..OPPPPPMMO..",
        "...OPPPMMO...",
        "....OPMMO....",
        ".....OMO.....",
        "......O......",
    ]
    colors = {"O": INK, "W": WHITE, "P": (255, 70, 150, 255), "M": (190, 20, 110, 255)}
    px = 116
    ox = 1024 - len(pattern[0]) * px // 2
    oy = 1000 - len(pattern) * px // 2

    shape = new_mask()
    sd = ImageDraw.Draw(shape)
    for r, row in enumerate(pattern):
        for col, ch in enumerate(row):
            if ch != ".":
                sd.rectangle([ox + col * px, oy + r * px, ox + (col + 1) * px - 1, oy + (r + 1) * px - 1], fill=255)

    # Neon parıltı
    glow = dilate(shape, 120).filter(ImageFilter.GaussianBlur(70))
    glow = glow.point(lambda v: int(v * 0.75))
    paint(c, glow, (255, 60, 200, 255))

    d = ImageDraw.Draw(c)
    for r, row in enumerate(pattern):
        for col, ch in enumerate(row):
            if ch in colors:
                d.rectangle([ox + col * px, oy + r * px, ox + (col + 1) * px - 1, oy + (r + 1) * px - 1],
                            fill=colors[ch])

    def pixel_plus(cx, cy, p, color):
        m = new_mask()
        md = ImageDraw.Draw(m)
        md.rectangle([cx - p // 2, cy - p * 3 // 2, cx + p // 2, cy + p * 3 // 2], fill=255)
        md.rectangle([cx - p * 3 // 2, cy - p // 2, cx + p * 3 // 2, cy + p // 2], fill=255)
        g = dilate(m, 40).filter(ImageFilter.GaussianBlur(30))
        paint(c, g.point(lambda v: int(v * 0.6)), color)
        paint(c, m, color, stroke=22)

    pixel_plus(300, 330, 70, (90, 240, 255, 255))
    pixel_plus(1760, 300, 56, (255, 240, 90, 255))
    pixel_plus(1820, 1500, 70, (180, 130, 255, 255))
    pixel_plus(230, 1450, 50, (255, 255, 255, 255))

    # Alt yazı: piksel tarzı "PLAYER 1"
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 190)
    t = new_mask()
    td = ImageDraw.Draw(t)
    w = td.textlength("PLAYER 1", font=f)
    td.text((1024 - w / 2, 1790), "PLAYER 1", font=f, fill=255, anchor="lm")
    small = t.resize((S // 16, S // 16), Image.BILINEAR).point(lambda v: 255 if v > 90 else 0)
    t = small.resize((S, S), Image.NEAREST)
    paint(c, t, (90, 240, 255, 255), stroke=40)
    return finish(c, "5_y2k_piksel_kalp.png")


# ---------------------------------------------------------------------------
# 6) MUTLU FİLİZ — saksıda sevimli bitki (Grow a Garden bahçe trendi, telifsiz)
# ---------------------------------------------------------------------------
def filiz():
    c = new_layer()
    green = vgradient((140, 230, 110), (60, 170, 80), 300, 1100)

    stem = new_mask()
    ImageDraw.Draw(stem).line([(1024, 1150), (1010, 950), (1030, 780), (1024, 660)], fill=255, width=70, joint="curve")

    def leaf(cx, cy, w, h, angle):
        m = new_mask()
        ImageDraw.Draw(m).ellipse([cx - w, cy - h, cx + w, cy + h], fill=255)
        return m.rotate(angle, center=(cx, cy), resample=Image.BICUBIC)

    leaves = new_mask()
    leaves.paste(255, (0, 0), leaf(760, 600, 300, 150, 28))
    leaves.paste(255, (0, 0), leaf(1290, 520, 320, 160, -32))
    plant = Image.new("L", (S, S), 0)
    plant.paste(255, (0, 0), stem)
    plant.paste(255, (0, 0), leaves)
    paint(c, plant, green, stroke=55)
    # Yaprak damarları
    veins = new_mask()
    vd = ImageDraw.Draw(veins)
    vd.line([(1010, 670), (560, 760)], fill=255, width=22)
    vd.line([(1040, 640), (1530, 390)], fill=255, width=22)
    inside = Image.new("L", (S, S), 0)
    inside.paste(255, (0, 0), leaf(760, 600, 250, 100, 28))
    inside.paste(255, (0, 0), leaf(1290, 520, 270, 110, -32))
    veins.paste(0, (0, 0), Image.eval(inside, lambda v: 255 - v))
    paint(c, veins, (40, 130, 60, 255))

    # Tepedeki küçük çiçek
    flower = new_mask()
    fd = ImageDraw.Draw(flower)
    for k in range(5):
        a = math.radians(k * 72 - 90)
        x, y = 1024 + 85 * math.cos(a), 300 + 85 * math.sin(a)
        fd.ellipse([x - 80, y - 80, x + 80, y + 80], fill=255)
    paint(c, flower, (255, 150, 200, 255), stroke=40)
    center = new_mask()
    ImageDraw.Draw(center).ellipse([974, 250, 1074, 350], fill=255)
    paint(c, center, (255, 215, 70, 255), stroke=20)
    stem2 = new_mask()
    ImageDraw.Draw(stem2).line([(1024, 660), (1024, 400)], fill=255, width=50)
    paint(c, stem2, (70, 175, 85, 255), stroke=40)
    paint(c, flower, (255, 150, 200, 255), stroke=40)
    paint(c, center, (255, 215, 70, 255), stroke=20)

    # Saksı
    pot = new_mask()
    pd = ImageDraw.Draw(pot)
    pd.polygon([(600, 1260), (1448, 1260), (1330, 1880), (718, 1880)], fill=255)
    pd.rounded_rectangle([520, 1100, 1528, 1320], radius=60, fill=255)
    pot = pot.filter(ImageFilter.GaussianBlur(14)).point(lambda v: 255 if v > 128 else 0)
    paint(c, pot, vgradient((255, 150, 90), (215, 95, 60), 1100, 1880), stroke=60)
    rim = new_mask()
    ImageDraw.Draw(rim).rounded_rectangle([520, 1100, 1528, 1320], radius=60, fill=255)
    paint(c, rim, (255, 175, 110, 255))
    ImageDraw.Draw(c).line([(560, 1320), (1488, 1320)], fill=INK, width=34)
    soil = new_mask()
    ImageDraw.Draw(soil).ellipse([620, 1110, 1428, 1200], fill=255)
    paint(c, soil, (110, 70, 50, 255))

    # Saksı yüzü
    eyes = new_mask()
    d = ImageDraw.Draw(eyes)
    d.ellipse([790, 1460, 900, 1600], fill=255)
    d.ellipse([1148, 1460, 1258, 1600], fill=255)
    paint(c, eyes, INK)
    shine = new_mask()
    d = ImageDraw.Draw(shine)
    for ex in (790, 1148):
        d.ellipse([ex + 22, 1480, ex + 66, 1524], fill=255)
    paint(c, shine, WHITE)
    blush = new_mask()
    d = ImageDraw.Draw(blush)
    d.ellipse([680, 1610, 830, 1690], fill=255)
    d.ellipse([1218, 1610, 1368, 1690], fill=255)
    paint(c, blush, (255, 110, 120, 200))
    mouth = new_mask()
    ImageDraw.Draw(mouth).chord([950, 1560, 1098, 1720], start=0, end=180, fill=255)
    paint(c, mouth, INK)

    sparkle(c, 330, 380, 140, (255, 225, 90, 255))
    sparkle(c, 1780, 900, 110, WHITE)
    sparkle(c, 300, 1050, 80, (130, 220, 255, 255))
    return finish(c, "6_mutlu_filiz.png")


# ---------------------------------------------------------------------------
# 7) SAKİN KAPİBARA — başında portakal olan viral kapibara meme'i
# ---------------------------------------------------------------------------
def kapibara():
    c = new_layer()
    fur = vgradient((210, 155, 100), (170, 115, 70), 700, 1900)

    ears = new_mask()
    ed = ImageDraw.Draw(ears)
    ed.ellipse([430, 700, 650, 900], fill=255)
    ed.ellipse([1398, 700, 1618, 900], fill=255)
    head = new_mask()
    ImageDraw.Draw(head).rounded_rectangle([380, 780, 1668, 1860], radius=480, fill=255)
    both = Image.new("L", (S, S), 0)
    both.paste(255, (0, 0), ears)
    both.paste(255, (0, 0), head)
    paint(c, both, fur, stroke=65)
    inner = new_mask()
    ed = ImageDraw.Draw(inner)
    ed.ellipse([480, 750, 600, 860], fill=255)
    ed.ellipse([1448, 750, 1568, 860], fill=255)
    inner.paste(0, (0, 0), head)
    paint(c, inner, (140, 90, 55, 255))
    ImageDraw.Draw(c).arc([380, 780, 1668, 1860], start=200, end=340, fill=INK, width=26)

    # Burun bölgesi
    snout = new_mask()
    ImageDraw.Draw(snout).rounded_rectangle([640, 1330, 1408, 1820], radius=240, fill=255)
    paint(c, snout, (145, 95, 60, 255), stroke=26)
    nost = new_mask()
    nd = ImageDraw.Draw(nost)
    nd.rounded_rectangle([840, 1430, 940, 1500], radius=35, fill=255)
    nd.rounded_rectangle([1108, 1430, 1208, 1500], radius=35, fill=255)
    paint(c, nost, INK)
    d = ImageDraw.Draw(c)
    d.line([(1024, 1520), (1024, 1600)], fill=INK, width=24)
    d.arc([920, 1540, 1028, 1660], start=10, end=150, fill=INK, width=24)
    d.arc([1020, 1540, 1128, 1660], start=30, end=170, fill=INK, width=24)

    # Huzurlu kapalı gözler
    for ex in (720, 1328):
        d.arc([ex - 110, 1080, ex + 110, 1260], start=200, end=340, fill=INK, width=38)
    blush = new_mask()
    bd = ImageDraw.Draw(blush)
    bd.ellipse([470, 1260, 680, 1380], fill=255)
    bd.ellipse([1368, 1260, 1578, 1380], fill=255)
    paint(c, blush, (255, 130, 130, 200))

    # Başındaki portakal
    orange = new_mask()
    ImageDraw.Draw(orange).ellipse([784, 340, 1264, 820], fill=255)
    paint(c, orange, vgradient((255, 180, 60), (245, 120, 20), 340, 820), stroke=55)
    shine = new_mask()
    ImageDraw.Draw(shine).ellipse([870, 420, 980, 520], fill=255)
    paint(c, shine, (255, 255, 255, 170))
    dots = new_mask()
    dd = ImageDraw.Draw(dots)
    for x, y in ((1080, 470), (1150, 560), (1050, 640), (950, 700), (1170, 690)):
        dd.ellipse([x - 12, y - 12, x + 12, y + 12], fill=255)
    paint(c, dots, (225, 110, 20, 255))
    lf = new_mask()
    ImageDraw.Draw(lf).ellipse([1040, 200, 1340, 340], fill=255)
    lf = lf.rotate(25, center=(1190, 270), resample=Image.BICUBIC)
    paint(c, lf, (90, 190, 90, 255), stroke=34)
    ImageDraw.Draw(c).line([(1024, 350), (1060, 300)], fill=INK, width=30)

    sparkle(c, 330, 400, 140, (255, 225, 90, 255))
    sparkle(c, 1780, 500, 100, WHITE)
    sparkle(c, 1850, 1500, 90, (130, 220, 255, 255))
    sparkle(c, 200, 1550, 70, WHITE)
    return finish(c, "7_sakin_kapibara.png")


# ---------------------------------------------------------------------------
# Önizleme: blok Roblox avatarı üstünde 3 tasarım
# ---------------------------------------------------------------------------
def preview(items, name):
    """items: (görsel, gömlek rengi, etiket) listesi."""
    W, H = 80 + 620 * len(items), 760
    img = Image.new("RGBA", (W, H), (34, 36, 48, 255))
    d = ImageDraw.Draw(img)
    lab_font = ImageFont.truetype(FONT, 40)
    skin = (255, 214, 120)
    pants = (40, 60, 120)
    for i, (des, shirt, lab) in enumerate(items):
        cx = 350 + i * 620
        # Kafa
        d.rounded_rectangle([cx - 70, 70, cx + 70, 200], radius=30, fill=skin, outline=(0, 0, 0), width=4)
        d.ellipse([cx - 35, 115, cx - 15, 140], fill=(0, 0, 0))
        d.ellipse([cx + 15, 115, cx + 35, 140], fill=(0, 0, 0))
        d.arc([cx - 35, 130, cx + 35, 175], start=20, end=160, fill=(0, 0, 0), width=5)
        # Gövde
        d.rectangle([cx - 140, 210, cx + 140, 490], fill=shirt, outline=(0, 0, 0), width=4)
        # Kollar
        d.rectangle([cx - 285, 210, cx - 145, 490], fill=shirt, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 145, 210, cx + 285, 490], fill=shirt, outline=(0, 0, 0), width=4)
        d.rectangle([cx - 285, 440, cx - 145, 490], fill=skin, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 145, 440, cx + 285, 490], fill=skin, outline=(0, 0, 0), width=4)
        # Bacaklar
        d.rectangle([cx - 140, 495, cx - 3, 680], fill=pants, outline=(0, 0, 0), width=4)
        d.rectangle([cx + 3, 495, cx + 140, 680], fill=pants, outline=(0, 0, 0), width=4)
        # T-shirt görseli gövde önünde (Roblox'taki gibi gövdeyi kaplar)
        t = des.resize((276, 276), Image.LANCZOS)
        img.alpha_composite(t, (cx - 138, 212))
        w = d.textlength(lab, font=lab_font)
        d.text((cx - w / 2, 700), lab, font=lab_font, fill=(255, 255, 255))
    img.convert("RGB").save(os.path.join(HERE, name), optimize=True)


if __name__ == "__main__":
    preview([(kedi(), (70, 70, 80), "Sevimli Kedi"),
             (smiley(), (240, 240, 245), "Havalı Smiley"),
             (good_vibes(), (120, 180, 255), "Good Vibes")], "onizleme.png")
    preview([(tavsan(), (60, 60, 75), "Kawaii Tavşan"),
             (piksel_kalp(), (25, 25, 35), "Y2K Piksel Kalp"),
             (filiz(), (245, 240, 225), "Mutlu Filiz"),
             (kapibara(), (120, 200, 170), "Sakin Kapibara")], "onizleme_yeni.png")
    print("Tamam:", sorted(os.listdir(HERE)))

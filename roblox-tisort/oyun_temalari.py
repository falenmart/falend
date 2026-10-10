"""En popüler Roblox oyunlarının temalarından esinlenen T-shirt'ler.

Oyun adı, logosu veya karakteri KULLANILMAZ (Roblox telifli içerikleri reddeder).
Her tasarım, o oyunun herkesin tanıdığı temasını kendi çizimimizle anlatır.

Çalıştırma:  python3 roblox-tisort/oyun_temalari.py
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from olustur import (FONT, INK, S, WHITE, _over, dilate, finish, new_layer, new_mask, paint,
                     preview, sparkle, star_points, vgradient)


def smooth(mask, r=14):
    return mask.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 128 else 0)


def text_mask(txt, size, cy, cx=S // 2, font=FONT):
    m = new_mask()
    f = ImageFont.truetype(font, size)
    d = ImageDraw.Draw(m)
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, cy), txt, font=f, fill=255, anchor="lm")
    return m


def banner(c, txt, cy, size, fill, text_color=WHITE, pad_x=90, h=None):
    """Yazının arkasına kalın konturlu bir şerit koyar."""
    f = ImageFont.truetype(FONT, size)
    w = ImageDraw.Draw(new_mask()).textlength(txt, font=f)
    h = h or int(size * 1.25)
    b = new_mask()
    ImageDraw.Draw(b).rounded_rectangle([S // 2 - w / 2 - pad_x, cy - h // 2, S // 2 + w / 2 + pad_x, cy + h // 2],
                                        radius=h // 2, fill=255)
    paint(c, b, fill, stroke=50)
    paint(c, text_mask(txt, size, cy), text_color)


def flame(cx, cy, w, h):
    m = new_mask()
    d = ImageDraw.Draw(m)
    d.ellipse([cx - w, cy - w, cx + w, cy + w], fill=255)
    d.polygon([(cx - w * 0.97, cy - w * 0.25), (cx, cy - h), (cx + w * 0.97, cy - w * 0.25)], fill=255)
    return smooth(m, 16)


def intersect(a, b):
    return ImageChops.multiply(a, b)


# ---------------------------------------------------------------------------
# 8) ŞERİF YILDIZI — Murder Mystery 2'nin Şerif rolü
# ---------------------------------------------------------------------------
def serif():
    c = new_layer()
    gold = vgradient((255, 230, 110), (235, 150, 30), 200, 1850)
    star = new_mask()
    d = ImageDraw.Draw(star)
    pts = star_points(1024, 1000, 820, 500, n=6, rot=math.pi / 6)
    d.polygon(pts, fill=255)
    for x, y in pts[::2]:
        d.ellipse([x - 105, y - 105, x + 105, y + 105], fill=255)
    star = smooth(star, 10)

    glow = dilate(star, 90).filter(ImageFilter.GaussianBlur(60)).point(lambda v: int(v * 0.6))
    paint(c, glow, (255, 210, 80, 255))
    paint(c, star, gold, stroke=60)

    inner = new_mask()
    ImageDraw.Draw(inner).polygon(star_points(1024, 1000, 620, 380, n=6, rot=math.pi / 6), fill=255)
    paint(c, smooth(inner, 10), vgradient((255, 245, 170), (250, 185, 50), 380, 1620))

    ring = new_mask()
    ImageDraw.Draw(ring).ellipse([764, 740, 1284, 1260], fill=255)
    paint(c, ring, vgradient((250, 190, 50), (210, 120, 20), 740, 1260), stroke=36)
    small = new_mask()
    ImageDraw.Draw(small).polygon(star_points(1024, 1010, 190, 80, n=5), fill=255)
    paint(c, smooth(small, 6), (255, 245, 190, 255), stroke=26)

    # Parlama
    shine = new_mask()
    ImageDraw.Draw(shine).polygon([(620, 560), (760, 520), (560, 1000), (470, 960)], fill=255)
    _over(c, intersect(shine, star), (255, 255, 255, 140))

    banner(c, "SHERIFF", 1690, 230, vgradient((60, 90, 200), (30, 50, 140), 1560, 1820))
    sparkle(c, 300, 320, 120, WHITE)
    sparkle(c, 1780, 330, 90, (255, 240, 120, 255))
    return finish(c, "8_serif_yildizi.png")


# ---------------------------------------------------------------------------
# 9) GECE KAMPI — 99 Nights in the Forest (ormanda kamp ateşi, ay, çam ağaçları)
# ---------------------------------------------------------------------------
def gece_kampi():
    c = new_layer()
    circle = new_mask()
    ImageDraw.Draw(circle).ellipse([224, 120, 1824, 1720], fill=255)
    paint(c, circle, vgradient((20, 25, 70), (90, 50, 130), 120, 1720), stroke=60)

    # Yıldızlar
    stars = new_mask()
    sd = ImageDraw.Draw(stars)
    for x, y, r in ((520, 420, 16), (700, 300, 10), (900, 480, 12), (1150, 330, 14), (620, 640, 10),
                    (1000, 700, 9), (430, 760, 12), (1500, 760, 10)):
        sd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    _over(c, stars, WHITE)
    sparkle(c, 820, 360, 50, WHITE, stroke=0)

    # Hilal ay
    moon = new_mask()
    ImageDraw.Draw(moon).ellipse([1250, 300, 1590, 640], fill=255)
    cut = new_mask()
    ImageDraw.Draw(cut).ellipse([1150, 230, 1490, 570], fill=255)
    moon = ImageChops.subtract(moon, cut)
    mglow = dilate(moon, 50).filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.5))
    _over(c, mglow, (255, 240, 170, 255))
    paint(c, moon, (255, 235, 140, 255), stroke=26)

    # Çam ağaçları (daireyle kırpılır)
    trees = new_mask()
    td = ImageDraw.Draw(trees)
    for tx, base, hgt in ((360, 1600, 900), (560, 1650, 700), (1690, 1600, 920), (1490, 1660, 680)):
        for k in range(3):
            w = 230 - k * 50
            yb = base - k * hgt * 0.27
            td.polygon([(tx - w, yb), (tx, yb - hgt * 0.45), (tx + w, yb)], fill=255)
        td.rectangle([tx - 30, base - 10, tx + 30, base + 120], fill=255)
    td.ellipse([100, 1440, 1948, 2000], fill=255)  # zemin
    trees = intersect(trees, circle)
    _over(c, trees, (15, 45, 45, 255))

    # Ateşin ışığı
    light = new_mask()
    ImageDraw.Draw(light).ellipse([524, 1000, 1524, 1800], fill=255)
    light = intersect(light.filter(ImageFilter.GaussianBlur(120)), circle).point(lambda v: int(v * 0.55))
    _over(c, light, (255, 140, 40, 255))

    # Odunlar
    logs = new_mask()
    for ang in (18, -18):
        m = new_mask()
        ImageDraw.Draw(m).rounded_rectangle([744, 1440, 1304, 1550], radius=55, fill=255)
        logs.paste(255, (0, 0), m.rotate(ang, center=(1024, 1495), resample=Image.BICUBIC))
    paint(c, logs, vgradient((170, 100, 55), (110, 60, 35), 1380, 1620), stroke=34)

    # Alevler
    paint(c, flame(1024, 1340, 210, 700), vgradient((255, 120, 40), (230, 40, 30), 700, 1550), stroke=40)
    paint(c, flame(1024, 1380, 150, 520), vgradient((255, 200, 60), (255, 120, 30), 860, 1530))
    paint(c, flame(1024, 1410, 85, 330), (255, 245, 170, 255))
    for x, y, r in ((860, 820, 16), (1200, 760, 12), (1120, 620, 10)):
        e = new_mask()
        ImageDraw.Draw(e).ellipse([x - r, y - r, x + r, y + r], fill=255)
        _over(c, e, (255, 200, 80, 255))

    banner(c, "NIGHT SURVIVOR", 1790, 160, vgradient((255, 140, 40), (220, 70, 30), 1690, 1890))
    return finish(c, "9_gece_kampi.png")


# ---------------------------------------------------------------------------
# 10) SİHİRLİ MEYVE — Blox Fruits (süper güç veren girdaplı meyve)
# ---------------------------------------------------------------------------
def sihirli_meyve():
    c = new_layer()
    body = new_mask()
    bd = ImageDraw.Draw(body)
    bd.ellipse([380, 560, 1080, 1780], fill=255)
    bd.ellipse([968, 560, 1668, 1780], fill=255)
    bd.ellipse([430, 700, 1618, 1840], fill=255)
    body = smooth(body, 30)

    aura = dilate(body, 140).filter(ImageFilter.GaussianBlur(90)).point(lambda v: int(v * 0.7))
    _over(c, aura, (190, 90, 255, 255))
    paint(c, body, vgradient((190, 110, 255), (95, 40, 190), 560, 1840), stroke=60)

    # Girdap desenleri
    swirl = new_mask()
    sd = ImageDraw.Draw(swirl)
    for cx, cy, r in ((720, 1000, 200), (1300, 960, 210), (1010, 1430, 230), (600, 1450, 150), (1450, 1420, 150)):
        pts = []
        for i in range(160):
            t = i / 159 * 3.2 * math.pi
            rr = r * t / (3.2 * math.pi)
            pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
        sd.line(pts, fill=255, width=46, joint="curve")
    _over(c, intersect(swirl, body), (230, 190, 255, 255))

    # Parlama
    hi = new_mask()
    ImageDraw.Draw(hi).ellipse([560, 700, 800, 860], fill=255)
    _over(c, hi.rotate(30, center=(680, 780)).filter(ImageFilter.GaussianBlur(6)), (255, 255, 255, 170))

    # Kıvırcık sap ve yaprak
    stem = new_mask()
    pts = []
    for i in range(80):
        t = i / 79
        pts.append((1024 + 120 * math.sin(t * 2.6 * math.pi) * (1 - t), 680 - t * 330))
    ImageDraw.Draw(stem).line(pts, fill=255, width=70, joint="curve")
    paint(c, stem, (60, 150, 70, 255), stroke=34)
    leaf = new_mask()
    ImageDraw.Draw(leaf).ellipse([1040, 330, 1440, 500], fill=255)
    leaf = leaf.rotate(-25, center=(1060, 420), resample=Image.BICUBIC)
    paint(c, leaf, vgradient((120, 220, 100), (60, 160, 70), 280, 560), stroke=40)

    sparkle(c, 300, 420, 140, (255, 225, 90, 255))
    sparkle(c, 1780, 380, 110, WHITE)
    sparkle(c, 1850, 1600, 100, (255, 170, 255, 255))
    sparkle(c, 210, 1500, 80, WHITE)
    return finish(c, "10_sihirli_meyve.png")


# ---------------------------------------------------------------------------
# 11) ÇATLAYAN YUMURTA — Adopt Me / Steal an Egg (yumurtadan çıkan evcil hayvan)
# ---------------------------------------------------------------------------
def yumurta():
    c = new_layer()
    cx, cy, w, h = 1024, 1150, 600, 760

    def egg_points(dx=0, dy=0):
        pts = []
        for i in range(240):
            t = 2 * math.pi * i / 240
            x = w * math.sin(t) * (1 - 0.16 * math.cos(t))
            y = -h * math.cos(t)
            pts.append((cx + x + dx, cy + y + dy))
        return pts

    egg = new_mask()
    ImageDraw.Draw(egg).polygon(egg_points(), fill=255)

    # Zikzak çatlak
    zig = [(0, 980)]
    for k in range(9):
        zig.append((380 + k * 160, 900 if k % 2 == 0 else 1020))
    zig.append((S, 960))
    top_region = new_mask()
    ImageDraw.Draw(top_region).polygon([(0, 0), (S, 0)] + zig[::-1], fill=255)
    top = intersect(egg, top_region)
    bottom = ImageChops.subtract(egg, top_region)

    shell = vgradient((200, 255, 230), (120, 220, 200), 380, 1910)
    spots = new_mask()
    sd = ImageDraw.Draw(spots)
    for x, y, r in ((780, 1300, 80), (1250, 1450, 110), (1000, 1680, 70), (900, 650, 70), (1200, 560, 50),
                    (1350, 1200, 60), (650, 1580, 55)):
        sd.ellipse([x - r, y - r, x + r, y + r], fill=255)

    # İçerisi (karanlık) ve bakan gözler
    paint(c, bottom, shell, stroke=60)
    _over(c, intersect(spots, bottom), (255, 170, 210, 255))
    inside = new_mask()
    ImageDraw.Draw(inside).ellipse([470, 780, 1578, 1200], fill=255)
    inside = intersect(inside, bottom)
    paint(c, inside, vgradient((20, 15, 40), (60, 40, 90), 880, 1200))
    eyes = new_mask()
    ed = ImageDraw.Draw(eyes)
    ed.ellipse([830, 990, 930, 1100], fill=255)
    ed.ellipse([1118, 990, 1218, 1100], fill=255)
    eyes = intersect(eyes, inside)
    _over(c, dilate(eyes, 30).filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * 0.6)),
          (255, 240, 120, 255))
    _over(c, eyes, (255, 245, 170, 255))
    shines = new_mask()
    for x in (852, 1140):
        ImageDraw.Draw(shines).ellipse([x, 1008, x + 36, 1044], fill=255)
    _over(c, shines, WHITE)

    # Üst kabuk havaya kalkmış
    lifted = top.rotate(-14, center=(cx, 900), resample=Image.BICUBIC)
    moved = new_mask()
    moved.paste(lifted, (60, -260))
    paint(c, moved, shell, stroke=60)
    sp_top = new_mask()
    sp_top.paste(intersect(spots, top).rotate(-14, center=(cx, 900), resample=Image.BICUBIC), (60, -260))
    _over(c, sp_top, (255, 170, 210, 255))

    # Parlama
    hi = new_mask()
    ImageDraw.Draw(hi).ellipse([560, 1180, 680, 1460], fill=255)
    _over(c, intersect(hi.filter(ImageFilter.GaussianBlur(10)), bottom), (255, 255, 255, 150))

    # Hareket çizgileri ve ışıltılar
    d = ImageDraw.Draw(c)
    for x0, y0, x1, y1 in ((330, 600, 230, 520), (300, 760, 180, 760), (1730, 520, 1830, 440), (1760, 690, 1880, 690)):
        d.line([(x0, y0), (x1, y1)], fill=INK, width=40)
    sparkle(c, 400, 300, 120, (255, 225, 90, 255))
    sparkle(c, 1800, 1300, 110, (255, 170, 255, 255))
    sparkle(c, 250, 1400, 80, WHITE)
    return finish(c, "11_catlayan_yumurta.png")


# ---------------------------------------------------------------------------
# 12) AÇMA O KAPIYI — Doors (aralık kapıdan bakan parlayan gözler)
# ---------------------------------------------------------------------------
def kapi():
    c = new_layer()
    frame = new_mask()
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle([470, 180, 1578, 1720], radius=60, fill=255)
    paint(c, frame, vgradient((120, 80, 55), (80, 50, 35), 180, 1720), stroke=60)
    opening = new_mask()
    ImageDraw.Draw(opening).rectangle([580, 290, 1468, 1720], fill=255)
    paint(c, opening, (12, 10, 20, 255))

    # Gölgeden bakan gözler
    eyes = new_mask()
    ed = ImageDraw.Draw(eyes)
    ed.ellipse([1190, 820, 1290, 900], fill=255)
    ed.ellipse([1340, 820, 1440, 900], fill=255)
    _over(c, dilate(eyes, 40).filter(ImageFilter.GaussianBlur(30)), (255, 230, 90, 255))
    _over(c, eyes, (255, 250, 200, 255))
    pupils = new_mask()
    pd = ImageDraw.Draw(pupils)
    pd.ellipse([1228, 830, 1252, 890], fill=255)
    pd.ellipse([1378, 830, 1402, 890], fill=255)
    _over(c, pupils, INK)
    grin = new_mask()
    ImageDraw.Draw(grin).chord([1200, 960, 1430, 1100], start=0, end=180, fill=255)
    _over(c, grin, (230, 230, 240, 220))

    # Aralık kapı kanadı (perspektif)
    panel = new_mask()
    ImageDraw.Draw(panel).polygon([(580, 290), (1140, 370), (1140, 1650), (580, 1720)], fill=255)
    paint(c, panel, vgradient((185, 120, 75), (140, 85, 50), 290, 1720), stroke=30)
    insets = new_mask()
    idd = ImageDraw.Draw(insets)
    idd.polygon([(660, 420), (1060, 470), (1060, 900), (660, 900)], fill=255)
    idd.polygon([(660, 1010), (1060, 1010), (1060, 1540), (660, 1590)], fill=255)
    paint(c, insets, vgradient((160, 100, 60), (125, 75, 45), 420, 1590), stroke=20)
    knob = new_mask()
    ImageDraw.Draw(knob).ellipse([1020, 960, 1100, 1040], fill=255)
    paint(c, knob, (255, 200, 60, 255), stroke=20)
    # Kapı numarası tabelası
    plate = new_mask()
    ImageDraw.Draw(plate).rounded_rectangle([760, 560, 960, 700], radius=24, fill=255)
    paint(c, plate, (230, 200, 140, 255), stroke=18)
    paint(c, text_mask("?", 120, 632, cx=860), INK)

    banner(c, "DON'T OPEN", 1840, 190, vgradient((235, 50, 50), (170, 20, 30), 1720, 1960))
    return finish(c, "12_acma_kapiyi.png")


# ---------------------------------------------------------------------------
# 13) RP EVİ — Brookhaven RP (rol yapma: kendi evin, kendi hayatın)
# ---------------------------------------------------------------------------
def rp_evi():
    c = new_layer()
    sky = new_mask()
    ImageDraw.Draw(sky).ellipse([224, 180, 1824, 1780], fill=255)
    paint(c, sky, vgradient((150, 215, 255), (200, 240, 255), 180, 1500), stroke=60)
    grass = new_mask()
    ImageDraw.Draw(grass).ellipse([0, 1420, S, 2300], fill=255)
    _over(c, intersect(grass, sky), (110, 205, 110, 255))

    # Bulutlar
    cloud = new_mask()
    cd = ImageDraw.Draw(cloud)
    for x, y, r in ((520, 520, 90), (620, 470, 110), (730, 530, 80), (1420, 430, 70), (1510, 390, 90), (1600, 440, 70)):
        cd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    _over(c, cloud, WHITE)

    # Ev
    walls = new_mask()
    ImageDraw.Draw(walls).rectangle([600, 950, 1448, 1560], fill=255)
    paint(c, walls, vgradient((255, 215, 225), (255, 180, 200), 950, 1560), stroke=45)
    chimney = new_mask()
    ImageDraw.Draw(chimney).rectangle([1220, 600, 1340, 860], fill=255)
    paint(c, chimney, (200, 110, 90, 255), stroke=40)
    roof = new_mask()
    ImageDraw.Draw(roof).polygon([(500, 990), (1024, 560), (1548, 990)], fill=255)
    paint(c, smooth(roof, 10), vgradient((110, 140, 255), (70, 90, 210), 560, 990), stroke=45)
    heart_win = new_mask()
    from olustur import heart_points
    ImageDraw.Draw(heart_win).polygon(heart_points(1024, 820, 170), fill=255)
    paint(c, heart_win, (255, 120, 160, 255), stroke=22)

    door = new_mask()
    ImageDraw.Draw(door).rounded_rectangle([930, 1240, 1118, 1560], radius=90, fill=255)
    paint(c, door, (150, 95, 60, 255), stroke=30)
    ImageDraw.Draw(c).ellipse([1070, 1400, 1100, 1430], fill=(255, 210, 80, 255))
    wins = new_mask()
    wd = ImageDraw.Draw(wins)
    wd.rounded_rectangle([680, 1070, 850, 1240], radius=20, fill=255)
    wd.rounded_rectangle([1198, 1070, 1368, 1240], radius=20, fill=255)
    paint(c, wins, (255, 240, 150, 255), stroke=30)
    d = ImageDraw.Draw(c)
    for x0 in (680, 1198):
        d.line([(x0 + 85, 1070), (x0 + 85, 1240)], fill=INK, width=20)
        d.line([(x0, 1155), (x0 + 170, 1155)], fill=INK, width=20)

    # Çit ve çiçekler
    for x in range(330, 1750, 110):
        if 560 < x < 1488:
            continue
        p = new_mask()
        ImageDraw.Draw(p).polygon([(x - 35, 1600), (x - 35, 1420), (x, 1380), (x + 35, 1420), (x + 35, 1600)], fill=255)
        paint(c, intersect(p, sky), WHITE, stroke=18)
    for x, col in ((660, (255, 90, 130)), (760, (255, 210, 60)), (1290, (180, 120, 255)), (1390, (255, 90, 130))):
        f = new_mask()
        ImageDraw.Draw(f).ellipse([x - 40, 1580, x + 40, 1660], fill=255)
        paint(c, f, col + (255,), stroke=16)

    banner(c, "RP LIFE", 1820, 220, vgradient((255, 110, 170), (220, 60, 140), 1690, 1950))
    sparkle(c, 330, 320, 110, (255, 225, 90, 255))
    sparkle(c, 1780, 300, 90, WHITE)
    return finish(c, "13_rp_evi.png")


if __name__ == "__main__":
    items = [(serif(), (40, 40, 55), "Şerif Yıldızı"),
             (gece_kampi(), (30, 60, 50), "Gece Kampı"),
             (sihirli_meyve(), (240, 240, 245), "Sihirli Meyve"),
             (yumurta(), (255, 220, 235), "Çatlayan Yumurta"),
             (kapi(), (25, 25, 35), "Açma O Kapıyı"),
             (rp_evi(), (250, 245, 230), "RP Evi")]
    preview(items[:3], "onizleme_oyunlar_1.png")
    preview(items[3:], "onizleme_oyunlar_2.png")
    print("Tamam")

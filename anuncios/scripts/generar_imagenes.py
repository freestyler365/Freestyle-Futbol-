#!/usr/bin/env python3
"""Genera las imágenes de anuncio del porta-balón (feed 4:5 y story 9:16).

Uso:  python3 anuncios/scripts/generar_imagenes.py
Lee las fotos de anuncios/fuentes/ y escribe PNG/JPG en anuncios/imagenes/.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "fuentes"
OUT = ROOT / "imagenes"
OUT.mkdir(exist_ok=True)

FONT_DIR = Path("/usr/share/fonts/opentype/inter")
F_BLACK = str(FONT_DIR / "InterDisplay-Black.otf")
F_BOLD = str(FONT_DIR / "Inter-Bold.otf")
F_SEMI = str(FONT_DIR / "Inter-SemiBold.otf")
F_MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
if not Path(F_MONO).exists():
    import glob
    hits = glob.glob("/usr/share/fonts/**/JetBrainsMono*Bold*.ttf", recursive=True)
    F_MONO = hits[0] if hits else F_BOLD

INK = (11, 11, 11)
WHITE = (250, 250, 248)
RED = (225, 6, 0)
STEEL = (190, 194, 199)

SIZES = {"feed": (1080, 1350), "story": (1080, 1920)}
URL = "FRE365TYLE.COM"


# ---------- utilidades ----------
def load(name, crop=None):
    im = Image.open(SRC / name).convert("RGB")
    if crop:
        im = im.crop(crop)
    return im


def cover(im, size, focus=(0.5, 0.5)):
    """Recorta/escala tipo CSS object-fit: cover, respetando un punto focal."""
    tw, th = size
    s = max(tw / im.width, th / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = int((im.width - tw) * focus[0])
    y = int((im.height - th) * focus[1])
    return im.crop((x, y, x + tw, y + th))


def grade(im, contrast=1.08, sat=1.06, sharp=1.25):
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = ImageEnhance.Color(im).enhance(sat)
    return ImageEnhance.Sharpness(im).enhance(sharp)


def gradient(size, top_alpha, bottom_alpha, start=0.0, end=1.0, color=INK):
    w, h = size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        if t <= start:
            a = top_alpha
        elif t >= end:
            a = bottom_alpha
        else:
            k = (t - start) / (end - start)
            k = k * k * (3 - 2 * k)  # smoothstep
            a = top_alpha + (bottom_alpha - top_alpha) * k
        g.putpixel((0, y), int(a))
    layer = Image.new("RGBA", size, color + (0,))
    layer.putalpha(g.resize(size))
    return layer


def text_w(font, s, track=0):
    return sum(font.getlength(c) for c in s) + track * (len(s) - 1)


def draw_tracked(d, xy, s, font, fill, track=0):
    x, y = xy
    for c in s:
        d.text((x, y), c, font=font, fill=fill)
        x += font.getlength(c) + track


def wrap(s, font, maxw, track=0):
    words, lines, cur = s.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if text_w(font, test, track) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def headline(d, s, box, max_size, min_size=48, fill=WHITE, accent_words=(),
             max_lines=4, lh=0.92, align="left"):
    """Titular en mayúsculas, ajusta tamaño para caber en box=(x,y,w).
    Devuelve la coordenada y final."""
    x, y, w = box
    s = s.upper()
    size = max_size
    while size >= min_size:
        f = ImageFont.truetype(F_BLACK, size)
        track = -size * 0.02
        lines = wrap(s, f, w, track)
        if len(lines) <= max_lines:
            break
        size -= 4
    for ln in lines:
        lx = x if align == "left" else x + (w - text_w(f, ln, track)) / 2
        cx = lx
        for i, word in enumerate(ln.split(" ")):
            col = RED if word.strip(".,!?¿¡") in accent_words else fill
            draw_tracked(d, (cx, y), word, f, col, track)
            cx += text_w(f, word + " ", track) + track
        y += int(size * lh)
    return y


def body(d, s, xy, w, size=36, fill=WHITE, font=F_SEMI, lh=1.3, align="left"):
    f = ImageFont.truetype(font, size)
    x, y = xy
    for ln in wrap(s, f, w):
        lx = x if align == "left" else x + (w - f.getlength(ln)) / 2
        d.text((lx, y), ln, font=f, fill=fill)
        y += int(size * lh)
    return y


def tag(d, s, xy, size=26, bg=RED, fg=WHITE, pad=(18, 10)):
    f = ImageFont.truetype(F_MONO, size)
    s = s.upper()
    tw = text_w(f, s, 2)
    x, y = xy
    d.rectangle((x, y, x + tw + pad[0] * 2, y + size + pad[1] * 2), fill=bg)
    draw_tracked(d, (x + pad[0], y + pad[1] - size * 0.08), s, f, fg, 2)
    return x + tw + pad[0] * 2


def cta(d, s, y, W, size=34, bg=WHITE, fg=INK, center=True, x=72):
    f = ImageFont.truetype(F_BLACK, size)
    s = s.upper()
    tw = text_w(f, s, 1)
    pw, ph = tw + 76, size + 44
    x0 = (W - pw) // 2 if center else x
    d.rounded_rectangle((x0, y, x0 + pw, y + ph), radius=ph // 2, fill=bg)
    draw_tracked(d, (x0 + 38, y + 20 - size * 0.1), s, f, fg, 1)
    # flecha
    return y + ph


def brand(d, W, H, y=None, color=WHITE):
    """Firma 365 en la esquina superior derecha."""
    f = ImageFont.truetype(F_BLACK, 44)
    fs = ImageFont.truetype(F_MONO, 16)
    y = 56 if y is None else y
    s1, s2, s3 = "3", "6", "5"
    total = f.getlength("365")
    x = W - 72 - total
    d.text((x, y), s1, font=f, fill=color)
    x += f.getlength(s1)
    d.text((x, y), s2, font=f, fill=RED)
    x += f.getlength(s2)
    d.text((x, y), s3, font=f, fill=color)
    sub = "EVERYDAY FREESTYLE"
    d.text((W - 72 - fs.getlength(sub), y + 54), sub, font=fs, fill=color)


def chain_rule(d, x, y, w, color=STEEL):
    """Línea tipo cadena (eslabones) como separador gráfico."""
    lw, lh, gap = 34, 16, -6
    cx = x
    i = 0
    while cx + lw <= x + w:
        if i % 2 == 0:
            d.rounded_rectangle((cx, y, cx + lw, y + lh), radius=8, outline=color, width=4)
        else:
            d.line((cx, y + lh // 2, cx + lw, y + lh // 2), fill=color, width=4)
        cx += lw + gap
        i += 1


def save(im, name):
    im = im.convert("RGB")
    im.save(OUT / f"{name}.png", optimize=True)
    im.save(OUT / f"{name}.jpg", quality=92)
    print("✓", name)


# ---------- fuentes recortadas ----------
def src_puesto():      # persona con el porta-balón cruzado (captura de pantalla)
    return load("foto_puesto.jpg", (0, 362, 923, 1950))


def src_pared365():    # porta-balón colgado en la pared 365 (captura)
    return load("foto_pared_365.jpg", (0, 252, 923, 1876))


def src_model(name):   # fotos 2000x2000 sin el título superior ni el logo
    return load(f"foto_{name}.jpg", (330, 500, 1830, 1880))


# ---------- creativos ----------
def ad_manos_libres(fmt):
    W, H = SIZES[fmt]
    im = grade(cover(src_puesto(), (W, H), (0.5, 0.35 if fmt == "feed" else 0.5)))
    im = im.convert("RGBA")
    im.alpha_composite(gradient((W, H), 150, 0, 0.0, 0.28))
    im.alpha_composite(gradient((W, H), 0, 245, 0.48, 0.86))
    d = ImageDraw.Draw(im)
    tag(d, "Porta-balón + correa", (72, 64))
    brand(d, W, H)
    y0 = H - (560 if fmt == "feed" else 700)
    y = headline(d, "Manos libres. Estilo completo.", (72, y0, W - 144), 116,
                 accent_words=("LIBRES",))
    y = body(d, "Cuélgalo cruzado y llega a la cancha, al parque o al spot con tu balón listo.",
             (72, y + 30), W - 220, 36, STEEL)
    cta(d, f"Pídelo en {URL}", y + 36, W, center=False)
    save(im, f"01_manos_libres_{fmt}")


def ad_virus(fmt):
    W, H = SIZES[fmt]
    base = Image.new("RGBA", (W, H), INK + (255,))
    photo_h = int(H * (0.66 if fmt == "feed" else 0.62))
    ph = grade(cover(src_model("virus"), (W, photo_h), (0.5, 0.3)), sharp=1.35)
    base.paste(ph, (0, 0))
    base.alpha_composite(gradient((W, H), 0, 255, (photo_h - 260) / H, photo_h / H))
    d = ImageDraw.Draw(base)
    tag(d, "Modelo VIRUS", (72, 64))
    brand(d, W, H, color=INK)
    y = headline(d, "Tu balón también se viste.", (72, photo_h - 150, W - 144), 112,
                 accent_words=("VISTE.",))
    chain_rule(d, 72, y + 22, 420)
    y = body(d, "Triple línea de estoperoles + cadena metálica. El porta-balón más rudo de la colección.",
             (72, y + 70), W - 180, 34, STEEL)
    cta(d, f"Pídelo en {URL}", y + 34, W, center=False)
    save(base, f"02_virus_{fmt}")


def ad_tres_estilos(fmt):
    W, H = SIZES[fmt]
    base = Image.new("RGBA", (W, H), INK + (255,))
    d = ImageDraw.Draw(base)
    top = 60
    tag(d, "3 estilos", (72, top))
    brand(d, W, H)
    y = headline(d, "Elige tu nivel de actitud.", (72, top + 110, W - 144), 104,
                 accent_words=("ACTITUD.",))
    models = [("elemental", "ELEMENTAL", "Liso"),
              ("balance", "BALANCE", "Estoperoles"),
              ("virus", "VIRUS", "Full metal")]
    gap = 18
    cw = (W - 144 - gap * 2) // 3
    ch = int(cw * (1.55 if fmt == "feed" else 2.75))
    cy = y + (40 if fmt == "feed" else 90)
    fl = ImageFont.truetype(F_BLACK, 34)
    fs = ImageFont.truetype(F_MONO, 20)
    for i, (src, name, desc) in enumerate(models):
        cx = 72 + i * (cw + gap)
        card = grade(cover(src_model(src), (cw, ch), (0.5, 0.35)), sharp=1.3)
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw, ch), 22, fill=255)
        base.paste(card, (cx, cy), mask)
        ly = cy + ch + 22
        d.text((cx, ly), name, font=fl, fill=WHITE if i < 2 else RED)
        d.text((cx, ly + 46), desc.upper(), font=fs, fill=STEEL)
    cta(d, f"Elige el tuyo en {URL}", H - (150 if fmt == "feed" else 230), W, 32)
    save(base, f"03_tres_estilos_{fmt}")


def ad_coleccion(fmt):
    W, H = SIZES[fmt]
    im = grade(cover(load("frame_7.5.png"), (W, H), (0.5, 0.5)), 1.1, 1.12, 1.4).convert("RGBA")
    im.alpha_composite(gradient((W, H), 225, 0, 0.0, 0.42))
    im.alpha_composite(gradient((W, H), 0, 200, 0.7, 1.0))
    d = ImageDraw.Draw(im)
    brand(d, W, H)
    tag(d, "Para coleccionistas", (72, 64))
    y = headline(d, "Tu colección merece una pared.", (72, 160, W - 144), 116,
                 accent_words=("PARED.",))
    body(d, "Cuélgalos. Exhíbelos. Llévalos.", (72, y + 30), W - 144, 40, WHITE, F_BOLD)
    cta(d, f"Arma tu pared en {URL}", H - (160 if fmt == "feed" else 240), W, 32)
    save(im, f"04_coleccion_{fmt}")


def ad_todos_los_balones(fmt):
    W, H = SIZES[fmt]
    im = grade(cover(load("frame_11.0.png"), (W, H), (0.5, 0.4)), 1.1, 1.08, 1.4).convert("RGBA")
    im.alpha_composite(gradient((W, H), 0, 245, 0.55, 0.9))
    d = ImageDraw.Draw(im)
    brand(d, W, H)
    y0 = H - (470 if fmt == "feed" else 640)
    fb = ImageFont.truetype(F_BLACK, 96 if fmt == "feed" else 104)
    y = y0
    for word, col in (("FÚTBOL.", WHITE), ("BÁSQUET.", WHITE), ("FREESTYLE.", RED)):
        draw_tracked(d, (72, y), word, fb, col, -2)
        y += int(fb.size * 0.92)
    y = body(d, "Un porta-balón para todos tus balones.", (72, y + 16), W - 144, 36, STEEL)
    cta(d, f"Pídelo en {URL}", y + 30, W, center=False)
    save(im, f"05_todos_los_balones_{fmt}")


def ad_declaracion(fmt):
    W, H = SIZES[fmt]
    im = grade(cover(src_pared365(), (W, H), (0.5, 0.55)), 1.08, 1.1, 1.3).convert("RGBA")
    im.alpha_composite(gradient((W, H), 0, 250, 0.5, 0.88))
    d = ImageDraw.Draw(im)
    tag(d, "Hecho para freestylers", (72, 64))
    y0 = H - (520 if fmt == "feed" else 660)
    y = headline(d, "No es una red. Es una declaración.", (72, y0, W - 144), 104,
                 accent_words=("DECLARACIÓN.",))
    y = body(d, "Correas, cadena y mosquetones. Tu balón, colgado con estilo.",
             (72, y + 30), W - 180, 34, STEEL)
    cta(d, f"Pídelo en {URL}", y + 32, W, center=False)
    save(im, f"06_declaracion_{fmt}")


if __name__ == "__main__":
    for fmt in SIZES:
        ad_manos_libres(fmt)
        ad_virus(fmt)
        ad_tres_estilos(fmt)
        ad_coleccion(fmt)
        ad_todos_los_balones(fmt)
        ad_declaracion(fmt)

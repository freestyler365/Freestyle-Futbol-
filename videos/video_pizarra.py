#!/usr/bin/env python3
"""Video vertical estilo pizarra (1080x1920, 15 s): ¿Por qué practicar freestyle fútbol?

Uso: python3 video_pizarra.py [salida.mp4]
Requiere Pillow, numpy y ffmpeg.
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 15
SS = 2  # supersampling para bordes suaves
BG = (247, 245, 239)
INK = (27, 27, 27)
RED = (230, 57, 70)
BLUE = (29, 127, 230)
GREEN = (42, 157, 110)
FONT_BLACK = "/usr/share/fonts/truetype/inter/Inter-Black.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/inter/Inter-Bold.ttf"


def find_font(name, fallback):
    for root, _, files in os.walk("/usr/share/fonts"):
        if name in files:
            return os.path.join(root, name)
    return fallback


FONT_BLACK = find_font("InterDisplay-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_BOLD = find_font("Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


# ---------- utilidades de trazo ----------
def wobble(pts, amt=2.5, seed=0):
    rnd = random.Random(seed)
    return [(x + rnd.uniform(-amt, amt), y + rnd.uniform(-amt, amt)) for x, y in pts]


def circle(cx, cy, r, start=-90, sweep=360, n=72, seed=0):
    pts = []
    for i in range(n + 1):
        a = math.radians(start + sweep * i / n)
        rr = r * (1 + 0.015 * math.sin(3 * a + seed))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def line(x1, y1, x2, y2, n=12):
    return [(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n + 1)]


def arrow_head(x, y, ang, size=34):
    a1, a2 = math.radians(ang + 150), math.radians(ang - 150)
    return [
        [(x + size * math.cos(a1), y + size * math.sin(a1)), (x, y)],
        [(x, y), (x + size * math.cos(a2), y + size * math.sin(a2))],
    ]


def ball(cx, cy, r, color=INK, seed=0):
    strokes = [(circle(cx, cy, r, seed=seed), color, 11)]
    pr = r * 0.32
    pent = [(cx + pr * math.cos(math.radians(-90 + 72 * i)), cy + pr * math.sin(math.radians(-90 + 72 * i)))
            for i in range(6)]
    strokes.append((pent, color, 9))
    for i in range(5):
        a = math.radians(-90 + 72 * i)
        strokes.append((line(cx + pr * math.cos(a), cy + pr * math.sin(a),
                             cx + r * 0.93 * math.cos(a), cy + r * 0.93 * math.sin(a), 6), color, 8))
    return strokes


def polylen(p):
    return sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 1))


def draw_strokes(d, strokes, prog):
    """Dibuja los trazos progresivamente (prog 0..1 sobre la longitud total)."""
    total = sum(polylen(s[0]) for s in strokes)
    budget = total * max(0.0, min(1.0, prog))
    tip = None
    for pts, color, w in strokes:
        if budget <= 0:
            break
        pts = [(x * SS, y * SS) for x, y in pts]
        ws = w * SS
        drawn = [pts[0]]
        for i in range(len(pts) - 1):
            seg = math.dist(pts[i], pts[i + 1]) / SS
            if budget >= seg:
                drawn.append(pts[i + 1])
                budget -= seg
            else:
                t = budget / seg if seg else 1
                drawn.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                              pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
                budget = 0
                break
        d.line(drawn, fill=color, width=int(ws), joint="curve")
        for p in (drawn[0], drawn[-1]):
            d.ellipse([p[0] - ws / 2, p[1] - ws / 2, p[0] + ws / 2, p[1] + ws / 2], fill=color)
        tip = (drawn[-1][0] / SS, drawn[-1][1] / SS)
    return tip if prog < 1 else None


def marker(img, x, y):
    """Plumón dibujado en la punta del trazo."""
    d = ImageDraw.Draw(img)
    x, y = x * SS, y * SS
    ang = math.radians(-50)
    L, Wd = 230 * SS, 42 * SS
    ux, uy = math.cos(ang), math.sin(ang)
    px, py = -uy, ux

    def quad(a, b, w):
        return [(x + ux * a + px * w, y + uy * a + py * w), (x + ux * b + px * w, y + uy * b + py * w),
                (x + ux * b - px * w, y + uy * b - py * w), (x + ux * a - px * w, y + uy * a - py * w)]

    d.polygon([(x, y), (x + ux * 34 * SS + px * 12 * SS, y + uy * 34 * SS + py * 12 * SS),
               (x + ux * 34 * SS - px * 12 * SS, y + uy * 34 * SS - py * 12 * SS)], fill=INK)
    d.polygon(quad(30 * SS, 75 * SS, Wd / 2), fill=(60, 60, 60))
    d.polygon(quad(75 * SS, L, Wd / 2), fill=(250, 250, 250), outline=INK, width=4 * SS)
    d.polygon(quad(L - 40 * SS, L, Wd / 2), fill=RED)


# ---------- texto ----------
def text_layer(lines):
    """lines: [(texto, tamaño, color, fuente, y)] -> lista de (imagen RGBA, x, y) a resolución SS."""
    out = []
    for txt, size, color, font, y in lines:
        f = ImageFont.truetype(font, size * SS)
        bbox = f.getbbox(txt)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        layer = Image.new("RGBA", (tw + 20 * SS, th + 40 * SS), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10 * SS - bbox[0], 20 * SS - bbox[1]), txt, font=f, fill=color)
        out.append((layer, (W * SS - layer.width) // 2, y * SS))
    return out


def paste_reveal(img, item, prog):
    layer, x, y = item
    if prog <= 0:
        return None
    wcut = int(layer.width * min(1, prog))
    img.alpha_composite(layer.crop((0, 0, wcut, layer.height)), (x, y))
    if prog < 1:
        return ((x + wcut) / SS, (y + layer.height * 0.75) / SS)
    return None


def underline(x1, x2, y, color, seed):
    return [(wobble([(x1 + (x2 - x1) * i / 20, y + 6 * math.sin(i / 3)) for i in range(21)], 2, seed), color, 14)]


# ---------- escenas ----------
def scene_intro():
    s = ball(540, 560, 190, seed=1)
    s += [(wobble(circle(540, 560, 250, start=200, sweep=60, n=12), 1, 3), BLUE, 9),
          (wobble(circle(540, 560, 250, start=-20, sweep=60, n=12), 1, 4), BLUE, 9)]
    txt = [("¿POR QUÉ", 120, INK, FONT_BLACK, 880), ("FREESTYLE", 150, RED, FONT_BLACK, 1030),
           ("FÚTBOL?", 150, INK, FONT_BLACK, 1210)]
    extra = underline(220, 860, 1420, BLUE, 7)
    return s, txt, extra


def scene_control():
    # zapato + balón con flechas de toque
    shoe = [(330, 900), (330, 820), (380, 790), (450, 800), (520, 840), (640, 860), (720, 880),
            (740, 920), (720, 950), (330, 950), (330, 900)]
    s = [(wobble(shoe, 2, 11), INK, 11), (wobble(line(340, 930, 730, 930, 10), 1.5, 12), INK, 7)]
    s += ball(560, 470, 140, seed=2)
    s += [(wobble([(400, 760), (380, 640), (420, 540)], 1, 13), BLUE, 9)]
    s += [(h, BLUE, 9) for h in arrow_head(420, 540, -70)]
    s += [(wobble([(720, 540), (750, 660), (700, 770)], 1, 14), BLUE, 9)]
    s += [(h, BLUE, 9) for h in arrow_head(700, 770, 110)]
    txt = [("1. CONTROL", 130, INK, FONT_BLACK, 1080), ("TOTAL", 150, RED, FONT_BLACK, 1240),
           ("del balón en cualquier lugar", 54, INK, FONT_BOLD, 1450)]
    return s, txt, underline(300, 780, 1420, BLUE, 15)


def scene_coord():
    cx = 540
    s = ball(cx, 280, 90, seed=3)
    s += [(wobble(circle(cx, 470, 70, seed=5), 1.2, 21), INK, 11),
          (wobble(line(cx, 540, cx, 760), 2, 22), INK, 11),
          (wobble([(cx - 200, 560), (cx - 90, 610), (cx, 620)], 2, 23), INK, 11),
          (wobble([(cx, 620), (cx + 90, 610), (cx + 200, 560)], 2, 24), INK, 11),
          (wobble(line(cx, 760, cx - 30, 980), 2, 25), INK, 11),
          (wobble([(cx, 760), (cx + 130, 830), (cx + 60, 930)], 2, 26), INK, 11),
          (wobble(line(cx - 150, 990, cx + 150, 990), 2, 27), INK, 8)]
    s += [(wobble(circle(cx, 280, 130, start=150, sweep=60, n=10), 1, 28), GREEN, 8),
          (wobble(circle(cx, 280, 130, start=-30, sweep=60, n=10), 1, 29), GREEN, 8)]
    txt = [("2. COORDINACIÓN", 96, INK, FONT_BLACK, 1080), ("Y EQUILIBRIO", 120, GREEN, FONT_BLACK, 1240),
           ("cuerpo y mente en sintonía", 54, INK, FONT_BOLD, 1450)]
    return s, txt, underline(260, 820, 1420, RED, 30)


def scene_creative():
    cx, cy = 540, 520
    bulb = circle(cx, cy, 200, start=130, sweep=280, n=60, seed=7)
    s = [(wobble(bulb + [(cx - 70, cy + 270), (cx + 70, cy + 270), bulb[0]], 1.5, 31), INK, 11)]
    for i, yy in enumerate((cy + 300, cy + 335)):
        s.append((wobble(line(cx - 70, yy, cx + 70, yy, 6), 1.5, 32 + i), INK, 10))
    s += ball(cx, cy - 10, 95, color=RED, seed=4)
    for i, a in enumerate((-160, -125, -90, -55, -20)):
        r = math.radians(a)
        s.append((wobble(line(cx + 245 * math.cos(r), cy + 245 * math.sin(r),
                              cx + 320 * math.cos(r), cy + 320 * math.sin(r), 4), 1, 40 + i), BLUE, 10))
    txt = [("3. CREATIVIDAD", 112, INK, FONT_BLACK, 1080), ("SIN LÍMITES", 130, BLUE, FONT_BLACK, 1240),
           ("crea tu propio estilo", 58, INK, FONT_BOLD, 1450)]
    return s, txt, underline(300, 780, 1420, RED, 45)


def scene_cta():
    s = ball(420, 520, 170, seed=5)
    s += [(wobble([(600, 520), (680, 610), (860, 360)], 2, 51), GREEN, 22)]
    txt = [("SOLO NECESITAS", 100, INK, FONT_BLACK, 860), ("UN BALÓN", 160, RED, FONT_BLACK, 1000),
           ("¡EMPIEZA HOY!", 112, INK, FONT_BLACK, 1300)]
    box = [(wobble([(90, 1270), (990, 1265), (995, 1470), (85, 1475), (90, 1270)], 3, 52), BLUE, 12)]
    return s, txt, box


SCENES = [scene_intro(), scene_control(), scene_coord(), scene_creative(), scene_cta()]
SCENE_LEN = DUR * FPS // len(SCENES)  # 90 frames = 3 s


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


def render(frame):
    si = min(frame // SCENE_LEN, len(SCENES) - 1)
    f = frame - si * SCENE_LEN
    last = si == len(SCENES) - 1
    strokes, txt, extra = SCENES[si]
    layers = text_layer(txt) if not hasattr(render, "cache") or si not in render.cache else render.cache[si]
    render.cache = getattr(render, "cache", {})
    render.cache[si] = layers

    img = Image.new("RGBA", (W * SS, H * SS), BG + (255,))
    d = ImageDraw.Draw(img)
    tip = draw_strokes(d, strokes, ease(f / 34))
    n = len(layers)
    t0, span = 22, 40 / n
    for i, item in enumerate(layers):
        p = paste_reveal(img, item, (f - t0 - i * span) / span)
        tip = p or tip
    d = ImageDraw.Draw(img)
    p = draw_strokes(d, extra, (f - 64) / 10)
    tip = p or tip
    if tip:
        marker(img, *tip)
    # borrador: barrido al final de cada escena
    if not last and f >= SCENE_LEN - 8:
        k = (f - (SCENE_LEN - 8)) / 7
        ew = int(W * SS * min(1, k))
        d.rectangle([0, 0, ew, H * SS], fill=BG)
        d.rounded_rectangle([ew - 60 * SS, 0, ew + 60 * SS, H * SS], radius=20 * SS, fill=(70, 90, 140))
    # marca pequeña
    d.text((W * SS // 2, (H - 110) * SS), "FREESTYLE FÚTBOL", anchor="mm",
           font=ImageFont.truetype(FONT_BOLD, 36 * SS), fill=(150, 150, 150))
    # puntos de progreso
    for i in range(len(SCENES)):
        x = W // 2 + (i - 2) * 40
        col = RED if i == si else (200, 200, 200)
        d.ellipse([(x - 9) * SS, (H - 180 - 9) * SS, (x + 9) * SS, (H - 180 + 9) * SS], fill=col)
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "freestyle_pizarra.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in range(DUR * FPS):
        p.stdin.write(np.asarray(render(fr)).tobytes())
    p.stdin.close()
    p.wait()
    print("OK", out)


if __name__ == "__main__":
    main()

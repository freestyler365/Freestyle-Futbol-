#!/usr/bin/env python3
"""Genera 3 cortes de video 9:16 (1080x1920) a partir del anuncio original y las fotos.

Uso:  python3 anuncios/scripts/generar_videos.py
Requiere ffmpeg. Reutiliza los estilos de generar_imagenes.py.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import generar_imagenes as g  # noqa: E402

ROOT = g.ROOT
SRC = g.SRC
OUT = ROOT / "videos"
OUT.mkdir(exist_ok=True)
VIDEO = SRC / "anuncio_original.mp4"
W, H = 1080, 1920
FPS = 30
TMP = Path(tempfile.mkdtemp(prefix="pb_"))

# Tramos limpios del video original (segundos)
CLIPS = {
    "giro":     (2.0, 4.3),    # porta-balón girando en la pared 365
    "pared":    (5.0, 8.3),    # pared llena de porta-balones
    "racimo":   (8.6, 12.0),   # racimo de balones en la mano
    "estopero": (12.4, 16.2),  # close-up estoperoles (tiene marca de agua abajo)
    "puesto":   (17.4, 20.0),  # persona colgándoselo (tiene texto original)
}


# ---------- overlays de texto ----------
def overlay(name, lines, y, size=118, accent=(), plate=False, sub=None):
    """PNG transparente con titular. plate=True pone placa negra detrás;
    si no, un degradado oscuro suave detrás del texto para legibilidad."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(g.F_BLACK, size)
    track = -size * 0.02
    lh = int(size * 0.95)
    if not plate:
        th = lh * len(lines) + (80 if sub else 0)
        bh = th + 360
        band = Image.new("RGBA", (W, bh), (0, 0, 0, 0))
        top = g.gradient((W, bh // 2), 0, 150)
        band.alpha_composite(top, (0, 0))
        band.alpha_composite(top.transpose(Image.FLIP_TOP_BOTTOM), (0, bh // 2))
        im.alpha_composite(band, (0, max(0, y - 180)))
        d = ImageDraw.Draw(im)
    if plate:
        tot = lh * len(lines) + (70 if sub else 0) + 60
        pl = Image.new("RGBA", (W, tot), g.INK + (225,))
        im.alpha_composite(pl, (0, y - 30))
    cy = y
    for ln in lines:
        lw = g.text_w(f, ln, track)
        x = (W - lw) / 2
        # sombra suave para legibilidad
        for word in ln.split(" "):
            col = g.RED if word in accent else g.WHITE
            g.draw_tracked(d, (x + 4, cy + 5), word, f, (0, 0, 0, 160), track)
            g.draw_tracked(d, (x, cy), word, f, col, track)
            x += g.text_w(f, word + " ", track) + track
        cy += lh
    if sub:
        fs = ImageFont.truetype(g.F_BOLD, 44)
        sw = fs.getlength(sub)
        d.text(((W - sw) / 2 + 3, cy + 18), sub, font=fs, fill=(0, 0, 0, 170))
        d.text(((W - sw) / 2, cy + 15), sub, font=fs, fill=g.STEEL)
    p = TMP / f"{name}.png"
    im.save(p)
    return p


def endcard(name, headline_txt, accent=()):
    im = Image.new("RGBA", (W, H), g.INK + (255,))
    ph = g.grade(g.cover(g.src_model("virus"), (W, 1100), (0.5, 0.3)), sharp=1.3)
    im.paste(ph, (0, 0))
    im.alpha_composite(g.gradient((W, H), 0, 255, 0.32, 0.58))
    d = ImageDraw.Draw(im)
    g.brand(d, W, H, color=g.INK)
    y = g.headline(d, headline_txt, (72, 1040, W - 144), 120, accent_words=accent)
    g.chain_rule(d, 72, y + 26, 460)
    y = g.body(d, "Porta-balón + correa · Fútbol · Básquet · Freestyle", (72, y + 80), W - 144, 38, g.STEEL)
    g.cta(d, f"Pídelo en {g.URL}", y + 60, W, 40, bg=g.RED, fg=g.WHITE, center=False)
    p = TMP / f"{name}.png"
    im.convert("RGB").save(p)
    return p


def photo_still(name, src_img, focus=(0.5, 0.4)):
    """Foto preparada 10% más grande para hacer paneo (Ken Burns)."""
    p = TMP / f"{name}.png"
    g.grade(g.cover(src_img, (int(W * 1.1), int(H * 1.1)), focus), sharp=1.3).save(p)
    return p


# ---------- armado con ffmpeg ----------
def build(out_name, segments):
    """segments: lista de dicts con
       kind='clip' (key, ov, speed) | kind='photo' (img, ov, dur) | kind='card' (img, dur)"""
    inputs, chains, labels = [], [], []
    idx = 0
    total = 0.0
    for i, s in enumerate(segments):
        if s["kind"] == "clip":
            a, b = CLIPS[s["key"]]
            if "trim" in s:
                a, b = a + s["trim"][0], a + s["trim"][1]
            spd = s.get("speed", 1.0)
            dur = (b - a) / spd
            inputs += ["-ss", f"{a}", "-t", f"{b - a}", "-i", str(VIDEO)]
            zoom = s.get("zoom", 1.0)
            sw, sh = int(W * zoom) // 2 * 2, int(H * zoom) // 2 * 2
            yfoc = s.get("yfocus", 0.5)
            base = (f"[{idx}:v]setpts=(PTS-STARTPTS)/{spd},fps={FPS},"
                    f"scale={sw}:{sh}:flags=lanczos,crop={W}:{H}:(in_w-{W})/2:(in_h-{H})*{yfoc},"
                    f"unsharp=5:5:0.5,eq=contrast=1.05:saturation=1.08,setsar=1,format=yuv420p")
            idx += 1
        elif s["kind"] == "photo":
            dur = s["dur"]
            inputs += ["-loop", "1", "-t", f"{dur}", "-i", str(s["img"])]
            pw, ph = int(W * 1.1), int(H * 1.1)
            base = (f"[{idx}:v]fps={FPS},crop={W}:{H}:"
                    f"'({pw}-{W})*t/{dur}':'({ph}-{H})/2',setsar=1,format=yuv420p")
            idx += 1
        else:  # card
            dur = s["dur"]
            inputs += ["-loop", "1", "-t", f"{dur}", "-i", str(s["img"])]
            base = (f"[{idx}:v]fps={FPS},scale={int(W*1.06)}:-2,"
                    f"zoompan=z='1.0+0.0':d=1:s={int(W*1.06)}x{int(H*1.06)},"
                    f"crop={W}:{H}:'(in_w-{W})/2':'(in_h-{H})/2*(1-t/{dur})',"
                    f"setsar=1,format=yuv420p")
            idx += 1
        lbl = f"v{i}"
        if s.get("ov"):
            inputs += ["-loop", "1", "-t", f"{dur}", "-i", str(s["ov"])]
            chains.append(base + f"[b{i}]")
            chains.append(f"[{idx}:v]format=rgba,fade=in:st=0.08:d=0.18:alpha=1[o{i}]")
            chains.append(f"[b{i}][o{i}]overlay=0:0:shortest=1,format=yuv420p[{lbl}]")
            idx += 1
        else:
            chains.append(base + f"[{lbl}]")
        labels.append(f"[{lbl}]")
        total += dur
    # audio: la pista del original, recortada y con fade out
    inputs += ["-i", str(VIDEO)]
    aidx = idx
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[vout]")
    chains.append(f"[{aidx}:a]atrim=0:{total},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.2,afade=t=out:st={total - 1.2}:d=1.2[aout]")
    out = OUT / f"{out_name}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains),
           "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow",
           "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", "-t", f"{total}", str(out)]
    subprocess.run(cmd, check=True)
    print(f"✓ {out.name}  ({total:.1f}s)")


def video_manos_libres():
    build("V1_manos_libres_9x16", [
        dict(kind="clip", key="puesto", speed=1.0,
             ov=overlay("v1a", ["¿TODAVÍA", "CARGAS TU", "BALÓN EN", "LA MANO?"], 1150, 120,
                        accent=("MANO?",), plate=True)),
        dict(kind="clip", key="giro", speed=1.1,
             ov=overlay("v1b", ["CUÉLGALO.", "CRÚZALO.", "LLÉVALO."], 1300, 124,
                        accent=("LLÉVALO.",))),
        dict(kind="clip", key="estopero", trim=(0.4, 3.2), zoom=1.3, yfocus=0.1,
             ov=overlay("v1c", ["CADENA +", "ESTOPEROLES"], 1380, 116, accent=("ESTOPEROLES",),
                        sub="Correas, cadena y mosquetones")),
        dict(kind="clip", key="racimo", trim=(0.4, 3.0),
             ov=overlay("v1d", ["FÚTBOL.", "BÁSQUET.", "FREESTYLE."], 300, 118,
                        accent=("FREESTYLE.",))),
        dict(kind="card", img=endcard("v1e", "Manos libres. Estilo completo.", ("LIBRES.",)), dur=2.8),
    ])


def video_coleccion():
    build("V2_coleccion_9x16", [
        dict(kind="clip", key="pared", speed=1.0,
             ov=overlay("v2a", ["¿TUS BALONES", "SIGUEN", "TIRADOS?"], 260, 116,
                        accent=("TIRADOS?",), plate=True)),
        dict(kind="clip", key="racimo", trim=(0.0, 2.6),
             ov=overlay("v2b", ["DALES UN", "LUGAR."], 1450, 130, accent=("LUGAR.",))),
        dict(kind="clip", key="giro", speed=1.0,
             ov=overlay("v2c", ["TU PARED.", "TU MUSEO."], 1350, 130, accent=("MUSEO.",))),
        dict(kind="card", img=endcard("v2d", "Tu colección merece una pared.", ("PARED.",)), dur=2.8),
    ])


def video_tres_estilos():
    build("V3_tres_estilos_9x16", [
        dict(kind="clip", key="estopero", trim=(0.0, 2.2), zoom=1.3, yfocus=0.1,
             ov=overlay("v3a", ["ELIGE TU", "NIVEL DE", "ACTITUD"], 260, 128,
                        accent=("ACTITUD",), plate=True)),
        dict(kind="photo", dur=1.6, img=photo_still("p_el", g.src_model("elemental")),
             ov=overlay("v3b", ["ELEMENTAL"], 1500, 132, sub="Liso. Clásico. Esencial.")),
        dict(kind="photo", dur=1.6, img=photo_still("p_ba", g.src_model("balance")),
             ov=overlay("v3c", ["BALANCE"], 1500, 132, sub="Una línea de estoperoles.")),
        dict(kind="photo", dur=1.8, img=photo_still("p_vi", g.src_model("virus")),
             ov=overlay("v3d", ["VIRUS"], 1500, 150, accent=("VIRUS",), sub="Full estoperoles. Full actitud.")),
        dict(kind="clip", key="giro", trim=(0.2, 2.3),
             ov=overlay("v3e", ["¿CUÁL ES", "EL TUYO?"], 1350, 130, accent=("TUYO?",))),
        dict(kind="card", img=endcard("v3f", "Elige el tuyo.", ("TUYO.",)), dur=2.6),
    ])


if __name__ == "__main__":
    video_manos_libres()
    video_coleccion()
    video_tres_estilos()

#!/usr/bin/env python3
"""Música de fondo + narración para video_pizarra.py y mezcla final.

Uso: python3 audio_pizarra.py video_sin_audio.mp4 salida.mp4
Con ELEVENLABS_API_KEY definida usa ElevenLabs; si no, requiere espeak-ng, mbrola y la voz mexicana mbrola-mx2
(apt install espeak-ng mbrola mbrola-mx2).
"""
import os
import subprocess
import sys
import tempfile
import json
import urllib.request
import wave

import numpy as np

SR = 44100
DUR = 15.0
BPM = 120
BEAT = 60 / BPM
SCENE = 3.0

# "fristáil" escrito como se pronuncia; la voz es mexicana (mbrola mx2).
NARRACION = [
    "¿Por qué practicar fristáil fútbol?",
    "Uno. Control total del balón.",
    "Dos. Coordinación y equilibrio.",
    "Tres. Creatividad sin límites.",
    "Solo necesitas un balón. ¡Empieza hoy!",
]
VOZ = "mx2"

# Si existe ELEVENLABS_API_KEY se usa ElevenLabs (voz natural); si no, mbrola como respaldo.
ELEVEN_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "TX3LPaxmHKxFdv7VOQHJ")  # Liam (prediseñada, sirve en plan gratis)
NARRACION_ELEVEN = [
    "¿Por qué practicar freestyle fútbol?",
    "Uno: control total del balón.",
    "Dos: coordinación y equilibrio.",
    "Tres: creatividad sin límites.",
    "Solo necesitas un balón. ¡Empieza hoy!",
]


def tts_eleven(txt, out_mp3, prev="", nxt=""):
    body = json.dumps({
        "text": txt,
        "model_id": "eleven_multilingual_v2",
        "language_code": "es",
        "previous_text": prev,
        "next_text": nxt,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35,
                           "use_speaker_boost": True, "speed": 1.08},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                            "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=60) as r, open(out_mp3, "wb") as fh:
        fh.write(r.read())


# ---------------- música ----------------
def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12)


def clap(rng):
    n = int(0.25 * SR)
    x = rng.standard_normal(n) * env(n, 0.001, 0.06)
    return np.convolve(x, np.ones(6) / 6, "same") * 0.5


def hat(rng):
    n = int(0.06 * SR)
    x = rng.standard_normal(n)
    x = np.diff(x, prepend=0)
    return x * env(n, 0.001, 0.015) * 0.18


def tone(freq, dur, kind="saw", a=0.01, r=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "sine":
        x = np.sin(2 * np.pi * freq * t)
    else:  # saw suave (pocos armónicos)
        x = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 7))
    return x * env(n, a, r)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def music():
    rng = np.random.default_rng(7)
    out = np.zeros(int((DUR + 1) * SR))

    def add(sig, t, g=1.0):
        i = int(t * SR)
        j = min(len(out), i + len(sig))
        out[i:j] += sig[: j - i] * g

    # C - G - Am - F (un acorde por compás de 2 s)
    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    roots = [36, 43, 45, 41]
    bars = int(DUR / (4 * BEAT)) + 1
    pad = np.zeros_like(out)
    for b in range(bars):
        t0 = b * 4 * BEAT
        ch = chords[b % 4]
        for m in ch:
            s = tone(midi(m), 4 * BEAT, "saw", a=0.25, r=3.0)
            i = int(t0 * SR)
            j = min(len(pad), i + len(s))
            pad[i:j] += s[: j - i] * 0.05
        # bajo en corcheas con salto de octava
        for k in range(8):
            m = roots[b % 4] + (12 if k % 2 else 0)
            add(tone(midi(m), BEAT / 2, "sine", 0.005, 0.18), t0 + k * BEAT / 2, 0.22)
        # arpegio pluck
        arp = ch + [ch[0] + 12, ch[1] + 12]
        for k in range(8):
            m = arp[[0, 1, 2, 3, 4, 3, 2, 1][k]] + 12
            add(tone(midi(m), 0.3, "saw", 0.002, 0.09), t0 + k * BEAT / 2, 0.035)
        # batería (entra completa después del primer compás)
        for k in range(4):
            tb = t0 + k * BEAT
            add(kick(), tb, 0.9)
            if k in (1, 3) and b > 0:
                add(clap(rng), tb, 0.45)
            for h in range(2):
                if b > 0 or h == 1:
                    add(hat(rng), tb + h * BEAT / 2, 1.0 if h else 0.6)
    out += lowpass(pad, 1800)
    out = out[: int(DUR * SR)]
    # fade in/out
    fi, fo = int(0.3 * SR), int(1.2 * SR)
    out[:fi] *= np.linspace(0, 1, fi)
    out[-fo:] *= np.linspace(1, 0, fo)
    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.9


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


# ---------------- voz ----------------
def voz(tmp):
    """Genera cada frase, la ajusta a < 2.6 s y la coloca al inicio de su escena."""
    filters, inputs = [], []
    eleven = bool(os.environ.get("ELEVENLABS_API_KEY"))
    for i, txt in enumerate(NARRACION):
        raw = os.path.join(tmp, f"v{i}.wav")
        if eleven:
            frases = NARRACION_ELEVEN
            raw = os.path.join(tmp, f"v{i}.mp3")
            tts_eleven(frases[i], raw, frases[i - 1] if i else "", frases[i + 1] if i + 1 < len(frases) else "")
        else:
            synth_mbrola(txt, raw, tmp, i)
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", raw]))
        limit = 2.7 if i < len(NARRACION) - 1 else 2.8
        tempo = min(1.25, max(1.0, d / limit))
        start = i * SCENE + (0.2 if i else 0.15)
        inputs += ["-i", raw]
        filters.append(f"[{i}:a]aresample={SR},silenceremove=start_periods=1:start_threshold=-45dB,"
                       f"atempo={tempo:.3f},adelay={int(start * 1000)}:all=1[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(NARRACION)))
    eq = ("highpass=f=80,acompressor=threshold=-20dB:ratio=2.5:makeup=3" if eleven else
          "highpass=f=90,lowpass=f=7500,equalizer=f=200:t=q:w=1:g=3,equalizer=f=3000:t=q:w=1.5:g=2,"
          "aecho=0.8:0.5:40:0.12,acompressor=threshold=-18dB:ratio=3:makeup=4")
    chain = (f"{mix}amix=inputs={len(NARRACION)}:normalize=0,{eq},"
             f"apad,atrim=0:{DUR},aformat=channel_layouts=stereo[v]")
    out = os.path.join(tmp, "voz.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                    ";".join(filters) + ";" + chain, "-map", "[v]", out], check=True)
    return out


def synth_mbrola(txt, raw, tmp, i):
    # espeak-ng marca vocales tónicas como "e/", que las voces mbrola no traen: se limpian.
    pho = subprocess.check_output(["espeak-ng", "-v", f"mb-{VOZ}", "-s", "160", "-q", "--pho", txt],
                                  stderr=subprocess.DEVNULL, text=True)
    pho = "\n".join(l.split("\t", 1)[0].rstrip("/") + ("\t" + l.split("\t", 1)[1] if "\t" in l else "")
                    for l in pho.splitlines())
    pho_path = os.path.join(tmp, f"v{i}.pho")
    with open(pho_path, "w") as fh:
        fh.write(pho + "\n")
    subprocess.run(["mbrola", "-f", "1.08", f"/usr/share/mbrola/{VOZ}/{VOZ}", pho_path, raw],
                   check=True, stderr=subprocess.DEVNULL)


def main():
    video, salida = sys.argv[1], sys.argv[2]
    with tempfile.TemporaryDirectory() as tmp:
        mus = os.path.join(tmp, "musica.wav")
        write_wav(mus, music())
        vz = voz(tmp)
        fc = ("[2:a]asplit=2[vz][sc];"
              "[1:a]volume=0.55[m];"
              "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];"
              "[md][vz]amix=inputs=2:normalize=0,alimiter=limit=0.95,"
              "loudnorm=I=-14:TP=-1.5:LRA=11[out]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", mus, "-i", vz,
                        "-filter_complex", fc, "-map", "0:v", "-map", "[out]", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest",
                        "-movflags", "+faststart", salida], check=True)
    print("OK", salida)


if __name__ == "__main__":
    main()

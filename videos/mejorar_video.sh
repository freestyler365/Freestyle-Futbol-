#!/usr/bin/env bash
# Reduce grano y mejora la nitidez de un video.
# Uso: ./mejorar_video.sh entrada.mp4 [salida.mp4]
set -euo pipefail
IN="$1"
OUT="${2:-${IN%.*}_mejorado.mp4}"
# hqdn3d: quita ruido temporal (parpadeo del grano entre cuadros)
# nlmeans: quita ruido espacial y artefactos de compresión
# cas + unsharp: recupera nitidez en bordes
# eq: leve aumento de contraste y saturación
VF="hqdn3d=3:2:5:4,nlmeans=s=2.5:p=5:r=11,cas=strength=0.6,unsharp=5:5:0.6:5:5:0.0,eq=contrast=1.04:saturation=1.05"
ffmpeg -y -i "$IN" -vf "$VF" -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
  -tag:v avc1 -movflags +faststart -c:a aac -b:a 128k "$OUT"

"""Step 1 tooling: fine contact sheets for frame-by-frame motion measurement.

    python tests/study_moves.py <ref> <start> <dur> <out.png> [cols] [rows] [tile_w]

Renders consecutive frames at source fps over a short window, each stamped with
its exact time, so an entrance / push / count-up can be counted frame by frame.
"""
from __future__ import annotations

import os
import sys

import imageio_ffmpeg
import subprocess

FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "artifacts/_ref/font.ttf"


def sheet(ref, start, dur, out, cols=5, rows=5, w=512, fps=30, label=""):
    text = f"%{{pts\\:hms}}"
    vf = (
        f"fps={fps},scale={w}:-2,"
        f"drawtext=fontfile={FONT}:text='{text}':x=6:y=6:fontsize=17:"
        f"fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4"
    )
    if label:
        vf += (f",drawtext=fontfile={FONT}:text='{label}':x=6:y=h-28:fontsize=17:"
               f"fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=4")
    vf += f",tile={cols}x{rows}"
    p = subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
         "-t", str(dur), "-i", ref, "-vf", vf, "-frames:v", "1", out],
        capture_output=True, text=True)
    if p.returncode != 0:
        print("ERR", p.stderr[-400:])
    return p.returncode == 0


def main():
    ref = sys.argv[1]
    os.makedirs("artifacts/_ref", exist_ok=True)
    windows = [
        ("w_text", 0.30, 1.40, "headline word entrance"),
        ("w_push", 0.30, 3.20, "intro card camera push + chip stack"),
        ("w_cut", 3.10, 1.00, "match cut UI to character"),
        ("w_scatter", 10.30, 1.50, "platform chips fan out"),
        ("w_turn", 21.30, 1.60, "blur dissolve turn"),
        ("w_logo", 26.60, 1.60, "icons converge -> logo glow reveal"),
        ("w_count", 42.80, 1.60, "health score count-up"),
        ("w_click", 56.80, 1.60, "cursor click -> row state change"),
        ("w_stats", 71.20, 1.60, "big stat count-up"),
    ]
    for name, s, d, label in windows:
        ok = sheet(ref, s, d, f"artifacts/_ref/{name}.png", label=label)
        print(name, "ok" if ok else "FAIL")


if __name__ == "__main__":
    main()

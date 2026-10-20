"""Step 1 tooling: take a reference video apart properly.

Extracts 3 fps frames + timecoded contact sheets, frames at source fps for
frame-by-frame motion measurement, integrated loudness (LUFS) and a rough
tempo / onset-density estimate.

    python tests/study_reference.py artifacts/VID-20261020-WA0002.mp4
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
# a colon-free copy: ffmpeg filter args split on ':', so a Windows path breaks them
FONT_SRC = r"C:\Windows\Fonts\segoeuib.ttf"
FONT = "artifacts/_ref/font.ttf"


def run(args):
    return subprocess.run(args, capture_output=True, text=True, errors="replace")


def contacts(ref, out, fps=3, cols=5, rows=4, w=384):
    os.makedirs(out, exist_ok=True)
    if not os.path.exists(FONT) and os.path.exists(FONT_SRC):
        shutil.copyfile(FONT_SRC, FONT)
    vf = (
        f"fps={fps},scale={w}:{int(w * 9 / 16)},"
        f"drawtext=fontfile={FONT}:text='%{{pts\\:hms}}':x=8:y=8:fontsize=18:"
        f"fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=5,"
        f"tile={cols}x{rows}"
    )
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", ref, "-vf", vf,
         "-frames:v", "20", os.path.join(out, "sheet_%02d.png")])


def frames(ref, out, fps=3, w=854):
    os.makedirs(out, exist_ok=True)
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", ref,
         "-vf", f"fps={fps},scale={w}:-2", os.path.join(out, "f_%04d.png")])


def loudness(ref):
    p = run([FF, "-hide_banner", "-nostats", "-i", ref, "-af", "ebur128=peak=true",
             "-f", "null", "-"])
    txt = p.stderr
    out = {}
    m = re.findall(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", txt, re.M)
    if m:
        out["integrated_lufs"] = float(m[-1])
    m = re.findall(r"^\s*LRA:\s*(-?[\d.]+)\s*LU", txt, re.M)
    if m:
        out["lra"] = float(m[-1])
    m = re.findall(r"^\s*Peak:\s*(-?[\d.]+)\s*dBFS", txt, re.M)
    if m:
        out["peak_dbfs"] = float(m[-1])
    return out


def tempo(ref, tmp="artifacts/_ref/audio.wav"):
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", ref,
         "-ac", "1", "-ar", "22050", "-vn", tmp])
    with wave.open(tmp, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    hop = 512
    n = 1024
    win = np.hanning(n).astype(np.float32)
    nf = (len(x) - n) // hop
    mags = np.empty((nf, n // 2 + 1), dtype=np.float32)
    for i in range(nf):
        seg = x[i * hop:i * hop + n] * win
        mags[i] = np.abs(np.fft.rfft(seg))
    flux = np.maximum(0.0, np.diff(mags, axis=0)).sum(axis=1)
    flux -= flux.mean()
    fps = sr / hop
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    bpm_lo, bpm_hi = 70.0, 170.0
    lo, hi = int(60 * fps / bpm_hi), int(60 * fps / bpm_lo)
    lag = lo + int(np.argmax(ac[lo:hi]))
    bpm = 60.0 * fps / lag
    # onset density: peaks above a rolling threshold
    thr = np.percentile(flux, 88)
    peaks = ((flux[1:-1] > flux[:-2]) & (flux[1:-1] >= flux[2:]) & (flux[1:-1] > thr)).sum()
    dur = len(x) / sr
    return {"bpm": round(bpm, 1), "onset_peaks": int(peaks),
            "onsets_per_sec": round(peaks / dur, 2), "duration": round(dur, 2)}


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "artifacts/VID-20261020-WA0002.mp4"
    out = "artifacts/_ref"
    os.makedirs(out, exist_ok=True)
    contacts(ref, out)
    frames(ref, os.path.join(out, "frames"))
    print("loudness", loudness(ref))
    print("tempo", tempo(ref))
    print("sheets:", len([f for f in os.listdir(out) if f.startswith("sheet")]),
          "frames:", len(os.listdir(os.path.join(out, "frames"))))


if __name__ == "__main__":
    main()

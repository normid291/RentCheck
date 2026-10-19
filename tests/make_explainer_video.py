"""
Build the RentCheck explainer video: motion-graphic title cards, a voiceover,
burned-in captions, the app footage, and an outro.

Pipeline
--------
1. Synthesise one voiceover line per scene with Edge neural TTS (a Nigerian
   English voice, en-NG-AbeoNeural).
2. Each scene's length is driven by its voiceover, so narration and pictures
   stay in sync.
3. Title/outro cards are animated frame-by-frame with Pillow (logo, gradient,
   sliding text, particles, growing accent bar).
4. The app footage is cut into scenes, gently panned/zoomed, and given a
   lower-third caption plate + progress dots (rendered with Pillow).
5. Scenes are concatenated and the per-scene narration is concatenated to
   match, then muxed to H.264/AAC mp4.

Requires (dev only):  pip install -r requirements-dev.txt
    playwright imageio-ffmpeg edge-tts

Run from the repo root:
    python tests/make_explainer_video.py
    python tests/make_explainer_video.py --source artifacts/rentcheck-demo.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import shutil
import subprocess

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")
WORK = os.path.join(ARTIFACTS, "_explainer")

W, H, FPS = 1280, 800, 25
VOICE = "en-NG-AbeoNeural"
RATE = "+6%"

# Brand palette (matches app/static/styles.css)
BRAND = (14, 122, 82)
BRAND_DARK = (10, 92, 62)
BRAND_DEEP = (7, 61, 41)
BRAND_SOFT = (232, 244, 238)
INK = (16, 32, 26)
BG = (244, 247, 245)
MINT = (143, 227, 189)
AMBER = (185, 119, 10)
RED = (192, 57, 43)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]
FONT_REG_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]

# Scene definitions. `slice` is a (start, end) window into the source footage.
SCENES = [
    {
        "kind": "intro",
        "vo": "Know what you're signing, before you sign it. This is RentCheck.",
        "title1": "Know what you're signing",
        "title2": "before you sign it.",
        "footer": "RentCheck  \u00b7  tenancy agreement review",
    },
    {
        "kind": "footage",
        "slice": (2.0, 6.0),
        "step": "INPUT",
        "caption": "Paste text, or upload a PDF, photo, or Word file",
        "vo": "Paste your agreement, or upload a PDF, a photo, or a Word document.",
    },
    {
        "kind": "footage",
        "slice": (6.0, 9.2),
        "step": "ANALYSIS",
        "caption": "Every clause checked against Nigerian rental norms",
        "vo": "RentCheck splits it into clauses, and checks each one against common "
        "Nigerian rental norms.",
    },
    {
        "kind": "footage",
        "slice": (9.3, 14.2),
        "step": "RESULTS",
        "caption": "Risky clauses flagged \u2014 each quoting your own words",
        "vo": "You get the risky clauses, flagged by severity, each one quoting the "
        "exact words from your agreement.",
    },
    {
        "kind": "footage",
        "slice": (14.6, 20.5),
        "step": "QUESTIONS",
        "caption": "Missing protections + questions to ask before signing",
        "vo": "The protections that are missing. And a ready-made list of questions "
        "to ask your landlord before you sign.",
    },
    {
        "kind": "footage",
        "slice": (23.3, 28.0),
        "step": "SAFETY",
        "caption": "Not a tenancy agreement? It says so \u2014 no invented problems",
        "vo": "And if it isn't a tenancy agreement at all, RentCheck tells you, "
        "instead of inventing problems.",
    },
    {
        "kind": "outro",
        "vo": "RentCheck. Read the fine print, in seconds. Not legal advice.",
        "title1": "RentCheck",
        "title2": "Read the fine print, in seconds.",
        "footer": "rentcheck.rumptycloud.app  \u00b7  Not legal advice",
    },
]

PAD = 0.9        # extra seconds added to each scene beyond its voiceover
CARD_PAD = 1.2   # cards get a little more breathing room
LEAD = 0.35      # delay before narration starts within a scene
FADE = 0.4       # scene fade in/out (seconds)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def ff(args: list[str]) -> None:
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    subprocess.run(cmd, check=True)


def probe_duration(path: str) -> float:
    out = subprocess.run([FFMPEG, "-i", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in out.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"could not read duration of {path}")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (FONT_CANDIDATES if bold else FONT_REG_CANDIDATES):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_font(text: str, max_w: int, start: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    size = start
    while size > 18:
        font = load_font(size, bold)
        if font.getlength(text) <= max_w:
            return font
        size -= 2
    return load_font(18, bold)


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_shield(draw, cx, cy, size, color, check_color=(255, 255, 255)):
    w = size
    h = size * 1.15
    x, y = cx - w / 2, cy - h / 2
    pts = [
        (x, y),
        (x + w, y),
        (x + w, y + h * 0.44),
        (x + w * 0.62, y + h * 0.82),
        (x + w * 0.5, y + h),
        (x + w * 0.38, y + h * 0.82),
        (x, y + h * 0.44),
    ]
    draw.polygon(pts, fill=color)
    # check mark
    lw = max(3, int(size * 0.09))
    p1 = (x + w * 0.30, y + h * 0.42)
    p2 = (x + w * 0.45, y + h * 0.58)
    p3 = (x + w * 0.72, y + h * 0.30)
    draw.line([p1, p2, p3], fill=check_color, width=lw, joint="curve")


def gradient_bg(top, bottom) -> Image.Image:
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp(top, bottom, y / H))
    return img


# --------------------------------------------------------------------------- #
# voiceover
# --------------------------------------------------------------------------- #
async def _synth_all(items: list[tuple[str, str]]) -> None:
    for text, out in items:
        comm = edge_tts.Communicate(text, VOICE, rate=RATE)
        await comm.save(out)


def synthesize(scenes: list[dict]) -> list[float]:
    os.makedirs(WORK, exist_ok=True)
    items = []
    for i, s in enumerate(scenes):
        items.append((s["vo"], os.path.join(WORK, f"vo_{i:02d}.mp3")))
    print("[vo] synthesising narration ...")
    asyncio.run(_synth_all(items))
    return [probe_duration(out) for _, out in items]


# --------------------------------------------------------------------------- #
# motion cards
# --------------------------------------------------------------------------- #
def render_card(scene: dict, idx: int, dur: float, out: str) -> None:
    top = BRAND_DARK if scene["kind"] == "intro" else BRAND
    bottom = BRAND_DEEP
    bg = gradient_bg(top, bottom)

    rng = random.Random(7 + idx)
    particles = [
        (rng.uniform(0, W), rng.uniform(120, H - 60), rng.uniform(1.5, 4.5), rng.uniform(0.10, 0.30))
        for _ in range(30)
    ]

    frames_dir = os.path.join(WORK, f"card_{idx:02d}")
    shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)

    n = max(2, int(dur * FPS))
    title1_font = fit_font(scene["title1"], int(W * 0.82), 88, bold=True)
    title2_font = fit_font(scene["title2"], int(W * 0.82), 58, bold=False)
    foot_font = load_font(26, bold=False)
    is_intro = scene["kind"] == "intro"

    for i in range(n):
        t = i / (n - 1)
        img = bg.copy()
        d = ImageDraw.Draw(img, "RGBA")

        # drifting particles
        for (px, py, pr, pa) in particles:
            y = py - t * 44
            x = px + math.sin((y + idx) * 0.02) * 8
            d.ellipse((x - pr, y - pr, x + pr, y + pr), fill=(255, 255, 255, int(pa * 255)))

        # logo: scale + fade in
        a = ease_out(t / 0.35)
        if a > 0:
            draw_shield(
                d, W / 2, H * 0.27, 70 * (0.7 + 0.3 * a),
                (255, 255, 255, int(255 * a)), check_color=(10, 92, 62),
            )

        # title slide up + fade
        ta = ease_out((t - 0.10) / 0.45)
        if ta > 0:
            y1 = H * 0.50 - (1 - ta) * 34
            txt = scene["title1"]
            d.text((W / 2, y1), txt, font=title1_font, fill=(255, 255, 255, int(255 * ta)), anchor="mm")
            y2 = y1 + title1_font.size + 24
            col = MINT if is_intro else BRAND_SOFT
            d.text((W / 2, y2), scene["title2"], font=title2_font, fill=(*col, int(255 * ta)), anchor="mm")

        # growing accent bar
        ba = ease_out((t - 0.28) / 0.5)
        if ba > 0:
            bw = 240 * ba
            by = H * 0.72
            d.rounded_rectangle((W / 2 - bw / 2, by, W / 2 + bw / 2, by + 6), radius=3, fill=(*MINT, int(255 * ba)))

        # footer
        fa = ease_out((t - 0.4) / 0.5)
        if fa > 0:
            d.text((W / 2, H * 0.84), scene["footer"], font=foot_font, fill=(255, 255, 255, int(190 * fa)), anchor="mm")

        img.save(os.path.join(frames_dir, f"{i:04d}.png"))

    ff([
        "-framerate", str(FPS), "-i", os.path.join(frames_dir, "%04d.png"),
        "-t", f"{dur:.3f}", "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-crf", "19", "-preset", "medium", out,
    ])
    shutil.rmtree(frames_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# caption plate for footage scenes
# --------------------------------------------------------------------------- #
def make_caption(scene: dict, idx: int, total: int, out_png: str) -> None:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    x0, x1 = 88, W - 88
    y0, y1 = 628, 782
    # soft shadow, then the plate itself
    rounded(d, (x0 - 4, y0 - 2, x1 + 4, y1 + 6), 24, fill=(16, 32, 26, 60))
    rounded(d, (x0, y0, x1, y1), 22, fill=(13, 28, 22, 242))
    # left accent bar
    rounded(d, (x0 + 18, y0 + 22, x0 + 26, y1 - 22), 4, fill=(*MINT, 255))

    step_font = load_font(20, bold=True)
    step_txt = f"{idx} \u00b7 {scene['step']}"
    d.text((x0 + 48, y0 + 26), step_txt, font=step_font, fill=(*MINT, 255))

    cap_font = load_font(31, bold=True)
    lines = wrap(d, scene["caption"], cap_font, x1 - x0 - 80)[:2]
    cy = y0 + 60
    for ln in lines:
        d.text((x0 + 48, cy), ln, font=cap_font, fill=(255, 255, 255, 255))
        cy += cap_font.size + 8

    # progress dots
    dots = total - 2  # footage scenes only (exclude intro/outro)
    gap = 22
    total_w = (dots - 1) * gap
    dx = W / 2 - total_w / 2
    dy = y1 - 20
    for k in range(dots):
        filled = k <= (idx - 1)
        color = (*MINT, 255) if filled else (255, 255, 255, 90)
        r = 5 if filled else 4
        d.ellipse((dx + k * gap - r, dy - r, dx + k * gap + r, dy + r), fill=color)

    # full-width progress bar at the very bottom
    frac = idx / (total - 1)
    d.rectangle((0, H - 6, W * frac, H), fill=(*MINT, 255))

    img.save(out_png)


# --------------------------------------------------------------------------- #
# footage scene
# --------------------------------------------------------------------------- #
def render_footage(scene: dict, dur: float, overlay: str, source: str, out: str) -> None:
    s, e = scene["slice"]
    slice_dur = e - s
    speed = slice_dur / dur
    fo = max(0.0, dur - FADE)
    vf = (
        f"[0:v]setpts=PTS/{speed:.6f},trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
        f"scale=1344:840,"
        f"crop=1280:800:x='(in_w-1280)*(1-cos(2*PI*t/{dur:.3f}))/2':y='(in_h-800)*0.5',"
        f"setsar=1[bg];"
        f"[bg][1:v]overlay=0:0:format=auto[ov];"
        f"[ov]fade=t=in:st=0:d={FADE}:color=0xf4f7f5,"
        f"fade=t=out:st={fo:.3f}:d={FADE}:color=0xf4f7f5,format=yuv420p[v]"
    )
    ff([
        "-ss", f"{s}", "-t", f"{slice_dur}", "-i", source,
        "-i", overlay,
        "-filter_complex", vf, "-map", "[v]",
        "-t", f"{dur:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-an", out,
    ])


def render_audio(vo: str, dur: float, out: str) -> None:
    ms = int(LEAD * 1000)
    ff([
        "-i", vo, "-af", f"adelay={ms}|{ms},apad",
        "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", out,
    ])


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join(ARTIFACTS, "rentcheck-demo.mp4"))
    ap.add_argument("--out", default=os.path.join(ARTIFACTS, "rentcheck-explainer.mp4"))
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print(f"source footage not found: {args.source}\nRun tests/make_demo_video.py first.")
        return 1

    os.makedirs(WORK, exist_ok=True)
    vo_durs = synthesize(SCENES)

    # scene durations (voiceover-driven)
    durs = []
    for sc, vd in zip(SCENES, vo_durs):
        pad = CARD_PAD if sc["kind"] in ("intro", "outro") else PAD
        durs.append(round(max(3.0, vd + pad), 3))
    print("[timing]")
    for sc, vd, dd in zip(SCENES, vo_durs, durs):
        print(f"  {sc.get('step', sc['kind']):10s} vo={vd:5.2f}s  scene={dd:5.2f}s")

    total = len(SCENES)
    vparts, aparts = [], []
    for i, (sc, dur) in enumerate(zip(SCENES, durs)):
        vp = os.path.join(WORK, f"v_{i:02d}.mp4")
        ap = os.path.join(WORK, f"a_{i:02d}.wav")
        print(f"[render] scene {i} ({sc.get('step', sc['kind'])}) ...")
        if sc["kind"] in ("intro", "outro"):
            render_card(sc, i, dur, vp)
        else:
            overlay = os.path.join(WORK, f"cap_{i:02d}.png")
            make_caption(sc, i, total, overlay)
            render_footage(sc, dur, overlay, args.source, vp)
        render_audio(os.path.join(WORK, f"vo_{i:02d}.mp3"), dur, ap)
        vparts.append(vp)
        aparts.append(ap)

    # concat video + audio
    vlist = os.path.join(WORK, "v.txt")
    alist = os.path.join(WORK, "a.txt")
    with open(vlist, "w", encoding="utf-8") as fh:
        for p in vparts:
            fh.write(f"file '{p}'\n")
    with open(alist, "w", encoding="utf-8") as fh:
        for p in aparts:
            fh.write(f"file '{p}'\n")

    full_v = os.path.join(WORK, "full.mp4")
    full_a = os.path.join(WORK, "full.wav")
    ff(["-f", "concat", "-safe", "0", "-i", vlist, "-c", "copy", full_v])
    ff(["-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", full_a])

    ff([
        "-i", full_v, "-i", full_a,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", args.out,
    ])

    dur = probe_duration(args.out)
    print(f"\n[done] {args.out}  ({dur:.1f}s, {os.path.getsize(args.out)} bytes)")
    shutil.rmtree(WORK, ignore_errors=True)
    return 0


FFMPEG = str(imageio_ffmpeg.get_ffmpeg_exe())

if __name__ == "__main__":
    raise SystemExit(main())

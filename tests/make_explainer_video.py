"""
Build the RentCheck explainer video as a premium SaaS-style motion explainer.

Reference style (per the brief): a dark gradient stage, a flat-illustration
character at a laptop, floating glass UI cards, stage labels ("01 - UPLOAD"),
animated stat numbers, and subtitle-style captions - but with RentCheck's own
brand, wording and real analysis data.

Design rules
------------
* Motion is calm: fades, gentle scale, vertical bobbing/easing. Nothing slides
  sideways across the screen.
* Every number and clause shown comes from REAL output:
  tests/export_explainer_data.py runs a real agreement from the database
  through the real pipeline and writes tests/fixtures/explainer_data.json
  (already anonymised).
* Professional voiceover (Edge neural TTS) synced to the scenes, plus a quiet
  ambient music bed that is sidechain-ducked under the voice.

Pipeline
--------
1. Load the real analysis JSON.
2. Synthesise one voiceover line per scene; each scene's length follows its VO.
3. Render each scene frame-by-frame with Pillow and pipe raw RGB frames
   straight into ffmpeg (no PNG round-trip).
4. Concatenate video, build the narration track, synthesise a music bed,
   mix/duck and mux to H.264/AAC mp4.

Requires (dev only):  pip install -r requirements-dev.txt   (imageio-ffmpeg edge-tts)

Run from the repo root:
    python tests/make_explainer_video.py
    python tests/make_explainer_video.py --voice en-GB-SoniaNeural --rate -2%
"""
from __future__ import annotations

import argparse
import array
import asyncio
import json
import math
import os
import random
import shutil
import subprocess
import wave

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")
WORK = os.path.join(ARTIFACTS, "_explainer")
DATA = os.path.join(HERE, "fixtures", "explainer_data.json")

W, H, FPS = 1920, 1080, 30
DEFAULT_VOICE = "en-US-AndrewNeural"

# --- dark, premium RentCheck palette ---------------------------------------- #
BG_TOP = (10, 58, 43)
BG_BOT = (4, 22, 19)
BRAND = (34, 176, 122)
MINT = (143, 227, 189)
MINT_DIM = (96, 168, 138)
TEXT = (236, 246, 241)
MUTED = (150, 182, 170)
FAINT = (92, 122, 111)
GLASS = (255, 255, 255, 22)
GLASS_LINE = (255, 255, 255, 54)
CARD = (13, 46, 36)
RED = (238, 96, 84)
AMBER = (240, 180, 74)
BLUE = (112, 171, 238)
WHITE = (255, 255, 255)

SEV_COLOR = {"high": RED, "medium": AMBER, "low": BLUE}
SEV_LABEL = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
RISK_COLOR = {"high": RED, "medium": AMBER, "low": BLUE}

# character
SKIN = (233, 189, 158)
HAIR = (34, 30, 36)
SHIRT = (46, 148, 120)
SHIRT_DARK = (30, 104, 84)

FONT_BOLD = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
FONT_SEMI = [r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
FONT_REG = [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]

PAD = 1.05
HOOK_PAD = 1.2
LEAD = 0.5
FADE = 0.5

FFMPEG = str(imageio_ffmpeg.get_ffmpeg_exe())


# --------------------------------------------------------------------------- #
# math / easing
# --------------------------------------------------------------------------- #
def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(t: float) -> float:
    return 1 - (1 - clamp01(t)) ** 3


def ease_io(t: float) -> float:
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def pop(t: float, s: float = 1.70158) -> float:
    t = clamp01(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def a_in(el: float, start: float, dur: float = 0.5) -> float:
    return ease_out((el - start) / dur) if dur > 0 else (1.0 if el >= start else 0.0)


def a_out(el: float, dur: float, d: float = 0.5) -> float:
    return ease_out((dur - el) / d) if d > 0 else 1.0


def al(a: float) -> int:
    return max(0, min(255, int(round(a * 255))))


def mix(c, a: float):
    return (c[0], c[1], c[2], al(a))


def rgba(c, mult: float):
    return (c[0], c[1], c[2], al((c[3] / 255.0) * mult))


def bob(el: float, amp: float = 6.0, speed: float = 1.5, phase: float = 0.0) -> float:
    return math.sin(el * speed + phase) * amp


# --------------------------------------------------------------------------- #
# fonts / text
# --------------------------------------------------------------------------- #
_FONT_CACHE: dict = {}


def load_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    cands = {"bold": FONT_BOLD, "semi": FONT_SEMI, "regular": FONT_REG}[weight]
    for path in cands:
        if os.path.exists(path):
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = f
            return f
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def fit_font(text: str, max_w: int, start: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    size = start
    while size > 18:
        f = load_font(size, weight)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return load_font(18, weight)


def wrap(d, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def wrap_clamp(d, text: str, font, max_w: int, max_lines: int) -> list[str]:
    lines = wrap(d, text, font, max_w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,;:.") + " ..."
    return lines


def rich_line(d, cx, y, parts, font, alpha=1.0, anchor="mm"):
    """Draw a centred line made of coloured runs: parts = [(text, colour), ...]."""
    total = sum(d.textlength(t, font=font) for t, _ in parts)
    x = cx - total / 2 if anchor == "mm" else cx
    for t, c in parts:
        d.text((x, y), t, font=font, fill=mix(c, alpha), anchor="lm")
        x += d.textlength(t, font=font)


def headline(d, el, text, sub=None, y=262, size=80):
    ha = a_in(el, 0.15, 0.5)
    if ha > 0:
        f = fit_font(text, 1560, size, "bold")
        d.text((W / 2, y - (1 - ha) * 22), text, font=f, fill=mix(TEXT, ha), anchor="mm")
    if sub:
        sa = a_in(el, 0.35, 0.5)
        if sa > 0:
            sf = fit_font(sub, 1300, 36, "regular")
            d.text((W / 2, y + 62), sub, font=sf, fill=mix(MUTED, sa), anchor="mm")


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def glass(d, box, r=22, a=1.0, fill=GLASS, line=GLASS_LINE, shadow=True, shadow_a=0.5, dy=14):
    x0, y0, x1, y1 = box
    if shadow and a > 0:
        d.rounded_rectangle((x0 + 2, y0 + dy, x1 + 2, y1 + dy), radius=r, fill=(0, 0, 0, al(0.30 * a * shadow_a)))
    if a > 0:
        d.rounded_rectangle(box, radius=r, fill=rgba(fill, a))
        d.rounded_rectangle(box, radius=r, outline=rgba(line, a), width=2)


def pill(d, box, r, fill, line=None, a=1.0):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=r, fill=rgba(fill, a) if len(fill) == 4 else mix(fill, a))
    if line is not None:
        d.rounded_rectangle(box, radius=r, outline=(rgba(line, a) if len(line) == 4 else mix(line, a)), width=2)


def line_round(d, pts, fill, w):
    d.line(pts, fill=fill, width=int(w), joint="curve")
    r = w / 2.0
    for p in (pts[0], pts[-1]):
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=fill)


def text_bars(d, x, y, w, color, a, rows=2):
    d.rounded_rectangle((x, y, x + w, y + 16), radius=8, fill=mix(color, a))
    if rows > 1:
        d.rounded_rectangle((x, y + 28, x + w * 0.6, y + 40), radius=6, fill=mix(color, a * 0.5))


# --------------------------------------------------------------------------- #
# icons
# --------------------------------------------------------------------------- #
def icon_doc(d, cx, cy, s, color, w=None, alpha=1.0, lines=4):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    x0, y0 = cx - s * 0.42, cy - s * 0.55
    x1, y1 = cx + s * 0.42, cy + s * 0.55
    d.rounded_rectangle((x0, y0, x1, y1), radius=int(s * 0.10), outline=col, width=w)
    ly = y0 + s * 0.30
    for i in range(lines):
        end = x1 - s * (0.14 if i % 3 == 2 else 0.30)
        d.line((x0 + s * 0.16, ly, end, ly), fill=col, width=w)
        ly += s * 0.20


def icon_upload(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    y0 = cy + s * 0.10
    line_round(d, [(cx - s * 0.34, y0), (cx - s * 0.34, cy + s * 0.44), (cx + s * 0.34, cy + s * 0.44), (cx + s * 0.34, y0)], col, w)
    d.line((cx, cy + s * 0.30, cx, cy - s * 0.42), fill=col, width=w)
    d.line((cx - s * 0.22, cy - s * 0.18, cx, cy - s * 0.42, cx + s * 0.22, cy - s * 0.18), fill=col, width=w, joint="curve")


def icon_search(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.32
    d.ellipse((cx - r - s * 0.06, cy - r - s * 0.20, cx + r - s * 0.06, cy + r - s * 0.20), outline=col, width=w)
    line_round(d, [(cx + r * 0.62, cy + r * 0.42), (cx + s * 0.40, cy + s * 0.44)], col, w)


def icon_check(d, cx, cy, s, color, alpha=1.0):
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.46
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    lw = max(3, int(s * 0.13))
    line_round(d, [(cx - s * 0.22, cy + s * 0.02), (cx - s * 0.05, cy + s * 0.19), (cx + s * 0.24, cy - s * 0.19)], WHITE, lw)


def icon_check_outline(d, cx, cy, s, color, alpha=1.0):
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.46
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=max(3, int(s * 0.09)))


def icon_flag(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    d.line((cx - s * 0.22, cy - s * 0.46, cx - s * 0.22, cy + s * 0.48), fill=col, width=w)
    d.polygon([(cx - s * 0.22, cy - s * 0.44), (cx + s * 0.40, cy - s * 0.26), (cx - s * 0.22, cy - s * 0.04)], fill=col)


def icon_lock(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    bw, bh = s * 0.66, s * 0.50
    d.rounded_rectangle((cx - bw / 2, cy - s * 0.06, cx + bw / 2, cy + s * 0.44), radius=int(s * 0.10), fill=col)
    d.arc((cx - bw * 0.32, cy - s * 0.44, cx + bw * 0.32, cy + s * 0.10), start=180, end=360, fill=col, width=w)


def icon_clock(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.44
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)
    line_round(d, [(cx, cy - r * 0.55), (cx, cy), (cx + r * 0.50, cy + r * 0.30)], col, w)


def icon_bars(d, cx, cy, s, color, alpha=1.0):
    col = mix(color, alpha) if len(color) == 3 else color
    base_y = cy + s * 0.42
    w = max(4, int(s * 0.14))
    for i, hh in enumerate((0.40, 0.66, 0.92)):
        x = cx - s * 0.30 + i * s * 0.30
        d.rounded_rectangle((x - w / 2, base_y - s * hh, x + w / 2, base_y), radius=int(w / 2), fill=col)


def icon_shield(d, cx, cy, s, color, alpha=1.0, check=True, check_color=WHITE):
    col = mix(color, alpha) if len(color) == 3 else color
    w, h = s, s * 1.15
    x, y = cx - w / 2, cy - h / 2
    d.polygon([(x, y), (x + w, y), (x + w, y + h * 0.44), (x + w * 0.62, y + h * 0.82),
               (x + w * 0.5, y + h), (x + w * 0.38, y + h * 0.82), (x, y + h * 0.44)], fill=col)
    if check:
        line_round(d, [(x + w * 0.30, y + h * 0.42), (x + w * 0.45, y + h * 0.58), (x + w * 0.72, y + h * 0.30)],
                   check_color if len(check_color) == 4 else mix(check_color, alpha), max(3, int(s * 0.10)))


ICONS = {
    "doc": icon_doc, "upload": icon_upload, "search": icon_search, "flag": icon_flag,
    "lock": icon_lock, "clock": icon_clock, "bars": icon_bars,
}
ICON_EMOJI_LABEL = {"doc": "PDF", "upload": "Upload"}


# --------------------------------------------------------------------------- #
# background + particles
# --------------------------------------------------------------------------- #
_BASE = {}
_PARTICLES = []


def soft_glow(d, cx, cy, radius, color, max_alpha, steps=56):
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = max_alpha * (1 - i / steps) ** 2.0
        if a <= 0.004:
            continue
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, al(a)))


def get_base() -> Image.Image:
    if "base" in _BASE:
        return _BASE["base"]
    img = Image.new("RGBA", (W, H), (*BG_BOT, 255))
    d = ImageDraw.Draw(img, "RGBA")
    # vertical gradient
    for y in range(0, H, 3):
        t = y / H
        c = (int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
             int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
             int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t))
        d.rectangle((0, y, W, y + 3), fill=(*c, 255))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov, "RGBA")
    soft_glow(od, W * 0.5, -120, 980, BRAND, 0.22)
    soft_glow(od, W - 260, H - 120, 760, MINT, 0.10)
    soft_glow(od, 220, H + 60, 700, BRAND, 0.10)
    img = Image.alpha_composite(img, ov)
    # vignette
    v = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(v)
    vd.rectangle((0, 0, W, H), fill=0)
    vd.ellipse((-W * 0.35, -H * 0.5, W * 1.35, H * 1.5), fill=255)
    dark = Image.new("RGBA", (W, H), (2, 12, 10, 120))
    dark.putalpha(Image.composite(Image.new("L", (W, H), 0), v, v))
    img = Image.alpha_composite(img, dark)
    _BASE["base"] = img
    return img


def init_particles():
    rng = random.Random(11)
    for _ in range(64):
        _PARTICLES.append((rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.0, 2.6),
                           rng.uniform(0, 6.28), rng.uniform(0.05, 0.22), rng.uniform(6, 18)))


def draw_particles(d, el):
    for (px, py, pr, ph, pa, spd) in _PARTICLES:
        y = (py - el * spd) % (H + 60) - 30
        tw = 0.55 + 0.45 * math.sin(el * 1.7 + ph)
        a = pa * tw
        d.ellipse((px - pr, y - pr, px + pr, y + pr), fill=(*MINT, al(a)))


# --------------------------------------------------------------------------- #
# the character (flat illustration)
# --------------------------------------------------------------------------- #
def draw_character(d, cx, base_y, s, el, mood="idle", alpha=1.0, laptop=False):
    by = base_y + bob(el, s * 0.012, 1.5)
    hr = s * 0.105
    head_y = by - s * 0.72
    tw = s * 0.30
    lw = max(4, int(s * 0.062))
    sh_y = by - s * 0.56
    lsh = (cx - tw * 0.48, sh_y + s * 0.03)
    rsh = (cx + tw * 0.48, sh_y + s * 0.03)
    arm = mix(SHIRT_DARK, alpha)
    skin = mix(SKIN, alpha)
    # arms (behind the torso)
    if mood == "wave":
        line_round(d, [lsh, (lsh[0] - s * 0.06, by - s * 0.22)], arm, lw)
        hx, hy = cx + tw * 0.62, by - s * 0.80
        line_round(d, [rsh, (rsh[0] + s * 0.05, by - s * 0.50), (hx, hy)], arm, lw)
        d.ellipse((hx - s * 0.045, hy - s * 0.045, hx + s * 0.045, hy + s * 0.045), fill=skin)
    elif mood == "point":
        line_round(d, [lsh, (lsh[0] - s * 0.05, by - s * 0.20)], arm, lw)
        tip = (cx - tw * 1.05, by - s * 0.44)
        line_round(d, [rsh, (rsh[0] + s * 0.10, by - s * 0.06), tip], arm, lw)
        d.ellipse((tip[0] - s * 0.04, tip[1] - s * 0.04, tip[0] + s * 0.04, tip[1] + s * 0.04), fill=skin)
    else:
        line_round(d, [lsh, (lsh[0] - s * 0.03, by - s * 0.16)], arm, lw)
        line_round(d, [rsh, (rsh[0] + s * 0.03, by - s * 0.16)], arm, lw)
    # torso
    d.rounded_rectangle((cx - tw / 2, sh_y, cx + tw / 2, by + s * 0.50),
                        radius=int(tw * 0.42), fill=mix(SHIRT, alpha))
    d.polygon([(cx - tw * 0.22, sh_y), (cx, sh_y + s * 0.10), (cx + tw * 0.22, sh_y)],
              fill=mix(SHIRT_DARK, alpha))
    # neck
    d.rounded_rectangle((cx - hr * 0.28, head_y + hr * 0.50, cx + hr * 0.28, sh_y + s * 0.03),
                        radius=int(hr * 0.3), fill=skin)
    # hair back + bun
    d.ellipse((cx - hr * 1.06, head_y - hr * 1.16, cx + hr * 1.06, head_y + hr * 1.02), fill=mix(HAIR, alpha))
    d.ellipse((cx - hr * 0.40, head_y - hr * 1.62, cx + hr * 0.46, head_y - hr * 1.00), fill=mix(HAIR, alpha))
    # face
    d.ellipse((cx - hr * 0.86, head_y - hr * 0.94, cx + hr * 0.86, head_y + hr * 1.00), fill=skin)
    # fringe
    d.pieslice((cx - hr * 0.92, head_y - hr * 1.06, cx + hr * 0.92, head_y + hr * 0.62),
               start=184, end=356, fill=mix(HAIR, alpha))
    # eyes (blink occasionally)
    eye_y = head_y - hr * 0.02
    blink = (el % 3.6) > 0.14
    for sx in (-1, 1):
        ex = cx + sx * hr * 0.33
        if blink:
            d.ellipse((ex - hr * 0.07, eye_y - hr * 0.07, ex + hr * 0.07, eye_y + hr * 0.07), fill=mix(HAIR, alpha))
        else:
            d.line((ex - hr * 0.08, eye_y, ex + hr * 0.08, eye_y), fill=mix(HAIR, alpha), width=max(2, int(hr * 0.09)))
    d.arc((cx - hr * 0.28, head_y + hr * 0.22, cx + hr * 0.28, head_y + hr * 0.70),
          start=15, end=165, fill=mix((150, 84, 74), alpha), width=max(2, int(hr * 0.09)))
    for sx in (-1, 1):
        d.ellipse((cx + sx * hr * 0.60 - hr * 0.13, head_y + hr * 0.28 - hr * 0.08,
                   cx + sx * hr * 0.60 + hr * 0.13, head_y + hr * 0.28 + hr * 0.08),
                  fill=mix((224, 150, 138), alpha * 0.45))
    if laptop:
        draw_laptop(d, cx, by, s * 1.05, alpha)


def draw_laptop(d, cx, base_y, s, alpha=1.0):
    """Back of a laptop in front of the character, as in the reference."""
    w, h = s * 0.66, s * 0.40
    x0, y0 = cx - w / 2, base_y - h
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=int(s * 0.03),
                        fill=mix((26, 40, 46), alpha), outline=mix((74, 102, 106), alpha), width=3)
    d.rounded_rectangle((x0 + 14, y0 + 14, x0 + w - 14, y0 + h - 14), radius=int(s * 0.02),
                        fill=mix((18, 30, 35), alpha))
    d.ellipse((cx - s * 0.045, y0 + h * 0.42, cx + s * 0.045, y0 + h * 0.52), fill=mix((74, 102, 106), alpha))
    d.rounded_rectangle((x0 - w * 0.06, y0 + h, x0 + w * 1.06, y0 + h + s * 0.03), radius=int(s * 0.015),
                        fill=mix((32, 50, 56), alpha))


# --------------------------------------------------------------------------- #
# chrome: brand, stage chip, captions, dots
# --------------------------------------------------------------------------- #
STAGE_ORDER = ["upload", "analyse", "flag", "understand", "act"]


def draw_chrome(d, scene, el, g_before, total):
    key = scene["key"]
    # brand mark top-left
    a = a_in(el, 0.1, 0.5)
    if a > 0:
        icon_shield(d, 118, 84, 40, mix(BRAND, a), check_color=mix(WHITE, a))
        d.text((152, 86), "RentCheck", font=load_font(34, "bold"), fill=mix(TEXT, a), anchor="lm")
    # stage chip top-right
    stage = scene.get("stage")
    if stage:
        sa = a_in(el, 0.2, 0.5)
        if sa > 0:
            f = load_font(26, "bold")
            tw = f.getlength(stage) + 56
            x1 = W - 96
            pill(d, (x1 - tw, 64, x1, 116), 26, (BRAND[0], BRAND[1], BRAND[2], 46),
                 line=(MINT[0], MINT[1], MINT[2], 150), a=sa)
            d.text((x1 - tw / 2, 90), stage, font=f, fill=mix(MINT, sa), anchor="mm")
    # caption pill (subtitle)
    vo = scene["vo"]
    ca = a_in(el, 0.4, 0.6)
    if ca > 0:
        cf = load_font(32, "regular")
        lines = wrap_clamp(d, vo, cf, 1180, 2)
        lh = 40
        pad_x, pad_y = 40, 22
        tw = max(d.textlength(ln, font=cf) for ln in lines) + pad_x * 2
        th = len(lines) * lh + pad_y * 2 - 8
        x0 = W / 2 - tw / 2
        y0 = H - 58 - th
        pill(d, (x0, y0, x0 + tw, y0 + th), 18, (6, 18, 15, 190), a=ca)
        ty = y0 + pad_y + lh / 2 - 4
        for ln in lines:
            d.text((W / 2, ty), ln, font=cf, fill=mix((232, 244, 238), ca), anchor="mm")
            ty += lh
    # stage dots bottom-left
    if stage:
        idx = STAGE_ORDER.index(key) if key in STAGE_ORDER else 0
        for i in range(len(STAGE_ORDER)):
            x = 118 + i * 26
            on = i <= idx
            r = 6 if on else 5
            d.ellipse((x - r, H - 52 - r, x + r, H - 52 + r),
                      fill=(*MINT, al(0.9 if on else 0.25)))


# --------------------------------------------------------------------------- #
# scenes
# --------------------------------------------------------------------------- #
def scene_hook(d, el, dur, data):
    # faint dashboard card behind the headline
    ba = a_in(el, 0.0, 0.8) * 0.5
    if ba > 0:
        cx, cy = W / 2, 500 + bob(el, 8, 0.9)
        bw, bh = 1180, 520
        glass(d, (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), 26, ba, shadow_a=0.6)
        # fake dashboard rows
        d.rounded_rectangle((cx - bw / 2 + 40, cy - bh / 2 + 36, cx - bw / 2 + 240, cy - bh / 2 + 60),
                            radius=10, fill=mix(MINT_DIM, ba * 0.7))
        for i in range(4):
            yy = cy - bh / 2 + 110 + i * 78
            d.rounded_rectangle((cx - bw / 2 + 40, yy, cx + bw / 2 - 40, yy + 56), radius=14,
                                fill=(255, 255, 255, al(0.05 * ba)))
    # headline with a highlighted word
    ha = a_in(el, 0.35, 0.7)
    if ha > 0:
        f = fit_font("Do you actually understand", 1500, 92, "bold")
        y = 420 - (1 - ha) * 24
        rich_line(d, W / 2, y, [("Do you ", TEXT), ("actually", MINT), (" understand", TEXT)], f, alpha=ha)
        f2 = fit_font("what's in your tenancy agreement?", 1500, 92, "bold")
        d.text((W / 2, y + 110), "what's in your tenancy agreement?", font=f2, fill=mix(TEXT, ha), anchor="mm")


def scene_upload(d, el, dur, data):
    headline(d, el, "Add your agreement.", "Paste the text, or upload a file.")
    # dropzone glass card
    a = a_in(el, 0.5, 0.7)
    if a > 0:
        x0, x1 = 300, 1150
        y0, y1 = 400, 820
        rise = (1 - a) * 24
        glass(d, (x0, y0 + rise, x1, y1 + rise), 26, a)
        ia = a_in(el, 0.7, 0.6)
        if ia > 0:
            icon_upload(d, (x0 + x1) / 2, y0 + 150 + rise - (1 - ia) * 20, 150, mix(MINT, ia))
        ta = a_in(el, 0.85, 0.6)
        if ta > 0:
            d.text(((x0 + x1) / 2, y0 + 300 + rise), "Drop a file here, or paste your text",
                   font=load_font(40, "semi"), fill=mix(TEXT, ta), anchor="mm")
    # format chips floating on the right
    chips = [("doc", "PDF"), ("doc", "Photo"), ("doc", "Word"), ("doc", "Plain text")]
    for i, (ic, label) in enumerate(chips):
        ca = a_in(el, 0.9 + i * 0.22, 0.55)
        if ca <= 0:
            continue
        cw, ch = 290, 84
        cx = 1330
        cy = 430 + i * 110 + bob(el, 7, 1.1, i) - (1 - ca) * 18
        glass(d, (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2), 20, ca, shadow_a=0.4)
        ICONS[ic](d, cx - cw / 2 + 52, cy, 46, mix(MINT, ca), alpha=ca)
        d.text((cx - cw / 2 + 94, cy), label, font=load_font(32, "semi"), fill=mix(TEXT, ca), anchor="lm")
    draw_character(d, 1780, H + 30, 520, el, mood="idle", laptop=True)


def scene_analyse(d, el, dur, data):
    headline(d, el, "Every clause, checked.", "Compared against common Nigerian rental norms.")
    rows = 5
    rw, rh, gap = 760, 92, 18
    x0 = 470
    top = 400
    total_h = rows * rh + (rows - 1) * gap
    scan = clamp01((el - 0.7) / 2.4)
    for i in range(rows):
        ra = a_in(el, 0.55 + i * 0.13, 0.5)
        if ra <= 0:
            continue
        yy = top + i * (rh + gap) - (1 - ra) * 18
        glass(d, (x0, yy, x0 + rw, yy + rh), 18, ra, shadow_a=0.4)
        d.rounded_rectangle((x0 + 30, yy + rh / 2 - 9, x0 + 30 + (rw - 260) * 0.7, yy + rh / 2 + 9),
                            radius=9, fill=(255, 255, 255, al(0.22 * ra)))
        d.rounded_rectangle((x0 + 30, yy + rh / 2 + 20, x0 + 30 + (rw - 260) * 0.4, yy + rh / 2 + 32),
                            radius=6, fill=(255, 255, 255, al(0.10 * ra)))
        cb = a_in(el, 1.1 + i * 0.28, 0.45)
        if cb > 0:
            cs = 46 * (0.6 + 0.4 * pop(min(1.0, (el - (1.1 + i * 0.28)) / 0.45)))
            icon_check(d, x0 + rw - 54, yy + rh / 2, cs, mix(BRAND, cb))
    if scan < 1.0:
        by = top + scan * (total_h + 40) - 30
        d.rounded_rectangle((x0 - 30, by, x0 + rw + 30, by + 58), radius=18,
                            fill=(BRAND[0], BRAND[1], BRAND[2], 26), outline=(*MINT, 54), width=2)
    draw_character(d, 1660, H + 60, 540, el, mood="point")


def scene_flag(d, el, dur, data):
    headline(d, el, "Unfair terms, flagged.", "Every flag quotes the words in your agreement.")
    flags = data["flagged"]
    rw, rh, gap = 880, 104, 16
    x0 = 300
    top = 360
    for i, f in enumerate(flags):
        ra = a_in(el, 0.5 + i * 0.24, 0.5)
        if ra <= 0:
            continue
        yy = top + i * (rh + gap) - (1 - ra) * 20
        sev = f["severity"]
        col = SEV_COLOR.get(sev, BLUE)
        glass(d, (x0, yy, x0 + rw, yy + rh), 18, ra, shadow_a=0.45)
        d.rounded_rectangle((x0 + 22, yy + 20, x0 + 30, yy + rh - 20), radius=4, fill=mix(col, ra))
        icon_flag(d, x0 + 76, yy + rh / 2, 46, mix(col, ra))
        d.text((x0 + 126, yy + rh / 2), f["label"], font=load_font(40, "semi"), fill=mix(TEXT, ra), anchor="lm")
        pf = load_font(24, "bold")
        label = SEV_LABEL.get(sev, sev.upper())
        pw = pf.getlength(label) + 52
        px1 = x0 + rw - 24
        px0 = px1 - pw
        pill(d, (px0, yy + rh / 2 - 22, px1, yy + rh / 2 + 22), 22, (col[0], col[1], col[2], 60), a=ra)
        d.rounded_rectangle((px0, yy + rh / 2 - 22, px1, yy + rh / 2 + 22), radius=22, outline=mix(col, ra), width=2)
        d.text(((px0 + px1) / 2, yy + rh / 2), label, font=pf, fill=mix(col, ra), anchor="mm")
    # real quote in a floating card on the right (no overlap with the caption)
    qa = a_in(el, 0.5 + len(flags) * 0.24 + 0.2, 0.7)
    if qa > 0:
        cx = 1580
        cy = 520 + bob(el, 8, 0.9)
        bx0, bx1 = cx - 250, cx + 250
        by0, by1 = 340, 720
        glass(d, (bx0, by0, bx1, by1), 26, qa, fill=(BRAND[0], BRAND[1], BRAND[2], 66), shadow_a=0.5)
        icon_flag(d, cx, by0 + 78, 74, mix(RED, qa))
        d.text((cx, by0 + 150), "QUOTED FROM THE", font=load_font(22, "bold"), fill=mix(MINT, qa), anchor="mm")
        d.text((cx, by0 + 180), "AGREEMENT", font=load_font(22, "bold"), fill=mix(MINT, qa), anchor="mm")
        qf = load_font(34, "semi")
        lines = wrap_clamp(d, f"\u201c{data['quote']}\u201d", qf, bx1 - bx0 - 70, 3)
        ty = by0 + 236
        for ln in lines:
            d.text((cx, ty), ln, font=qf, fill=mix(TEXT, qa), anchor="mm")
            ty += 44


def scene_understand(d, el, dur, data):
    headline(d, el, "A clear risk score.", "What is risky, what is missing, and what to ask.")
    score = int(data["risk_score"])
    key = data["risk_key"]
    col = RISK_COLOR.get(key, BRAND)
    a = a_in(el, 0.5, 0.7)
    if a <= 0:
        return
    x0, x1 = 300, 1180
    y0, y1 = 400, 900
    rise = (1 - a) * 24
    glass(d, (x0, y0 + rise, x1, y1 + rise), 26, a)
    # gauge on the left of the card
    gx, gy, gr = x0 + 240, (y0 + y1) / 2 + rise, 150
    p = ease_out((el - 0.8) / 1.6)
    d.arc((gx - gr, gy - gr, gx + gr, gy + gr), start=135, end=405, fill=(255, 255, 255, al(0.10 * a)), width=26)
    d.arc((gx - gr, gy - gr, gx + gr, gy + gr), start=135, end=135 + 270 * max(0.0, p), fill=mix(col, a), width=26)
    d.text((gx, gy - 6), str(int(round(score * max(0.0, min(1.0, p))))), font=load_font(84, "bold"), fill=mix(TEXT, a), anchor="mm")
    d.text((gx, gy + 66), "RISK SCORE", font=load_font(22, "bold"), fill=mix(MUTED, a), anchor="mm")
    # stat rows on the right of the card
    c = data["counts"]
    rows = [("flag", c["flagged"], "flagged clauses"), ("lock", c["missing"], "missing protections"),
            ("search", c["questions"], "questions to ask")]
    rx = x0 + 470
    for i, (ic, num, label) in enumerate(rows):
        ra = a_in(el, 0.75 + i * 0.2, 0.55)
        if ra <= 0:
            continue
        yy = y0 + 80 + i * 130 + rise
        d.rounded_rectangle((rx, yy, rx + 70, yy + 70), radius=16, fill=(BRAND[0], BRAND[1], BRAND[2], al(0.30 * ra)))
        ICONS[ic](d, rx + 35, yy + 35, 44, mix(MINT, ra))
        pp = max(0.0, ease_out((el - (0.95 + i * 0.2)) / 1.1))
        d.text((rx + 96, yy + 20), str(int(round(num * pp))), font=load_font(56, "bold"), fill=mix(TEXT, ra), anchor="lm")
        d.text((rx + 96, yy + 62), label, font=load_font(28, "regular"), fill=mix(MUTED, ra), anchor="lm")
    draw_character(d, 1780, H + 30, 520, el, mood="idle", laptop=True)


def scene_act(d, el, dur, data):
    headline(d, el, "Know what to ask.", "Plain questions to raise before you sign.")
    qs = data.get("questions") or []
    items = qs[:3] if qs else ["Ask about notice periods.", "Ask who pays for repairs.", "Ask about the deposit."]
    a = a_in(el, 0.5, 0.7)
    if a <= 0:
        return
    x0, x1 = 300, 1180
    y0, y1 = 400, 900
    rise = (1 - a) * 24
    glass(d, (x0, y0 + rise, x1, y1 + rise), 26, a)
    n = len(items)
    row_h = (y1 - y0 - 70) / n
    for i, q in enumerate(items):
        ra = a_in(el, 0.7 + i * 0.25, 0.55)
        if ra <= 0:
            continue
        yy = y0 + 40 + i * row_h + rise
        d.ellipse((x0 + 34, yy + 8, x0 + 70, yy + 44), outline=mix(MINT_DIM, ra * 0.7), width=2)
        # tick once the row has settled
        tb = a_in(el, 1.2 + i * 0.25, 0.4)
        if tb > 0:
            icon_check(d, x0 + 52, yy + 26, 34, mix(BRAND, tb))
        f = load_font(28, "regular")
        lines = wrap_clamp(d, q, f, x1 - x0 - 130, 3)
        ly = yy + 6
        for ln in lines:
            d.text((x0 + 96, ly), ln, font=f, fill=mix(TEXT, ra), anchor="lm")
            ly += 36
    draw_character(d, 1740, H + 50, 540, el, mood="idle")


def scene_outro(d, el, dur, data):
    a = a_in(el, 0.05, 0.6)
    if a > 0:
        s = 160 * (0.82 + 0.18 * pop(min(1.0, (el - 0.05) / 0.6)))
        icon_shield(d, W / 2 - 60, 430, s, mix(BRAND, a), check_color=mix(WHITE, a))
    ta = a_in(el, 0.3, 0.6)
    if ta > 0:
        d.text((W / 2 - 60, 560), "RentCheck", font=load_font(104, "bold"), fill=mix(TEXT, ta), anchor="mm")
    da = a_in(el, 0.55, 0.6)
    if da > 0:
        d.text((W / 2 - 60, 640), "Know what you're signing, before you sign it.",
               font=load_font(44, "semi"), fill=mix(MINT, da), anchor="mm")
    ua = a_in(el, 0.8, 0.6)
    if ua > 0:
        f = load_font(38, "bold")
        url = "rentcheck.rumptycloud.app"
        pw = f.getlength(url) + 76
        pill(d, (W / 2 - 60 - pw / 2, 706, W / 2 - 60 + pw / 2, 776), 36, (BRAND[0], BRAND[1], BRAND[2], 230), a=ua)
        d.text((W / 2 - 60, 741), url, font=f, fill=mix(WHITE, ua), anchor="mm")
    fa = a_in(el, 1.05, 0.6)
    if fa > 0:
        d.text((W / 2 - 60, 846), "Not legal advice - always verify anything important.",
               font=load_font(28, "regular"), fill=mix(MUTED, fa), anchor="mm")
    draw_character(d, 1780, H + 20, 560, el, mood="wave")


# --------------------------------------------------------------------------- #
# scene table
# --------------------------------------------------------------------------- #
SCENES = [
    {"key": "hook", "build": scene_hook, "pad": HOOK_PAD,
     "vo": "Signing a tenancy agreement shouldn't feel like a guess. But too often, it does."},
    {"key": "upload", "build": scene_upload, "stage": "01  -  UPLOAD",
     "vo": "So start by adding your agreement. You can paste the text, or upload a PDF, a photo, "
           "or a Word document."},
    {"key": "analyse", "build": scene_analyse, "stage": "02  -  ANALYSE",
     "vo": "RentCheck splits it into clauses, and checks each one against common Nigerian rental norms."},
    {"key": "flag", "build": scene_flag, "stage": "03  -  FLAGGED",
     "vo": "Anything unfair or risky gets flagged. And every flag quotes the exact words, so you can "
           "check it for yourself."},
    {"key": "understand", "build": scene_understand, "stage": "04  -  YOUR REPORT",
     "vo": "You get a clear risk score, the protections that are missing, and a plain-English reason "
           "behind every flag."},
    {"key": "act", "build": scene_act, "stage": "05  -  WHAT TO ASK",
     "vo": "And a ready list of questions to ask, so you know exactly what to raise before you sign."},
    {"key": "outro", "build": scene_outro,
     "vo": "RentCheck. Know what you're signing, before you sign it. Not legal advice."},
]


# --------------------------------------------------------------------------- #
# ffmpeg helpers
# --------------------------------------------------------------------------- #
def ff(args: list[str]) -> None:
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def probe_duration(path: str) -> float:
    out = subprocess.run([FFMPEG, "-i", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in out.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"could not read duration of {path}")


# --------------------------------------------------------------------------- #
# voiceover
# --------------------------------------------------------------------------- #
async def _synth(items, voice, rate, pitch):
    for text, out in items:
        await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)


def synthesize(scenes, voice, rate, pitch) -> list[float]:
    os.makedirs(WORK, exist_ok=True)
    items = [(s["vo"], os.path.join(WORK, f"vo_{i:02d}.mp3")) for i, s in enumerate(scenes)]
    print("[vo] synthesising narration ...")
    asyncio.run(_synth(items, voice, rate, pitch))
    return [probe_duration(out) for _, out in items]


# --------------------------------------------------------------------------- #
# ambient music bed
# --------------------------------------------------------------------------- #
def make_music(path: str, duration: float, sr: int = 44100) -> None:
    if duration <= 1:
        duration = 1.0
    chords = [
        (220.00, 261.63, 329.63),   # A minor
        (174.61, 220.00, 261.63),   # F major
        (130.81, 164.81, 196.00),   # C major
        (196.00, 246.94, 293.66),   # G major
    ]
    seg = max(6.0, duration / max(1, math.ceil(duration / 8.0)))
    xfade = 2.5
    n = int(duration * sr)
    buf = array.array("h", bytes(2 * n))
    two_pi = 2 * math.pi
    fade_in, fade_out = 2.5, 3.0
    for i in range(n):
        t = i / sr
        pos = t / seg
        k = int(pos) % len(chords)
        nxt = (k + 1) % len(chords)
        into = (pos - int(pos)) * seg
        blend = clamp01((seg - into) / xfade) if into > seg - xfade else 0.0
        s = 0.0
        for ci, wgt in ((k, 1.0 - blend), (nxt, blend)):
            for f in chords[ci]:
                s += wgt * (math.sin(two_pi * f * t) + 0.32 * math.sin(two_pi * 2 * f * t)
                            + 0.10 * math.sin(two_pi * 3 * f * t))
        s /= 4.26
        s *= 0.88 + 0.12 * math.sin(two_pi * 0.07 * t)
        env = min(clamp01(t / fade_in), clamp01((duration - t) / fade_out))
        buf[i] = int(max(-32767, min(32767, s * env * 0.30 * 32767)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_scene(scene, dur, g_before, total, out):
    bg = get_base()
    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt",
           "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = max(2, int(round(dur * FPS)))
    build = scene["build"]
    for i in range(n):
        el = i / FPS
        content.paste((0, 0, 0, 0), (0, 0, W, H))
        d = ImageDraw.Draw(content, "RGBA")
        draw_particles(d, el + g_before)
        build(d, el, dur, DATA_CACHE)
        fade = min(a_in(el, 0.0, FADE), a_out(el, dur, FADE))
        img = Image.alpha_composite(bg, content)
        # chrome on its own layer so alpha blends correctly
        ch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(ch, "RGBA")
        draw_chrome(cd, scene, el, g_before, total)
        img = Image.alpha_composite(img, ch)
        if fade < 0.999:
            img = Image.blend(img, bg, 1 - fade)
        proc.stdin.write(img.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()


def render_audio(vo: str, dur: float, out: str) -> None:
    ms = int(LEAD * 1000)
    ff(["-i", vo, "-af", f"adelay={ms}|{ms},apad", "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", out])


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
DATA_CACHE: dict = {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", default="-3%")
    ap.add_argument("--pitch", default="-2Hz")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--out", default=os.path.join(ARTIFACTS, "rentcheck-explainer.mp4"))
    ap.add_argument("--no-music", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print(f"real-data file not found: {args.data}\nRun tests/export_explainer_data.py first.")
        return 1
    with open(args.data, encoding="utf-8") as fh:
        DATA_CACHE.update(json.load(fh))
    print(f"[data] risk={DATA_CACHE['risk_score']} ({DATA_CACHE['risk_level']}), "
          f"flagged={len(DATA_CACHE['flagged'])}, questions={len(DATA_CACHE.get('questions') or [])}, "
          f"provenance={DATA_CACHE.get('provenance', '?')}")

    init_particles()
    os.makedirs(WORK, exist_ok=True)
    vo_durs = synthesize(SCENES, args.voice, args.rate, args.pitch)

    durs = [round(max(3.2, vd + sc.get("pad", PAD)), 3) for sc, vd in zip(SCENES, vo_durs)]
    total = sum(durs)
    print(f"[timing] total {total:.2f}s")
    for sc, vd, dd in zip(SCENES, vo_durs, durs):
        print(f"  {sc['key']:11s} vo={vd:5.2f}s  scene={dd:5.2f}s")

    vparts, aparts = [], []
    g_before = 0.0
    for i, (sc, dur) in enumerate(zip(SCENES, durs)):
        vp = os.path.join(WORK, f"v_{i:02d}.mp4")
        apre = os.path.join(WORK, f"a_{i:02d}.wav")
        print(f"[render] scene {i} ({sc['key']}) {dur:.2f}s ...")
        render_scene(sc, dur, g_before, total, vp)
        render_audio(os.path.join(WORK, f"vo_{i:02d}.mp3"), dur, apre)
        vparts.append(vp)
        aparts.append(apre)
        g_before += dur

    vlist, alist = os.path.join(WORK, "v.txt"), os.path.join(WORK, "a.txt")
    with open(vlist, "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{p}'\n" for p in vparts)
    with open(alist, "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{p}'\n" for p in aparts)

    full_v, full_a = os.path.join(WORK, "full.mp4"), os.path.join(WORK, "full.wav")
    ff(["-f", "concat", "-safe", "0", "-i", vlist, "-c", "copy", full_v])
    ff(["-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", full_a])

    if args.no_music:
        ff(["-i", full_v, "-i", full_a, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", args.out])
    else:
        music = os.path.join(WORK, "music.wav")
        print("[music] synthesising ambient bed ...")
        make_music(music, total)
        ff([
            "-i", full_v, "-i", full_a, "-i", music,
            "-filter_complex",
            "[2:a]volume=0.11,highpass=f=55,lowpass=f=7500,"
            "afade=t=in:st=0:d=3,afade=t=out:st=%.2f:d=3[m];"
            "[1:a]volume=1.0,asplit=2[v][sc];"
            "[m][sc]sidechaincompress=threshold=0.045:ratio=7:attack=25:release=380:makeup=1[duck];"
            "[v][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
            % max(0.0, total - 3.0),
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", args.out,
        ])

    dur = probe_duration(args.out)
    print(f"\n[done] {args.out}  ({dur:.1f}s, {os.path.getsize(args.out)} bytes)")
    shutil.rmtree(WORK, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

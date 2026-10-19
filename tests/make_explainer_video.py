"""
Build the RentCheck explainer video as a classic MOTION-GRAPHICS explainer.

Design rules (per the brief)
----------------------------
* Motion is calm and minimal: fades, gentle scale, soft opacity, subtle
  vertical easing only.  Nothing slides sideways across the screen.
* It is an explainer, not a screen recording: every scene is drawn with icons,
  simple illustrations and short on-screen text - the app UI is never shown.
* One idea per scene, with a short voiceover line each.
* The content is driven by REAL analysis output: tests/export_explainer_data.py
  runs a real tenancy agreement from the database through the real pipeline and
  writes tests/fixtures/explainer_data.json (already anonymised).
* Brand palette and fonts match the product.
* Professional voiceover (Edge neural TTS) with scene timing synced to the
  narration, plus a soft ambient music bed at low volume.

Pipeline
--------
1. Load the real analysis JSON.
2. Synthesise one voiceover line per scene; each scene's length follows its VO.
3. Render each scene frame-by-frame with Pillow and pipe raw RGB frames
   straight into ffmpeg (no PNG round-trip).
4. Concatenate video, build the matching narration track, synthesise a quiet
   music bed, mix and mux to H.264/AAC mp4.

Requires (dev only):  pip install -r requirements-dev.txt
    imageio-ffmpeg edge-tts

Run from the repo root:
    python tests/make_explainer_video.py
    python tests/make_explainer_video.py --voice en-GB-SoniaNeural
"""
from __future__ import annotations

import argparse
import array
import asyncio
import json
import math
import os
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

# Brand palette (matches app/static/styles.css)
BRAND = (14, 122, 82)
BRAND_DARK = (10, 92, 62)
BRAND_DEEP = (7, 61, 41)
BRAND_SOFT = (232, 244, 238)
INK = (16, 32, 26)
MUTED = (86, 106, 97)
FAINT = (150, 168, 160)
BG = (244, 247, 245)
CARD = (255, 255, 255)
LINE = (216, 226, 221)
MINT = (143, 227, 189)
AMBER = (185, 119, 10)
RED = (192, 57, 43)
BLUE = (47, 111, 176)
WHITE = (255, 255, 255)

SEV_COLOR = {"high": RED, "medium": AMBER, "low": BLUE}
SEV_LABEL = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
RISK_COLOR = {"high": RED, "medium": AMBER, "low": BLUE}

FONT_BOLD = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
FONT_SEMI = [r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
FONT_REG = [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]

# extra seconds beyond the voiceover, and narration lead-in
PAD = 1.0
INTRO_PAD = 1.7
LEAD = 0.45
FADE = 0.5

FFMPEG = str(imageio_ffmpeg.get_ffmpeg_exe())


# --------------------------------------------------------------------------- #
# small math / easing helpers
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
    while size > 20:
        f = load_font(size, weight)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return load_font(20, weight)


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


def draw_center(d, cx, y, text, font, fill, anchor="mm"):
    d.text((cx, y), text, font=font, fill=fill, anchor=anchor)


def tracked(text: str) -> str:
    """Fake letter-spacing for small uppercase kickers."""
    return " ".join(text.upper())


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def panel(d, box, radius, fill, shadow=True, shadow_a=0.10, dy=10):
    x0, y0, x1, y1 = box
    if shadow:
        d.rounded_rectangle((x0 + 2, y0 + dy, x1 + 2, y1 + dy), radius=radius,
                            fill=(16, 32, 26, al(shadow_a)))
    d.rounded_rectangle(box, radius=radius, fill=fill)


def line_round(d, pts, fill, w):
    d.line(pts, fill=fill, width=int(w), joint="curve")
    r = w / 2.0
    for p in (pts[0], pts[-1]):
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=fill)


def shield_pts(cx, cy, w, h):
    x, y = cx - w / 2, cy - h / 2
    return [
        (x, y), (x + w, y), (x + w, y + h * 0.44),
        (x + w * 0.62, y + h * 0.82), (x + w * 0.5, y + h),
        (x + w * 0.38, y + h * 0.82), (x, y + h * 0.44),
    ]


def draw_shield(d, cx, cy, size, color, check=True, check_color=WHITE):
    w, h = size, size * 1.15
    x, y = cx - w / 2, cy - h / 2
    d.polygon(shield_pts(cx, cy, w, h), fill=color)
    if check:
        lw = max(3, int(size * 0.10))
        line_round(d, [(x + w * 0.30, y + h * 0.42), (x + w * 0.45, y + h * 0.58),
                       (x + w * 0.72, y + h * 0.30)], check_color, lw)


# --- line icons (all centred on cx,cy, sized to s) ------------------------- #
def icon_doc(d, cx, cy, s, color, w=None, lines=4, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    x0, y0 = cx - s * 0.42, cy - s * 0.55
    x1, y1 = cx + s * 0.42, cy + s * 0.55
    d.rounded_rectangle((x0, y0, x1, y1), radius=int(s * 0.09), outline=col, width=w)
    ly = y0 + s * 0.30
    for i in range(lines):
        end = x1 - s * (0.14 if i % 3 == 2 else 0.30)
        d.line((x0 + s * 0.16, ly, end, ly), fill=col, width=w)
        ly += s * 0.20


def icon_upload(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    # tray
    y0 = cy + s * 0.10
    d.line((cx - s * 0.34, y0, cx - s * 0.34, cy + s * 0.44), fill=col, width=w, joint="curve")
    d.line((cx - s * 0.34, cy + s * 0.44, cx + s * 0.34, cy + s * 0.44), fill=col, width=w, joint="curve")
    d.line((cx + s * 0.34, cy + s * 0.44, cx + s * 0.34, y0), fill=col, width=w, joint="curve")
    # up arrow
    d.line((cx, cy + s * 0.30, cx, cy - s * 0.42), fill=col, width=w)
    d.line((cx - s * 0.22, cy - s * 0.18, cx, cy - s * 0.42, cx + s * 0.22, cy - s * 0.18),
           fill=col, width=w, joint="curve")


def icon_search(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.32
    d.ellipse((cx - r - s * 0.06, cy - r - s * 0.20, cx + r - s * 0.06, cy + r - s * 0.20),
              outline=col, width=w)
    line_round(d, [(cx + r * 0.62, cy + r * 0.42), (cx + s * 0.40, cy + s * 0.44)], col, w)


def icon_check(d, cx, cy, s, color, alpha=1.0):
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.46
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    lw = max(3, int(s * 0.13))
    line_round(d, [(cx - s * 0.22, cy + s * 0.02), (cx - s * 0.05, cy + s * 0.19),
                   (cx + s * 0.24, cy - s * 0.19)], WHITE, lw)


def icon_flag(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    d.line((cx - s * 0.22, cy - s * 0.46, cx - s * 0.22, cy + s * 0.48), fill=col, width=w)
    d.polygon([(cx - s * 0.22, cy - s * 0.44), (cx + s * 0.40, cy - s * 0.26),
               (cx - s * 0.22, cy - s * 0.04)], fill=col)


def icon_bars(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.10))
    col = mix(color, alpha) if len(color) == 3 else color
    base_y = cy + s * 0.42
    for i, hh in enumerate((0.40, 0.66, 0.92)):
        x = cx - s * 0.30 + i * s * 0.30
        d.rounded_rectangle((x - w / 2, base_y - s * hh, x + w / 2, base_y),
                            radius=int(w / 2), fill=col)


def icon_question(d, cx, cy, s, color, alpha=1.0):
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.46
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    f = load_font(int(s * 0.66), "bold")
    d.text((cx, cy + s * 0.02), "?", font=f, fill=WHITE, anchor="mm")


def icon_clock(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    r = s * 0.44
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)
    line_round(d, [(cx, cy - r * 0.55), (cx, cy), (cx + r * 0.50, cy + r * 0.30)], col, w)


def icon_lock(d, cx, cy, s, color, w=None, alpha=1.0):
    w = w or max(3, int(s * 0.075))
    col = mix(color, alpha) if len(color) == 3 else color
    bw, bh = s * 0.66, s * 0.50
    d.rounded_rectangle((cx - bw / 2, cy - s * 0.06, cx + bw / 2, cy + s * 0.44),
                        radius=int(s * 0.10), fill=col)
    d.arc((cx - bw * 0.32, cy - s * 0.44, cx + bw * 0.32, cy + s * 0.10),
          start=180, end=360, fill=col, width=w)


ICONS = {
    "doc": lambda d, x, y, s, c, a=1.0: icon_doc(d, x, y, s, c, alpha=a),
    "upload": lambda d, x, y, s, c, a=1.0: icon_upload(d, x, y, s, c, alpha=a),
    "search": lambda d, x, y, s, c, a=1.0: icon_search(d, x, y, s, c, alpha=a),
    "bars": lambda d, x, y, s, c, a=1.0: icon_bars(d, x, y, s, c, alpha=a),
    "flag": lambda d, x, y, s, c, a=1.0: icon_flag(d, x, y, s, c, alpha=a),
    "clock": lambda d, x, y, s, c, a=1.0: icon_clock(d, x, y, s, c, alpha=a),
    "lock": lambda d, x, y, s, c, a=1.0: icon_lock(d, x, y, s, c, alpha=a),
}


# --------------------------------------------------------------------------- #
# background
# --------------------------------------------------------------------------- #
_BASE_CACHE: dict = {}


def soft_glow(d, cx, cy, radius, color, max_alpha, steps=54):
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = max_alpha * (1 - i / steps) ** 2.1
        if a <= 0.004:
            continue
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, al(a)))


def get_base() -> Image.Image:
    if "base" in _BASE_CACHE:
        return _BASE_CACHE["base"]
    img = Image.new("RGBA", (W, H), (*BG, 255))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    # faint vertical wash, slightly brighter at the top
    for y in range(0, H, 4):
        t = y / H
        v = int(6 * (1 - t))
        d.rectangle((0, y, W, y + 4), fill=(255, 255, 255, v))
    # soft brand-tinted glows (top-right and bottom-left)
    soft_glow(d, W - 300, 90, 760, BRAND, 0.085)
    soft_glow(d, 240, H - 60, 720, MINT, 0.16)
    img = Image.alpha_composite(img, ov)
    _BASE_CACHE["base"] = img
    return img


# --------------------------------------------------------------------------- #
# global chrome: progress rail, brand mark, caption
# --------------------------------------------------------------------------- #
def draw_chrome(d, scene_key, idx, el, dur, g_before, total):
    # vertical progress rail (grows downward - no sideways motion)
    x = 52
    top, bot = 150, H - 150
    d.rounded_rectangle((x, top, x + 6, bot), radius=3, fill=(16, 32, 26, 26))
    frac = clamp01((g_before + el) / total)
    y = top + (bot - top) * frac
    if y > top + 3:
        d.rounded_rectangle((x, top, x + 6, y), radius=3, fill=(*BRAND, 235))

    # brand mark (top-left), fades in
    if scene_key not in ("intro", "outro"):
        a = a_in(el, 0.15, 0.5)
        if a > 0:
            draw_shield(d, 132, 92, 34, mix(BRAND, a), check_color=mix(WHITE, a))
            d.text((166, 94), "RentCheck", font=load_font(30, "bold"),
                   fill=mix(BRAND_DEEP, a), anchor="lm")

    # soft caption of the narration line (accessibility), fades in late
    vo = SCENE_BY_KEY[scene_key]["vo"]
    a = a_in(el, 0.5, 0.6)
    if a > 0:
        cap = load_font(28, "regular")
        lines = wrap(d, vo, cap, 1560)[:2]
        y0 = H - 78 if len(lines) == 2 else H - 54
        for i, ln in enumerate(lines):
            d.text((W / 2 + 1, y0 + i * 36 + 1), ln, font=cap, fill=(16, 32, 26, al(0.10 * a)), anchor="mm")
            d.text((W / 2, y0 + i * 36), ln, font=cap, fill=(72, 90, 82, al(0.92 * a)), anchor="mm")


# --------------------------------------------------------------------------- #
# scene drawing
# --------------------------------------------------------------------------- #
def kicker_headline(d, el, kicker, headline, sub=None, hsize=78):
    ka = a_in(el, 0.10, 0.45)
    if ka > 0:
        d.text((W / 2, 168), tracked(kicker), font=load_font(26, "bold"),
               fill=mix(BRAND, ka), anchor="mm")
    ha = a_in(el, 0.22, 0.55)
    if ha > 0:
        hf = fit_font(headline, 1500, hsize, "bold")
        y = 246 - (1 - ha) * 22
        d.text((W / 2, y), headline, font=hf, fill=mix(INK, ha), anchor="mm")
    if sub:
        sa = a_in(el, 0.45, 0.55)
        if sa > 0:
            sf = fit_font(sub, 1200, 38, "regular")
            d.text((W / 2, 316), sub, font=sf, fill=mix(MUTED, sa), anchor="mm")


def scene_intro(d, el, dur, data):
    a = a_in(el, 0.05, 0.6)
    if a > 0:
        s = 176 * (0.80 + 0.20 * pop(min(1.0, (el - 0.05) / 0.6)))
        draw_shield(d, W / 2, 470, s, mix(BRAND, a), check_color=mix(WHITE, a))
    ta = a_in(el, 0.35, 0.6)
    if ta > 0:
        y = 690 - (1 - ta) * 24
        d.text((W / 2, y), "RentCheck", font=load_font(118, "bold"), fill=mix(BRAND_DEEP, ta), anchor="mm")
    sa = a_in(el, 0.60, 0.6)
    if sa > 0:
        d.text((W / 2, 770), "Tenancy agreement review", font=load_font(40, "regular"),
               fill=mix(MUTED, sa), anchor="mm")


def scene_problem(d, el, dur, data):
    kicker_headline(d, el, "The problem", "Long agreements. One-sided terms.",
                    "It is easy to sign without understanding what is inside.")
    # a document card, revealed with a gentle rise
    ca = a_in(el, 0.55, 0.7)
    if ca <= 0:
        return
    cw, ch = 660, 520
    cx, top = W / 2, 418
    rise = (1 - ca) * 26
    top = top + rise
    panel(d, (cx - cw / 2, top, cx + cw / 2, top + ch), 28, mix(CARD, ca))
    # heading line inside the document
    d.rounded_rectangle((cx - cw / 2 + 46, top + 50, cx - cw / 2 + 240, top + 72),
                        radius=7, fill=mix((30, 60, 50), ca * 0.85))
    ly = top + 122
    highlights = {2: AMBER, 5: RED, 8: AMBER}
    for i in range(11):
        w = cw - 130 if i % 4 else cw - 280
        col = mix(LINE, ca)
        if i in highlights:
            pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(el * 3.2 + i))
            col = mix(highlights[i], ca * (0.35 + 0.5 * pulse))
            fx = cx - cw / 2 + 46 + w + 30
            fa = a_in(el, 0.9 + i * 0.12, 0.5)
            if fa > 0:
                d.ellipse((fx - 9, ly - 9, fx + 9, ly + 9), fill=mix(highlights[i], ca * fa))
        d.rounded_rectangle((cx - cw / 2 + 46, ly - 8, cx - cw / 2 + 46 + w, ly + 8),
                            radius=8, fill=col)
        ly += 36
    # question badge on the card's top-right corner (scale pop)
    qa = a_in(el, 1.25, 0.6)
    if qa > 0:
        qs = 68 * (0.7 + 0.3 * pop(min(1.0, (el - 1.25) / 0.6)))
        icon_question(d, cx + cw / 2 - 10, top + 18, qs, mix(RED, qa))


def scene_add(d, el, dur, data):
    kicker_headline(d, el, "Step 1 - add it", "Add your agreement.",
                    "Paste the text, or upload a file.")
    ca = a_in(el, 0.5, 0.7)
    if ca <= 0:
        return
    cw, ch = 1120, 380
    x0, y0 = W / 2 - cw / 2, 420
    rise = (1 - ca) * 24
    y0 += rise
    # dashed drop zone
    dash = mix((150, 200, 178), ca)
    step = 30
    x = x0
    while x < x0 + cw:
        d.line((x, y0, min(x + 18, x0 + cw), y0), fill=dash, width=5)
        d.line((x, y0 + ch, min(x + 18, x0 + cw), y0 + ch), fill=dash, width=5)
        x += step
    y = y0
    while y < y0 + ch:
        d.line((x0, y, x0, min(y + 18, y0 + ch)), fill=dash, width=5)
        d.line((x0 + cw, y, x0 + cw, min(y + 18, y0 + ch)), fill=dash, width=5)
        y += step
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=28, fill=mix((247, 251, 249), ca))
    # upload icon rises gently + fades
    ia = a_in(el, 0.75, 0.7)
    if ia > 0:
        icon_upload(d, W / 2, y0 + 120 - (1 - ia) * 22, 150, mix(BRAND, ia))
    ta = a_in(el, 0.95, 0.6)
    if ta > 0:
        d.text((W / 2, y0 + 232), "Drop a file here, or paste your text",
               font=load_font(38, "semi"), fill=mix(INK, ta), anchor="mm")
        d.text((W / 2, y0 + 288), "PDF  .  Photo  .  Word  .  Plain text",
               font=load_font(30, "regular"), fill=mix(MUTED, ta), anchor="mm")


def scene_analyse(d, el, dur, data):
    kicker_headline(d, el, "Step 2 - analyse", "Every clause, checked.",
                    "Compared against common Nigerian rental norms.")
    rows = 5
    rw, rh, gap = 1080, 92, 18
    x0 = W / 2 - rw / 2
    top = 400
    total_h = rows * rh + (rows - 1) * gap
    # scanning highlight sweeping downward over the clause rows (vertical only)
    scan = clamp01((el - 0.6) / 2.2)
    col_a = a_in(el, 0.5, 0.6)
    for i in range(rows):
        ra = a_in(el, 0.55 + i * 0.14, 0.55)
        if ra <= 0:
            continue
        yy = top + i * (rh + gap) - (1 - ra) * 18
        panel(d, (x0, yy, x0 + rw, yy + rh), 18, mix(CARD, ra), shadow_a=0.07, dy=7)
        # fake clause text bars
        bw = rw - 320 if i % 2 == 0 else rw - 420
        d.rounded_rectangle((x0 + 34, yy + rh / 2 - 9, x0 + 34 + bw * 0.62, yy + rh / 2 + 9),
                            radius=9, fill=mix(LINE, ra))
        d.rounded_rectangle((x0 + 34, yy + rh / 2 + 20, x0 + 34 + bw * 0.38, yy + rh / 2 + 32),
                            radius=6, fill=mix((238, 244, 241), ra))
        # check badge pops in
        cb = a_in(el, 1.0 + i * 0.30, 0.45)
        if cb > 0:
            cs = 46 * (0.65 + 0.35 * pop(min(1.0, (el - (1.0 + i * 0.30)) / 0.45)))
            icon_check(d, x0 + rw - 58, yy + rh / 2, cs, mix(BRAND, cb))
    # soft scan band sweeping downward
    if col_a > 0 and scan < 1.0:
        by = top + scan * (total_h + 40) - 30
        d.rounded_rectangle((x0 - 40, by, x0 + rw + 40, by + 60), radius=20,
                            fill=(*BRAND, 22), outline=(*BRAND, 40), width=2)


def scene_flagged(d, el, dur, data):
    kicker_headline(d, el, "Step 3 - flagged", "Risky terms, flagged.",
                    "Every flag quotes the words in your agreement.")
    flags = data["flagged"]
    rw, rh, gap = 1120, 100, 16
    x0 = W / 2 - rw / 2
    top = 372
    for i, f in enumerate(flags):
        ra = a_in(el, 0.5 + i * 0.26, 0.55)
        if ra <= 0:
            continue
        yy = top + i * (rh + gap) - (1 - ra) * 20
        sev = f["severity"]
        col = SEV_COLOR.get(sev, BLUE)
        panel(d, (x0, yy, x0 + rw, yy + rh), 18, mix(CARD, ra), shadow_a=0.08, dy=7)
        d.rounded_rectangle((x0 + 22, yy + 20, x0 + 30, yy + rh - 20), radius=4, fill=mix(col, ra))
        icon_flag(d, x0 + 78, yy + rh / 2, 46, mix(col, ra))
        d.text((x0 + 128, yy + rh / 2), f["label"], font=load_font(42, "semi"),
               fill=mix(INK, ra), anchor="lm")
        # severity pill
        pf = load_font(24, "bold")
        label = SEV_LABEL.get(sev, sev.upper())
        pw = pf.getlength(label) + 52
        px1 = x0 + rw - 24
        px0 = px1 - pw
        d.rounded_rectangle((px0, yy + rh / 2 - 22, px1, yy + rh / 2 + 22), radius=22,
                            fill=(col[0], col[1], col[2], al(0.14 * ra)))
        d.rounded_rectangle((px0, yy + rh / 2 - 22, px1, yy + rh / 2 + 22), radius=22,
                            outline=(*col, al(0.9 * ra)), width=2)
        d.text(((px0 + px1) / 2, yy + rh / 2), label, font=pf, fill=mix(col, ra), anchor="mm")
    # quote plate
    qa = a_in(el, 0.5 + len(flags) * 0.26 + 0.15, 0.7)
    if qa > 0:
        y0 = top + len(flags) * (rh + gap) + 6
        y1 = y0 + 128
        panel(d, (x0, y0, x0 + rw, y1), 18, mix(BRAND_DEEP, qa), shadow_a=0.14, dy=8)
        d.rounded_rectangle((x0 + 22, y0 + 22, x0 + 30, y1 - 22), radius=4, fill=mix(MINT, qa))
        d.text((x0 + 60, y0 + 34), tracked("Quoted from the agreement"),
               font=load_font(22, "bold"), fill=mix(MINT, qa), anchor="lm")
        qf = fit_font(f"\u201c{data['quote']}\u201d", rw - 140, 40, "semi")
        d.text((x0 + 60, y0 + 84), f"\u201c{data['quote']}\u201d", font=qf,
               fill=mix(WHITE, qa), anchor="lm")


def scene_result(d, el, dur, data):
    kicker_headline(d, el, "Step 4 - your report", "A clear risk score.",
                    "What is risky, what is missing, and what to ask.")
    score = int(data["risk_score"])
    key = data["risk_key"]
    col = RISK_COLOR.get(key, BRAND)
    # gauge
    ga = a_in(el, 0.55, 0.7)
    if ga > 0:
        cx, cy, r = 540, 640, 168
        lw = 30
        box = (cx - r, cy - r, cx + r, cy + r)
        d.arc(box, start=135, end=405, fill=(16, 32, 26, al(0.10 * ga)), width=lw)
        p = ease_out((el - 0.75) / 1.6)
        d.arc(box, start=135, end=135 + 270 * max(0.0, p), fill=mix(col, ga), width=lw)
        shown = int(round(score * max(0.0, min(1.0, p)) / 1) )
        f = load_font(104, "bold")
        d.text((cx, cy - 14), str(shown), font=f, fill=mix(INK, ga), anchor="mm")
        d.text((cx, cy + 74), "RISK SCORE", font=load_font(26, "bold"),
               fill=mix(MUTED, ga), anchor="mm")
        lab = data["risk_level"].upper()
        lf = load_font(34, "bold")
        lw_ = lf.getlength(lab) + 56
        d.rounded_rectangle((cx - lw_ / 2, cy + 118, cx + lw_ / 2, cy + 174), radius=28,
                            fill=(col[0], col[1], col[2], al(0.14 * ga)))
        d.text((cx, cy + 146), lab, font=lf, fill=mix(col, ga), anchor="mm")
    # stat cards
    c = data["counts"]
    stats = [
        ("flag", c["flagged"], "flagged clauses"),
        ("lock", c["missing"], "missing protections"),
        ("search", c["questions"], "questions to ask"),
    ]
    x0, x1 = 880, 1700
    ch, gap = 140, 22
    top = 430
    for i, (ic, num, label) in enumerate(stats):
        ra = a_in(el, 0.7 + i * 0.22, 0.6)
        if ra <= 0:
            continue
        yy = top + i * (ch + gap) - (1 - ra) * 20
        panel(d, (x0, yy, x1, yy + ch), 20, mix(CARD, ra), shadow_a=0.08, dy=7)
        d.rounded_rectangle((x0 + 24, yy + 24, x0 + 24 + 92, yy + ch - 24), radius=18,
                            fill=(BRAND[0], BRAND[1], BRAND[2], al(0.10 * ra)))
        ICONS[ic](d, x0 + 70, yy + ch / 2, 58, mix(BRAND, ra))
        p = max(0.0, ease_out((el - (0.9 + i * 0.22)) / 1.1))
        d.text((x0 + 150, yy + ch / 2 - 18), str(int(round(num * p))), font=load_font(66, "bold"),
               fill=mix(INK, ra), anchor="lm")
        d.text((x0 + 150, yy + ch / 2 + 40), label, font=load_font(32, "regular"),
               fill=mix(MUTED, ra), anchor="lm")
    # real summary line
    sa = a_in(el, 1.5, 0.7)
    if sa > 0:
        d.text((W / 2, 930), data["summary"], font=load_font(30, "regular"),
               fill=mix(MUTED, sa), anchor="mm")


def scene_outro(d, el, dur, data):
    a = a_in(el, 0.05, 0.6)
    if a > 0:
        s = 150 * (0.82 + 0.18 * pop(min(1.0, (el - 0.05) / 0.6)))
        draw_shield(d, W / 2, 372, s, mix(BRAND, a), check_color=mix(WHITE, a))
    ta = a_in(el, 0.30, 0.6)
    if ta > 0:
        d.text((W / 2, 540), "RentCheck", font=load_font(104, "bold"),
               fill=mix(BRAND_DEEP, ta), anchor="mm")
    da = a_in(el, 0.55, 0.6)
    if da > 0:
        d.text((W / 2, 622), "Know what you are signing, before you sign it.",
               font=load_font(48, "semi"), fill=mix(INK, da), anchor="mm")
    ua = a_in(el, 0.8, 0.6)
    if ua > 0:
        f = load_font(40, "bold")
        url = "rentcheck.rumptycloud.app"
        pw = f.getlength(url) + 76
        d.rounded_rectangle((W / 2 - pw / 2, 706, W / 2 + pw / 2, 782), radius=38,
                            fill=mix(BRAND, ua))
        d.text((W / 2, 744), url, font=f, fill=mix(WHITE, ua), anchor="mm")
    fa = a_in(el, 1.05, 0.6)
    if fa > 0:
        d.text((W / 2, 856), "Not legal advice - always verify anything important.",
               font=load_font(30, "regular"), fill=mix(MUTED, fa), anchor="mm")


# --------------------------------------------------------------------------- #
# scenes
# --------------------------------------------------------------------------- #
SCENES = [
    {"key": "intro", "build": scene_intro, "pad": INTRO_PAD,
     "vo": "RentCheck."},
    {"key": "problem", "build": scene_problem,
     "vo": "Most tenancy agreements are long, and, honestly, pretty one-sided. "
           "And it's far too easy to sign one without understanding what's actually in it."},
    {"key": "add", "build": scene_add,
     "vo": "So, add your agreement. You can paste the text, or upload a PDF, a photo, "
           "or a Word document."},
    {"key": "analyse", "build": scene_analyse,
     "vo": "RentCheck reads it clause by clause, and checks each one against common "
           "Nigerian rental norms."},
    {"key": "flagged", "build": scene_flagged,
     "vo": "Anything unfair or risky gets flagged. And every flag quotes the exact words, "
           "so you can check it for yourself."},
    {"key": "result", "build": scene_result,
     "vo": "Then you get a clear risk score, the protections that are missing, and the "
           "questions to ask before you sign."},
    {"key": "outro", "build": scene_outro,
     "vo": "RentCheck. Know what you're signing, before you sign it. Not legal advice."},
]
SCENE_BY_KEY = {s["key"]: s for s in SCENES}


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
# ambient music bed (synthesised, no external asset / licence)
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
        # slow tremolo + envelopes
        s /= 4.26
        s *= 0.88 + 0.12 * math.sin(two_pi * 0.07 * t)
        env = min(clamp01(t / fade_in), clamp01((duration - t) / fade_out))
        s *= env * 0.30
        buf[i] = int(max(-32767, min(32767, s * 32767)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_scene(scene, idx, dur, g_before, total, out):
    bg = get_base()
    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = max(2, int(round(dur * FPS)))
    build = scene["build"]
    for i in range(n):
        el = i / FPS
        content.paste((0, 0, 0, 0), (0, 0, W, H))
        d = ImageDraw.Draw(content, "RGBA")
        build(d, el, dur, DATA_CACHE)
        fade = min(a_in(el, 0.0, FADE), a_out(el, dur, FADE))
        img = Image.alpha_composite(bg, content)
        if fade < 0.999:
            img = Image.blend(img, bg, 1 - fade)
        dc_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dc = ImageDraw.Draw(dc_img, "RGBA")
        draw_chrome(dc, scene["key"], idx, el, dur, g_before, total)
        img = Image.alpha_composite(img, dc_img)
        proc.stdin.write(img.convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()


def render_audio(vo: str, dur: float, out: str) -> None:
    ms = int(LEAD * 1000)
    ff(["-i", vo, "-af", f"adelay={ms}|{ms},apad", "-t", f"{dur:.3f}",
        "-ar", "44100", "-ac", "2", out])


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
          f"flagged={len(DATA_CACHE['flagged'])}, counts={DATA_CACHE['counts']}, "
          f"provenance={DATA_CACHE.get('provenance', '?')}")

    os.makedirs(WORK, exist_ok=True)
    vo_durs = synthesize(SCENES, args.voice, args.rate, args.pitch)

    durs = []
    for sc, vd in zip(SCENES, vo_durs):
        pad = sc.get("pad", PAD)
        durs.append(round(max(3.2, vd + pad), 3))
    total = sum(durs)
    print(f"[timing] total {total:.2f}s")
    for sc, vd, dd in zip(SCENES, vo_durs, durs):
        print(f"  {sc['key']:8s} vo={vd:5.2f}s  scene={dd:5.2f}s")

    vparts, aparts = [], []
    g_before = 0.0
    for i, (sc, dur) in enumerate(zip(SCENES, durs)):
        vp = os.path.join(WORK, f"v_{i:02d}.mp4")
        apre = os.path.join(WORK, f"a_{i:02d}.wav")
        print(f"[render] scene {i} ({sc['key']}) {dur:.2f}s ...")
        render_scene(sc, i, dur, g_before, total, vp)
        render_audio(os.path.join(WORK, f"vo_{i:02d}.mp3"), dur, apre)
        vparts.append(vp)
        aparts.append(apre)
        g_before += dur

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

    if args.no_music:
        ff(["-i", full_v, "-i", full_a, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", args.out])
    else:
        music = os.path.join(WORK, "music.wav")
        print("[music] synthesising ambient bed ...")
        make_music(music, total)
        # keep the voice clearly in front: the bed is sidechain-ducked under the
        # narration (dips while speaking), then gently limited.
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

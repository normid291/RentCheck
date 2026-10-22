"""Bake the whole brand-blue world (gradients + blooms + vignette + grain) into
one 1920x1080 PNG.

Why: rendering 4 full-screen radial gradients plus an overlay-blend grain layer
every frame is what made a software-rasterised Remotion render crawl (~0.5-1 s a
frame). One cached image + the animated dust gives the identical look for a
fraction of the cost.
"""
import os
import numpy as np
from PIL import Image

W, H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "public", "stage.png")

# palette, straight from src/theme.ts
BASE = (0x07, 0x0A, 0x1C)
MID = (0x0B, 0x11, 0x36)
LIFT = (0x1A, 0x24, 0x70)


def hexf(c):
    return np.array(c, dtype=np.float64) / 255.0


def ramp(t, stops):
    """Piecewise-linear ramp over normalised radius t. stops = [(pos, value)]."""
    out = np.full_like(t, stops[0][1], dtype=np.float64)
    for (p0, v0), (p1, v1) in zip(stops, stops[1:]):
        seg = (t >= p0) & (t <= p1)
        f = np.clip((t - p0) / max(p1 - p0, 1e-9), 0, 1)
        out = np.where(seg, v0 + (v1 - v0) * f, out)
    out = np.where(t > stops[-1][0], stops[-1][1], out)
    return out


def ell(t, centre, rx, ry):
    cx, cy = centre
    return np.sqrt(((t[1] - cx) / rx) ** 2 + ((t[0] - cy) / ry) ** 2)


xs = np.arange(W, dtype=np.float64)
ys = np.arange(H, dtype=np.float64)
xx, yy = np.meshgrid(xs, ys)
grid = (yy, xx)

# 1. base wash: radial-gradient(120% 92% at 50% 118%, lift 0%, mid 40%, base 100%)
d = ell(grid, (0.50 * W, 1.18 * H), 1.20 * W, 0.92 * H)
img = np.zeros((H, W, 3), dtype=np.float64)
for ch in range(3):
    img[:, :, ch] = ramp(d, [
        (0.0, hexf(LIFT)[ch]),
        (0.40, hexf(MID)[ch]),
        (1.0, hexf(BASE)[ch]),
    ])


def glow(rgb, peak, centre, rx, ry, falloff, opacity):
    t = ell(grid, centre, rx, ry) / falloff
    a = np.clip(peak * (1.0 - t), 0.0, peak) * opacity
    return hexf(rgb), a[:, :, None]


# 2. cool brand-blue pool: radial-gradient(58% 44% at 50% 74%, rgba(47,110,255,.36) .. 78%)
c, a = glow((47, 110, 255), 0.36, (0.50 * W, 0.74 * H), 0.58 * W, 0.44 * H, 0.78, 0.90)
img = img * (1 - a) + c * a

# 3. violet pool: radial-gradient(38% 30% at 78% 26%, rgba(120,60,255,.26) .. 80%)
c, a = glow((120, 60, 255), 0.26, (0.78 * W, 0.26 * H), 0.38 * W, 0.30 * H, 0.80, 0.80)
img = img * (1 - a) + c * a

# 4. film grain, overlay-blended at 9% (matches mixBlendMode: overlay)
rng = np.random.default_rng(7)
n = rng.random((512, 512))
tiles = np.tile(n, (int(np.ceil(H / 512)), int(np.ceil(W / 512))))[:H, :W][:, :, None]
ov = np.where(img < 0.5, 2 * img * tiles, 1 - 2 * (1 - img) * (1 - tiles))
img = img * 0.91 + ov * 0.09

# 5. vignette: radial-gradient(135% 105% at 50% 48%, .06 0%, .20 56%, .50 100%)
dv = ell(grid, (0.50 * W, 0.48 * H), 1.35 * W, 1.05 * H)
va = ramp(dv, [(0.0, 0.06), (0.56, 0.20), (1.0, 0.50)])[:, :, None]
img = img * (1 - va)

out = np.clip(img * 255.0, 0, 255).astype(np.uint8)
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
Image.fromarray(out, "RGB").save(os.path.abspath(OUT), optimize=True)
print("stage.png", os.path.getsize(os.path.abspath(OUT)) // 1024, "KB")

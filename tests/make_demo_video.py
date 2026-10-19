"""
Record a short demo video of the live RentCheck app.

Drives a real Chromium browser through the page the way a person would:

  1. land on the page
  2. click "Try a sample agreement" and analyse it
  3. scroll through the risk score, flagged clauses, missing protections and
     questions to ask
  4. paste something that is not a tenancy agreement ("hello") and show the
     friendly rejection notice

Playwright records the session to a .webm; imageio-ffmpeg (a bundled static
ffmpeg) transcodes it to an .mp4 under artifacts/.

Setup (one off):
    pip install playwright imageio-ffmpeg
    python -m playwright install chromium ffmpeg

Run from the repo root:
    python tests/make_demo_video.py
    python tests/make_demo_video.py --url http://127.0.0.1:8000   # local server
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import time
import urllib.request

from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(ROOT, "artifacts")

WIDTH, HEIGHT = 1280, 800

# The same sample the UI loads via the "Try a sample agreement" button; used to
# warm the model before recording so the demo does not sit on a cold start.
WARM_TEXT = (
    "1. TERM. The tenancy is for a term of two (2) years from the date of this agreement.\n"
    "2. TO PAY all taxes, rates, duties, assessments and outgoings whatsoever in respect of the demised premises.\n"
    "3. Provided that if any part of the rent hereby reserved is in arrears for 21 days, whether or not lawfully "
    "demanded, the Landlord may re-enter the demised premises and the term shall absolutely cease and determine."
)


def warm_up(base_url: str, timeout: float = 240) -> None:
    """Wait for the app to be up (no cold-start page) and warm the model."""
    print(f"[warmup] waiting for {base_url}/health ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=10) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(3)
    else:
        print("[warmup] health check timed out; continuing anyway")

    print("[warmup] warming the analysis model ...")
    try:
        req = urllib.request.Request(
            f"{base_url}/api/agreements/analyze",
            data=__import__("json").dumps({"text": WARM_TEXT}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
        print("[warmup] model ready")
    except Exception as exc:
        print(f"[warmup] warm call failed ({exc}); continuing")


async def record(base_url: str, webm_dir: str) -> str:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            record_video_dir=webm_dir,
            record_video_size={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page = await context.new_page()
        page.set_default_timeout(200_000)
        wait = page.wait_for_timeout

        # 1. Land on the page.
        await page.goto(base_url, wait_until="domcontentloaded")
        await page.wait_for_selector("#analyzeBtn", state="visible")
        await wait(2600)  # let the hero settle

        # 2. Click the sample button, then analyse.
        await page.click("#sampleBtn")
        await wait(1600)
        await page.click("#analyzeBtn")

        # 3. Wait for results (or the rejection notice), then tour the results.
        await page.wait_for_function(
            "() => {const r=document.querySelector('#results'), n=document.querySelector('#notice');"
            "return (r && !r.hidden) || (n && !n.hidden);}"
        )
        await wait(2500)  # score panel + ring animation
        await page.evaluate("document.querySelector('#flaggedSection').scrollIntoView({behavior:'smooth',block:'start'})")
        await wait(3200)
        await page.evaluate("document.querySelector('#missingSection').scrollIntoView({behavior:'smooth',block:'start'})")
        await wait(2800)
        await page.evaluate("document.querySelector('#questionsSection').scrollIntoView({behavior:'smooth',block:'start'})")
        await wait(3000)

        # 4. Show the "not a tenancy agreement" path.
        await page.evaluate("document.querySelector('#inputPanel').scrollIntoView({behavior:'smooth',block:'start'})")
        await wait(1200)
        await page.click("#tab-paste")
        await page.fill("#agreementText", "hello")
        await wait(900)
        await page.click("#analyzeBtn")
        await page.wait_for_function(
            "() => {const n=document.querySelector('#notice'); return n && !n.hidden;}"
        )
        await wait(4200)  # read the notice
        await page.click("#noticeAction")
        await wait(1500)

        video = page.video
        await context.close()
        await browser.close()
        return await video.path()


def to_mp4(webm_path: str, mp4_path: str, trim: float = 4.5) -> None:
    """Transcode to H.264 mp4, trimming the blank page shown while the live app
    loads, and fading in/out for a clean start and finish."""
    import imageio_ffmpeg
    import subprocess

    ffmpeg = str(imageio_ffmpeg.get_ffmpeg_exe())
    dur = max(1.0, _duration(webm_path) - trim)
    fade_out = max(0.0, dur - 0.8)
    vf = f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out:.2f}:d=0.8"
    cmd = [
        ffmpeg, "-y", "-ss", f"{trim}", "-i", str(webm_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(mp4_path),
    ]
    print("[encode] " + " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _duration(path: str) -> float:
    import imageio_ffmpeg
    import subprocess

    ffprobe = None
    ffmpeg = str(imageio_ffmpeg.get_ffmpeg_exe())
    # imageio-ffmpeg ships ffmpeg only; use it to read the duration from stderr.
    out = subprocess.run([ffmpeg, "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    text = out.stderr.decode("utf-8", "ignore")
    for line in text.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://rentcheck.rumptycloud.app")
    ap.add_argument("--out", default=os.path.join(ARTIFACTS, "rentcheck-demo.mp4"))
    ap.add_argument("--trim", type=float, default=4.5, help="seconds of blank page to trim from the front")
    args = ap.parse_args()

    os.makedirs(ARTIFACTS, exist_ok=True)
    tmp = os.path.join(ARTIFACTS, "_webm")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    warm_up(args.url)
    print("[record] starting browser ...")
    webm = str(asyncio.run(record(args.url, tmp)))
    print(f"[record] saved {webm} ({os.path.getsize(webm)} bytes)")

    to_mp4(webm, args.out, trim=args.trim)
    print(f"[done] {args.out} ({os.path.getsize(args.out)} bytes)")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

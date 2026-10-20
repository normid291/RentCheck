"""Build the RentCheck promo voiceover and the master timeline.

Synthesises each script line with edge-tts, captures the real word boundaries,
lays the lines out with the reference's phrase pauses (mean 0.65 s), writes the
master VO and a single `timeline.json` that BOTH the Remotion animation and the
audio mixer read - so motion, captions and sound cues can never drift apart.

    python video/scripts/build_vo.py [--voice en-US-AndrewMultilingualNeural] [--rate +8%]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess

import edge_tts
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
PUBLIC = os.path.join(VIDEO, "public")
VO_DIR = os.path.join(PUBLIC, "vo")
LEAD_IN = 0.20
FPS = 60
# every synthesised line used to carry ~0.5 s of its own trailing silence, which
# was silently *added* to these pauses — that is what made the read staccato.
# build_vo.py now trims that tail, so these gaps are the whole pause, and 1.28x
# puts the mean pause back at the reference's measured 0.65 s.
GAP_SCALE = 1.28

# --------------------------------------------------------------------------- #
# the script: 11 beats, matching docs/video/rentcheck-plan.md
#   gap = pause AFTER the line (measured reference mean: 0.65 s)
#   events = named animation moments, shared by the animation and the mixer
# --------------------------------------------------------------------------- #
BEATS: list[dict] = [
    dict(id="b01_hook", label="HOOK", lines=[
        dict(text="Do you actually know what's in your tenancy agreement?", gap=0.60),
    ], events=[
        dict(id="docIn", at=0.10, sfx="paper"),
        dict(id="scan", at=0.55, sfx="sweep"),
        dict(id="chip1", at=1.20, sfx="pop"),
        dict(id="chip2", at=1.50, sfx="pop"),
        dict(id="chip3", at=1.80, sfx="pop"),
        dict(id="stamp", at=2.60, sfx="tick"),
    ]),
    dict(id="b02_meet", label="MEET", lines=[
        dict(text="Meet Ada.", gap=0.45),
        dict(text="She found a flat, paid the agent,", gap=0.35),
        dict(text="and got a ten-page deed.", gap=0.60),
    ], events=[
        dict(id="hostIn", at=0.10, sfx="whoosh"),
        dict(id="paper1", at=0.55, sfx="pop"),
        dict(id="paper2", at=1.10, sfx="pop"),
        dict(id="deed", at=1.90, sfx="paper"),
    ]),
    dict(id="b03_pain", label="PAIN", lines=[
        dict(text="Every clause is in legal English.", gap=0.45),
        dict(text="Nobody explains it.", gap=0.45),
        dict(text="And when something goes wrong, she only finds out after she has signed.", gap=0.70),
    ], events=[
        dict(id="cards", at=0.10, sfx="whoosh"),
        dict(id="card1", at=0.45, sfx="pop"),
        dict(id="card2", at=0.70, sfx="pop"),
        dict(id="card3", at=0.95, sfx="pop"),
        dict(id="chipA", at=2.30, sfx="pop"),
        dict(id="chipB", at=2.60, sfx="pop"),
        dict(id="chipC", at=2.90, sfx="pop"),
        dict(id="drop", at=4.60, sfx="thud"),
    ]),
    dict(id="b04_turn", label="TURN", lines=[
        dict(text="Ada doesn't need any more jargon.", gap=0.50),
        dict(text="She needs one clear answer.", gap=0.80),
    ], events=[
        dict(id="out1", at=0.05, sfx="whoosh"),
        dict(id="in2", at=2.30, sfx="bloom"),
        dict(id="pulse", at=2.90, sfx="tick"),
    ]),
    dict(id="b05_reveal", label="REVEAL", lines=[
        dict(text="Meet RentCheck.", gap=0.90),
    ], events=[
        dict(id="converge", at=0.00, sfx="sweep"),
        dict(id="bloom", at=0.55, sfx="bloom"),
        dict(id="mark", at=0.70, sfx="chime"),
        dict(id="pill1", at=1.50, sfx="pop"),
        dict(id="pill2", at=1.80, sfx="pop"),
        dict(id="pill3", at=2.10, sfx="pop"),
    ]),
    dict(id="b06_upload", label="UPLOAD", lines=[
        dict(text="First, upload.", gap=0.50),
        dict(text="RentCheck checks it is a tenancy agreement,", gap=0.35),
        dict(text="reads every clause,", gap=0.35),
        dict(text="and scores the risk.", gap=0.60),
    ], events=[
        dict(id="panel", at=0.10, sfx="whoosh"),
        dict(id="dropzone", at=0.35, sfx="pop"),
        dict(id="clickUpload", at=1.60, sfx="click"),
        dict(id="rowGate", at=2.20, sfx="tick"),
        dict(id="gateOk", at=3.10, sfx="chime"),
        dict(id="rowRead", at=3.60, sfx="sweep"),
        dict(id="readDone", at=4.90, sfx="tick"),
        dict(id="rowScore", at=5.60, sfx="pop"),
        dict(id="scoreDone", at=6.60, sfx="chime"),
    ]),
    dict(id="b07_report", label="REPORT", lines=[
        dict(text="You get one clear risk score,", gap=0.35),
        dict(text="the clauses that are risky,", gap=0.35),
        dict(text="and the protections that are missing.", gap=0.65),
    ], events=[
        dict(id="screen", at=0.05, sfx="whoosh"),
        dict(id="ring", at=0.55, sfx="rise"),
        dict(id="ringDone", at=2.30, sfx="chime"),
        dict(id="tile1", at=2.70, sfx="pop"),
        dict(id="tile2", at=2.95, sfx="pop"),
        dict(id="tile3", at=3.20, sfx="pop"),
        dict(id="tile4", at=3.45, sfx="pop"),
        dict(id="list", at=4.60, sfx="whoosh"),
        dict(id="row1", at=4.90, sfx="tick"),
        dict(id="row2", at=5.15, sfx="tick"),
        dict(id="row3", at=5.40, sfx="tick"),
        dict(id="row4", at=5.65, sfx="tick"),
    ]),
    dict(id="b08_clause", label="CLAUSE", lines=[
        dict(text="Every flag shows the exact wording,", gap=0.35),
        dict(text="and explains it in plain English.", gap=0.65),
    ], events=[
        dict(id="cardIn", at=0.10, sfx="whoosh"),
        dict(id="quote", at=1.20, sfx="sweep"),
        dict(id="quoteDone", at=2.20, sfx="tick"),
        dict(id="reason", at=3.00, sfx="pop"),
    ]),
    dict(id="b09_ask", label="ASK", lines=[
        dict(text="And a ready list of questions to ask before you sign.", gap=0.65),
    ], events=[
        dict(id="listIn", at=0.10, sfx="whoosh"),
        dict(id="q1", at=0.50, sfx="tick"),
        dict(id="q2", at=0.75, sfx="tick"),
        dict(id="q3", at=1.00, sfx="tick"),
        dict(id="q4", at=1.25, sfx="tick"),
        dict(id="cursor", at=2.20, sfx="pop"),
        dict(id="expand", at=3.00, sfx="pop"),
    ]),
    dict(id="b10_proof", label="PROOF", lines=[
        dict(text="Four risky clauses.", gap=0.30),
        dict(text="Four missing protections.", gap=0.30),
        dict(text="Eight questions to ask.", gap=0.65),
    ], events=[
        dict(id="stat1", at=0.10, sfx="rise"),
        dict(id="stat2", at=1.30, sfx="rise"),
        dict(id="stat3", at=2.40, sfx="rise"),
    ]),
    dict(id="b11_close", label="CLOSE", lines=[
        dict(text="RentCheck.", gap=0.45),
        dict(text="Stop guessing.", gap=0.50),
        dict(text="Know what you're signing.", gap=1.10),
    ], events=[
        dict(id="logo", at=0.05, sfx="bloom"),
        dict(id="mark", at=0.20, sfx="chime"),
        dict(id="line", at=0.75, sfx="pop"),
        dict(id="sub", at=1.90, sfx="pop"),
        dict(id="cta", at=3.40, sfx="pop"),
        dict(id="hover", at=4.10, sfx="click"),
    ], hold=2.10),
]


async def synth_one(text: str, out: str, voice: str, rate: str, pitch: str,
                    tries: int = 8):
    """Write one line's mp3 and return its word boundaries (absolute to the line).

    The service occasionally drops a request mid-stream, so each line is retried
    with a growing backoff and the file is only written once a line is complete.
    """
    last: Exception | None = None
    for attempt in range(tries):
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                        boundary="WordBoundary")
            words: list[dict] = []
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append({
                        "w": chunk["text"],
                        "s": round(chunk["offset"] / 1e7, 3),
                        "e": round((chunk["offset"] + chunk["duration"]) / 1e7, 3),
                    })
            if not buf:
                raise RuntimeError("no audio in stream")
            with open(out, "wb") as fh:
                fh.write(buf)
            return words
        except Exception as exc:  # noqa: BLE001 - retry anything transient
            last = exc
            if attempt < tries - 1:
                await asyncio.sleep(min(2.0 * (attempt + 1), 8.0))
    raise RuntimeError(f"synthesis failed for {text!r}: {last}")


def spread_words(text: str, spoken: float):
    """Fallback when the service sends no boundaries: distribute the words
    across the line's measured duration in proportion to their length, so the
    captions can never silently go missing."""
    toks = text.split()
    if not toks or spoken <= 0:
        return []
    weights = [len(t.strip(".,?!'\"-")) + 1 for t in toks]
    total = sum(weights)
    out, t = [], 0.0
    for tok, weight in zip(toks, weights):
        length = spoken * weight / total
        out.append({"w": tok, "s": round(t, 3), "e": round(t + length * 0.92, 3)})
        t += length
    return out


def to_wav(src: str, dst: str, pad: float):
    """Convert one line to wav, dropping the synthesiser's own trailing silence
    before the intended pause is added.

    Every TTS line ends with a variable tail of dead air. Left in, that tail is
    *added* to the scripted pause, which is exactly what made the read sound
    staccato: phrases kept arriving a beat late. Trimming it means the phrasing
    pause is the only silence, so the voice flows.
    """
    subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
         "-af", ("areverse,"
                 "silenceremove=start_periods=1:start_duration=0:"
                 "start_threshold=-50dB:start_silence=0.04:detection=peak,"
                 "areverse,"
                 f"aresample=44100,apad=pad_dur={pad:.3f}"),
         "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", dst], check=True)


def wav_duration(path: str) -> float:
    out = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True)
    for line in out.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")


def remap_events(beat: dict, beat_dur: float, prev: dict) -> list[dict]:
    """Re-anchor a beat's authored event times to its new VO length."""
    old = prev.get(beat["id"])
    hold = beat.get("hold", 0.0)
    vo_new, vo_old = beat_dur - hold, (old - hold) if old else 0.0
    if vo_old <= 0:
        return beat["events"]
    k = vo_new / vo_old
    return [
        dict(e, at=min(round(e["at"] * k, 3), round(beat_dur - 0.20, 3)))
        for e in beat["events"]
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-US-AndrewMultilingualNeural")
    ap.add_argument("--rate", default="+6%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--no-remap", action="store_true",
                    help="keep the authored event times instead of re-anchoring them "
                         "to the new beat lengths")
    args = ap.parse_args()

    # The animation events are authored against one particular voice timing. If
    # the voice, rate or pause scale moves, every beat changes length, so the
    # events are re-anchored proportionally — that keeps each animated moment on
    # the same spoken words instead of drifting a second off them.
    prev: dict[str, float] = {}
    tl_path = os.path.join(PUBLIC, "timeline.json")
    if os.path.exists(tl_path) and not args.no_remap:
        try:
            with open(tl_path, encoding="utf-8") as fh:
                prev = {b["id"]: b["dur"] for b in json.load(fh)["beats"]}
        except Exception:
            prev = {}
    return build(args, prev)


def build(args, prev: dict):
    """Synthesise every line, lay the beats out and write the master timeline."""
    os.makedirs(VO_DIR, exist_ok=True)
    tmp = os.path.join(VO_DIR, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    words_total = 0
    parts: list[str] = []
    beats_out = []
    cursor = LEAD_IN
    if LEAD_IN > 0:
        lead = os.path.join(tmp, "lead.wav")
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
                        "-t", f"{LEAD_IN:.3f}", "-c:a", "pcm_s16le", lead],
                       check=True)
        parts.append(lead)

    for i, beat in enumerate(BEATS):
        beat_start = cursor
        lines_out = []
        words_out = []
        for j, line in enumerate(beat["lines"]):
            mp3 = os.path.join(tmp, f"{beat['id']}_{j}.mp3")
            words = asyncio.run(synth_one(line["text"], mp3, args.voice,
                                          args.rate, args.pitch))
            gap = round(line["gap"] * GAP_SCALE, 3)
            wav = os.path.join(tmp, f"{beat['id']}_{j}.wav")
            to_wav(mp3, wav, gap)
            dur = wav_duration(wav)
            line_start = cursor
            if not words:
                words = spread_words(line["text"], max(0.05, dur - gap))
            for w in words:
                words_out.append({"w": w["w"], "s": round(line_start + w["s"], 3),
                                  "e": round(line_start + w["e"], 3)})
            lines_out.append({"text": line["text"], "start": round(line_start, 3),
                              "end": round(line_start + dur - gap, 3)})
            parts.append(wav)
            cursor += dur
            words_total += len(line["text"].split())
        beat_dur = cursor - beat_start + beat.get("hold", 0.0)
        if beat.get("hold"):
            tail = os.path.join(tmp, f"{beat['id']}_hold.wav")
            subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-t", f"{beat['hold']:.3f}", "-c:a", "pcm_s16le", tail],
                           check=True)
            parts.append(tail)
            cursor += beat["hold"]
        beats_out.append({
            "id": beat["id"], "label": beat["label"],
            "start": round(beat_start, 3), "dur": round(beat_dur, 3),
            "lines": lines_out, "words": words_out,
            "events": remap_events(beat, beat_dur, prev),
        })
        print(f"{beat['id']:<12} start={beat_start:6.2f}  dur={beat_dur:5.2f}  "
              f"vo={sum(l['end'] - l['start'] for l in lines_out):5.2f}")

    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{p.replace(os.sep, '/')}'\n")
    master = os.path.join(VO_DIR, "master.wav")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                    "-safe", "0", "-i", listing, "-c:a", "pcm_s16le", master],
                   check=True)

    total = wav_duration(master)
    spoken = sum(l["end"] - l["start"] for b in beats_out for l in b["lines"])
    timeline = {
        "fps": FPS, "voice": args.voice, "rate": args.rate,
        "total": round(total, 3), "total_frames": int(round(total * FPS)),
        "lead_in": LEAD_IN, "words": words_total,
        "vo_seconds": round(spoken, 2),
        "wpm": round(words_total / spoken * 60, 1) if spoken else 0,
        "beats": beats_out,
    }
    with open(os.path.join(PUBLIC, "timeline.json"), "w", encoding="utf-8") as fh:
        json.dump(timeline, fh, indent=1)
    print(f"\n{words_total} words, {spoken:.1f}s spoken -> {timeline['wpm']} wpm "
          f"(reference 147)\nfilm {total:.2f}s = {timeline['total_frames']} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

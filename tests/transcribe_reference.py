"""Step 1 tooling: transcribe a reference with word timestamps.

    python tests/transcribe_reference.py <video> [model]

Writes artifacts/_ref/vo.json (word + segment timestamps) and prints a script
listing with per-line timing, words-per-minute and pause lengths, so the
narration pacing and the caption sync can be matched exactly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import wave

import numpy as np
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "artifacts/VID-20261020-WA0002.mp4"
    model_size = sys.argv[2] if len(sys.argv) > 2 else "small.en"
    out = "artifacts/_ref"
    os.makedirs(out, exist_ok=True)
    wav = os.path.join(out, "vo.wav")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", ref,
                    "-ac", "1", "-ar", "16000", "-vn", wav], check=True)

    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # decode ourselves: faster-whisper's PyAV path is version-fragile
    with wave.open(wav, "rb") as w:
        audio = (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                 .astype(np.float32) / 32768.0)
    segments, info = model.transcribe(audio, language="en", word_timestamps=True,
                                      beam_size=5, vad_filter=False)
    segs = []
    for s in segments:
        words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                 for w in (s.words or [])]
        segs.append({"start": round(s.start, 2), "end": round(s.end, 2),
                     "text": s.text.strip(), "words": words})
    json.dump({"language": info.language, "duration": info.duration,
               "segments": segs}, open(os.path.join(out, "vo.json"), "w"), indent=1)

    prev_end = 0.0
    print(f"\nmodel={model_size}  lang={info.language}  dur={info.duration:.2f}s\n")
    for s in segs:
        gap = s["start"] - prev_end
        n = len(s["text"].split())
        dur = max(0.01, s["end"] - s["start"])
        wpm = n / dur * 60
        print(f"[{s['start']:6.2f}-{s['end']:6.2f}] gap={gap:4.2f}s "
              f"{n:2d}w {wpm:5.0f}wpm  {s['text']}")
        prev_end = s["end"]

    words = [w for s in segs for w in s["words"]]
    if words:
        span = words[-1]["e"] - words[0]["s"]
        gaps = [round(words[i + 1]["s"] - words[i]["e"], 2) for i in range(len(words) - 1)]
        big = [g for g in gaps if g >= 0.30]
        print(f"\ntotal words={len(words)}  span={span:.1f}s  "
              f"overall={len(words) / span * 60:.0f}wpm")
        print(f"pauses>=0.30s: {len(big)}  mean={sum(big) / len(big):.2f}s  "
              f"max={max(gaps):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

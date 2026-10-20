# RentCheck promo film

A Remotion project that renders the RentCheck promo. The delivered cut is
tracked at `artifacts/rentcheck-promo.mp4`.

| | |
| --- | --- |
| **Output** | 1920×1080, 60 fps, 61.92 s, H.264 High crf 17, AAC 48 kHz stereo |
| **Loudness** | −14.1 LUFS integrated, −2.0 dBFS peak |
| **Brief / script / beat sheet** | `docs/video/rentcheck-plan.md` |
| **Reference study (measured timings)** | `docs/video/technique-guide.md` |
| **Engine** | Remotion 4.0.537 + React 19 + TypeScript |

## How it fits together

`public/timeline.json` is the single source of truth. It holds every beat's
start and duration, the VO word timestamps and the on-screen event times.
Remotion reads it for the caption layer, and `build_audio.py` reads it to size
the mix — so picture and sound can never drift apart. Nothing else hard-codes a
time; if a beat's length changes, `build_vo.py` rewrites the file and
re-anchors the authored event times into the new layout (`remap_events`).

The whole background world — base wash, mint pool, warm pool, vignette and film
grain — is baked into a single `public/stage.png`. That one change is what took
the render from ~0.5–1 s a frame to ~0.1 s; the live frame only composites that
plate plus the animated dust.

The UI in the film is not a screenshot. It is the real app redrawn in code as
cards (`src/components/AppUi.tsx`), driven by real values from
`src/data/analysis.json` — a real agreement run through the real pipeline with
PII anonymised. No customer, number or claim in the film is invented.

## Build order

```bash
cd video
npm install

python scripts/fetch_fonts.py     # once — Inter woff2 + src/fonts.generated.ts
python scripts/make_stage.py      # bakes public/stage.png
python scripts/build_vo.py        # narration -> public/vo/, rewrites timeline.json
python scripts/build_audio.py     # music + mix -> public/audio/mix.wav
npx remotion render RentCheck out/rentcheck.mp4
```

The font woff2 files, `stage.png` and `timeline.json` are committed, so a fresh
clone can go straight to the render. Only `public/vo/` and `public/audio/` are
regenerable and ignored.

`python scripts/build_vo.py --help` exposes the voice, rate and pitch, plus
`--no-remap`. `scripts/vo_basis.json` snapshots the authored event timings;
restore it over `public/timeline.json` before a rebuild if a previous run's
remap would otherwise compound.

## Things that will bite you

- **edge-tts defaults to `boundary="SentenceBoundary"`**, which yields no word
  timings at all — the caption layer silently renders nothing. `build_vo.py`
  requests `"WordBoundary"` and falls back to proportional spreading.
- **Each synthesised line carries ~0.5 s of its own trailing silence.** Adding
  that on top of the scripted pauses put ~15 s of dead air into a 62 s film and
  is what made the voice sound robotic. `to_wav()` trims the tail before
  padding; `GAP_SCALE` then sets the phrase pause to the reference's ~0.65 s.
- **A `rate` change barely moves the pace on the multilingual voice** (~4 %
  between −4 % and +10 %); the voice itself sets the tempo.
- **The audio mix carries a ~1 s tail past the picture.** Swapping audio onto an
  existing render needs `-shortest -ar 48000`, or the file grows past the video.
- **Web-font loading is a race in Remotion.** Fonts are self-hosted and
  registered before the root `AbsoluteFill`, which pins `Inter, sans-serif`.
- The output is tagged `yuvj420p(pc, bt470bg)` — full-range, and correct here.

## Swapping audio without re-rendering

The picture and sound are independent. To audition a change to the mix on the
existing render, copy the video stream and take only the new audio:

```bash
python scripts/build_audio.py
ffmpeg -y -i out/rentcheck.mp4 -i public/audio/mix.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 320k -ar 48000 \
  -shortest -movflags +faststart out/rentcheck_fix.mp4
```

The video stream comes through byte-identical, so it is a sub-minute loop
instead of a full render.

"""Build the RentCheck promo soundtrack and master it.

- synthesises the music bed in numpy: a pad over I-V-vi-IV in A major, a soft
  sub, a rhodes-like motif and convolution reverb (no licences, no samples)
- the SFX registry is empty by request, so no cue is fired; the film plays on
  voice and music alone. The mixer still reads cue names from
  `public/timeline.json`, so re-registering one in `SFX` is all it takes to
  bring a cue back
- mixes VO + bed (bed sidechain-ducked under the voice) and masters to
  -14 LUFS / -2 dBTP, matching the reference (-14.2 LUFS / -1.3 dBFS peak)

    python video/scripts/build_audio.py
"""
from __future__ import annotations

import json
import os
import subprocess

import numpy as np
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
PUBLIC = os.path.join(VIDEO, "public")
OUT = os.path.join(PUBLIC, "audio")
rng = np.random.default_rng(7)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def env_exp(n: int, attack: float, decay: float) -> np.ndarray:
    a = max(1, int(attack * SR))
    d = max(1, n - a)
    e = np.concatenate([np.linspace(0, 1, a), np.exp(-np.arange(d) / (decay * SR))])
    return e[:n]


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """FFT brick-wall band (fine for short one-shots)."""
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    mask = np.ones_like(freqs)
    if lo > 0:
        mask *= 1 / (1 + np.exp(-(freqs - lo) / (lo * 0.25 + 1)))
    if hi > 0:
        mask *= 1 / (1 + np.exp((freqs - hi) / (hi * 0.25 + 1)))
    return np.fft.irfft(spec * mask, n)


def lowpass(x, cutoff):
    """Gentle zero-phase low-pass (FFT brick with a soft shoulder)."""
    return bandpass(x, 0.0, cutoff)


def stereo(mono: np.ndarray, width: float = 0.0) -> np.ndarray:
    """Mono -> (n, 2). `width` adds a tiny inter-channel delay for air."""
    if width <= 0:
        return np.stack([mono, mono], axis=1)
    d = int(width * SR)
    l = np.concatenate([mono, np.zeros(d)])
    r = np.concatenate([np.zeros(d), mono])
    return np.stack([l, r], axis=1)


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


# --------------------------------------------------------------------------- #
# sound effects
# --------------------------------------------------------------------------- #
def sfx_pop() -> np.ndarray:
    """A soft, rounded 'appear' blip.

    This used to be a 1500->700 Hz swept chirp, which read as a bird squawk on
    every pop-up. A stationary tone has no chirp to squawk with: a damped 440 Hz
    body with a whisper of a transient, over in ~30 ms.
    """
    n = int(0.10 * SR)
    body = (0.78 * np.sin(2 * np.pi * 440 * t(n))
            + 0.16 * np.sin(2 * np.pi * 880 * t(n)))
    y = body * env_exp(n, 0.005, 0.026)
    soft = bandpass(rng.standard_normal(int(0.007 * SR)), 700, 2400) * 0.10
    y[:len(soft)] += soft
    return normalize(y, 0.5)


def sfx_tick() -> np.ndarray:
    """A soft, low wooden tap.

    This was a 2600 Hz sine ping — the second-most-used cue, and a high pure
    tone is what reads as 'off'. Same accent, dropped two octaves and quietened.
    """
    n = int(0.07 * SR)
    body = np.sin(2 * np.pi * 190 * t(n)) * env_exp(n, 0.0015, 0.015)
    y = body * 0.9
    w = max(1, int(0.012 * SR))
    tap = bandpass(rng.standard_normal(w), 250, 1800) * env_exp(w, 0.0006, 0.005) * 0.4
    y[:w] += tap
    return normalize(y, 0.30)


def sfx_click() -> np.ndarray:
    n = int(0.06 * SR)
    burst = bandpass(rng.standard_normal(int(0.008 * SR)), 1200, 7000) * env_exp(int(0.008 * SR), 0.0003, 0.004)
    ping = np.sin(2 * np.pi * 1200 * t(n)) * env_exp(n, 0.0005, 0.012)
    out = ping * 0.6
    out[:len(burst)] += burst
    return normalize(out, 0.45)


def sfx_whoosh(dur=0.38) -> np.ndarray:
    n = int(dur * SR)
    x = rng.standard_normal(n)
    y = np.empty(n, dtype=np.float64)
    cut = np.linspace(400, 4200, n)
    # cheap time-varying band: blend two static bands
    a = bandpass(x, 250, 1100)
    b = bandpass(x, 1200, 5200)
    w = np.linspace(0, 1, n) ** 1.5
    y = a * (1 - w) + b * w
    y *= np.sin(np.pi * np.linspace(0, 1, n)) ** 1.2
    y *= env_exp(n, 0.02, 0.10)
    return normalize(y, 0.5)


def sfx_sweep(dur=0.62) -> np.ndarray:
    n = int(dur * SR)
    x = rng.standard_normal(n)
    y = bandpass(x, 900, 6500)
    y *= np.linspace(0.0, 1.0, n) ** 2.0
    y *= np.exp(-np.linspace(0, 1, n) * 1.6)
    shimmer = np.sin(2 * np.pi * np.cumsum(np.linspace(1600, 3600, n)) / SR) * 0.12
    shimmer *= np.linspace(0, 1, n) ** 3
    return normalize(y + shimmer, 0.42)


def sfx_bloom(dur=0.9) -> np.ndarray:
    n = int(dur * SR)
    x = rng.standard_normal(n)
    swell = bandpass(x, 300, 5000) * (np.linspace(0, 1, n) ** 2.2)
    chord = sum(np.sin(2 * np.pi * f * t(n)) * 0.25 for f in (392.0, 523.25, 784.0))
    chord *= np.linspace(0, 1, n) ** 2.5
    body = swell * 0.7 + chord * 0.5
    body *= np.exp(-np.clip(np.linspace(-0.35, 1.25, n), 0, None) * 2.2)
    return normalize(body, 0.5)


def sfx_chime(dur=0.85) -> np.ndarray:
    n = int(dur * SR)
    out = np.zeros(n)
    for f, a, d in ((1046.5, 0.5, 0.22), (1568.0, 0.3, 0.16), (2093.0, 0.18, 0.11)):
        out += a * np.sin(2 * np.pi * f * t(n)) * env_exp(n, 0.002, d)
    out += 0.06 * np.sin(2 * np.pi * 523.25 * t(n)) * env_exp(n, 0.004, 0.4)
    return normalize(out, 0.42)


def sfx_paper(dur=0.22) -> np.ndarray:
    n = int(dur * SR)
    x = rng.standard_normal(n)
    y = bandpass(x, 1400, 8000)
    y *= env_exp(n, 0.004, 0.045)
    y += bandpass(x, 400, 1400) * env_exp(n, 0.002, 0.02) * 0.4
    return normalize(y, 0.32)


def sfx_thud(dur=0.26) -> np.ndarray:
    n = int(dur * SR)
    f = np.linspace(120, 46, n)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.003, 0.06)
    y += bandpass(rng.standard_normal(n), 60, 300) * env_exp(n, 0.002, 0.03) * 0.5
    return normalize(y, 0.6)


def sfx_rise(dur=0.75) -> np.ndarray:
    n = int(dur * SR)
    f = np.linspace(220, 1300, n)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5
    air = bandpass(rng.standard_normal(n), 800, 6000) * 0.35
    y = (tone + air) * (np.linspace(0, 1, n) ** 1.8)
    y *= np.exp(-np.clip(np.linspace(-0.4, 1.1, n), 0, None) * 1.6)
    return normalize(y, 0.38)


SFX: dict = {
    # Every cue has been removed on request: the film now plays on voice and
    # music alone.
}


# --------------------------------------------------------------------------- #
# music bed
# --------------------------------------------------------------------------- #
def env_sustain(n: int, attack: float, release: float) -> np.ndarray:
    """Smooth attack/release envelope (no clicks, no percussive decay)."""
    a = max(1, min(int(attack * SR), n // 2))
    r = max(1, min(int(release * SR), n - a))
    e = np.ones(n)
    e[:a] = np.linspace(0.0, 1.0, a) ** 1.4
    e[n - r:] = np.linspace(1.0, 0.0, r) ** 1.2
    return e


def fftconv(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Fast linear convolution (the strict numpy equivalent of fftconvolve)."""
    n = x.shape[0] + ir.shape[0] - 1
    nfft = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: x.shape[0]]


def reverb(x: np.ndarray, decay: float = 2.8, mix: float = 0.42) -> np.ndarray:
    """Convolution reverb against a synthetic exponentially-decaying noise tail.

    This is the single biggest reason the bed sounds like an instrument rather
    than a synth: the notes get a room.
    """
    m = int(decay * SR)
    ir = rng.standard_normal(m) * np.exp(-np.arange(m) / (decay * SR * 0.34))
    ir[: int(0.012 * SR)] = 0.0                    # pre-delay
    build = int(0.09 * SR)
    ir[:build] *= np.linspace(0.0, 1.0, build)     # soft early build
    ir /= np.sqrt(float(np.sum(ir ** 2))) + 1e-9
    wet = fftconv(x, ir)
    wet *= (np.sqrt(float(np.mean(x ** 2))) + 1e-9) / (
        np.sqrt(float(np.mean(wet ** 2))) + 1e-9)  # match the dry level
    return x * (1 - mix) + wet * mix


def music_bed(duration: float, bpm: float = 76.0) -> np.ndarray:
    """A warm, slow bed: a sustained pad over I-V-vi-IV in A major, a soft sub,
    a rhodes-like motif and real convolution reverb.

    No drums. The old bed was a kick-and-hat loop, which is what read as cheap.
    Nothing here sits above 7.5 kHz, and the whole thing is built to be felt
    rather than noticed under the voice.
    """
    n = int(duration * SR)
    beat = 60.0 / bpm
    bar = beat * 4
    chord_len = bar * 2
    out = np.zeros(n)
    tone = np.zeros(n)  # the part that gets reverb

    def add(buf, pos_s, sig, gain):
        i = int(pos_s * SR)
        if i >= len(buf):
            return
        seg = sig[: len(buf) - i]
        buf[i:i + len(seg)] += seg * gain

    # I(A) - V(E) - vi(F#m) - IV(D)
    CHORDS = [
        dict(bass=110.00, notes=[220.00, 277.18, 329.63]),
        dict(bass=82.41, notes=[246.94, 329.63, 415.30]),
        dict(bass=92.50, notes=[220.00, 277.18, 369.99]),
        dict(bass=73.42, notes=[185.00, 220.00, 293.66]),
    ]
    nc = int(np.ceil(duration / chord_len))
    for ci in range(nc):
        ch = CHORDS[ci % 4]
        t0 = ci * chord_len

        # sustained pad, three voices, gently detuned against itself
        pn = int((chord_len + 1.4) * SR)
        tt = t(pn)
        pad = np.zeros(pn)
        for f in ch["notes"]:
            for mult, amp, det in ((1, 0.42, 0.0), (1, 0.18, 0.55),
                                   (2, 0.10, 0.0), (3, 0.04, -0.7)):
                pad += amp * np.sin(2 * np.pi * (f + det) * mult * tt)
        pad = lowpass(pad, 1500) * env_sustain(pn, 0.85, 1.7)
        add(tone, t0, pad, 0.10)

        # soft sub, one note per chord
        bn = int(chord_len * 0.96 * SR)
        sub = np.sin(2 * np.pi * ch["bass"] * t(bn))
        sub += 0.12 * np.sin(2 * np.pi * 2 * ch["bass"] * t(bn))
        add(out, t0, lowpass(sub, 320) * env_sustain(bn, 0.30, 1.0), 0.30)

        # rhodes-like motif, one chord tone every two beats
        for k in range(4):
            f = ch["notes"][(ci * 3 + k) % 3] * 2
            mn = int(1.1 * SR)
            mt = t(mn)
            bell = (0.70 * np.sin(2 * np.pi * f * mt)
                    + 0.12 * np.sin(2 * np.pi * 2 * f * mt)
                    + 0.05 * np.sin(2 * np.pi * 3.01 * f * mt))
            bell *= env_exp(mn, 0.004, 0.20)
            add(tone, t0 + k * beat * 2, lowpass(bell, 4200), 0.07)

    # a faint breathing top so it never sounds like a loop
    air = bandpass(rng.standard_normal(n), 1800, 6000)
    air *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t(n))
    out += air * 0.006

    out += reverb(tone, decay=2.8, mix=0.42)  # reverb on the tonal layer only,
    out = lowpass(out, 7500)                  # so the low end stays tight

    fade_in = np.minimum(1.0, np.arange(n) / (1.6 * SR))
    fade_out = np.clip((n - np.arange(n)) / (4.0 * SR), 0.0, 1.0) ** 1.5
    return normalize(out * fade_in * fade_out, 0.5)


# --------------------------------------------------------------------------- #
def write_wav(path: str, data: np.ndarray):
    import wave
    if data.ndim == 1:
        data = stereo(data)
    pcm = np.clip(data, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pcm * 32767).astype("<i2").tobytes())


def read_wav(path: str) -> np.ndarray:
    import wave
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768.0
        if w.getnchannels() == 2:
            return raw.reshape(-1, 2)
        return stereo(raw)


def main():
    os.makedirs(OUT, exist_ok=True)
    tl = json.load(open(os.path.join(PUBLIC, "timeline.json"), encoding="utf-8"))
    total = tl["total"]
    n = int(total * SR) + SR

    # ---- SFX track, cued from the animation's own event list ----
    sfx = np.zeros((n, 2))
    cues = 0
    for beat in tl["beats"]:
        for ev in beat["events"]:
            name = ev.get("sfx")
            if not name or name not in SFX:
                continue
            s = SFX[name]()
            s = stereo(s, width=0.004) if name in ("whoosh", "sweep", "bloom") else stereo(s)
            i = int((beat["start"] + ev["at"]) * SR)
            seg = s[: max(0, n - i)]
            sfx[i:i + len(seg)] += seg
            cues += 1
    write_wav(os.path.join(OUT, "sfx.wav"), normalize(sfx, 0.85))

    # ---- music bed ----
    bed = stereo(music_bed(total + 1.5), width=0.006)
    write_wav(os.path.join(OUT, "music.wav"), bed)

    # ---- mix: bed ducked under the VO, SFX on top ----
    vo = os.path.join(PUBLIC, "vo", "master.wav")
    pre = os.path.join(OUT, "pre.wav")
    mix = os.path.join(OUT, "mix.wav")
    fc = (
        "[1:a]volume=0.30,highpass=f=45[bed];"
        "[0:a]asplit=2[vo][key];"
        "[bed][key]sidechaincompress=threshold=0.03:ratio=9:attack=8:release=380:"
        "makeup=1[bedduck];"
        "[2:a]volume=0.62[fx];"
        "[vo][bedduck][fx]amix=inputs=3:weights=1 0.75 0.55:normalize=0[pre];"
        "[pre]highpass=f=35,alimiter=limit=0.92[out]"
    )
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", vo, "-i", os.path.join(OUT, "music.wav"),
                    "-i", os.path.join(OUT, "sfx.wav"),
                    "-filter_complex", fc, "-map", "[out]",
                    "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", pre], check=True)

    # ---- two-pass loudness master to -14 LUFS / -2 dBTP ----
    import re
    p = subprocess.run([FF, "-hide_banner", "-nostats", "-i", pre,
                        "-af", "loudnorm=I=-14:TP=-2:LRA=3:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    blob = p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1]
    m = json.loads(blob)
    subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-y", "-i", pre,
         "-af", ("loudnorm=I=-14:TP=-2:LRA=3"
                 f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                 f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                 f":offset={m['target_offset']}:linear=true"),
         "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", mix], check=True)

    # report
    p = subprocess.run([FF, "-hide_banner", "-nostats", "-i", mix,
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", p.stderr)
    pk = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", p.stderr)
    print(f"cues={cues}  mix={total:.1f}s  "
          f"integrated={i[-1] if i else '?'} LUFS  peak={pk[-1] if pk else '?'} dBFS")
    print("reference:   integrated=-14.2 LUFS  peak=-1.3 dBFS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

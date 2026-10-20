import React, {useMemo} from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import type {Timeline} from "../lib";
import {EASE, FPS} from "../lib";
import {STAGE} from "../theme";

type W = {w: string; s: number; e: number};
type Chunk = {words: W[]; start: number; end: number};

/** Words that get the accent colour + glow, per the skill. */
const KEY =
  /^(₦|\$)?\d|\d|^rentcheck$|^risk$|^flagged$|^missing$|^signing$|^sign$|^high$|^questions$|^tenancy$|^protections$|^clauses$|^plain$|^english$/i;

const isKey = (w: string) => KEY.test(w.replace(/[.,?!…]/g, ""));

/**
 * Kinetic captions: the VO word for word, revealed in phrase chunks on the frame
 * each word is spoken (word timestamps straight out of the TTS), exactly like
 * the reference.
 */
export const Captions: React.FC<{timeline: Timeline}> = ({timeline}) => {
  const frame = useCurrentFrame();
  const chunks = useMemo(() => buildChunks(timeline), [timeline]);
  const t = frame / FPS;

  const active = chunks.find((c) => t >= c.start - 0.14 && t <= c.end + 0.20);
  if (!active) {
    return null;
  }
  const a = interpolate(
    frame,
    [
      (active.start - 0.14) * FPS,
      (active.start - 0.14) * FPS + 7,
      (active.end + 0.20) * FPS - 8,
      (active.end + 0.20) * FPS,
    ],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const rise = interpolate(a, [0, 1], [7, 0], {easing: EASE});

  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center"}}>
      <div
        style={{
          marginBottom: 42,
          opacity: a,
          transform: `translateY(${rise}px)`,
          display: "inline-flex",
          gap: "0.34em",
          padding: "15px 34px 17px",
          borderRadius: 999,
          background: "rgba(4,17,12,0.76)",
          border: "1px solid rgba(238,244,240,0.10)",
          boxShadow: "0 18px 50px rgba(0,0,0,0.45)",
          color: STAGE.ink,
          fontFamily: "Inter, sans-serif",
          fontSize: 31,
          fontWeight: 500,
          letterSpacing: -0.2,
          whiteSpace: "nowrap",
        }}
      >
        {active.words.map((w, i) => (
          <CaptionWord key={i} w={w} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

const CaptionWord: React.FC<{w: W}> = ({w}) => {
  const frame = useCurrentFrame();
  const from = w.s * FPS;
  const d = frame - from;
  const o = interpolate(d, [0, 3.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(d, [0, 7], [5, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const key = isKey(w.w);
  const glow = interpolate(d, [0, 3, 22], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        display: "inline-block",
        opacity: o,
        transform: `translateY(${y}px)`,
        color: key ? STAGE.mint : undefined,
        textShadow: key && glow > 0 ? `0 0 ${20 * glow}px rgba(95,224,168,${0.5 * glow})` : undefined,
      }}
    >
      {w.w}
    </span>
  );
};

/** group each spoken line into short phrases, so the pill rolls like the reference */
const buildChunks = (timeline: Timeline): Chunk[] => {
  const out: Chunk[] = [];
  for (const beat of timeline.beats) {
    for (const line of beat.lines) {
      const words = beat.words.filter(
        (w) => w.s >= line.start - 0.06 && w.e <= line.end + 0.25,
      );
      if (!words.length) {
        continue;
      }
      let cur: W[] = [];
      const flush = () => {
        if (!cur.length) return;
        out.push({words: cur, start: cur[0].s, end: cur[cur.length - 1].e});
        cur = [];
      };
      for (const w of words) {
        cur.push(w);
        const done = cur.length >= 6 || /[.,?!]$/.test(w.w);
        if (done) flush();
      }
      flush();
    }
  }
  return out;
};

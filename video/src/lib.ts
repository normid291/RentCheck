import {Easing, interpolate} from "remotion";

export const FPS = 60;
export const W = 1920;
export const H = 1080;

/** seconds -> frames */
export const f = (s: number) => Math.round(s * FPS);

/** expo-out: fast in, soft settle (the reference's signature curve) */
export const EASE = Easing.bezier(0.22, 1, 0.36, 1);
/** a softer settle for long camera moves */
export const SOFT = Easing.bezier(0.16, 1, 0.3, 1);
/** accelerate away */
export const EASE_IN = Easing.bezier(0.5, 0, 0.9, 0.4);
export const LINEAR = (v: number) => v;
export const BACK = Easing.bezier(0.34, 1.4, 0.64, 1);

export type Word = {w: string; s: number; e: number};
export type Line = {text: string; start: number; end: number};
export type Event = {id: string; at: number; sfx?: string};
export type Beat = {
  id: string;
  label: string;
  start: number;
  dur: number;
  lines: Line[];
  words: Word[];
  events: Event[];
};
export type Timeline = {
  fps: number;
  total: number;
  total_frames: number;
  lead_in: number;
  words: number;
  vo_seconds: number;
  wpm: number;
  beats: Beat[];
};

/** local frame of an event (event times are relative to the beat) */
export const at = (beat: Beat, id: string): number => {
  const e = beat.events.find((x) => x.id === id);
  return e ? f(e.at) : 0;
};

/** local frame where a line starts */
export const lineAt = (beat: Beat, i: number): number => f(beat.lines[i].start - beat.start);

/** progress 0..1 for a move that starts at `from` frames and takes `dur` frames */
export const run = (frame: number, from: number, dur: number, ease = EASE) =>
  interpolate(frame, [from, from + Math.max(1, dur)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

/** fade in at `from`, hold, fade out ending at `to` */
export const inOut = (
  frame: number,
  from: number,
  to: number,
  fin = 9,
  fout = 12,
) =>
  interpolate(frame, [from, from + fin, to - fout, to], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/** 0..1 pop with a spring-like overshoot-free settle */
export const pop = (frame: number, from: number, dur = 14) =>
  interpolate(frame, [from, from + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });

/** deterministic value noise, so every frame renders identically */
export const noise = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

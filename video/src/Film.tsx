import React from "react";
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from "remotion";
import type {Beat, Timeline} from "./lib";
import {f} from "./lib";
import {World} from "./components/World";
import {Captions} from "./components/Caption";
import {B01Hook, B02Meet, B03Pain, B04Turn, B05Reveal} from "./beats/narrative";
import {B06Upload, B07Report, B08Clause, B11Close} from "./beats/product";
import {B09Ask, B10Proof} from "./beats/close";

const REGISTRY: Record<string, React.FC<{beat: Beat; ev: (id: string) => number}>> = {
  b01_hook: B01Hook,
  b02_meet: B02Meet,
  b03_pain: B03Pain,
  b04_turn: B04Turn,
  b05_reveal: B05Reveal,
  b06_upload: B06Upload,
  b07_report: B07Report,
  b08_clause: B08Clause,
  b09_ask: B09Ask,
  b10_proof: B10Proof,
  b11_close: B11Close,
};

/**
 * Beats are joined with the reference's measured 0.17-0.2s cross-dissolve.
 * Sequences are extended by OVER frames and each beat fades in over its first
 * OVER frames and out over its last OVER — so the incoming beat is already
 * dissolving up while the outgoing one is still dissolving down. The world
 * behind them never cuts at all.
 */
const OVER = 12;

const Dissolve: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const frame = useCurrentFrame();
  const end = dur + OVER;
  const a = interpolate(frame, [0, OVER, dur, end], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{opacity: a}}>{children}</AbsoluteFill>;
};

/** the whole picture settles to black at the very end */
const FadeOut: React.FC<{total: number}> = ({total}) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [total - 20, total - 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{background: "#050814", opacity: o}} />;
};

export const Film: React.FC<{timeline: Timeline}> = ({timeline}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#060a1a",
        fontFamily: "Inter, sans-serif",
        WebkitFontSmoothing: "antialiased",
        textRendering: "optimizeLegibility",
      }}
    >
      <World />
      <Audio src={staticFile("audio/mix.wav")} />
      {timeline.beats.map((beat) => {
        const Comp = REGISTRY[beat.id];
        const dur = f(beat.dur);
        if (!Comp) {
          return null;
        }
        return (
          <Sequence
            key={beat.id}
            from={Math.max(0, f(beat.start) - OVER)}
            durationInFrames={dur + OVER}
            name={beat.label}
          >
            <Dissolve dur={dur}>
              <Comp
                beat={beat}
                ev={(id) => OVER + f(beat.events.find((e) => e.id === id)?.at ?? 0)}
              />
            </Dissolve>
          </Sequence>
        );
      })}
      <Captions timeline={timeline} />
      <FadeOut total={timeline.total_frames} />
    </AbsoluteFill>
  );
};

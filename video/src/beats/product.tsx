import React from "react";
import {interpolate, useCurrentFrame} from "remotion";
import type {Beat} from "../lib";
import {EASE, FPS, pop, run} from "../lib";
import {BRAND, STAGE} from "../theme";
import {Camera} from "../components/Camera";
import {Ada} from "../components/Character";
import {ClauseCard, ResultsPanel, UploadPanel} from "../components/AppUi";
import {Hand, LogoMark, Stepper} from "../components/Ui";

type P = {beat: Beat; ev: (id: string) => number};

const STEPS = ["UPLOAD", "CHECK", "ANALYSE", "REPORT"];

const Stage: React.FC<{active: number; p: number}> = ({active, p}) => (
  <div style={{position: "absolute", left: 0, right: 0, top: 40, display: "flex", justifyContent: "center"}}>
    <Stepper steps={STEPS} active={active} p={p} />
  </div>
);

/* ========================================================== 06 · upload */

export const B06Upload: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const dur = beat.dur * FPS;
  const push = run(frame, 0, dur * 0.8, EASE);
  const active = frame >= ev("readDone") ? 2 : frame >= ev("gateOk") ? 1 : 0;
  const click = pop(frame, ev("clickUpload"), 10);
  const handP = interpolate(
    frame,
    [ev("clickUpload") - 26, ev("clickUpload") - 4, ev("clickUpload") + 26, ev("clickUpload") + 54],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );

  return (
    <>
      <Stage active={active} p={1} />
      <Camera p={1} from={{scale: 1.0 + 0.05 * push, y: 0}} to={{scale: 1.055, y: -6}}>
        <UploadPanel ev={ev} frame={frame} p={pop(frame, ev("panel"), 18)} />
        <Hand x={896} y={322 - 12 * click} p={handP} click={click} size={0.95} rot={-6} />
      </Camera>
    </>
  );
};

/* ========================================================== 07 · report */

export const B07Report: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const dur = beat.dur * FPS;
  const push = run(frame, 0, dur, EASE);
  const macro = run(frame, ev("list"), 96, EASE);
  const scale = 1.0 + 0.05 * push + 0.29 * macro;
  const y = -12 * push + 40 * macro;
  const hud = interpolate(macro, [0, 0.62], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <>
      <Stage active={3} p={hud} />
      <Camera p={1} from={{scale, y}} to={{scale, y}}>
        <ResultsPanel ev={ev} frame={frame} p={pop(frame, ev("screen"), 20)} />
      </Camera>
    </>
  );
};

/* ========================================================== 08 · clause */

export const B08Clause: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const dur = beat.dur * FPS;
  const push = run(frame, 0, dur, EASE);
  const zoom = run(frame, ev("quote"), 90, EASE);
  const handP = interpolate(
    frame,
    [ev("quote") - 30, ev("quote") - 6, ev("quote") + 24, ev("quote") + 56],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );

  return (
    <>
      <Stage active={3} p={1} />
      <Camera p={1} from={{scale: 1.0 + 0.05 * push, y: 0}} to={{scale: 1.06 + 0.06 * zoom, y: 34 * zoom}}>
        <ClauseCard ev={ev} frame={frame} p={pop(frame, ev("cardIn"), 20)} />
        <Hand x={1091} y={411} p={handP} size={0.85} rot={10} click={pop(frame, ev("quote"), 10)} />
      </Camera>
    </>
  );
};

/* ========================================================= 11 · close */

export const B11Close: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const dur = beat.dur * FPS;
  const push = run(frame, 0, dur, EASE);
  const bloom = pop(frame, ev("logo"), 14);
  const mark = pop(frame, ev("mark"), 22);
  const line1 = pop(frame, ev("line"), 18);
  const line2 = pop(frame, ev("sub"), 18);
  const cta = pop(frame, ev("cta"), 18);
  const hover = pop(frame, ev("hover"), 10);
  const holdFade = interpolate(frame, [dur - 26, dur - 6], [1, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Camera p={push} from={{scale: 1.0}} to={{scale: 1.05, y: -12}} style={{opacity: holdFade}}>
      <div
        style={{
          position: "absolute",
          left: 960,
          top: 300,
          width: 620,
          height: 620,
          marginLeft: -310,
          marginTop: -310,
          borderRadius: 999,
          background: "radial-gradient(circle, rgba(140,240,190,0.30) 0%, rgba(0,0,0,0) 68%)",
          opacity: bloom,
          transform: `scale(${0.5 + bloom * 0.7})`,
        }}
      />
      <div style={{position: "absolute", left: 0, right: 0, top: 96, display: "flex", justifyContent: "center", opacity: mark}}>
        <div style={{display: "flex", alignItems: "center", gap: 20}}>
          <LogoMark size={78} color={STAGE.mint} />
          <span style={{fontFamily: "Inter, sans-serif", fontSize: 66, fontWeight: 800, letterSpacing: -2, color: "#ffffff"}}>
            RentCheck
          </span>
        </div>
      </div>

      <div style={{position: "absolute", left: 0, right: 0, top: 268, textAlign: "center"}}>
        <div
          style={{
            fontFamily: "Inter, sans-serif",
            fontSize: 92,
            fontWeight: 800,
            letterSpacing: -2.5,
            color: "#ffffff",
            opacity: line1,
            transform: `translateY(${(1 - line1) * 20}px)`,
          }}
        >
          Stop guessing.
        </div>
      </div>

      <div style={{position: "absolute", left: 0, right: 0, top: 392, textAlign: "center", opacity: line2}}>
        <span
          style={{
            fontFamily: "Inter, sans-serif",
            fontSize: 62,
            fontWeight: 700,
            letterSpacing: -1.5,
            color: STAGE.mint,
            fontStyle: "italic",
            transform: `translateY(${(1 - line2) * 16}px)`,
            display: "inline-block",
          }}
        >
          Know what you&rsquo;re signing.
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 560,
          display: "flex",
          justifyContent: "center",
          gap: 22,
          opacity: cta,
          transform: `translateY(${(1 - cta) * 18}px)`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "24px 44px",
            borderRadius: 999,
            background: BRAND.green,
            color: "#ffffff",
            fontFamily: "Inter, sans-serif",
            fontSize: 32,
            fontWeight: 700,
            boxShadow: `0 26px 70px rgba(14,122,82,0.55), 0 0 ${40 * hover}px rgba(95,224,168,0.5)`,
            transform: `scale(${1 - 0.04 * hover})`,
          }}
        >
          rentcheck.rumptycloud.app
          <span style={{fontSize: 28}}>→</span>
        </div>
      </div>

      <div style={{position: "absolute", left: 250, top: 470, opacity: pop(frame, ev("cta"), 20)}}>
        <Ada size={1.9} mood="point" frame={frame} tone="light" />
      </div>
      <div style={{position: "absolute", left: 1420, top: 300, opacity: pop(frame, ev("cta"), 20)}}>
        <Ada size={1.9} mood="pointLeft" frame={frame} tone="warm" />
      </div>
    </Camera>
  );
};

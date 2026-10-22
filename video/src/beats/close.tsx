import React from "react";
import {interpolate, useCurrentFrame} from "remotion";
import type {Beat} from "../lib";
import {EASE, FPS, pop, run} from "../lib";
import {BRAND, INK, SEV, STAGE} from "../theme";
import {Camera} from "../components/Camera";
import {QuestionsPanel} from "../components/AppUi";
import {Hand, IconFlag, IconLock, IconSearch, Stepper} from "../components/Ui";
import analysis from "../data/analysis.json";

type P = {beat: Beat; ev: (id: string) => number};

/* ============================================================= 09 · ask */

export const B09Ask: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const push = run(frame, 0, beat.dur * FPS, EASE);
  const cursorIn = pop(frame, ev("cursor"), 22);
  const hover = pop(frame, ev("expand"), 14);
  const handP = interpolate(
    frame,
    [ev("cursor"), ev("cursor") + 18, ev("expand") + 8, ev("expand") + 26],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  return (
    <>
      <div style={{position: "absolute", left: 0, right: 0, top: 40, display: "flex", justifyContent: "center"}}>
        <Stepper steps={["UPLOAD", "CHECK", "ANALYSE", "REPORT"]} active={3} p={1} />
      </div>
      <Camera p={push} from={{scale: 1.0, y: 0}} to={{scale: 1.07, y: 26}}>
        <QuestionsPanel ev={ev} frame={frame} p={pop(frame, ev("listIn"), 20)} />
        <div style={{position: "absolute", left: 0, top: 0, opacity: cursorIn}}>
          <Hand
            x={1447}
            y={424 - 12 * hover}
            p={handP}
            size={0.62}
            rot={-8}
            click={hover}
          />
        </div>
      </Camera>
    </>
  );
};

/* =========================================================== 10 · proof */

export const B10Proof: React.FC<P> = ({beat, ev}) => {
  const frame = useCurrentFrame();
  const push = run(frame, 0, beat.dur * FPS, EASE);
  const stats = [
    {id: "stat1", n: analysis.counts.flagged, l: "Flagged clauses", c: SEV.high.fg, icon: <IconFlag size={42} color={SEV.high.fg} />},
    {id: "stat2", n: analysis.counts.missing, l: "Missing protections", c: SEV.medium.fg, icon: <IconLock size={42} color={SEV.medium.fg} />},
    {id: "stat3", n: analysis.counts.questions, l: "Questions to ask", c: SEV.low.fg, icon: <IconSearch size={42} color={SEV.low.fg} />},
  ];
  const foot = pop(frame, ev("stat3") + 26, 20);
  const footline = `${analysis.counts.flagged} of ${analysis.counts.checked} checked clauses flagged · ${analysis.counts.missing} protections missing · ${analysis.counts.clauses} clauses found`;

  return (
    <Camera p={push} from={{scale: 1.0, y: 18}} to={{scale: 1.06, y: -18}}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 236,
          textAlign: "center",
          fontFamily: "Inter, sans-serif",
        }}
      >
        <div style={{fontSize: 28, fontWeight: 800, letterSpacing: 4, color: STAGE.accent, opacity: pop(frame, 6, 16)}}>
          WHAT THE CHECK FOUND
        </div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 316, display: "flex", justifyContent: "center", gap: 90}}>
        {stats.map((s) => {
          const at = ev(s.id);
          const p = pop(frame, at, 20);
          const num = Math.round(s.n * interpolate(frame, [at, at + 40], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE,
          }));
          return (
            <div
              key={s.id}
              style={{
                width: 440,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                opacity: p,
                transform: `translateY(${(1 - p) * 26}px)`,
                fontFamily: "Inter, sans-serif",
              }}
            >
              <span
                style={{
                  width: 112,
                  height: 112,
                  borderRadius: 999,
                  display: "grid",
                  placeItems: "center",
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(238,244,240,0.16)",
                  boxShadow: "0 20px 50px rgba(0,0,0,0.4)",
                }}
              >
                {s.icon}
              </span>
              <div style={{fontSize: 206, fontWeight: 800, lineHeight: 1, letterSpacing: -7, color: "#ffffff", marginTop: 24, fontVariantNumeric: "tabular-nums"}}>
                {num}
              </div>
              <div style={{fontSize: 26, fontWeight: 700, letterSpacing: 2.6, textTransform: "uppercase", color: s.c, marginTop: 12}}>
                {s.l}
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 838,
          textAlign: "center",
          opacity: foot,
          fontFamily: "Inter, sans-serif",
          fontSize: 27,
          fontWeight: 500,
          color: STAGE.muted,
        }}
      >
        {footline}
      </div>
    </Camera>
  );
};

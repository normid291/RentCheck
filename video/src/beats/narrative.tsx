import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import type {Beat} from "../lib";
import {EASE, EASE_IN, FPS, pop, run} from "../lib";
import {BRAND, INK, SEV, STAGE, TYPE} from "../theme";
import {Camera} from "../components/Camera";
import {WordReveal} from "../components/WordReveal";
import {Ada, Deed, Plant} from "../components/Character";
import {LogoMark} from "../components/Ui";
import analysis from "../data/analysis.json";

type P = {beat: Beat; ev: (id: string) => number};

const chipStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "18px 26px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.085)",
  border: "1px solid rgba(238,244,240,0.16)",
  boxShadow: "0 20px 50px rgba(0,0,0,0.4)",
  color: STAGE.ink,
  fontFamily: "Inter, sans-serif",
  fontSize: 27,
  fontWeight: 600,
  whiteSpace: "nowrap",
};

const GlassCard: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  p: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({x, y, w, h, p, children, style}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      borderRadius: 20,
      background: "rgba(255,255,255,0.085)",
      border: "1px solid rgba(238,244,240,0.16)",
      boxShadow: "0 26px 60px rgba(0,0,0,0.42)",
      opacity: p,
      transform: `translateY(${(1 - p) * 22}px)`,
      ...style,
    }}
  >
    {children}
  </div>
);

/* ============================================================ 01 · hook */

export const B01Hook: React.FC<P> = ({beat, ev}) => {
  const frame = useFrameLocal();
  const push = run(frame, 0, beat.dur * FPS, EASE);
  const docP = pop(frame, ev("docIn"), 18);
  const sweep = interpolate(frame, [ev("scan"), ev("scan") + 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const marks = [
    {i: 4, color: SEV.medium.fg, p: pop(frame, ev("chip1"), 14)},
    {i: 9, color: SEV.low.fg, p: pop(frame, ev("chip2"), 14)},
    {i: 13, color: SEV.high.fg, p: pop(frame, ev("chip3"), 14)},
  ];
  const chips = [
    {id: "chip1", text: "12 months rent upfront", color: SEV.medium.fg},
    {id: "chip2", text: "Entry without notice", color: SEV.low.fg},
    {id: "chip3", text: "No repairs clause", color: SEV.high.fg},
  ];

  return (
    <Camera p={push} from={{scale: 1.0, y: 6}} to={{scale: 1.055, y: -12}}>
      <WordReveal
        text="Do you actually know what's in your tenancy agreement?"
        at={6}
        size={TYPE.display}
        width={1560}
        accentWords={["tenancy", "agreement"]}
        style={{position: "absolute", left: 180, top: 106, width: 1560, textAlign: "center"}}
      />
      <div style={{position: "absolute", left: 600, top: 300, opacity: docP, transform: `translateY(${(1 - docP) * 26}px)`}}>
        <Deed w={592} h={652} rot={-2.4} label="Deed of Lease" scan={sweep} marks={marks} />
      </div>
      {chips.map((c, i) => {
        const p = pop(frame, ev(c.id), 16);
        return (
          <div
            key={c.id}
            style={{
              ...chipStyle,
              position: "absolute",
              left: 1330,
              top: 420 + i * 106,
              opacity: p,
              transform: `translateX(${(1 - p) * 34}px)`,
            }}
          >
            <span style={{width: 5, height: 30, borderRadius: 3, background: c.color}} />
            {c.text}
          </div>
        );
      })}
    </Camera>
  );
};

/* ============================================================ 02 · meet */

export const B02Meet: React.FC<P> = ({beat, ev}) => {
  const frame = useFrameLocal();
  const push = run(frame, 0, beat.dur * FPS, EASE);
  const host = pop(frame, ev("hostIn"), 20);
  const sheets = [
    {id: "paper1", x: 1292, y: 302, rot: 7, w: 360, h: 470},
    {id: "paper2", x: 1182, y: 262, rot: -5, w: 360, h: 470},
    {id: "deed", x: 1112, y: 232, rot: 2, w: 432, h: 570},
  ];

  return (
    <Camera p={push} from={{scale: 1.0, y: 0}} to={{scale: 1.07, y: -16}}>
      <Plant x={1700} y={718} size={2.0} p={host} />
      <div style={{position: "absolute", left: 496, top: 400, opacity: host, transform: `translateY(${(1 - host) * 30}px)`}}>
        <Ada size={2.0} mood="idle" frame={frame} />
      </div>
      {sheets.map((s, i) => {
        const p = pop(frame, ev(s.id), 20);
        return (
          <div key={s.id} style={{position: "absolute", left: s.x, top: s.y, opacity: p, transform: `translateY(${(1 - p) * 40}px) rotate(${s.rot}deg)`}}>
            <Deed w={s.w} h={s.h} label={i === 2 ? "Deed of Lease" : undefined} lines={i === 2 ? 18 : 14} />
          </div>
        );
      })}
    </Camera>
  );
};

/* ============================================================ 03 · pain */

export const B03Pain: React.FC<P> = ({beat, ev}) => {
  const frame = useFrameLocal();
  const push = run(frame, 0, beat.dur * FPS, EASE);
  const cards = [
    {id: "card1", x: 1030, y: 188, label: analysis.flagged[0].label, sev: analysis.flagged[0].severity},
    {id: "card2", x: 1348, y: 396, label: analysis.flagged[3].label, sev: analysis.flagged[3].severity},
    {id: "card3", x: 1012, y: 606, label: analysis.flagged[2].label, sev: analysis.flagged[2].severity},
  ];
  const chips = [
    {id: "chipA", text: "Too much legalese"},
    {id: "chipB", text: "Nobody explains it"},
    {id: "chipC", text: "You only find out later"},
  ];
  const drop = pop(frame, ev("drop"), 40);

  return (
    <Camera p={push} from={{scale: 1.0, y: 0}} to={{scale: 1.13, y: -18}}>
      <div style={{position: "absolute", left: 232, top: 402}}>
        <Ada size={1.9} mood="idle" frame={frame} />
      </div>

      {cards.map((c) => {
        const p = pop(frame, ev(c.id), 18);
        const sevC = SEV[c.sev as "high" | "medium" | "low"];
        return (
          <GlassCard key={c.id} x={c.x} y={c.y} w={430} h={150} p={p} style={{padding: 24}}>
            <div style={{width: 44, height: 5, borderRadius: 3, background: sevC.fg, marginBottom: 14}} />
            <div style={{fontSize: 27, fontWeight: 700, color: STAGE.ink, fontFamily: "Inter, sans-serif"}}>{c.label}</div>
            <div style={{marginTop: 12, display: "flex", flexDirection: "column", gap: 7}}>
              {[96, 88, 92].map((w, i) => (
                <div key={i} style={{width: `${w}%`, height: 7, borderRadius: 4, background: "rgba(238,244,240,0.22)"}} />
              ))}
            </div>
          </GlassCard>
        );
      })}

      {chips.map((c, i) => {
        const p = pop(frame, ev(c.id), 16);
        return (
          <div
            key={c.id}
            style={{
              ...chipStyle,
              position: "absolute",
              left: 152,
              top: 128 + i * 100,
              opacity: p,
              transform: `translateX(${(1 - p) * -30}px)`,
              fontSize: 26,
            }}
          >
            <span style={{width: 11, height: 11, borderRadius: 99, background: STAGE.mint}} />
            {c.text}
          </div>
        );
      })}

      <AbsoluteFill
        style={{
          background: "radial-gradient(70% 60% at 50% 52%, rgba(0,0,0,0) 42%, rgba(0,0,0,0.34) 100%)",
          opacity: drop,
        }}
      />
    </Camera>
  );
};

/* ============================================================ 04 · turn */

export const B04Turn: React.FC<P> = ({beat, ev}) => {
  const frame = useFrameLocal();
  const out = run(frame, ev("out1"), 22, EASE);
  const second = pop(frame, ev("in2"), 22);
  const dim = interpolate(frame, [ev("in2"), ev("in2") + 24], [1, 0.34], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });

  return (
    <Camera p={out} from={{scale: 1.0}} to={{scale: 1.035}}>
      <div style={{position: "absolute", left: 0, right: 0, top: 380, opacity: dim, transform: `translateY(${-14 * second}px)`}}>
        <WordReveal
          text="Ada doesn't need any more jargon."
          at={8}
          size={TYPE.turn}
          accentWords={["jargon"]}
          accent="#5fe0a8"
          style={{justifyContent: "center"}}
        />
      </div>
      {second > 0 ? (
        <div style={{position: "absolute", left: 0, right: 0, top: 512, opacity: second, transform: `translateY(${(1 - second) * 22}px)`}}>
          <WordReveal
            text="She needs one clear answer."
            at={ev("in2") + 2}
            size={TYPE.turn}
            accentWords={["clear"]}
            italicWords={["clear"]}
            accent="#5fe0a8"
            style={{justifyContent: "center"}}
          />
        </div>
      ) : null}
    </Camera>
  );
};

/* ========================================================== 05 · reveal */

export const B05Reveal: React.FC<P> = ({beat, ev}) => {
  const frame = useFrameLocal();
  const drift = run(frame, 0, beat.dur * FPS, EASE);
  const conv = run(frame, ev("converge"), Math.round(0.62 * FPS), EASE_IN);
  const bloomIn = interpolate(frame, [ev("bloom"), ev("bloom") + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const bloomOut = interpolate(frame, [ev("bloom") + 12, ev("bloom") + 46], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const bloom = bloomIn * bloomOut;
  const mark = pop(frame, ev("mark"), 20);
  const pills = [
    {id: "pill1", text: "UPLOAD"},
    {id: "pill2", text: "UNDERSTAND"},
    {id: "pill3", text: "KNOW WHAT TO ASK"},
  ];
  const petals = new Array(10).fill(0).map((_, i) => {
    const a = (i / 10) * Math.PI * 2 + 0.4;
    const r = 520 + (i % 3) * 90;
    return {x: 960 + Math.cos(a) * r, y: 470 + Math.sin(a) * r * 0.62, rot: (i % 5) * 12 - 24};
  });

  return (
    <Camera p={drift} from={{scale: 1.0, y: 4}} to={{scale: 1.045, y: -8}}>
      {petals.map((pt, i) => {
        const p = 1 - conv;
        const x = pt.x + (960 - pt.x) * conv;
        const y = pt.y + (470 - pt.y) * conv;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: 150,
              height: 96,
              borderRadius: 14,
              background: "rgba(255,255,255,0.09)",
              border: "1px solid rgba(238,244,240,0.16)",
              transform: `translate(-50%,-50%) rotate(${pt.rot * p}deg) scale(${0.4 + 0.6 * p})`,
              opacity: p * 0.95,
            }}
          />
        );
      })}

      {/* bloom */}
      <div
        style={{
          position: "absolute",
          left: 960,
          top: 470,
          width: 700,
          height: 700,
          marginLeft: -350,
          marginTop: -350,
          borderRadius: 999,
          background: "radial-gradient(circle, rgba(255,255,255,0.72) 0%, rgba(150,242,196,0.38) 26%, rgba(120,220,175,0.13) 54%, rgba(0,0,0,0) 80%)",
          opacity: bloom * 0.95,
          transform: `scale(${0.25 + bloom * 1.05})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 960,
          top: 430,
          marginLeft: -120,
          marginTop: -120,
          width: 240,
          height: 240,
          borderRadius: 999,
          background: "rgba(255,255,255,0.10)",
          border: "2px solid rgba(255,255,255,0.35)",
          display: "grid",
          placeItems: "center",
          opacity: mark,
          transform: `scale(${0.6 + mark * 0.4})`,
          boxShadow: `0 0 120px rgba(95,224,168,${0.55 * mark})`,
        }}
      >
        <LogoMark size={150} color="#ffffff" sw={2} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 600,
          textAlign: "center",
          opacity: mark,
          fontFamily: "Inter, sans-serif",
        }}
      >
        <div style={{fontSize: 78, fontWeight: 800, letterSpacing: -2, color: "#ffffff"}}>Tenura</div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 730, display: "flex", justifyContent: "center", gap: 16}}>
        {pills.map((pl) => {
          const p = pop(frame, ev(pl.id), 16);
          return (
            <div
              key={pl.id}
              style={{
                padding: "14px 28px",
                borderRadius: 999,
                border: "1px solid rgba(95,224,168,0.4)",
                background: "rgba(95,224,168,0.10)",
                color: STAGE.mint,
                fontSize: 21,
                fontWeight: 800,
                letterSpacing: 2.2,
                fontFamily: "Inter, sans-serif",
                opacity: p,
                transform: `translateY(${(1 - p) * 12}px)`,
              }}
            >
              {pl.text}
            </div>
          );
        })}
      </div>
    </Camera>
  );
};

/* local frame helper (beats live inside a Sequence) */
const useFrameLocal = () => useCurrentFrame();

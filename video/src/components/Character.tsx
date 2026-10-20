import React from "react";
import {interpolate} from "remotion";

/**
 * Ada — the tenant. Flat illustration, SVG, drawn as a host for the film.
 * Poses: idle | hold | point | pointLeft
 */
export const Ada: React.FC<{
  size?: number;
  mood?: "idle" | "hold" | "point" | "pointLeft";
  frame: number;
  p?: number;
  tone?: "light" | "warm";
}> = ({size = 1, mood = "idle", frame, p = 1, tone = "light"}) => {
  const bob = Math.sin(frame / 60 * Math.PI * 2 * 0.5) * 3.2;
  const blink = frame % 216 > 208;
  const top = tone === "light" ? "#e8f4ee" : "#f0dfc6";
  const topShade = tone === "light" ? "#cfe6dc" : "#dbc7a8";
  const skin = "#e8c6a8";
  const skinShade = "#d3a985";
  const hair = "#2a2020";

  const armR =
    mood === "point"
      ? "M168 168 C196 176 208 190 214 206"
      : mood === "pointLeft"
        ? "M56 168 C34 178 22 192 16 206"
        : "M168 168 C182 196 186 224 184 250";
  const armL =
    mood === "idle" || mood === "point"
      ? "M56 168 C42 196 38 224 40 250"
      : "M56 168 C34 178 22 192 16 206";

  return (
    <div style={{opacity: p, transform: `translateY(${bob}px)`}}>
      <svg
        width={240 * size}
        height={360 * size}
        viewBox="0 0 240 360"
        style={{overflow: "visible"}}
      >
        {/* arms behind the torso */}
        <path d={armL} stroke={topShade} strokeWidth={26} strokeLinecap="round" fill="none" />
        <path d={armR} stroke={topShade} strokeWidth={26} strokeLinecap="round" fill="none" />
        {mood === "point" ? (
          <circle cx="214" cy="206" r="14" fill={skin} />
        ) : mood === "pointLeft" ? (
          <circle cx="16" cy="206" r="14" fill={skin} />
        ) : (
          <>
            <circle cx="40" cy="250" r="14" fill={skin} />
            <circle cx="184" cy="250" r="14" fill={skin} />
          </>
        )}

        {/* torso */}
        <path
          d="M64 176 C64 162 78 150 120 150 C162 150 176 162 176 176 L188 300 C188 312 178 320 166 320 L74 320 C62 320 52 312 52 300 Z"
          fill={top}
        />
        <path d="M120 150 C132 150 142 154 148 160 L132 178 L120 168 L108 178 L92 160 C98 154 108 150 120 150 Z" fill={topShade} />
        {/* collar accent, brand green */}
        <path d="M104 152 L120 172 L136 152" stroke="#0e7a52" strokeWidth={5} fill="none" strokeLinecap="round" />

        {/* neck */}
        <rect x={108} y={116} width={24} height={40} rx={11} fill={skinShade} />

        {/* head */}
        <ellipse cx={120} cy={78} rx={41} ry={45} fill={skin} />
        {/* hair back + bun */}
        <ellipse cx={120} cy={70} rx={49} ry={52} fill={hair} />
        <circle cx={120} cy={16} r={21} fill={hair} />
        <ellipse cx={120} cy={74} rx={41} ry={44} fill={skin} />
        {/* fringe */}
        <path d="M78 62 C86 30 154 30 162 62 C150 48 132 44 120 52 C108 44 90 48 78 62 Z" fill={hair} />
        {/* brows + eyes */}
        <path d="M98 70 C104 66 112 66 116 69" stroke={hair} strokeWidth={3.4} fill="none" strokeLinecap="round" />
        <path d="M124 69 C128 66 136 66 142 70" stroke={hair} strokeWidth={3.4} fill="none" strokeLinecap="round" />
        {blink ? (
          <>
            <path d="M99 84 L115 84" stroke={hair} strokeWidth={3.6} strokeLinecap="round" />
            <path d="M125 84 L141 84" stroke={hair} strokeWidth={3.6} strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx={107} cy={84} r={5.4} fill={hair} />
            <circle cx={133} cy={84} r={5.4} fill={hair} />
          </>
        )}
        {/* cheeks + smile + earring */}
        <ellipse cx={96} cy={96} rx={10} ry={6} fill="#d98f7f" opacity={0.32} />
        <ellipse cx={144} cy={96} rx={10} ry={6} fill="#d98f7f" opacity={0.32} />
        <path d="M110 100 C115 108 125 108 130 100" stroke="#a9553f" strokeWidth={3.6} fill="none" strokeLinecap="round" />
        <circle cx={80} cy={96} r={4} fill="#e0b04a" />
      </svg>
    </div>
  );
};

/* --------------------------------------------------------------- set dressing */

export const Deed: React.FC<{
  w?: number;
  h?: number;
  rot?: number;
  x?: number;
  y?: number;
  p?: number;
  label?: string;
  scan?: number | null; // 0..1 travelling highlight down the page
  lines?: number;
  marks?: {i: number; color: string; p: number}[];
  style?: React.CSSProperties;
}> = ({w = 300, h = 390, rot = 0, x = 0, y = 0, p = 1, label, scan = null, lines = 16, marks = [], style}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      transform: `rotate(${rot}deg)`,
      opacity: p,
      background: "#fbfaf7",
      borderRadius: 8,
      boxShadow: "0 24px 60px rgba(0,0,0,0.45)",
      padding: w * 0.11,
      boxSizing: "border-box",
      ...style,
    }}
  >
    {label ? (
      <div
        style={{
          fontFamily: "Inter, sans-serif",
          fontSize: w * 0.075,
          fontWeight: 800,
          letterSpacing: 2,
          color: "#10201a",
          textAlign: "center",
          marginBottom: w * 0.06,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
    ) : null}
    {new Array(lines).fill(0).map((_, i) => {
      const mark = marks.find((m) => m.i === i);
      const s = scan ?? -1;
      const sweeping = scan !== null && i === Math.round(s * (lines - 1));
      const sweepOp = sweeping ? Math.sin(Math.PI * s) : 0;
      const lit = mark || sweeping;
      return (
        <div
          key={i}
          style={{
            height: Math.max(3, h * 0.013),
            width: `${[100, 92, 97, 84, 96, 90, 99, 88, 95, 91, 97, 93, 89, 98, 94, 86][i % 16]}%`,
            background: mark ? mark.color : sweeping ? "#0e7a52" : "#d8d6cf",
            opacity: mark ? 0.35 + 0.65 * mark.p : sweeping ? sweepOp : 1,
            transform: mark ? `scaleY(${1 + 0.6 * mark.p})` : lit ? "scaleY(1.5)" : undefined,
            transformOrigin: "left center",
            borderRadius: 2,
            marginBottom: h * 0.029,
          }}
        />
      );
    })}
  </div>
);

export const Plant: React.FC<{size?: number; x?: number; y?: number; p?: number}> = ({
  size = 1,
  x = 0,
  y = 0,
  p = 1,
}) => (
  <div style={{position: "absolute", left: x, top: y, opacity: p}}>
    <svg width={150 * size} height={190 * size} viewBox="0 0 150 190">
      <path d="M75 120 C40 96 34 56 44 30 C70 54 76 92 75 120 Z" fill="#1f8f63" />
      <path d="M75 120 C110 96 116 56 106 30 C80 54 74 92 75 120 Z" fill="#25a675" />
      <path d="M75 122 C75 90 75 60 75 26" stroke="#0e7a52" strokeWidth={4} fill="none" />
      <path d="M40 118 h70 l-8 56 a8 8 0 0 1 -8 7 h-38 a8 8 0 0 1 -8 -7 Z" fill="#c9a27a" />
      <rect x={34} y={110} width={82} height={16} rx={8} fill="#d9b48c" />
    </svg>
  </div>
);

export const Mug: React.FC<{size?: number; x?: number; y?: number; p?: number; frame?: number}> = ({
  size = 1,
  x = 0,
  y = 0,
  p = 1,
  frame = 0,
}) => {
  const steam = interpolate(frame % 120, [0, 60, 120], [0, 1, 0]);
  return (
    <div style={{position: "absolute", left: x, top: y, opacity: p}}>
      <svg width={90 * size} height={110 * size} viewBox="0 0 90 110">
        <path
          d={`M30 18 C26 8 36 4 32 -6`}
          stroke="rgba(238,244,240,0.30)"
          strokeWidth={3}
          fill="none"
          strokeLinecap="round"
          opacity={0.35 + 0.4 * steam}
        />
        <path d="M14 30 h52 v46 a18 18 0 0 1 -18 18 h-16 a18 18 0 0 1 -18 -18 Z" fill="#f4efe6" />
        <path d="M66 40 h10 a14 14 0 0 1 0 28 h-10" stroke="#f4efe6" strokeWidth={9} fill="none" />
        <ellipse cx={40} cy={30} rx={26} ry={7} fill="#3a2a22" />
      </svg>
    </div>
  );
};

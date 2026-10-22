import React from "react";
import {Img, interpolate, staticFile} from "remotion";
import {EASE, FPS} from "../lib";
import {BRAND, INK, SEV, STAGE, TYPE} from "../theme";

/* ------------------------------------------------------------------ brand */

/** The real Tenura mark (app/static/tenura-mark.png), rendered exactly as shipped. */
const MARK = staticFile("tenura-mark.png");
/** The lockup adapted for the dark stage: the mark plus the wordmark in white. */
const LOCKUP_DARK = staticFile("tenura-lockup-dark.png");

export const LogoMark: React.FC<{size?: number; color?: string; sw?: number}> = ({size = 64}) => (
  <Img
    src={MARK}
    style={{
      width: size,
      height: size,
      objectFit: "contain",
      objectPosition: "center",
      display: "block",
    }}
  />
);

export const Wordmark: React.FC<{size?: number; color?: string; markColor?: string}> = ({size = 46}) => (
  <Img src={LOCKUP_DARK} style={{height: size, width: "auto", display: "block"}} />
);

/* ------------------------------------------------------------------ cards */

export const Card: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  r?: number;
  tone?: "light" | "dark";
  glow?: number;
  p?: number;
  opacity?: number;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({x, y, w, h, r = 22, tone = "light", glow = 1, p = 1, opacity = 1, style, children}) => {
  const s = 0.965 + 0.035 * p;
  const light = tone === "light";
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: r,
        transform: `scale(${s})`,
        transformOrigin: "50% 50%",
        opacity,
        background: light ? INK.surface : "rgba(9,13,32,0.72)",
        border: `1px solid ${light ? INK.line : "rgba(238,244,240,0.10)"}`,
        boxShadow: light
          ? `0 24px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.6) inset, 0 0 46px rgba(47,110,255,${0.16 * glow})`
          : `0 24px 60px rgba(0,0,0,0.5)`,
        backdropFilter: light ? undefined : "blur(14px)",
        padding: 0,
        color: light ? INK.ink : STAGE.ink,
        fontFamily: "Inter, sans-serif",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Label: React.FC<{
  children: React.ReactNode;
  color?: string;
  size?: number;
  style?: React.CSSProperties;
}> = ({children, color = INK.muted, size = TYPE.micro, style}) => (
  <span
    style={{
      fontSize: size,
      fontWeight: 700,
      letterSpacing: 1.6,
      textTransform: "uppercase",
      color,
      ...style,
    }}
  >
    {children}
  </span>
);

export const Pill: React.FC<{
  label: string;
  fg: string;
  bg: string;
  size?: number;
  style?: React.CSSProperties;
}> = ({label, fg, bg, size = 20, style}) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      padding: `${size * 0.36}px ${size * 0.85}px`,
      borderRadius: 999,
      background: bg,
      color: fg,
      fontSize: size,
      fontWeight: 700,
      letterSpacing: 0.2,
      ...style,
    }}
  >
    {label}
  </span>
);

export const SeverityPill: React.FC<{sev: "high" | "medium" | "low"; size?: number}> = ({
  sev,
  size = 20,
}) => {
  const c = SEV[sev] ?? SEV.low;
  return <Pill label={sev.toUpperCase()} fg={c.fg} bg={c.bg} size={size} />;
};

/* ------------------------------------------------------------------ icons */

export const IconCheck: React.FC<{size?: number; color?: string; sw?: number}> = ({
  size = 24,
  color = BRAND.blue,
  sw = 2.4,
}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const IconFlag: React.FC<{size?: number; color?: string}> = ({size = 24, color = SEV.high.fg}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M4 22V4" />
    <path d="M4 5h13l-2.5 4L17 13H4z" />
  </svg>
);

export const IconFile: React.FC<{size?: number; color?: string}> = ({size = 24, color = INK.muted}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
);

export const IconSearch: React.FC<{size?: number; color?: string}> = ({size = 24, color = INK.muted}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-3.5-3.5" />
  </svg>
);

export const IconLock: React.FC<{size?: number; color?: string}> = ({size = 24, color = INK.muted}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

export const IconAlert: React.FC<{size?: number; color?: string}> = ({size = 24, color = SEV.high.fg}) => (
  <svg
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4" />
    <path d="M12 16h.01" />
  </svg>
);

/* ------------------------------------------------------------------ gauge */

export const RingGauge: React.FC<{
  value: number; // 0..100
  size?: number;
  stroke?: number;
  color?: string;
  track?: string;
  p?: number;
}> = ({value, size = 260, stroke = 22, color = BRAND.blue, track = INK.line, p = 1}) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const shown = value * p;
  return (
    <svg width={size} height={size} style={{transform: "rotate(-90deg)"}}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - shown / 100)}
      />
    </svg>
  );
};

/* ------------------------------------------------------------------ cursor */

export const Cursor: React.FC<{
  x: number;
  y: number;
  p?: number;
  click?: number;
  scale?: number;
  sleeveColor?: string;
}> = ({x, y, p = 1, click = 0, scale = 1, sleeveColor = STAGE.ink}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      transform: `scale(${scale * (1 - 0.12 * click)})`,
      transformOrigin: "4px 4px",
      opacity: p,
    }}
  >
    <svg width={54} height={66} viewBox="0 0 27 33">
      <path
        d="M3 2l18 12.5-7.6 1.3 4.3 8.6-4.2 2.1-4.3-8.6-5.2 5.6z"
        fill="#ffffff"
        stroke="rgba(5,8,20,0.55)"
        strokeWidth={1.4}
      />
    </svg>
  </div>
);

/** the illustrated hand the reference uses for clicks */
export const Hand: React.FC<{
  x: number;
  y: number;
  rot?: number;
  p?: number;
  click?: number;
  size?: number;
}> = ({x, y, rot = 0, p = 1, click = 0, size = 1}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      transform: `rotate(${rot}deg) scale(${size * (1 - 0.08 * click)})`,
      transformOrigin: "50% 90%",
      opacity: p,
    }}
  >
    <svg width={150} height={190} viewBox="0 0 75 95">
      <path d="M40 88c-9 0-16-4-20-11L4 48" stroke="rgba(238,244,240,0.85)" strokeWidth={22} strokeLinecap="round" fill="none" />
      <ellipse cx="38" cy="46" rx="17" ry="19" fill="#e8c6a8" />
      <rect x="30" y="14" width="9" height="30" rx="4.5" fill="#e8c6a8" />
      <rect x="41" y="16" width="9" height="28" rx="4.5" fill="#e8c6a8" />
      <rect x="52" y="22" width="9" height="22" rx="4.5" fill="#e8c6a8" />
      <path d="M21 52c-4-6-2-13 3-16" stroke="#e8c6a8" strokeWidth={9} strokeLinecap="round" fill="none" />
    </svg>
  </div>
);

/* ------------------------------------------------------------------ stepper */

export const Stepper: React.FC<{
  steps: string[];
  active: number;
  p?: number;
  style?: React.CSSProperties;
}> = ({steps, active, p = 1, style}) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 14,
      opacity: p,
      fontFamily: "Inter, sans-serif",
      ...style,
    }}
  >
    {steps.map((s, i) => {
      const done = i < active;
      const now = i === active;
      return (
        <React.Fragment key={s}>
          {i > 0 ? (
            <div style={{width: 34, height: 1, background: "rgba(238,244,240,0.24)"}} />
          ) : null}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              padding: "9px 18px",
              borderRadius: 999,
              border: `1px solid ${
                now ? "rgba(47,92,246,0.60)" : "rgba(238,241,248,0.20)"
              }`,
              background: now ? "rgba(47,92,246,0.16)" : "rgba(255,255,255,0.07)",
            }}
          >
            <span
              style={{
                width: 22,
                height: 22,
                borderRadius: 999,
                display: "grid",
                placeItems: "center",
                background: done || now ? BRAND.blue : "rgba(238,244,240,0.12)",
              }}
            >
              {done ? (
                <IconCheck size={14} color="#ffffff" sw={3} />
              ) : (
                <span style={{fontSize: 12, fontWeight: 800, color: "#ffffff"}}>{i + 1}</span>
              )}
            </span>
            <span
              style={{
                fontSize: 19,
                fontWeight: 700,
                letterSpacing: 1.2,
                color: now ? STAGE.accent : "rgba(238,244,240,0.74)",
              }}
            >
              {s}
            </span>
          </div>
        </React.Fragment>
      );
    })}
  </div>
);

/* ------------------------------------------------------------------ toast */

export const Toast: React.FC<{
  text: string;
  x: number;
  y: number;
  w?: number;
  p: number;
  y0?: number;
  tone?: "good" | "warn" | "info";
  delay?: number;
  frame: number;
}> = ({text, x, y, w = 300, p, y0 = 0, tone = "good", delay = 0, frame}) => {
  const e = interpolate(frame - delay, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const o = p * e;
  const dy = (1 - e) * 18 + y0;
  const col = tone === "good" ? BRAND.blue : tone === "warn" ? SEV.medium.fg : SEV.low.fg;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        transform: `translateY(${dy}px)`,
        opacity: o,
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "16px 20px",
        borderRadius: 16,
        background: INK.surface,
        border: `1px solid ${INK.line}`,
        boxShadow: "0 20px 50px rgba(0,0,0,0.42)",
        fontFamily: "Inter, sans-serif",
        fontSize: 21,
        fontWeight: 600,
        color: INK.ink,
      }}
    >
      <span style={{display: "grid", placeItems: "center", width: 26, height: 26, borderRadius: 999, background: `${col}1f`}}>
        <IconCheck size={16} color={col} sw={3} />
      </span>
      {text}
    </div>
  );
};

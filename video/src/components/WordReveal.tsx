import React from "react";
import {interpolate, useCurrentFrame} from "remotion";
import {EASE, FPS} from "../lib";

/**
 * Hero type that reveals word by word at the reference's measured cadence
 * (~7 words/s): each word is a blurred ghost that rises ~8px and sharpens
 * within 4 frames (130ms).
 */
export const WordReveal: React.FC<{
  text: string;
  at: number;
  cadence?: number;
  size?: number;
  weight?: number;
  color?: string;
  accent?: string;
  accentWords?: string[];
  italicWords?: string[];
  italic?: boolean;
  width?: number;
  lineHeight?: number;
  letterSpacing?: number;
  style?: React.CSSProperties;
}> = ({
  text,
  at,
  cadence = FPS / 7,
  size = 96,
  weight = 700,
  color = "#ffffff",
  accent = "#8fb0ff",
  accentWords = [],
  italicWords = [],
  italic = false,
  width,
  lineHeight = 1.06,
  letterSpacing = -1.5,
  style,
}) => {
  // this component is rendered inside the beat's Sequence, so useCurrentFrame
  // is already local — passed in as `at` by the caller via evAt()
  const words = text.split(" ");
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        width: width ?? "auto",
        fontSize: size,
        fontWeight: weight,
        lineHeight,
        letterSpacing,
        color,
        ...style,
      }}
    >
      {words.map((w, i) => (
        <Word
          key={i}
          w={w}
          from={at + i * cadence}
          accent={accentWords.some((a) => w.toLowerCase().replace(/[^a-z0-9]/g, "").startsWith(a))}
          italic={italic || italicWords.includes(w.toLowerCase().replace(/[^a-z0-9]/g, ""))}
          accentColor={accent}
        />
      ))}
    </div>
  );
};

const Word: React.FC<{
  w: string;
  from: number;
  accent: boolean;
  italic: boolean;
  accentColor: string;
}> = ({w, from, accent, italic, accentColor}) => {
  const frame = useCurrentFrame();
  const d = frame - from;
  const o = interpolate(d, [0, 4], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const y = interpolate(d, [0, 8], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const blur = interpolate(d, [0, 5], [6, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const glow = interpolate(d, [0, 4, 26], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        display: "inline-block",
        marginRight: "0.26em",
        opacity: o,
        transform: `translateY(${y}px)`,
        filter: blur > 0.05 ? `blur(${blur}px)` : undefined,
        color: accent ? accentColor : undefined,
        fontStyle: italic ? "italic" : undefined,
        textShadow: accent && glow > 0 ? `0 0 ${26 * glow}px rgba(143,176,255,${0.55 * glow})` : undefined,
      }}
    >
      {w}
    </span>
  );
};

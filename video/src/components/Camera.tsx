import React from "react";
import {AbsoluteFill} from "remotion";

export type CamMove = {
  /** from -> to for each channel; frames are local to the beat */
  from?: Partial<CamState>;
  to?: Partial<CamState>;
  start?: number;
  dur?: number;
  ease?: (v: number) => number;
};

export type CamState = {
  scale: number;
  x: number;
  y: number;
  rotate: number;
  rotateY: number;
  opacity: number;
};

const IDENTITY: CamState = {scale: 1, x: 0, y: 0, rotate: 0, rotateY: 0, opacity: 1};

/**
 * The camera. Every scene is wrapped in one of these and nothing in this film is
 * allowed to hold still — see docs/video/technique-guide.md §3.
 */
export const Camera: React.FC<{
  p: number;
  from?: Partial<CamState>;
  to?: Partial<CamState>;
  perspective?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({p, from, to, perspective = 1600, style, children}) => {
  const a = {...IDENTITY, ...from};
  const b = {...IDENTITY, ...to};
  const lerp = (u: number, v: number) => u + (v - u) * p;
  const s = lerp(a.scale, b.scale);
  const x = lerp(a.x, b.x);
  const y = lerp(a.y, b.y);
  const rz = lerp(a.rotate, b.rotate);
  const ry = lerp(a.rotateY, b.rotateY);

  return (
    <AbsoluteFill
      style={{
        perspective,
        opacity: lerp(a.opacity, b.opacity),
        ...style,
      }}
    >
      <AbsoluteFill
        style={{
          transform: `translate3d(${x}px, ${y}px, 0) scale(${s}) rotate(${rz}deg) rotateY(${ry}deg)`,
          transformOrigin: "50% 50%",
          willChange: "transform",
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

import React from "react";
import {AbsoluteFill, staticFile, useCurrentFrame} from "remotion";
import {noise} from "../lib";
import {STAGE} from "../theme";

const stageUrl = staticFile("stage.png");

/**
 * One continuous world for the whole film: the brand-green stage, its light
 * pools, the vignette and the film grain are baked into a single cached plate
 * (scripts/make_stage.py), so a frame costs one image composite instead of five
 * full-screen gradient passes and an overlay blend. Only the dust moves on top.
 */
export const World: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: STAGE.base}}>
      <img
        src={stageUrl}
        style={{position: "absolute", inset: 0, width: "100%", height: "100%"}}
      />
      <Dust />
    </AbsoluteFill>
  );
};

const Dust: React.FC = () => {
  const frame = useCurrentFrame();
  const specks = new Array(34).fill(0).map((_, i) => {
    const x = noise(i * 3.1) * 1920;
    const speed = 6 + noise(i * 7.7) * 14;
    const y0 = noise(i * 5.3) * 1180;
    const y = ((y0 - (frame / 60) * speed + 1400) % 1400) - 120;
    const r = 1.1 + noise(i * 11.3) * 2.6;
    const o = 0.05 + noise(i * 13.9) * 0.16;
    return {x, y, r, o};
  });
  return (
    <AbsoluteFill>
      {specks.map((s, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: s.x,
            top: s.y,
            width: s.r * 2,
            height: s.r * 2,
            borderRadius: 99,
            background: STAGE.ink,
            opacity: s.o,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

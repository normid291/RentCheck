import {Composition} from "remotion";
import {Film} from "./Film";
import {ensureFonts} from "./fonts";
import timeline from "../public/timeline.json";
import type {Timeline} from "./lib";

ensureFonts();

export const RemotionRoot: React.FC = () => {
  const tl = timeline as unknown as Timeline;
  return (
    <Composition
      id="RentCheck"
      component={Film}
      durationInFrames={tl.total_frames}
      fps={tl.fps}
      width={1920}
      height={1080}
      defaultProps={{timeline: tl}}
    />
  );
};

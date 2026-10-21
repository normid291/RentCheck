import {continueRender, delayRender} from "remotion";
import {INTER_CSS} from "./fonts.generated";

/**
 * Load the self-hosted Inter faces and block the render until they are ready —
 * otherwise the first frames fall back to a serif.
 */
let started = false;

export const ensureFonts = () => {
  if (started || typeof document === "undefined") {
    return;
  }
  started = true;
  const handle = delayRender("Loading Inter");
  const style = document.createElement("style");
  style.setAttribute("data-tenura-fonts", "1");
  style.textContent = INTER_CSS;
  document.head.appendChild(style);
  const done = () => continueRender(handle);
  if (document.fonts && "ready" in document.fonts) {
    Promise.all([
      document.fonts.load("400 64px Inter"),
      document.fonts.load("600 64px Inter"),
      document.fonts.load("700 64px Inter"),
      document.fonts.load("800 64px Inter"),
      document.fonts.load("italic 700 64px Inter"),
      document.fonts.ready,
    ])
      .then(done)
      .catch(done);
  } else {
    done();
  }
};

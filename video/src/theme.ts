/**
 * Tenura promo — design tokens.
 * Palette is lifted from the app itself (app/static/styles.css) so the film and
 * the product can never drift apart.
 */

export const BRAND = {
  green: "#0e7a52",
  greenDark: "#0a5c3e",
  greenSoft: "#e8f4ee",
  greenRing: "rgba(14,122,82,0.16)",
};

export const INK = {
  ink: "#10201a",
  soft: "#33463d",
  muted: "#5c6f66",
  line: "#e2eae5",
  lineStrong: "#cfdcd4",
  surface: "#ffffff",
  surface2: "#fafcfb",
};

export const SEV = {
  high: { fg: "#c0392b", bg: "#fdeceb" },
  medium: { fg: "#b9770a", bg: "#fdf4e6" },
  low: { fg: "#2f6fb0", bg: "#eaf2fb" },
  rule: { fg: "#6d47d9", bg: "#f1ecfd" },
  ai: { fg: "#6b7280", bg: "#f1f2f4" },
};

/** The dark stage: one continuous brand-green world. */
export const STAGE = {
  base: "#061710",
  mid: "#0a2c1f",
  lift: "#0f4530",
  bloom: "rgba(30,170,118,0.34)",
  bloomWarm: "rgba(14,122,82,0.24)",
  ink: "#eef4f0",
  muted: "rgba(238,244,240,0.62)",
  faint: "rgba(238,244,240,0.34)",
  line: "rgba(238,244,240,0.14)",
  glass: "rgba(255,255,255,0.06)",
  mint: "#5fe0a8",
};

export const TYPE = {
  display: 90,
  hero: 84,
  turn: 76,
  title: 34,
  body: 26,
  label: 20,
  micro: 17,
  caption: 31,
};

/**
 * Tenura promo — design tokens.
 * Palette is lifted from the app itself (app/static/styles.css) so the film and
 * the product can never drift apart.
 */

export const BRAND = {
  blue: "#2f5cf6",
  blueDark: "#1e3fc9",
  blueSoft: "#eef2fe",
  blueRing: "rgba(47,92,246,0.18)",
  violet: "#6a35f0",
};

export const INK = {
  ink: "#0f172a",
  soft: "#334155",
  muted: "#64748b",
  line: "#e6eaf2",
  lineStrong: "#d4dae6",
  surface: "#ffffff",
  surface2: "#fafbfe",
};

export const SEV = {
  high: { fg: "#c0392b", bg: "#fdeceb" },
  medium: { fg: "#b9770a", bg: "#fdf4e6" },
  low: { fg: "#2f6fb0", bg: "#eaf2fb" },
  rule: { fg: "#6d47d9", bg: "#f1ecfd" },
  ai: { fg: "#6b7280", bg: "#f1f2f4" },
};

/** The dark stage: one continuous brand-blue world, blue pool low, violet high. */
export const STAGE = {
  base: "#070a1c",
  mid: "#0b1136",
  lift: "#1a2470",
  bloom: "rgba(47,110,255,0.36)",
  bloomWarm: "rgba(120,60,255,0.26)",
  ink: "#eef1f8",
  muted: "rgba(238,241,248,0.62)",
  faint: "rgba(238,241,248,0.34)",
  line: "rgba(238,241,248,0.14)",
  glass: "rgba(255,255,255,0.06)",
  accent: "#8fb0ff",
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

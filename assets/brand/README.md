# Tenura brand assets

`tenura-lockup-source.png` is the supplied master — the full lockup (mark +
wordmark) on a flat off-white plate, 1774×887. It is the single source of truth
for every derived logo file in the repo; nothing below is hand-drawn.

## What derives from it

| File | Size | Purpose |
| --- | --- | --- |
| `app/static/tenura-logo.png` | 1246×313 | the lockup, transparent — web header |
| `app/static/tenura-mark.png` | 344×313 | the mark alone, transparent |
| `app/static/favicon.png` | 512×512 | browser / PWA icon |
| `app/static/apple-touch-icon.png` | 180×180 | iOS home screen (opaque, iOS masks it) |
| `video/public/tenura-mark.png` | 344×313 | the mark inside the promo film |
| `video/public/tenura-logo.png` | 1246×313 | the lockup, for light plates |
| `video/public/tenura-lockup-dark.png` | 1246×313 | the lockup with the wordmark in white, for the film's dark stage |

The wordmark is dark navy, so it is invisible on the film's dark background;
`tenura-lockup-dark.png` recolours the wordmark to white while leaving the mark
in full colour. The film therefore shows the real lockup, never a redrawn one.

## Palette

The blue/violet palette is defined once, in `app/static/styles.css`
(`--brand #2f5cf6`, `--brand-dark #1e3fc9`, `--brand-2 #6a35f0`).
`video/src/theme.ts` mirrors those tokens, and `video/scripts/make_stage.py`
carries a copy because the film's background plate is pre-baked. If the brand
colour ever changes, all three need to move together.

## Derivations

The transparent files come from removing the source's flat background by
un-premultiplying its alpha (the plate colour is `(253,253,254)`), not by
cropping a white rectangle — so the lockup composites cleanly onto any
background. The film copies under `video/public/` are byte-for-byte the web
assets, except `tenura-lockup-dark.png`.

The original user-supplied reference screenshot lives at
`artifacts/_ref/brand-reference-2026-10-22.jpg` (gitignored scratch, not brand
matter).

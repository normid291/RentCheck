# Technique guide — SaaS promo reference

Source studied: `artifacts/VID-20261020-WA0002.mp4` (the user's reference).
All numbers below are **measured**, not guessed.

## 1. Source facts

| Property | Value |
| --- | --- |
| Resolution / fps | 1280×720, 30 fps (progressive, bt470bg) |
| Duration | 86.27 s |
| Video codec | H.264 High, 257 kb/s |
| Audio | AAC-LC 48 kHz stereo, 127 kb/s |
| Integrated loudness | **−14.2 LUFS**, LRA 2.4 LU, true peak **−1.3 dBFS** |
| Onset density | **3.63 events/s**, tempo estimate **161.5 BPM** (≈ 80.8 half-time) |
| Voiceover | 204 words over 83.3 s = **147 wpm** overall |
| Phrase pacing | per phrase 141–320 wpm; **39 pauses ≥ 0.30 s**, mean **0.65 s**, max **1.02 s** |
| Captions | the VO **word for word**, revealed in phrase chunks, one white line in a dark rounded pill, centred ~40 px from the bottom |
| Framing | hero UI fills **55–70 %** of frame width and grows to **overflow** during pushes; headline ≈ 66 px at 1920 |

## 2. Shot list

| # | Time | On screen | Move / transition in |
| --- | --- | --- | --- |
| 1 | 0.0–3.5 | Dark dashboard card floating on an indigo gradient; headline reveals word by word: *"Do you actually know which of your marketing is working?"* (`working?` italic + accent); pain chips stack down the right ("CTR down 0.4 %", "Report due Monday", "Why are leads down?") | Slow continuous push-in on the card (+~5 % over 3.3 s) |
| 2 | 3.5–9.0 | Flat-illustration woman at a laptop, plants + mug, same background; captions *"Meet Maya."* → *"She runs ads."* → *"posts every day,"* | **Cross-dissolve 0.17–0.2 s**; outgoing headline text outlives the card by ~2 frames |
| 3 | 9.0–13.0 | Platform app icons fly in around her, then fan into an arc of chips; card "Too Many Dashboards" rises | Icons accelerate in, arc settles with a soft overshoot-free ease |
| 4 | 13.0–20.0 | Cards "Hard To Understand", "Problems Go Unnoticed" appear at the frame edges | Camera pushes in on the character (cards drift out of frame as it does) |
| 5 | 20.0–22.4 | Extreme close-up of her face | Push continues to a macro, then a blur wipe |
| 6 | 22.4–26.5 | Turn: *"Not more dashboards."* → *"One that makes sense."* (`sense.` italic accent), old line fades below | Words reveal; old line drops and fades |
| 7 | 26.5–32.6 | Icons converge to the centre → **white bloom** → logo mark + wordmark; pills "Together." "What's working." "Needs attention." appear one by one | Match-cut morph: the chips *are* the logo |
| 8 | 32.6–39.9 | Connect panel: 5 rows (Meta Ads, Instagram, Google Analytics, Mailchimp, Shopify) with Connect buttons; a hand cursor clicks each; rows go **Syncing (amber) → Connected (green ✓)**; "Secure connections" badge | Panel scales+fades in; camera settles onto the list |
| 9 | 39.9–46.3 | Dashboard lands with a 3D tilt; KPI tiles; **health ring counts 0→94**; bottom KPI row; then a macro on that row | Push from whole-dashboard to single-tile (~2.5× over ~4 s) |
| 10 | 46.3–51.6 | Cursor clicks the CTR tile → "Marketing Cheat Sheet / Click-Through Rate (CTR)" popover; character peeks in at the frame corner | Popover pops with a spring, no overshoot wobble |
| 11 | 51.6–60.5 | "Lead audit" card: Scanning… → "1 action recommended" with a red row ("Not sending leads, for 48 hours") → cursor clicks **Review** → row turns green "Fixed", header → "Healthy" → toasts "+12 new leads this week" | State change on click; toasts stack in from the top-right |
| 12 | 60.5–67.4 | *"But there's more…"*; weekly report card with bars growing one by one; "AI help" toggle switches on | Bars grow staggered; toggle springs on |
| 13 | 67.4–71.4 | Three icon beads on a gentle arc: "Less guessing", "Fewer lost leads", "Smarter decisions" | Beads pop in left→right on the arc |
| 14 | 71.4–77.5 | Big stat counters: **14+** connected platforms, **150+** metrics, **100+** health checks (small caps labels below) | Numbers count up ~1.5 s each, label fades in after |
| 15 | 77.5–81.4 | Logo + character slides up from the bottom; *"Stop guessing."* → *"start understanding your marketing."* | Character rises from the frame edge |
| 16 | 81.4–84.8 | End card: logo, headline, CTA pill "Get a demo →" + `rothme.app`, cursor hovering. Hold ~3.5 s | CTA pill fades+rises |
| 17 | 84.8–86.3 | Fade to black → the template maker's own watermark ("samteck") — **ignore, not part of the product film** | Fade |

## 3. Measured motion table (the smoothness lives here)

| Move | Measurement |
| --- | --- |
| Headline word reveal | ~**7 words/s**. Each word: appears as a blurred ghost at ~40 % opacity ~2–3 frames early, rises **~8 px**, reaches full sharpness in **4 frames (≈130 ms)** |
| Chip / toast entrance | fade + rise **~10 px in 0.15 s**, stacked 1 per **~0.17 s** |
| Scene transition | **cross-dissolve 5–6 frames (0.17–0.20 s)** — never a hard cut inside a narrative beat |
| Turn crossfade | outgoing line drops & fades over ~0.25 s while the new one reveals |
| Logo reveal | chips converge **0.43 s** → collapse to a point + **white bloom 0.1 s** → mark glows in and scales **+5 % over 0.3 s** → wordmark fades in (~0.2 s) |
| Count-up (ring) | 0 → 94 over **~2.0 s**, strong ease-out with a long settle tail |
| Count-up (stats) | **~1.5 s** each, clean ease-out, label fades in **after** the number lands |
| Camera | **never static**: intro card push **+~5 % / 3.3 s**; understand scene **~2.5× / 4 s**; drift continues between beats |
| Cursor click | pointer arrives → row state swaps on the click frame → new colour settles over ~0.2 s |

## 4. Visual system

- **Background**: one continuous indigo/violet gradient (deep `#2a2b64` → `#4b4fa0`), a soft radial light bloom low-centre, fine film grain, slow floating dust specks. It **never cuts** — the whole film happens in one world.
- **Surfaces**: very dark navy cards (`#141a2e`), 1 px lighter border, radius 14–18 px, soft shadow + a faint inner glow.
- **Ink**: primary `#eef0f8`, secondary `#8f93b8`; accents violet `#7b6ff0`, green `#3ddc97`, amber `#f5b544`, red `#f4614d`.
- **Type**: one clean grotesk. Headline semibold ~66 px @1920, card titles 24–34 px, labels 12–13 px uppercase with letter-spacing. One **italic accent word** per headline, in colour.
- **UI is always redrawn as clean design in code** — never a screen recording. Rows, checkboxes, toggles, rings, charts are all real components.
- **Stepper**: a small check + stage word ("Connect", "Understand", "Audit") sits at the top as progress.
- **The character is a host, not the subject**: small, anchored at a frame corner, often cropped by the frame edge, entering from below.

## 5. Sound

- Beat-driven music bed, **−14.2 LUFS integrated / −1.3 dBFS peak / LRA 2.4** (i.e. dense and loud, but flat — no quiet valleys).
- **~3.6 sound events per second**: a whoosh on every scene change, a tick on every count-up step, a pop on every chip/toast, a click on every cursor press.
- VO is dry and forward; the bed ducks under it.

## 6. Techniques to build (and how)

1. **Eased camera rig** — a single `<Camera>` component (scale / x / y / rotateZ / rotateY) driven by an interpolation with `Easing.bezier(0.22, 1, 0.36, 1)` (expo-out). Every scene wraps in it; no scene is allowed a static frame except the final logo hold.
2. **Word-reveal headline** — split the script into words, each word gets `opacity` (0.07 s), `y` (+8 px, 0.13 s) and a CSS `blur(6px → 0)` over 0.13 s, staggered at 1/7 s. Accent word additionally italic + colour.
3. **Blur-in / blur-out** — `filter: blur()` on wrappers; also a `@remotion/motion-blur` velocity trail on fast moves.
4. **Match-cut morph** — same component tree re-parented: chips→glow→logo mark; upload card→document page→clause card. Achieved by keeping one persistent element across two scenes and interpolating its props.
5. **Count-up** — from a shared `useCountUp` hook with expo-out easing and an optional settle step, used by the risk ring, KPI tiles and big stats.
6. **Ring gauge** — SVG arc with `strokeDasharray`/`strokeDashoffset` driven by the count-up value.
7. **Cursor + click states** — a `<Cursor>` component that lerps to a target, then a `useState`-driven row state machine (idle → syncing → connected / flagged → fixed), swapping on the click frame.
8. **Glass / dark card system** — one `<Card>` primitive with border, radius, shadow, inner glow; every UI block is built from it.
9. **Grain + dust** — a fixed noise overlay (repeatable, low opacity) plus 60 slow-drifting specks; deterministic per frame so renders are stable.
10. **Caption engine** — driven by the VO's word timestamps (faster-whisper), grouping words into phrase pills, each phrase fading up 0.12 s before its first word and out 0.2 s after its last.
11. **Sound design** — one audio cue per animation event, fired from the same frame constants the animation uses (so audio and motion can never drift), plus a generated music bed, mixed and mastered to −14 LUFS / −2 dBTP with ffmpeg `loudnorm`.
12. **Progress stepper** — one component, 3 states (upcoming / active / done with tick), shared across the product beats.

Reusable components to build once: `Camera`, `Caption`, `WordReveal`, `StatPill`, `Ring`, `Card`, `Cursor`, `GlowBg`, `Toast`, `Stepper`, `LogoMark`.

# Tenura promo — brief, script and beat sheet

Plan for the Tenura promo film, built to match `docs/video/technique-guide.md`
(measured from the user's reference).

## 1. Brief

| | |
| --- | --- |
| **Brand / product** | **Tenura** — AI-assisted tenancy agreement analysis. `www.tenura.online` |
| **One-liner** | Upload a tenancy agreement; get a risk score, the risky clauses with the exact wording, the protections that are missing, and the questions to ask. |
| **Goal** | Launch / awareness ad that sells the *result*: **know what you are signing before you sign**. |
| **Audience** | Nigerian tenants about to sign a tenancy agreement (deed of lease / tenancy agreement), often handed dense legal English by a landlord or agent. |
| **Key message / change for the customer** | "You no longer have to guess what the document means. Risky clauses are flagged by severity with the exact wording, missing protections are named, and you get the questions to ask before you sign." |
| **Length / format** | 16:9, 1920×1080, 60 fps, **~63 s** (reference is 86 s; 9:16 recomposed version on request) |
| **Voiceover** | Yes — professional, warm, trustworthy, ~147 wpm with ~0.6 s phrase pauses (measured from the reference) |
| **Look** | Dark **brand-green** stage (one continuous gradient world, grain + dust), with the **real app UI redrawn in code as light cards** — the hero element filling the frame and being pushed into |
| **Characters** | Flat-illustration tenant (and agent) as *hosts*, small at the frame edge, entering from below — consistent with the reference |
| **Music / SFX** | Synthesised in numpy: a slow pad over I–V–vi–IV in A major, a soft sub, a rhodes-like motif and convolution reverb. No cues — the picture carries the beats. Mastered to −14 LUFS / −2 dBTP |

**No claims are invented.** Every number, label, quote and severity in the film
comes from `tests/fixtures/explainer_data.json` — a real agreement run through the
real pipeline with PII anonymised.

## 2. Script

VO lines are the **on-screen words** too (the reference is word-for-word).
Words in **bold** are the italic accent words.

| Beat | Voiceover | On-screen |
| --- | --- | --- |
| 1 Hook | *Do you actually know what's in your tenancy agreement?* | same words revealing one by one; pain chips stack right: "12 months rent upfront" · "Entry without notice" · "No repairs clause" |
| 2 Meet | *Meet Ada. She found a flat, paid the agent, and got a ten-page deed.* | "Meet Ada." · "She found a flat." · "and got a ten-page deed." |
| 3 Pain | *Every clause is in legal English. Nobody explains it. And when something goes wrong, she only finds out after she has signed.* | doc fanned into clause cards; chips "Too much legalese" · "Nothing explained" · "Problems go unnoticed" |
| 4 Turn | *Ada doesn't need more jargon. She needs **one clear answer**.* | **Not more jargon.** → **One clear answer.** |
| 5 Reveal | *Meet Tenura.* | shield-check mark bloom + TENURA; pills "Upload." · "Understand." · "Know what to ask." |
| 6 Upload | *First, upload. Tenura checks it is a tenancy agreement, reads every clause, and scores the risk.* | upload panel → scan rows "Is this a tenancy agreement? ✓" · "Reading the document…" · "Scoring 10 clauses…" |
| 7 Report | *You get one clear risk score, the clauses that are risky, and the protections that are missing.* | real results screen: ring counts to **100 / High risk**, tiles **4 flagged** · **4 missing protections** · **8 questions**, "4 of 7 checked" |
| 8 Clause | *Every flag shows the exact wording, and explains it in plain English.* | clause card **Subletting — HIGH**, real quote "such consent not to be unreasonably withheld" highlighted, plain-English reason under it |
| 9 Ask | *And a ready list of questions to ask before you sign.* | real question list; cursor hovers → "Ask for a clause requiring advance written notice" expands |
| 10 Proof | *Four risky clauses. Four missing protections. Eight questions to ask.* | counters 4 · 4 · 8 counting up |
| 11 Close | *Tenura. Stop guessing. Know what you're signing.* | logo + "Stop guessing." → "Know what you're **signing**." + CTA pill `www.tenura.online` |

Word count ≈ 136 → **~63 s** at the reference's 147 wpm pacing.
Exact line lengths get re-timed against the real VO before the beat sheet is locked.

## 3. Beat sheet

| # | Time | Beat | Technique (guide §) | Reference beat it copies |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:04 | Hook over a floating agreement page; pain chips | Camera push #1, WordReveal #2, Toast/chip #8 | shot 1 (dashboard + question + chips) |
| 2 | 0:04–0:09 | Ada at the table with the deed | Cross-dissolve #10, character rise | shot 2 ("Meet Maya") |
| 3 | 0:09–0:19 | Clauses fan out around her; cards at the frame edges; push to a macro | Match-cut #4, camera #1 | shots 3–5 (icons → arc → macro) |
| 4 | 0:19–0:24 | Turn: "Not more jargon." → "One clear answer." | WordReveal #2 + turn crossfade | shot 6 |
| 5 | 0:24–0:28 | Clause cards converge → bloom → Tenura mark + pills | Match-cut morph #4, glow | shot 7 (logo reveal) |
| 6 | 0:28–0:35 | Upload → gate → scan rows | Cursor #7 + row state machine | shot 8 (connect panel) |
| 7 | 0:35–0:42 | Results screen lands, ring counts to 100, camera pushes to the flagged list | Ring #6, count-up #5, camera #1 | shot 9 (dashboard + ring) |
| 8 | 0:42–0:49 | Macro on the Subletting clause; real quote highlights; reason pops | Card #8, popover spring #7 | shot 10 (cheat-sheet popover) |
| 9 | 0:49–0:54 | Question list; hover expands one question | Cursor #7, Card #8 | shot 11 (audit → click → fixed) |
| 10 | 0:54–0:59 | Counters 4 · 4 · 8 | Count-up #5 | shots 13–14 (beads, big stats) |
| 11 | 0:59–1:03 | Logo, "Stop guessing.", CTA pill, hold ~2.5 s | LogoMark #12 | shots 15–16 |

## 4. Build

- **Engine**: Remotion 4 (React + TypeScript) for all 2D motion; ffmpeg for encode and mix.
  *No 3D needed* — the reference is entirely flat redrawn UI plus one illustration;
  the only "3D" is a CSS 3D tilt on the results card.
- **Reusable components**: `Camera`, `WordReveal`, `Caption`, `Card`, `Cursor`,
  `Ring`, `StatPill`, `Toast`, `Stepper`, `GlowBg`, `LogoMark`.
- **Brand assets pulled from the app itself**: mark = the exact inline SVG in
  `app/static/index.html` (shield + check, stroke 2.2, round caps); palette from
  `app/static/styles.css` (`--brand #0e7a52`, `--brand-dark #0a5c3e`,
  `--high #c0392b`, `--medium #b9770a`, `--low #2f6fb0`, `--rule #6d47d9`,
  ink `#10201a`, muted `#5c6f66`, line `#e2eae5`).
- **Voice**: `edge-tts` `en-US-AndrewMultilingualNeural` at `+6%`. ElevenLabs was
  the intent, but no premium TTS key exists in the project — the Rumpty endpoint
  returns HTTP 403 — so edge-tts ships. Re-checked with faster-whisper for wrong words.
- **Captions**: generated from the VO's word timestamps — never hand-keyed.
- **Master**: voice + music mixed (bed sidechain-ducked under the voice), `loudnorm` to −14 LUFS / −2 dBTP, H.264 crf 17, `+faststart`.
- **Check stills first**: 5 key frames compared side by side with the matching
  reference frames before any full render.

## 5. Assets needed / decisions

1. **Logo** — confirm the shield-check SVG in `app/static/index.html` is the final mark (and whether a proper logo/wordmark file exists).
2. **Font** — the app uses the system stack. Inter (open licence) for the film, or keep Segoe UI to match the app exactly?
3. **Data** — confirm the real anonymised fixture (`tests/fixtures/explainer_data.json`) can be shown as-is.
4. **Voice** — ElevenLabs key for the final, or is `edge-tts` good enough?
5. **Music** — synthesised bed (no licence issues), or do you have a licensed track?
6. **Context** — Nigerian specifics confirmed: "deed of lease", "caution fee", ₦ amounts?

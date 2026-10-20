import React from "react";
import {interpolate} from "remotion";
import {EASE, FPS} from "../lib";
import {BRAND, INK, SEV, STAGE, TYPE} from "../theme";
import {Card, IconAlert, IconCheck, IconFile, IconFlag, IconLock, IconSearch, Label, Pill, RingGauge, SeverityPill} from "./Ui";
import analysis from "../data/analysis.json";

export type Analysis = typeof analysis;

const A = analysis as Analysis;

/** a number that counts up with an expo-out settle */
export const countUp = (frame: number, start: number, dur: number, value: number) => {
  const p = interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return Math.round(value * p);
};

const rowState = (frame: number, active: number, done: number) =>
  frame >= done ? "done" : frame >= active ? "busy" : "idle";

/* =========================================================== upload (b06) */

export const UploadPanel: React.FC<{
  ev: (id: string) => number;
  frame: number;
  p: number;
}> = ({ev, frame, p}) => {
  const clicked = frame >= ev("clickUpload");
  const rows = [
    {t: "Is this a tenancy agreement?", ok: "Yes — tenancy agreement", a: ev("rowGate"), d: ev("gateOk")},
    {t: "Reading every clause", ok: `${A.counts.clauses} clauses found`, a: ev("rowRead"), d: ev("readDone")},
    {t: "Scoring the risk", ok: "Risk score ready", a: ev("rowScore"), d: ev("scoreDone")},
  ];
  const progress = interpolate(
    frame,
    [ev("clickUpload"), ev("scoreDone")],
    [0, 1],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE},
  );

  return (
    <Card x={270} y={158} w={1380} h={744} r={26} p={p}>
      <div style={{padding: "44px 52px", display: "flex", flexDirection: "column", height: "100%", boxSizing: "border-box"}}>
        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
          <Label>Upload agreement</Label>
          <span style={{fontSize: TYPE.micro, color: INK.muted, fontWeight: 600}}>PDF · DOCX · photo</span>
        </div>

        {/* drop zone -> uploaded file */}
        <div
          style={{
            marginTop: 26,
            height: 248,
            borderRadius: 20,
            border: `2px ${clicked ? "solid" : "dashed"} ${clicked ? INK.lineStrong : INK.lineStrong}`,
            background: INK.surface2,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 14,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {!clicked ? (
            <>
              <svg width={54} height={54} viewBox="0 0 24 24" fill="none" stroke={BRAND.green} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 16V4" />
                <path d="M7 9l5-5 5 5" />
                <path d="M4 20h16" />
              </svg>
              <div style={{fontSize: 30, fontWeight: 700, color: INK.ink}}>Drop your tenancy agreement</div>
              <div style={{fontSize: 21, color: INK.muted, fontWeight: 500}}>or choose a file — we check it is a tenancy agreement first</div>
            </>
          ) : (
            <div style={{width: "100%", padding: "0 40px", boxSizing: "border-box"}}>
              <div style={{display: "flex", alignItems: "center", gap: 18}}>
                <span style={{width: 58, height: 58, borderRadius: 14, background: BRAND.greenSoft, display: "grid", placeItems: "center"}}>
                  <IconFile size={30} color={BRAND.green} />
                </span>
                <div style={{flex: 1}}>
                  <div style={{fontSize: 27, fontWeight: 700, color: INK.ink}}>Deed_of_Lease.pdf</div>
                  <div style={{fontSize: 20, color: INK.muted, fontWeight: 500}}>412 KB · 523 words</div>
                </div>
                {frame >= ev("gateOk") ? (
                  <Pill label="TENANCY AGREEMENT" fg={BRAND.green} bg={BRAND.greenSoft} size={18} />
                ) : frame >= ev("rowGate") ? (
                  <Pill label="CHECKING…" fg={SEV.medium.fg} bg={SEV.medium.bg} size={18} />
                ) : null}
              </div>
              {/* progress */}
              <div style={{marginTop: 26, height: 10, borderRadius: 6, background: INK.line, overflow: "hidden"}}>
                <div style={{width: `${progress * 100}%`, height: "100%", background: BRAND.green, borderRadius: 6}} />
              </div>
            </div>
          )}
        </div>

        {/* scan rows */}
        <div style={{marginTop: 30, display: "flex", flexDirection: "column", gap: 14}}>
          {rows.map((r) => {
            const s = rowState(frame, r.a, r.d);
            const on = s !== "idle";
            const tone = s === "done" ? BRAND.green : s === "busy" ? SEV.medium.fg : INK.lineStrong;
            return (
              <div
                key={r.t}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  padding: "21px 24px",
                  borderRadius: 16,
                  background: s === "done" ? BRAND.greenSoft : INK.surface2,
                  border: `1px solid ${s === "done" ? "rgba(14,122,82,0.22)" : INK.line}`,
                  opacity: interpolate(on ? 1 : 0.55, [0, 1], [0.55, 1]),
                }}
              >
                <span
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 999,
                    display: "grid",
                    placeItems: "center",
                    background: s === "done" ? BRAND.green : s === "busy" ? SEV.medium.bg : INK.line,
                    color: "#fff",
                    fontSize: 19,
                    fontWeight: 800,
                  }}
                >
                  {s === "done" ? <IconCheck size={22} color="#fff" sw={3} /> : s === "busy" ? "•••" : ""}
                </span>
                <div style={{flex: 1, fontSize: 26, fontWeight: 600, color: INK.ink}}>{r.t}</div>
                <div style={{fontSize: 22, fontWeight: 600, color: s === "done" ? BRAND.green : INK.muted}}>
                  {s === "done" ? r.ok : s === "busy" ? "Working…" : "Waiting"}
                </div>
                <div style={{width: 4}} />
                <span style={{width: 12, height: 12, borderRadius: 999, background: tone, opacity: on ? 1 : 0.5}} />
              </div>
            );
          })}
        </div>

        <div style={{marginTop: "auto", paddingTop: 22, borderTop: `1px solid ${INK.line}`, display: "flex", alignItems: "center", gap: 12}}>
          <IconLock size={22} color={INK.muted} />
          <span style={{fontSize: 21, color: INK.muted, fontWeight: 500}}>
            We confirm it is a tenancy agreement before anything is analysed — other documents are politely refused.
          </span>
        </div>
      </div>
    </Card>
  );
};

/* ========================================================== report (b07) */

export const ResultsPanel: React.FC<{
  ev: (id: string) => number;
  frame: number;
  p: number;
}> = ({ev, frame, p}) => {
  const score = countUp(frame, ev("ring"), 100, A.risk_score);
  const high = A.risk_key === "high";
  const ringColor = high ? SEV.high.fg : A.risk_key === "medium" ? SEV.medium.fg : BRAND.green;
  const tiles = [
    {n: A.counts.flagged, l: "Flagged clauses", icon: <IconFlag size={26} color={SEV.high.fg} />, at: ev("tile1")},
    {n: A.counts.missing, l: "Missing protections", icon: <IconLock size={26} color={SEV.medium.fg} />, at: ev("tile2")},
    {n: A.counts.questions, l: "Questions to ask", icon: <IconSearch size={26} color={SEV.low.fg} />, at: ev("tile3")},
    {n: A.counts.checked, l: "Clauses checked", icon: <IconFile size={26} color={INK.muted} />, at: ev("tile4")},
  ];

  return (
    <Card x={250} y={140} w={1420} h={740} r={26} p={p}>
      <div style={{padding: "40px 52px", display: "flex", gap: 56, height: "100%", boxSizing: "border-box"}}>
        {/* left: risk */}
        <div style={{width: 470, display: "flex", flexDirection: "column", alignItems: "center"}}>
          <div style={{alignSelf: "flex-start"}}>
            <Label>Risk score</Label>
          </div>
          <div style={{position: "relative", marginTop: 22}}>
            <RingGauge
              value={A.risk_score}
              size={300}
              stroke={26}
              color={ringColor}
              p={interpolate(frame, [ev("ring"), ev("ring") + 100], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: EASE,
              })}
            />
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{fontSize: 92, fontWeight: 800, color: INK.ink, lineHeight: 1}}>{score}</div>
              <div style={{fontSize: 19, fontWeight: 700, letterSpacing: 1.6, color: INK.muted, marginTop: 6}}>
                OUT OF 100
              </div>
            </div>
          </div>
          <div style={{marginTop: 20}}>
            <Pill
              label={A.risk_level.toUpperCase()}
              fg={ringColor}
              bg={high ? SEV.high.bg : SEV.medium.bg}
              size={24}
            />
          </div>
          <div style={{marginTop: 14, fontSize: 21, color: INK.muted, fontWeight: 500, textAlign: "center"}}>
            {A.counts.flagged} of {A.counts.checked} checked clauses flagged
          </div>
        </div>

        <div style={{width: 1, background: INK.line}} />

        {/* right: findings */}
        <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
          <Label>What we found</Label>
          <div style={{marginTop: 18, display: "flex", flexWrap: "wrap", gap: 16}}>
            {tiles.map((t, i) => {
              const p2 = interpolate(frame, [t.at, t.at + 14], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: EASE,
              });
              return (
                <div
                  key={t.l}
                  style={{
                    flex: "0 0 calc(50% - 8px)",
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    padding: "20px 22px",
                    borderRadius: 16,
                    background: INK.surface2,
                    border: `1px solid ${INK.line}`,
                    opacity: p2,
                    transform: `translateY(${(1 - p2) * 14}px)`,
                  }}
                >
                  <span style={{width: 46, height: 46, borderRadius: 12, background: "#fff", border: `1px solid ${INK.line}`, display: "grid", placeItems: "center"}}>
                    {t.icon}
                  </span>
                  <div>
                    <div style={{fontSize: 40, fontWeight: 800, color: INK.ink, lineHeight: 1}}>
                      {countUp(frame, t.at, 26, t.n)}
                    </div>
                    <div style={{fontSize: 20, fontWeight: 600, color: INK.muted, marginTop: 4}}>{t.l}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{marginTop: 26}}>
            <Label>Flagged clauses</Label>
          </div>
          <div style={{marginTop: 14, display: "flex", flexDirection: "column", gap: 10}}>
            {A.flagged.map((fl, i) => {
              const at = ev(`row${i + 1}`);
              const p2 = interpolate(frame, [at, at + 12], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: EASE,
              });
              return (
                <div
                  key={fl.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    padding: "12px 20px",
                    borderRadius: 12,
                    background: "#fff",
                    border: `1px solid ${INK.line}`,
                    opacity: p2,
                    transform: `translateX(${(1 - p2) * 18}px)`,
                  }}
                >
                  <span style={{width: 5, height: 30, borderRadius: 3, background: SEV[fl.severity as "high" | "medium" | "low"].fg}} />
                  <div style={{flex: 1, fontSize: 25, fontWeight: 600, color: INK.ink}}>{fl.label}</div>
                  <SeverityPill sev={fl.severity as "high" | "medium" | "low"} size={18} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
};

/* ========================================================== clause (b08) */

export const ClauseCard: React.FC<{
  ev: (id: string) => number;
  frame: number;
  p: number;
}> = ({ev, frame, p}) => {
  const clause =
    A.flagged.find((f) => f.reason && A.quote && f.evidence.includes(A.quote)) ??
    A.flagged.find((f) => f.reason) ??
    A.flagged[2];
  const quote = A.quote && clause.evidence.includes(A.quote) ? A.quote : clause.evidence;
  const sev = clause.severity as "high" | "medium" | "low";
  const col = SEV[sev].fg;
  const hl = interpolate(frame, [ev("quote"), ev("quote") + 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const rp = interpolate(frame, [ev("reason"), ev("reason") + 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const isRule = clause.source === "rule";
  const srcFg = isRule ? SEV.rule.fg : SEV.ai.fg;
  const srcBg = isRule ? SEV.rule.bg : SEV.ai.bg;

  return (
    <Card x={360} y={176} w={1200} h={664} r={28} p={p}>
      <div style={{position: "absolute", left: 0, top: 0, bottom: 0, width: 9, background: col, borderTopLeftRadius: 28, borderBottomLeftRadius: 28}} />
      <div style={{padding: "50px 62px 0 70px", position: "relative"}}>
        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
          <Label>Flagged clause</Label>
          <SeverityPill sev={sev} size={21} />
        </div>
        <div style={{marginTop: 16, fontSize: 50, fontWeight: 800, color: INK.ink, letterSpacing: -1.2}}>
          {clause.label}
        </div>

        {/* exact wording */}
        <div
          style={{
            marginTop: 32,
            padding: "26px 34px",
            borderRadius: 18,
            background: INK.surface2,
            borderLeft: `7px solid ${col}`,
            position: "relative",
          }}
        >
          <Label>Exact wording</Label>
          <div style={{marginTop: 12, fontSize: 37, fontWeight: 600, color: INK.soft, lineHeight: 1.34}}>
            <span
              style={{
                backgroundImage: "linear-gradient(90deg, rgba(14,122,82,0.22), rgba(14,122,82,0.22))",
                backgroundRepeat: "no-repeat",
                backgroundSize: `${hl * 100}% 100%`,
                WebkitBoxDecorationBreak: "clone",
                boxDecorationBreak: "clone",
                borderRadius: 3,
              }}
            >
              &ldquo;{quote}&rdquo;
            </span>
          </div>
        </div>

        {/* plain english */}
        <div style={{marginTop: 32, opacity: rp, transform: `translateY(${(1 - rp) * 14}px)`}}>
          <div style={{display: "flex", alignItems: "center", gap: 10}}>
            <IconAlert size={23} color={col} />
            <Label color={col}>In plain English</Label>
          </div>
          <div style={{marginTop: 14, fontSize: 30, lineHeight: 1.44, color: INK.soft, fontWeight: 500}}>
            {clause.reason}
          </div>
        </div>

        {/* provenance */}
        <div style={{marginTop: 34, display: "flex", alignItems: "center", gap: 14, opacity: rp}}>
          <Label>How it was flagged</Label>
          <Pill
            label={isRule ? "RULE · CLAUSE LIBRARY" : "AI REVIEW"}
            fg={srcFg}
            bg={srcBg}
            size={18}
          />
        </div>
      </div>
    </Card>
  );
};

/* ======================================================= questions (b09) */

export const QuestionsPanel: React.FC<{
  ev: (id: string) => number;
  frame: number;
  p: number;
}> = ({ev, frame, p}) => {
  const qs = A.questions.slice(0, 4);
  const expandAt = ev("expand");
  const openIdx = 1;
  const expandP = interpolate(frame, [expandAt, expandAt + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  return (
    <Card x={420} y={170} w={1080} h={660} r={26} p={p}>
      <div style={{padding: "42px 52px"}}>
        <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
          <Label>Questions to ask</Label>
          <Pill label={`${A.counts.questions} QUESTIONS`} fg={BRAND.green} bg={BRAND.greenSoft} size={18} />
        </div>
        <div style={{marginTop: 22, display: "flex", flexDirection: "column", gap: 12}}>
          {qs.map((q, i) => {
            const at = ev(`q${i + 1}`);
            const p2 = interpolate(frame, [at, at + 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: EASE,
            });
            const open = i === openIdx;
            const o = open ? expandP : 0;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 18,
                  alignItems: "flex-start",
                  padding: "18px 22px",
                  borderRadius: 16,
                  background: open ? BRAND.greenSoft : "#fff",
                  border: `1px solid ${open ? "rgba(14,122,82,0.35)" : INK.line}`,
                  boxShadow: open ? `0 10px 30px rgba(14,122,82,${0.10 * o})` : "none",
                  opacity: p2,
                  transform: `translateY(${(1 - p2) * 14}px)`,
                }}
              >
                <span
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 999,
                    flex: "0 0 auto",
                    display: "grid",
                    placeItems: "center",
                    background: open ? BRAND.green : INK.line,
                    color: open ? "#fff" : INK.muted,
                    fontSize: 17,
                    fontWeight: 800,
                  }}
                >
                  {open && o > 0.6 ? <IconCheck size={19} color="#fff" sw={3} /> : i + 1}
                </span>
                <div style={{flex: 1, fontSize: 25, lineHeight: 1.34, fontWeight: 600, color: INK.ink}}>{q}</div>
                {open ? (
                  <span
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      letterSpacing: 1.2,
                      color: BRAND.green,
                      opacity: o,
                      paddingTop: 8,
                    }}
                  >
                    READY TO SEND
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
        <div style={{marginTop: 20, fontSize: 21, color: INK.muted, fontWeight: 500, opacity: expandP}}>
          Written in plain language — take them straight to your landlord or agent.
        </div>
      </div>
    </Card>
  );
};

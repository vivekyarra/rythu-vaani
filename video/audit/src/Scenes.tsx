import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, FPS } from "./theme";
import T from "./timeline.json";

type TL = typeof T;
const ease = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { easing: Easing.out(Easing.exp), extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const blurIn = (f: number, a: number, d = 6) => ({
  opacity: interpolate(f, [a, a + d], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  filter: `blur(${interpolate(f, [a, a + d], [8, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px)`,
});

const useV = () => {
  const { width, height } = useVideoConfig();
  return { vertical: height > width, w: width, h: height };
};

/* ---------------- Hook: the real call audio plays from frame 0 ---------------- */
export const Hook: React.FC<{ d: TL["hook"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  const bars = d.wave;
  const played = f / (d.clipSec * FPS);
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, padding: vertical ? "160px 70px" : "90px 140px", color: C.ink }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: vertical ? 34 : 30, fontWeight: 700, color: C.ink2, ...blurIn(f, 0, 4) }}>
        <div style={{ width: 18, height: 18, borderRadius: 9, background: C.critical }} />
        RECORDED COLLECTION CALL · {d.time} · {d.language}
        <span style={{ fontSize: 22, fontWeight: 700, padding: "4px 12px", borderRadius: 999, border: `2px solid ${C.line}`, color: C.ink3 }}>SYNTHETIC</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 5, height: 150, marginTop: 40 }}>
        {bars.map((b: number, i: number) => (
          <div key={i} style={{ flex: 1, height: `${Math.max(6, b * 100)}%`, borderRadius: 3,
            background: i / bars.length < played ? C.critical : C.line }} />
        ))}
      </div>
      <div style={{ marginTop: 50, fontSize: vertical ? 58 : 46, fontWeight: 500, color: C.ink2, ...blurIn(f, 3, 6) }}>{d.native}</div>
      <div style={{ marginTop: 18, fontSize: vertical ? 74 : 66, fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.02em", ...blurIn(f, 6, 6) }}>
        “{d.english}”
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 44, flexWrap: "wrap" }}>
        {d.stamps.map((s: string, i: number) => {
          const a = d.stampAt * FPS + i * 6;
          return (
            <div key={s} style={{ fontSize: vertical ? 38 : 34, fontWeight: 800, color: C.critical, background: C.criticalSoft,
              border: `3px solid ${C.critical}`, borderRadius: 12, padding: "10px 22px",
              opacity: ease(f, a, a + 8), transform: `scale(${interpolate(ease(f, a, a + 8), [0, 1], [1.25, 1])})` }}>✕ {s}</div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: vertical ? 70 : 140, right: vertical ? 70 : 140, bottom: vertical ? 420 : 150, fontSize: vertical ? 60 : 56,
        fontWeight: 800, letterSpacing: "-0.02em", ...blurIn(f, d.punchAt * FPS, 8) }}>
        {d.punch}
      </div>
    </AbsoluteFill>
  );
};

/* ---------------- Problem: 1-2% audited + the RBI checklist ---------------- */
export const Problem: React.FC<{ d: TL["problem"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  const dots = Array.from({ length: 100 });
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, color: C.ink, padding: vertical ? "150px 70px" : "90px 140px",
      display: "flex", flexDirection: vertical ? "column" : "row", gap: vertical ? 60 : 110 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: vertical ? 64 : 60, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.1, ...blurIn(f, 0, 6) }}>
          Compliance teams hear <span style={{ color: C.critical, whiteSpace: "nowrap" }}>1–2%</span> of collection calls.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(20, 1fr)", gap: 10, marginTop: 50, width: vertical ? "100%" : 640 }}>
          {dots.map((_, i) => {
            const on = i < 2;
            const a = 8 + i * 0.35;
            return <div key={i} style={{ aspectRatio: "1", borderRadius: "50%", background: on ? C.brand : C.line, opacity: ease(f, a, a + 6) }} />;
          })}
        </div>
        <div style={{ marginTop: 26, fontSize: 30, color: C.ink2, fontWeight: 600, ...blurIn(f, 50, 6) }}>
          The rest, in Hindi, Telugu and code-mixed speech on noisy lines, is never checked.
        </div>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: C.ink3, letterSpacing: "0.06em", ...blurIn(f, d.listAt * FPS, 5) }}>RBI FAIR-PRACTICES RULES FOR RECOVERY CALLS</div>
        {d.rules.map((r: string, i: number) => {
          const a = (d.listAt + 0.9 + i * d.listStep) * FPS;
          return (
            <div key={r} style={{ display: "flex", gap: 18, alignItems: "center", padding: "16px 0", borderBottom: `2px solid ${C.line}`,
              fontSize: vertical ? 40 : 36, fontWeight: 600, opacity: ease(f, a, a + 10), transform: `translateX(${(1 - ease(f, a, a + 10)) * 30}px)` }}>
              <div style={{ width: 40, height: 40, borderRadius: 20, background: C.brandSoft, color: C.brandInk, display: "grid", placeItems: "center", fontSize: 24, fontWeight: 800 }}>{i + 1}</div>
              {r}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ---------------- Title ---------------- */
export const Title: React.FC<{ d: TL["title"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  return (
    <AbsoluteFill style={{ background: C.brand, fontFamily: FONT, color: "#fff", justifyContent: "center", padding: vertical ? 70 : 140 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 28, ...blurIn(f, 0, 6) }}>
        <svg width={vertical ? 110 : 120} height={vertical ? 110 : 120} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round">
          <path d="M4 10v4M8 6v12M12 9v6M16 4v16M20 10v4" />
        </svg>
        <div style={{ fontSize: vertical ? 120 : 140, fontWeight: 800, letterSpacing: "-0.04em" }}>Vaani Audit</div>
      </div>
      <div style={{ fontSize: vertical ? 52 : 54, fontWeight: 600, marginTop: 30, lineHeight: 1.2, ...blurIn(f, 8, 6) }}>{d.tagline}</div>
      <div style={{ fontSize: vertical ? 36 : 34, fontWeight: 600, marginTop: 30, opacity: 0.85, ...blurIn(f, 16, 6) }}>{d.sub}</div>
    </AbsoluteFill>
  );
};

/* ---------------- Demo: the real screen recording ---------------- */
export const Demo: React.FC<{ startFrom: number; label: string; crop?: { x: number; y: number; scale: number }; note?: string }> = ({ startFrom, label, crop, note }) => {
  const { vertical } = useV();
  const f = useCurrentFrame();
  const video = (
    <OffthreadVideo src={staticFile("demo_screen.mp4")} startFrom={startFrom} muted
      style={vertical ? { width: 1920 * (crop?.scale ?? 1), height: 1080 * (crop?.scale ?? 1), position: "absolute",
        left: -(crop?.x ?? 0) * (crop?.scale ?? 1), top: -(crop?.y ?? 0) * (crop?.scale ?? 1) } : { width: "100%", height: "100%" }} />
  );
  return (
    <AbsoluteFill style={{ background: vertical ? C.bg : "#000", fontFamily: FONT }}>
      {vertical ? (
        <>
          <div style={{ position: "absolute", top: 250, left: 60, right: 60, fontSize: 54, fontWeight: 800, color: C.ink, lineHeight: 1.1, letterSpacing: "-0.02em" }}>
            Every violation, with the exact quote and the second it happened.
          </div>
          <div style={{ position: "absolute", top: 480, left: 0, width: 1080, height: 1080 * (crop?.scale ?? 1), overflow: "hidden", background: C.surface,
            borderTop: `2px solid ${C.line}`, borderBottom: `2px solid ${C.line}` }}>{video}</div>
        </>
      ) : video}
      <div style={{ position: "absolute", top: vertical ? 150 : 22, right: vertical ? undefined : 24, left: vertical ? 60 : undefined,
        background: "rgba(11,11,11,0.82)", color: "#fff", fontSize: vertical ? 30 : 22, fontWeight: 700, padding: "8px 16px", borderRadius: 10,
        display: "flex", gap: 10, alignItems: "center", opacity: interpolate(f, [0, 6], [0, 1], { extrapolateRight: "clamp" }) }}>
        <div style={{ width: 12, height: 12, borderRadius: 6, background: "#0ca30c" }} />{label}
      </div>
      {note && (
        <div style={{ position: "absolute", top: vertical ? 1420 : 80, right: vertical ? undefined : 24, left: vertical ? 60 : undefined,
          background: C.warn, color: C.ink, fontSize: vertical ? 30 : 22, fontWeight: 800, padding: "8px 16px", borderRadius: 10,
          opacity: interpolate(f, [0, 6, 75, 90], [0, 1, 1, 0], { extrapolateRight: "clamp" }) }}>{note}</div>
      )}
    </AbsoluteFill>
  );
};

/* ---------------- Architecture ---------------- */
export const Architecture: React.FC<{ d: TL["arch"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, color: C.ink, padding: vertical ? "150px 60px" : "80px 110px 170px", justifyContent: vertical ? undefined : "center" }}>
      <div style={{ fontSize: vertical ? 60 : 64, fontWeight: 800, letterSpacing: "-0.02em", ...blurIn(f, 0, 6) }}>How it works</div>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", gap: vertical ? 22 : 18, marginTop: vertical ? 50 : 90, alignItems: "stretch" }}>
        {d.boxes.map((b: { t: string; s: string; gnani: boolean }, i: number) => {
          const a = (d.boxAt[i] ?? i * 2) * FPS;
          return (
            <React.Fragment key={b.t}>
              {i > 0 && <div style={{ alignSelf: "center", fontSize: 40, color: C.ink3, opacity: ease(f, a - 4, a + 4) }}>{vertical ? "↓" : "→"}</div>}
              <div style={{ flex: 1, background: b.gnani ? C.brand : C.surface, color: b.gnani ? "#fff" : C.ink, border: `2px solid ${b.gnani ? C.brand : C.line}`,
                borderRadius: 18, padding: vertical ? "22px 28px" : "34px 26px", minHeight: vertical ? undefined : 330, opacity: ease(f, a, a + 12), transform: `translateY(${(1 - ease(f, a, a + 12)) * 24}px)` }}>
                <div style={{ fontSize: vertical ? 38 : 36, fontWeight: 800, lineHeight: 1.15 }}>{b.t}</div>
                <div style={{ fontSize: vertical ? 28 : 27, fontWeight: 500, marginTop: 10, lineHeight: 1.35, opacity: 0.9, whiteSpace: "pre-line" }}>{b.s}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ marginTop: vertical ? 40 : 54, fontSize: vertical ? 32 : 28, color: C.ink2, fontWeight: 600, lineHeight: 1.4, ...blurIn(f, d.noteAt * FPS, 6) }}>{d.note}</div>
    </AbsoluteFill>
  );
};

/* ---------------- Results: measured numbers only ---------------- */
export const Results: React.FC<{ d: TL["results"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  const maxW = vertical ? 560 : 520;
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, color: C.ink, padding: vertical ? "140px 60px" : "70px 110px" }}>
      <div style={{ fontSize: vertical ? 56 : 50, fontWeight: 800, letterSpacing: "-0.02em", ...blurIn(f, 0, 6) }}>{d.title}</div>
      <div style={{ fontSize: vertical ? 28 : 26, color: C.ink2, fontWeight: 600, marginTop: 10, ...blurIn(f, 4, 6) }}>{d.subtitle}</div>
      <div style={{ display: "flex", flexDirection: vertical ? "column" : "row", gap: vertical ? 40 : 90, marginTop: 40 }}>
        <div style={{ flex: 1.1 }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: C.ink3, letterSpacing: "0.05em", marginBottom: 14 }}>{d.chartLabel}</div>
          {d.rows.map((r: { cond: string; vals: { sys: string; v: number | null; label: string }[] }, i: number) => {
            const a = (d.rowsAt + i * 0.6) * FPS;
            return (
              <div key={r.cond} style={{ marginBottom: 20, opacity: ease(f, a, a + 8) }}>
                <div style={{ fontSize: vertical ? 30 : 26, fontWeight: 700, marginBottom: 6 }}>{r.cond}</div>
                {r.vals.map((v, k) => (
                  <div key={v.sys} style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
                    <div style={{ width: vertical ? 200 : 180, fontSize: vertical ? 24 : 21, color: C.ink2, fontWeight: 600 }}>{v.sys}</div>
                    <div style={{ height: 26, width: maxW * (v.v ?? 0) * ease(f, a + 4, a + 22), background: k === r.vals.length - 1 ? C.brand : "#86b6ef",
                      borderRadius: "0 4px 4px 0", minWidth: 3 }} />
                    <div style={{ fontSize: vertical ? 26 : 23, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{v.label}</div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <div style={{ flex: 1 }}>
          {d.facts.map((x: { big: string; small: string }, i: number) => {
            const a = (d.factsAt + i * 1.2) * FPS;
            return (
              <div key={x.small} style={{ padding: "16px 0", borderBottom: `2px solid ${C.line}`, ...blurIn(f, a, 6) }}>
                <div style={{ fontSize: vertical ? 50 : 44, fontWeight: 800, letterSpacing: "-0.02em" }}>{x.big}</div>
                <div style={{ fontSize: vertical ? 26 : 22, color: C.ink2, fontWeight: 600, lineHeight: 1.35 }}>{x.small}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ---------------- Close ---------------- */
export const Close: React.FC<{ d: TL["close"] }> = ({ d }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  return (
    <AbsoluteFill style={{ background: C.ink, fontFamily: FONT, color: "#fff", padding: vertical ? "200px 70px" : "100px 140px", justifyContent: "center" }}>
      <div style={{ fontSize: vertical ? 80 : 84, fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.08, ...blurIn(f, 0, 6) }}>{d.line}</div>
      <div style={{ marginTop: 40, fontSize: vertical ? 34 : 32, lineHeight: 1.5, color: "#c3c2b7", fontWeight: 500, whiteSpace: "pre-line", ...blurIn(f, 10, 6) }}>{d.limits}</div>
      <div style={{ marginTop: 50, fontSize: vertical ? 36 : 34, fontWeight: 700, ...blurIn(f, 18, 6) }}>{d.credit}</div>
      <div style={{ marginTop: 12, fontSize: vertical ? 30 : 28, fontWeight: 600, color: "#86b6ef", ...blurIn(f, 22, 6) }}>{d.url}</div>
    </AbsoluteFill>
  );
};

/* ---------------- Captions (English, throughout) ---------------- */
export const Captions: React.FC<{ items: TL["captions"] }> = ({ items }) => {
  const f = useCurrentFrame();
  const { vertical } = useV();
  const cur = items.find((c) => f >= c.from && f < c.to);
  if (!cur) return null;
  const a = interpolate(f, [cur.from, cur.from + 4], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: vertical ? 50 : 200, right: vertical ? 50 : 200, bottom: vertical ? 170 : 42, display: "flex", justifyContent: "center", opacity: a }}>
      <div style={{ background: "rgba(11,11,11,0.86)", color: "#fff", fontFamily: FONT, borderRadius: 14, padding: vertical ? "18px 28px" : "12px 26px",
        fontSize: vertical ? 42 : 36, fontWeight: 600, lineHeight: 1.3, textAlign: "center", maxWidth: vertical ? 980 : 1500 }}>
        {cur.label && <span style={{ color: cur.label.startsWith("Agent") ? "#ff9b9b" : cur.label.startsWith("Timbre") ? "#7be07b" : "#9ec5f4", fontWeight: 800 }}>{cur.label}: </span>}
        {cur.text}
      </div>
    </div>
  );
};

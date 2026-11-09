import React from "react";
import { AbsoluteFill, Easing, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { Words } from "./Words";
import { BODY, C, DISPLAY } from "./theme";

// Real numbers: held-out set, 2026-11-02 run (README Results / results/benchmark_*heldout*).
const CONDS = ["clean", "phone", "20 dB", "10 dB", "5 dB", "0 dB"];
const V25 = [10, 9, 9, 9, 9, 6];
const V3 = [10, 10, 10, 10, 10, 10];

export const Benchmark: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chartTop = 560, chartH = 760, base = chartTop + chartH, groupW = 160, left = 60;
  const focus = interpolate(frame, [Math.round(3.2 * fps), Math.round(3.8 * fps)], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const bar = (v: number, i: number, k: number, color: string) => {
    const s = spring({ frame: frame - 12 - i * 3 - k * 2, fps, config: { damping: 16, stiffness: 100 } });
    const h = (v / 10) * chartH * s;
    const x = left + i * groupW + 22 + k * 62;
    const dim = i === 5 ? 1 : 1 - focus * 0.7;
    return (
      <g key={`${i}-${k}`} opacity={dim}>
        <rect x={x} y={base - h} width={56} height={h} rx={8} fill={color} />
        <text x={x + 28} y={base - h - 16} textAnchor="middle" fontFamily={DISPLAY} fontSize={34}
          fill={C.paper} opacity={s}>{v}</text>
      </g>
    );
  };
  return (
    <AbsoluteFill style={{ backgroundColor: "#1b1410" }}>
      <div style={{ position: "absolute", top: 150, width: "100%", textAlign: "center", padding: "0 60px",
        fontFamily: DISPLAY, fontSize: 84, color: C.paper, lineHeight: 1.1 }}>
        <Words text="So… can it?" stagger={3} />
      </div>
      <div style={{ position: "absolute", top: 400, width: "100%", textAlign: "center", fontFamily: BODY,
        fontWeight: 700, fontSize: 36, color: "rgba(255,248,236,.75)" }}>
        10 unseen Telugu questions · 8 kHz phone line + noise
      </div>
      <svg width={1080} height={1920} style={{ position: "absolute" }}>
        {CONDS.map((c, i) => (
          <g key={c}>
            {bar(V25[i], i, 0, C.chilli)}
            {bar(V3[i], i, 1, "#3fbf7f")}
            <text x={left + i * groupW + 81} y={base + 52} textAnchor="middle" fontFamily={BODY} fontWeight={800}
              fontSize={32} fill={i === 5 ? C.turmeric : C.paper} opacity={i === 5 ? 1 : 1 - focus * 0.6}>{c}</text>
          </g>
        ))}
        <line x1={50} x2={1030} y1={base} y2={base} stroke="rgba(255,248,236,.35)" strokeWidth={3} />
      </svg>
      <div style={{ position: "absolute", top: base + 100, width: "100%", display: "flex", justifyContent: "center",
        gap: 40, fontFamily: BODY, fontWeight: 800, fontSize: 32, color: C.paper }}>
        <span><span style={{ color: C.chilli }}>■</span> Prisma v2.5</span>
        <span><span style={{ color: "#3fbf7f" }}>■</span> Prisma v3.0 + keyterms</span>
      </div>
      <Sequence from={Math.round(3.6 * fps)} layout="none">
        <div style={{ position: "absolute", top: base + 190, width: "100%", textAlign: "center",
          fontFamily: DISPLAY, fontSize: 92, color: "#3fbf7f" }}>
          <Words text="0 dB: 6/10 → 10/10" stagger={3} punch />
        </div>
        <Audio src={staticFile("ding.wav")} volume={0.5} />
      </Sequence>
      <div style={{ position: "absolute", bottom: 40, width: "100%", textAlign: "center", fontFamily: BODY,
        fontWeight: 500, fontSize: 26, color: "rgba(255,248,236,.6)" }}>
        Real Gnani API run, 2 Nov 2026 · intent + details correct
      </div>
    </AbsoluteFill>
  );
};

export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const letters = "Rythu Vaani".split("");
  return (
    <AbsoluteFill style={{ backgroundColor: C.chilli, justifyContent: "center", alignItems: "center", color: C.paper }}>
      <div style={{ fontFamily: DISPLAY, fontSize: 150, display: "flex" }}>
        {letters.map((l, i) => {
          const t = interpolate(frame - i * 2, [0, 6], [0.25, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <span key={i} style={{ opacity: t, filter: `blur(${(1 - t) * 5}px)`, whiteSpace: "pre" }}>{l}</span>;
        })}
      </div>
      <Sequence from={10} layout="none">
        <div style={{ marginTop: 20, fontFamily: BODY, fontWeight: 800, fontSize: 50, textAlign: "center" }}>
          <Words text="A Telugu voice helpline for farmers" stagger={2} />
        </div>
      </Sequence>
      <Sequence from={22} layout="none">
        <div style={{ marginTop: 70, fontFamily: BODY, fontWeight: 700, fontSize: 40, textAlign: "center", lineHeight: 1.6 }}>
          <Words text="Built solo in Guntur" stagger={2} />
          <Words text="on Gnani Prisma + Timbre" stagger={2} highlight={["Prisma", "Timbre"]} highlightColor={C.turmeric} />
        </div>
      </Sequence>
      <Sequence from={34} layout="none">
        <div style={{ marginTop: 70, fontFamily: BODY, fontWeight: 800, fontSize: 40, background: C.ink,
          padding: "16px 30px", borderRadius: 16 }}>github.com/vivekyarra/rythu-vaani</div>
        <div style={{ marginTop: 50, fontFamily: BODY, fontWeight: 800, fontSize: 34, textAlign: "center", lineHeight: 1.5 }}>
          #GreatIndianAIInternshipChallenge<br />#GnaniAI
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};

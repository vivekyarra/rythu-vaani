import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Words } from "./Words";
import { BODY, C, DISPLAY } from "./theme";

const STEPS = [
  { k: "Caller", t: "Speaks Telugu or Telugu + English", c: C.paper },
  { k: "Gnani Prisma v3.0", t: "Speech → text, primed with farm keyterms", c: "#3fbf7f" },
  { k: "Telugu parser", t: "Finds crop, market, acres, tenant status", c: C.turmeric },
  { k: "Gnani Timbre", t: "Speaks the answer back in Telugu", c: "#3fbf7f" },
];

// Pipeline: each step lands 9 frames after the previous one; the connector draws as it lands.
export const HowItWorks: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: "#1b1410", alignItems: "center", paddingTop: 170 }}>
      <div style={{ fontFamily: DISPLAY, fontSize: 84, color: C.paper, textAlign: "center", lineHeight: 1.1 }}>
        <Words text="How it works" stagger={3} />
      </div>
      <div style={{ marginTop: 90, display: "flex", flexDirection: "column", alignItems: "center", width: 900 }}>
        {STEPS.map((s, i) => {
          const t = interpolate(frame - 8 - i * 9, [0, 10], [0, 1], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.exp) });
          const line = interpolate(frame - 14 - i * 9, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <React.Fragment key={s.k}>
              <div style={{ width: "100%", opacity: t, filter: `blur(${(1 - t) * 8}px)`, borderRadius: 26,
                border: `3px solid ${s.c}`, padding: "30px 36px", background: "rgba(255,248,236,0.04)" }}>
                <div style={{ fontFamily: DISPLAY, fontSize: 54, color: s.c }}>{s.k}</div>
                <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 38, color: C.paper, marginTop: 6 }}>{s.t}</div>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{ width: 6, height: 70, background: "rgba(255,248,236,.5)", scale: `1 ${line}`,
                  transformOrigin: "top" }} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

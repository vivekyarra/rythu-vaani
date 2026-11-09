import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";
import { ChilliField } from "./Chillies";
import { Words } from "./Words";
import { C, DISPLAY, rand } from "./theme";

// A broken phone-line waveform: jagged, with dropouts that move every frame.
const BrokenWave: React.FC = () => {
  const frame = useCurrentFrame();
  const pts: string[] = [];
  const segs: React.ReactNode[] = [];
  let cur: string[] = [];
  for (let i = 0; i <= 90; i++) {
    const x = (i / 90) * 1080;
    const drop = rand(frame * 0.37 + Math.floor(i / 6) * 1.3) < 0.28;
    const amp = 40 + 160 * rand(frame * 1.7 + i * 0.9);
    const y = 1500 + Math.sin(i * 0.9 + frame * 0.8) * amp * (i % 2 ? 1 : -1) * 0.6;
    if (drop) {
      if (cur.length > 1) segs.push(<polyline key={i} points={cur.join(" ")} />);
      cur = [];
    } else cur.push(`${x},${y}`);
    pts.push(`${x},${y}`);
  }
  if (cur.length > 1) segs.push(<polyline key="last" points={cur.join(" ")} />);
  return (
    <svg width={1080} height={1920} style={{ position: "absolute" }}>
      <g fill="none" stroke={C.turmeric} strokeWidth={7} strokeLinejoin="round" opacity={0.9}>
        {segs}
      </g>
    </svg>
  );
};

// TV/phone static that fades as the hook settles.
const Static: React.FC = () => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 70, 95], [0.42, 0.22, 0.12], { extrapolateRight: "clamp" });
  return (
    <svg width={1080} height={1920} style={{ position: "absolute", opacity: o, mixBlendMode: "screen" }}>
      <filter id="n">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={frame % 97} />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="1080" height="1920" filter="url(#n)" />
    </svg>
  );
};

const HookText: React.FC = () => {
  const frame = useCurrentFrame();
  // glitch: on a few frames the text splits into red/cyan copies and jumps
  const glitch = [9, 10, 23, 41, 42, 63].includes(frame);
  const jx = glitch ? (rand(frame) - 0.5) * 30 : 0;
  const block = (dx: number, color?: string, blend?: React.CSSProperties["mixBlendMode"]) => (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 70px",
        translate: `${jx + dx}px 0px`,
        color: color ?? C.paper,
        mixBlendMode: blend,
        opacity: color ? 0.8 : 1,
      }}
    >
      <div style={{ fontFamily: DISPLAY, fontSize: 104, lineHeight: 1.08, textAlign: "center", marginTop: -260,
        textShadow: color ? "none" : "0 6px 30px rgba(0,0,0,.55)" }}>
        <Words text="Can AI understand" start={-12} stagger={3} punch />
        <Words text="a Telugu farmer…" start={14} stagger={3} punch highlight={["Telugu"]} highlightColor={color ?? C.turmeric} />
        <Sequence from={30} layout="none">
          <Words text="on a TERRIBLE phone line?" start={0} stagger={4} punch highlight={["TERRIBLE"]}
            highlightColor={color ?? C.turmeric} style={{ fontSize: 112 }} />
        </Sequence>
      </div>
    </AbsoluteFill>
  );
  return (
    <>
      {glitch && block(-10, "#ff2a2a", "screen")}
      {glitch && block(10, "#2af0ff", "screen")}
      {block(0)}
    </>
  );
};

export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shake = frame < 70 ? (rand(frame * 3.3) - 0.5) * 10 : 0;
  return (
    <AbsoluteFill style={{ backgroundColor: C.chilliDark, overflow: "hidden" }}>
      <AbsoluteFill style={{ translate: `${shake}px ${-shake}px`,
        scale: String(interpolate(frame, [0, 100], [1.18, 1.05], { extrapolateRight: "clamp" })) }}>
        <svg width={1080} height={1920}>
          <ChilliField count={420} w={1180} h={2020} seed={11} scale={1.5} />
        </svg>
        <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(40,6,4,.55) 0%, rgba(40,6,4,.25) 45%, rgba(40,6,4,.6) 100%)" }} />
      </AbsoluteFill>
      <BrokenWave />
      <Static />
      <HookText />
      <Audio src={staticFile("static.wav")} volume={0.35} />
      <Sequence from={Math.round(2.9 * fps)} layout="none">
        <Audio src={staticFile("whoosh.wav")} volume={0.8} />
      </Sequence>
    </AbsoluteFill>
  );
};

import React from "react";
import { AbsoluteFill, Easing, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { ChilliField } from "./Chillies";
import { Caption } from "./Caption";
import { C, DISPLAY, rand } from "./theme";

const ease = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) } as const;

// Silhouette of a woman farmer in a saree, side-on, facing right. The arm raises the phone to her ear.
const Farmer: React.FC<{ raise: number; ring: number }> = ({ raise, ring }) => {
  const upper = interpolate(raise, [0, 1], [4, -20]); // shoulder angle
  const fore = interpolate(raise, [0, 1], [6, -158]); // elbow angle, relative
  const ink = "#2a160d";
  return (
    <g transform="translate(430 0)">
      {/* saree body */}
      <path d="M-62 960 C -78 1060, -92 1230, -118 1430 L 120 1430 C 96 1250, 70 1080, 58 960 Z" fill={ink} />
      {/* pallu over the left shoulder, flowing back */}
      <path d="M40 930 C 0 980, -70 1020, -140 1130 C -170 1180, -190 1230, -205 1290 C -150 1220, -90 1160, -40 1110 C 0 1060, 30 1010, 58 960 Z" fill={ink} />
      {/* torso / blouse */}
      <path d="M-50 900 C -66 930, -66 970, -62 990 L 60 990 C 64 960, 60 925, 46 900 Z" fill={ink} />
      {/* neck + head + bun */}
      <rect x={-12} y={858} width={26} height={50} rx={10} fill={ink} />
      <ellipse cx={4} cy={820} rx={44} ry={52} fill={ink} />
      <path d="M44 818 L 58 828 L 44 836 Z" fill={ink} />
      <circle cx={-40} cy={808} r={26} fill={ink} />
      {/* earring glint */}
      <circle cx={8} cy={850} r={4} fill={C.turmeric} />
      {/* arm: upper arm then forearm, phone in hand */}
      <g transform={`translate(30 920) rotate(${upper})`}>
        <rect x={-14} y={0} width={28} height={118} rx={14} fill={ink} />
        <g transform={`translate(0 112) rotate(${fore})`}>
          <rect x={-12} y={0} width={24} height={108} rx={12} fill={ink} />
          <g transform="translate(-14 96)">
            <rect x={0} y={0} width={30} height={56} rx={6} fill="#111" stroke={C.turmeric} strokeWidth={2} />
            <rect x={5} y={6} width={20} height={16} rx={2} fill={ring > 0 ? "#9be7a1" : "#3a3a3a"} />
          </g>
        </g>
      </g>
      {/* ring waves near the ear */}
      {ring > 0 &&
        [0, 1, 2].map((i) => {
          const p = (ring + i / 3) % 1;
          return (
            <circle key={i} cx={70} cy={815} r={30 + p * 110} fill="none" stroke={C.turmeric}
              strokeWidth={6} opacity={(1 - p) * 0.9} />
          );
        })}
    </g>
  );
};

// Slot-machine price that never settles: the question she can't answer yet.
const RollingPrice: React.FC = () => {
  const frame = useCurrentFrame();
  const d = (k: number) => Math.floor(rand(Math.floor(frame / 2) * 7 + k) * 10);
  const enter = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.exp) });
  return (
    <div style={{ position: "absolute", top: 230, width: "100%", textAlign: "center", opacity: enter,
      filter: `blur(${(1 - enter) * 8}px)` }}>
      <div style={{ fontFamily: DISPLAY, fontSize: 44, color: C.ink, opacity: 0.75, letterSpacing: 2 }}>CHILLI · GUNTUR MANDI</div>
      <div style={{ fontFamily: DISPLAY, fontSize: 170, color: C.chilli, lineHeight: 1.05 }}>
        ₹{d(1)}{d(2)},{d(3)}{d(4)}{d(5)}<span style={{ fontSize: 70, color: C.ink }}> /qtl?</span>
      </div>
    </div>
  );
};

export const Story: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const S = (s: number) => Math.round(s * fps);
  const sunY = interpolate(frame, [0, S(9)], [1210, 1040], ease);
  const camScale = interpolate(frame, [0, S(9)], [1.0, 1.12], ease);
  const raise = interpolate(frame, [S(6.6), S(7.4)], [0, 1], ease);
  const ring = frame > S(7.3) ? ((frame - S(7.3)) / 22) % 1 : 0;
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <AbsoluteFill style={{ scale: String(camScale), transformOrigin: "40% 55%" }}>
        <svg width={1080} height={1920}>
          <defs>
            <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#e98a3a" />
              <stop offset="0.45" stopColor="#f6bb6a" />
              <stop offset="0.66" stopColor="#fde3b0" />
            </linearGradient>
            <radialGradient id="sun">
              <stop offset="0" stopColor="#fff6dc" />
              <stop offset="0.55" stopColor="#ffe7a8" />
              <stop offset="1" stopColor="#ffe7a8" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#b9773d" />
              <stop offset="1" stopColor="#6e3a19" />
            </linearGradient>
          </defs>
          <rect width="1080" height="1920" fill="url(#sky)" />
          <circle cx={700} cy={sunY} r={320} fill="url(#sun)" />
          <circle cx={700} cy={sunY} r={150} fill="#fff4d6" />
          {/* distant tree line */}
          <path d="M0 1230 Q 60 1170 120 1225 Q 170 1150 240 1222 Q 300 1190 350 1228 Q 430 1160 520 1226 Q 600 1200 660 1228 Q 760 1150 860 1225 Q 930 1185 1000 1226 Q 1040 1200 1080 1222 L 1080 1260 L 0 1260 Z" fill="#7a5a3a" opacity={0.55} />
          <rect y={1250} width="1080" height="670" fill="url(#ground)" />
          {/* drying chilli spread on the ground, and heaps */}
          <g transform="translate(-60 1300)"><ChilliField count={160} w={1200} h={600} seed={3} scale={0.55} /></g>
          <g transform="translate(560 1220)"><ChilliField count={170} w={520} h={230} seed={21} scale={0.7} mound /></g>
          <g transform="translate(-120 1350)"><ChilliField count={150} w={420} h={170} seed={31} scale={0.7} mound /></g>
          <Farmer raise={raise} ring={ring} />
        </svg>
      </AbsoluteFill>

      <Sequence from={S(2.2)} durationInFrames={S(2.9)} layout="none"><RollingPrice /></Sequence>

      <Sequence durationInFrames={S(2.3)} layout="none">
        <Caption en="This is Lakshmi. She grows chilli near Guntur." />
      </Sequence>
      <Sequence from={S(2.3)} durationInFrames={S(2.5)} layout="none">
        <Caption en="Sell today… or wait for a better price?" highlight={["price"]} />
      </Sequence>
      <Sequence from={S(4.8)} durationInFrames={S(2.0)} layout="none">
        <Caption en="Price apps are in English. She speaks Telugu." highlight={["Telugu"]} />
      </Sequence>
      <Sequence from={S(6.8)} layout="none">
        <Caption en="So she just calls… and asks." highlight={["calls"]} />
      </Sequence>
      <div style={{ position: "absolute", bottom: 40, width: "100%", textAlign: "center", fontSize: 26,
        color: "rgba(255,248,236,.7)", fontFamily: "Inter" }}>
        Dramatization · synthetic voices and data
      </div>
      <Sequence from={S(7.3)} layout="none">
        <Audio src={staticFile("ring.wav")} volume={0.55} />
      </Sequence>
    </AbsoluteFill>
  );
};

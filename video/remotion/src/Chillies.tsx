import React from "react";
import { rand } from "./theme";

// One dried red chilli: a curved tapering pod with a green stem.
const Pod: React.FC<{ x: number; y: number; r: number; s: number; shade: number }> = ({ x, y, r, s, shade }) => {
  const body = ["#8e1b16", "#b3241d", "#c62a1f", "#d63a2a", "#a11d17"][shade];
  return (
    <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`}>
      <path d="M0 0 C 18 -10, 60 -8, 92 4 C 70 2, 30 8, 0 10 Z" fill={body} />
      <path d="M6 2 C 30 -2, 60 -1, 84 4" stroke="#ffffff" strokeOpacity={0.18} strokeWidth={2} fill="none" />
      <path d="M0 5 C -6 2, -12 -4, -16 -10" stroke="#3d6b2a" strokeWidth={5} strokeLinecap="round" fill="none" />
    </g>
  );
};

// A field of chillies scattered inside a rectangle (or an ellipse mound when `mound` is set).
export const ChilliField: React.FC<{
  count: number;
  w: number;
  h: number;
  seed?: number;
  scale?: number;
  mound?: boolean;
}> = ({ count, w, h, seed = 1, scale = 1, mound = false }) => {
  const pods = [];
  for (let i = 0; i < count; i++) {
    let x = rand(seed + i * 3.1) * w;
    let y = rand(seed + i * 7.7) * h;
    if (mound) {
      // squash points into an upper half-ellipse so heaps look piled
      const u = rand(seed + i * 5.3) * Math.PI;
      const rr = Math.sqrt(rand(seed + i * 9.9));
      x = w / 2 + Math.cos(u) * (w / 2) * rr;
      y = h - Math.sin(u) * h * rr;
    }
    pods.push(
      <Pod
        key={i}
        x={x}
        y={y}
        r={rand(seed + i * 1.7) * 360}
        s={scale * (0.7 + rand(seed + i * 2.3) * 0.6)}
        shade={Math.floor(rand(seed + i * 4.1) * 5)}
      />,
    );
  }
  return <g>{pods}</g>;
};

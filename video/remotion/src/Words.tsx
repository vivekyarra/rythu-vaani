import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";

// Words land one by one: blur 8px -> 0 and a slight scale-down, 3 frames apart. Landed words stay still.
export const Words: React.FC<{
  text: string;
  start?: number;
  stagger?: number;
  highlight?: string[];
  highlightColor?: string;
  style?: React.CSSProperties;
  punch?: boolean;
}> = ({ text, start = 0, stagger = 3, highlight = [], highlightColor = "#ffc93c", style, punch = false }) => {
  const frame = useCurrentFrame();
  const words = text.split(" ");
  return (
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: "0.28em", ...style }}>
      {words.map((w, i) => {
        const f = frame - start - i * stagger;
        const t = interpolate(f, [0, punch ? 5 : 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.out(Easing.exp),
        });
        const clean = w.replace(/[.,?!…"“”]/g, "");
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: t,
              filter: `blur(${(1 - t) * 8}px)`,
              scale: String(punch ? 1.35 - 0.35 * t : 1),
              color: highlight.includes(clean) ? highlightColor : undefined,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

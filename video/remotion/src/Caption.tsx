import React from "react";
import { Words } from "./Words";
import { BODY, C, TELUGU } from "./theme";

// Bottom caption band: optional Telugu line (as spoken) over the English subtitle.
export const Caption: React.FC<{
  en: string;
  te?: string;
  highlight?: string[];
  label?: string;
}> = ({ en, te, highlight = [], label }) => (
  <div
    style={{
      position: "absolute",
      left: 40,
      right: 40,
      bottom: 110,
      padding: "28px 36px 32px",
      borderRadius: 28,
      background: "rgba(22,18,15,0.88)",
      color: C.paper,
      textAlign: "center",
    }}
  >
    {label && (
      <div style={{ fontFamily: BODY, fontWeight: 800, fontSize: 30, color: C.turmeric, letterSpacing: 1.5,
        textTransform: "uppercase", marginBottom: 10 }}>
        {label}
      </div>
    )}
    {te && (
      <div style={{ fontFamily: TELUGU, fontWeight: 800, fontSize: 50, lineHeight: 1.3, color: C.turmeric, marginBottom: 8 }}>
        {te}
      </div>
    )}
    <Words text={en} stagger={2} highlight={highlight}
      style={{ fontFamily: BODY, fontWeight: 800, fontSize: te ? 46 : 58, lineHeight: 1.2 }} />
  </div>
);

import { loadFont as loadArchivo } from "@remotion/google-fonts/ArchivoBlack";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadTelugu } from "@remotion/google-fonts/NotoSansTelugu";

export const DISPLAY = loadArchivo().fontFamily;
export const BODY = loadInter("normal", { weights: ["500", "700", "800"] }).fontFamily;
export const TELUGU = loadTelugu("normal", { weights: ["600", "800"] }).fontFamily;

export const C = {
  chilli: "#c62a1f",
  chilliDark: "#5a0f0b",
  turmeric: "#ffc93c",
  leaf: "#2f7d32",
  ink: "#16120f",
  paper: "#fff8ec",
};

// Deterministic pseudo-random in [0, 1)
export const rand = (seed: number) => {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

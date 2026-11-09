import React from "react";
import { AbsoluteFill, Easing, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio, Video } from "@remotion/media";
import { Caption } from "./Caption";

// Event times (seconds into the screen recording) come from demo/recording_log.json of the real run.
export type CallTiming = {
  clip: string; // public/<clip>.mp4, <clip>_reply.wav
  callerAudio: string;
  pre?: number; // optional earlier start, played at 2x (e.g. ticking the noisy-line box)
  recStart: number;
  recStop: number;
  response: number;
  reply: number; // reply audio length
};

export const callFrames = (t: CallTiming, fps: number) => {
  const pre = t.pre !== undefined ? Math.round(((t.recStart - 0.6 - t.pre) / 2) * fps) : 0;
  const ask = Math.round((t.recStop + 0.1 - (t.recStart - 0.6)) * fps);
  const think = Math.round(((t.response + 0.2 - (t.recStop + 0.1)) / 2) * fps);
  const answer = Math.round((t.reply + 0.9) * fps);
  return { pre, ask, think, answer, total: pre + ask + think + answer };
};

// Gentle punch-in on the result card while the reply plays.
const Punch: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        scale: String(interpolate(frame, [0, 18], [1, 1.16], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) })),
        transformOrigin: "50% 60%",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const AppCall: React.FC<{
  t: CallTiming;
  preCaption?: { en: string; label?: string };
  askCaption: { te: string; en: string; label?: string };
  thinkCaption: string;
  answerCaption: { en: string; label?: string; highlight?: string[] };
}> = ({ t, preCaption, askCaption, thinkCaption, answerCaption }) => {
  const { fps } = useVideoConfig();
  const f = callFrames(t, fps);
  const src = staticFile(`${t.clip}.mp4`);
  const askFrom = t.recStart - 0.6;
  return (
    <AbsoluteFill style={{ backgroundColor: "#f7f5ef" }}>
      {f.pre > 0 && (
        <Sequence durationInFrames={f.pre}>
          <Video src={src} muted trimBefore={Math.round((t.pre ?? 0) * fps)} playbackRate={2} />
          {preCaption && <Caption en={preCaption.en} label={preCaption.label} highlight={["noisy"]} />}
        </Sequence>
      )}
      <Sequence from={f.pre} durationInFrames={f.ask}>
        <Video src={src} muted trimBefore={Math.round(askFrom * fps)} />
        {/* the app's mic stream starts ~0.15 s after Record is clicked */}
        <Sequence from={Math.round(0.75 * fps)} layout="none">
          <Audio src={staticFile(t.callerAudio)} volume={1} />
        </Sequence>
        <Caption te={askCaption.te} en={askCaption.en} label={askCaption.label ?? "Caller asks"} />
      </Sequence>
      <Sequence from={f.pre + f.ask} durationInFrames={f.think}>
        <Video src={src} muted trimBefore={Math.round((t.recStop + 0.1) * fps)} playbackRate={2} />
        <Caption en={thinkCaption} label="Gnani Prisma · speech to text" />
      </Sequence>
      <Sequence from={f.pre + f.ask + f.think} durationInFrames={f.answer}>
        <Punch>
          <Video src={src} muted trimBefore={Math.round((t.response + 0.2) * fps)} />
        </Punch>
        <Audio src={staticFile(`${t.clip}_reply.wav`)} trimBefore={Math.round(0.15 * fps)} />
        <Caption en={answerCaption.en} label={answerCaption.label ?? "Gnani Timbre · replies in Telugu"}
          highlight={answerCaption.highlight} />
      </Sequence>
    </AbsoluteFill>
  );
};

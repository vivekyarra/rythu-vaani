import React from "react";
import { AbsoluteFill, Audio, Composition, Sequence, staticFile } from "remotion";
import { Architecture, Captions, Close, Demo, Hook, Problem, Results, Title } from "./Scenes";
import { C, FPS } from "./theme";
import T from "./timeline.json";

type Cut = typeof T.main;
type Scene = Cut["scenes"][number];

const renderScene = (s: Scene) => {
  switch (s.kind) {
    case "hook": return <Hook d={T.hook} />;
    case "problem": return <Problem d={T.problem} />;
    case "title": return <Title d={T.title} />;
    case "demo": return <Demo startFrom={s.startFrom ?? 0} label={T.demoLabel} crop={(s as { crop?: { x: number; y: number; scale: number } }).crop} note={(s as { note?: string }).note} />;
    case "arch": return <Architecture d={T.arch} />;
    case "results": return <Results d={T.results} />;
    case "close": return <Close d={T.close} />;
    default: return null;
  }
};

const Cutter: React.FC<{ cut: Cut }> = ({ cut }) => (
  <AbsoluteFill style={{ background: C.bg }}>
    {cut.scenes.map((s, i) => (
      <Sequence key={i} from={s.from} durationInFrames={s.dur}>{renderScene(s)}</Sequence>
    ))}
    {cut.audio.map((a, i) => (
      <Sequence key={`a${i}`} from={a.from} durationInFrames={a.dur}>
        <Audio src={staticFile(a.src)} startFrom={a.startFrom ?? 0} volume={a.volume ?? 1} />
      </Sequence>
    ))}
    <Captions items={cut.captions} />
  </AbsoluteFill>
);

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="AuditDemo" component={() => <Cutter cut={T.main} />} durationInFrames={T.main.duration}
      fps={FPS} width={1920} height={1080} />
    <Composition id="AuditVertical" component={() => <Cutter cut={T.vertical as Cut} />} durationInFrames={T.vertical.duration}
      fps={FPS} width={1080} height={1920} />
  </>
);

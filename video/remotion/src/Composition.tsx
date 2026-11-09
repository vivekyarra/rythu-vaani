import React from "react";
import { Composition } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { Hook } from "./Hook";
import { Story } from "./Story";
import { AppCall, CallTiming, callFrames } from "./AppCall";
import { Benchmark, EndCard } from "./Payoff";
import { HowItWorks } from "./HowItWorks";

const FPS = 30;

// From demo/recording_log.json (real run against the live Gnani API).
const Q1: CallTiming = { clip: "q1_price", callerAudio: "q1_price_caller.wav", recStart: 3.12, recStop: 5.95, response: 8.14, reply: 7.04 };
const Q2: CallTiming = { clip: "q2_loan", callerAudio: "q2_loan_caller_phone5.wav", pre: 1.4, recStart: 4.74, recStop: 8.54, response: 11.06, reply: 8.16 };

const HOOK = 100;
const STORY = 280;
const HOW = 120;
const BENCH = 210;
const END = 150;
const T = 10; // transition length

const q1 = callFrames(Q1, FPS).total;
const q2 = callFrames(Q2, FPS).total;
export const TOTAL = HOOK + STORY + q1 + q2 + HOW + BENCH + END - 6 * T;

const Main: React.FC = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence durationInFrames={HOOK}>
      <Hook />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={STORY}>
      <Story />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={q1}>
      <AppCall
        t={Q1}
        askCaption={{ te: "గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?", en: "“What's the chilli price at Guntur market?”" }}
        thinkCaption="Understanding spoken Telugu… (sped up 2×)"
        answerCaption={{ en: "“₹14,200 per quintal, up ₹400 from last week.” (demo price)", highlight: ["₹14,200"] }}
      />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={q2}>
      <AppCall
        t={Q2}
        preCaption={{ label: "Now the hard part", en: "Same app, through a noisy 8 kHz phone line" }}
        askCaption={{ label: "Caller asks · noisy line, 5 dB", te: "కౌలు రైతుని, రెండు ఎకరాలు, crop loan వస్తుందా?",
          en: "“Tenant farmer, 2 acres. Will I get a crop loan?”" }}
        thinkCaption="Cleaning up a crackly phone line… (sped up 2×)"
        answerCaption={{ label: "Understood through the noise ✓",
          en: "“Tenant farmers aren't covered by this scheme. Ask me about others.”", highlight: ["noise"] }}
      />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={HOW}>
      <HowItWorks />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={BENCH}>
      <Benchmark />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={linearTiming({ durationInFrames: T })} />
    <TransitionSeries.Sequence durationInFrames={END}>
      <EndCard />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);

export const MyComposition = () => (
  <Composition id="RythuVaani" component={Main} durationInFrames={TOTAL} fps={FPS} width={1080} height={1920} />
);


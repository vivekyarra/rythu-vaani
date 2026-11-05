# Submission: Great Indian AI Internship Challenge (Gnani AI)

## Project title

**Rythu Vaani (రైతు వాణి): a Telugu voice helpline for farmers that works over noisy phone lines**

## Problem

Farmers around Guntur decide every week when to sell chilli or cotton, what to do about a pest, and
whether they qualify for insurance, seed subsidy or a crop loan. The information exists, but mostly
in English apps and websites. The farmers who need it most often only have a feature phone, are
more comfortable speaking Telugu (or Telugu mixed with English words like "rate" and "loan") than
typing, and call over congested lines.

Rythu Vaani lets a farmer simply call and ask in Telugu. The farmer gets a spoken Telugu answer
with the mandi price and weekly trend, generic safe crop advice, or a scheme-eligibility check
based on acreage and tenant status.

## Target users

Small and tenant farmers in Tier-2/3 towns and villages of coastal Andhra Pradesh
(Guntur, Tenali and Narasaraopet markets in the demo). Also the village-level agriculture staff
who take their calls.

## Gnani models / APIs used

| Model | How it is used |
|---|---|
| **Prisma v3.0** speech-to-text (`te-IN`, with `keyterms` + `topic`) | Transcribes the caller's Telugu or code-mixed question (REST `POST /stt/v3`). The noise benchmark compares it with Prisma v2.5 and plain v3.0. |
| **Timbre v2.5** text-to-speech, Beta (`te-IN`, voice Varuni) | Speaks the answer back as 8 kHz telephone-ready WAV. Also generates the clean synthetic Telugu speech for the noise benchmark. |

Evon and the agent builder are not used.

## What makes it fit the awards

* **Main Character:** Telugu-first. NLU understands Telugu script, Telugu-script English loan words and romanised Telugu. Replies are Telugu speech.
* **Small Town, Big Build:** built in Guntur, for Guntur-region farmers, around the markets and crops of the region.
* **Real Deal:** prices, crop advice and scheme eligibility are the three questions farmers actually ask. Advice stays safe and points to the local agriculture officer.
* **Noise Canceller:** every request can run through a simulated 8 kHz phone line (band-pass, G.711 mu-law, noise at a chosen SNR). The included benchmark measures WER, CER and intent accuracy per SNR with the real APIs.
* **Solo Ninja:** designed, built, tested and documented by one person.

## Solo contribution statement

I, Yarra Vivek (B.Tech CSE, class of 2027, Guntur, Andhra Pradesh), am a solo entrant. I chose
the problem, designed the pipeline, and integrated the Gnani Prisma and Timbre APIs. I wrote the
Telugu NLU and the synthetic knowledge base, the telephone-noise simulator and benchmark, the
FastAPI backend, the web page, the CLI and the tests. I used an AI coding assistant during
development and reviewed and tested the code myself.
<!-- Vivek: keep or edit the AI-assistant sentence so it matches the contest's disclosure rules. -->

All data is synthetic. No real phone numbers, account numbers, Aadhaar, PAN or recorded calls are used.

## 60-second demo script

Record the screen with the web app at `http://127.0.0.1:8000` in **real mode** (green LIVE banner
visible), with system audio captured. Speak Telugu lines naturally. Subtitles in English are added
in editing.

| Time | Shot | What you say / do |
|---|---|---|
| 0:00-0:06 | Face cam or a photo of a Guntur chilli yard (your own photo, no people's faces without consent) | "I'm Vivek from Guntur. Farmers here ask three questions: price, pests, and schemes. Rythu Vaani answers them in Telugu, over a phone call." |
| 0:06-0:10 | Web app, green **LIVE: prisma-v2.5 → timbre-v2.5** banner | "It runs on Gnani's Prisma speech-to-text and Timbre text-to-speech." |
| 0:10-0:22 | Click **Record**, say: *"గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?"*, then Stop | Screen shows the transcript, intent `mandi_price`, and the Telugu reply. Let the Timbre reply play in full. |
| 0:22-0:34 | Tick **Simulate noisy 8 kHz phone line**, pick **5 dB**, record a code-mixed question: *"కౌలు రైతుని, రెండు ఎకరాలు, crop loan వస్తుందా?"* | "Now the same thing through a noisy phone line." The reply plays: not eligible because tenant farmers aren't covered, ask about other schemes. |
| 0:34-0:44 | Record: *"పత్తికి పురుగు పట్టింది, ఏం చేయాలి?"* | Reply plays: sticky traps, neem oil, consult the agriculture officer. "Advice stays safe. It never prescribes a pesticide dose." |
| 0:44-0:54 | Terminal showing the `results/benchmark_*.md` table from a real run | "I tested Prisma on Telugu speech degraded to 8 kHz phone quality at 20 down to 0 dB SNR. Here's the measured word error rate and how often the helpline still understood." Read out **only the real numbers from your run**. |
| 0:54-0:60 | Title card: *Rythu Vaani · Gnani Prisma + Timbre · synthetic data only · github.com/vivekyarra* | "Built solo, from Guntur. Thank you, Gnani AI." |

Before recording, check:
- Real mode, not MOCK. The web page must show the green LIVE banner. Never record MOCK output as if it were real.
- Run each spoken question once beforehand. If Prisma mishears something, show it honestly or re-record. Don't edit transcripts.
- Keep the video at 60 seconds or under, with English subtitles.

## LinkedIn post draft

> I built **Rythu Vaani (రైతు వాణి)**, a Telugu voice helpline for farmers, as my solo entry to
> the Great Indian AI Internship Challenge by [tag: Gnani AI company page].
>
> I'm a B.Tech CSE student from Guntur. Around here farmers keep asking the same three things:
> what chilli or cotton is fetching at the mandi, what to do about a pest, and whether they qualify
> for a scheme. Many of them would rather just call and ask in Telugu than use an English app.
>
> How it works:
> 1. The caller speaks Telugu or Telugu-English mix → Gnani **Prisma v3.0** transcribes it, primed with farm keyterms
> 2. A rule-based Telugu parser finds the crop, market, acreage and tenant status
> 3. The answer comes from a small synthetic knowledge base
> 4. Gnani **Timbre v2.5** speaks the answer back in Telugu, as 8 kHz phone-ready audio
>
> Since real calls are noisy, I also built a benchmark that degrades speech to 8 kHz phone
> quality with noise from 20 dB down to 0 dB SNR and measures Prisma's word error rate and intent
> accuracy at each level. Result: [ONE LINE WITH YOUR REAL MEASURED NUMBERS, or remove this line].
>
> All data is synthetic: no real phone numbers, IDs or recorded calls.
>
> Demo video: [link] · Code: [link]
>
> #GreatIndianAIInternshipChallenge #GnaniAI #VoiceAI #Telugu #AgriTech

## X post draft (under 280 characters with a ~23-char link and a short handle)

> Rythu Vaani: farmers ask in Telugu about crop prices, pests or schemes and hear a Telugu reply.
> Gnani Prisma STT + Timbre TTS, tested on noisy 8 kHz calls. Solo build, Guntur. Synthetic data.
> [demo link] @[Gnani AI handle: check it]
> #GreatIndianAIInternshipChallenge #GnaniAI

# Rythu Vaani (రైతు వాణి): one-page solution pitch

**A Telugu voice helpline for farmers that still works on a noisy phone line.**
Solo entry by Yarra Vivek (B.Tech CSE 2027, Vignan's Lara Institute of Technology & Science, Guntur) ·
Great Indian AI Internship Challenge by Gnani.ai

## Problem
Every week, chilli and cotton farmers around Guntur ask three questions: *what is my crop fetching at the
mandi, what do I do about this pest, and do I qualify for this scheme?* The answers exist, but mostly in
English apps and websites. Many small and tenant farmers have only a basic phone, are most comfortable
speaking Telugu (often mixed with English words like "rate" and "loan"), and call over congested lines.

## Solution
The farmer simply calls and asks in Telugu, and gets a spoken Telugu answer:
1. **Gnani Prisma v3.0 (speech-to-text, `te-IN`)** transcribes Telugu or Telugu-English speech, primed with
   the helpline's own crop, market and scheme words (`keyterms`) and a short `topic`.
2. **A rule-based Telugu parser** extracts crop, market, acreage and tenant status from Telugu script,
   Telugu-script English loan words, or romanised Telugu.
3. **The answer** comes from a knowledge base: mandi price and weekly trend (live Agmarknet prices via
   data.gov.in when a key is set, synthetic demo prices otherwise), safe generic crop advice that never
   prescribes pesticide doses, and scheme eligibility.
4. **Gnani Timbre v2.5 (text-to-speech, Telugu)** speaks the answer back as 8 kHz phone-ready audio.

Channels: a web app (record or upload), a CLI, and a WhatsApp voice-note bot (signed webhook, tested).

## Why it works on real phone lines (measured)
Village calls are noisy, so every request can pass through a simulated phone line: 8 kHz, 300–3400 Hz
band-pass, G.711 μ-law, and noise at a chosen SNR. On **10 held-out questions** (written after tuning and
never used for it), run against the live Gnani API on 2 Nov 2026:

| Condition | Prisma v2.5 | Prisma v3.0 | **Prisma v3.0 + keyterms/topic** |
|---|---|---|---|
| Phone line, 5 dB | 9/10 | 9/10 | **10/10** |
| Phone line, 0 dB (noise as loud as the voice) | 6/10 | 7/10 | **10/10** (CER 0.170 → 0.035) |

The domain context, not the model upgrade alone, made the difference. Honest limits: the test speech is
Timbre TTS rather than real callers, 10 questions is a small set, and at 0 dB keyterms turned one of 5
off-domain calls into a farm word. The parser then asks which crop the caller means instead of answering.

## Open-source extra for developers
`vaani-bench` packages the phone-line simulator and the speech-to-text benchmark as a CLI, so any team
building an Indian-language voice agent can test Prisma on audio that sounds like their callers.

## Users and impact
Small and tenant farmers in Tier-2/3 coastal Andhra Pradesh (Guntur, Tenali, Narasaraopet markets), and
the village agriculture staff who take their calls. No app, literacy or smartphone needed: just a voice.

**Trust and privacy:** all data is synthetic, with no real phone numbers, IDs or recorded calls. The API key
lives only in a gitignored `.env`. There are 114 automated tests, which run without a key in a clearly
labelled MOCK mode.

Code: https://github.com/vivekyarra/rythu-vaani

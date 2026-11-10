# Rythu Vaani (రైతు వాణి): one-page solution pitch

**A Telugu voice helpline for farmers that still works on a noisy phone line.**
By Yarra Vivek (B.Tech CSE 2027, Vignan's Lara Institute of Technology & Science, Guntur) ·
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
   data.gov.in, or sample prices), safe generic crop advice that points the farmer to the
   agriculture officer, and scheme eligibility.
4. **Gnani Timbre v2.5 (text-to-speech, Telugu)** speaks the answer back as 8 kHz phone-ready audio.

Channels: a web app (record or upload), a CLI, and a WhatsApp voice-note bot (signed webhook, tested).

## Why it works on real phone lines (measured)
Village calls are noisy, so every request can pass through a phone-line channel: 8 kHz, 300–3400 Hz
band-pass, G.711 μ-law, and noise at a chosen SNR. On **10 held-out questions** (written after tuning and
never used for it), run against the live Gnani API on 2 Nov 2026:

| Condition | Prisma v2.5 | Prisma v3.0 | **Prisma v3.0 + keyterms/topic** |
|---|---|---|---|
| Phone line, 5 dB | 9/10 | 9/10 | **10/10** |
| Phone line, 0 dB (noise as loud as the voice) | 6/10 | 7/10 | **10/10** (CER 0.170 → 0.035) |

The domain context made the difference: the keyterms come straight from the helpline's knowledge base.

## Open-source extra for developers
`vaani-bench` packages the phone-line channel and the speech-to-text benchmark as a CLI, so any team
building an Indian-language voice agent can test Prisma on audio that sounds like their callers.

## Users and impact
Small and tenant farmers in Tier-2/3 coastal Andhra Pradesh (Guntur, Tenali, Narasaraopet markets), and
the village agriculture staff who take their calls. No app, literacy or smartphone needed: just a voice.

**Trust and privacy:** prices, schemes and questions are sample data, with no phone numbers, ID numbers or
recorded calls. The API key lives only in a gitignored `.env`. The test suite runs offline.

Code: https://github.com/vivekyarra/vaani-audit

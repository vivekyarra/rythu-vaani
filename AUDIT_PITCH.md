# Vaani Audit: every collection call audited, in Indian languages, with evidence

**Yarra Vivek, solo entry · Gnani.ai Great Indian AI Internship Challenge · built on Gnani Prisma (STT) + Timbre (TTS)**

## Problem
RBI's rules for loan-recovery calls are explicit:
- identify yourself, the lender and the purpose;
- call only between 08:00 and 19:00;
- no threats, abuse or public shaming;
- never disclose the debt to third parties;
- tell the borrower how to complain.

Lenders answer for their agents, yet compliance teams can listen to only **about 1–2% of calls**. Those calls are in Hindi, Telugu and code-mixed speech, over noisy phone lines. The other 98% are never checked.

## Buyer and value
**Buyer:** the Head of Collections QA or the Compliance Officer at banks, NBFCs, microfinance lenders and collection agencies. These are the same BFSI accounts that buy Gnani's voice agents and speech analytics.

**Value:**
- audit coverage goes from about 2% to **100%**, and humans review only the calls that were flagged;
- every finding carries a **timestamp and a verbatim quote**, so it is audit-ready evidence;
- Timbre speaks the compliant phrasing for agent coaching, in the call's language.

## How Gnani's models are used (live API)
- **Prisma v3.0 Batch** transcribes each leg of the call, with timestamps, domain `keywords` (in Latin, Devanagari and Telugu scripts), a `topic`, and `hi-IN,en-IN` for code-mixed calls.
  - Mono calls use Prisma diarization plus a documented role heuristic.
  - Finding: the live API accepts `keywords` but silently drops the documented `keyterms`.
- **Rules:** a deterministic RBI checklist. An optional LLM may only add a finding whose quote appears literally in the agent's turn; this is enforced in code.
- **Timbre v3.0** voiced the synthetic calls (two voices, `<shouting>` for angry turns) and speaks the coaching rephrasing.

## Measured results (live Gnani API, 9 Nov 2026)
The dataset is 26 synthetic calls (Hindi, Telugu, Hinglish, Telugu-English) through a simulated 8 kHz G.711 phone line with noise. **12 held-out calls** were never used for tuning. F1 is micro-averaged over 6 violation types; CER is the character error rate of the transcript.

| held-out, dual-channel | clean | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| Prisma v2.5 · F1 (CER) | 0.94 (0.18) | 0.94 (0.19) | 0.92 (0.20) | 0.92 (0.22) |
| **Prisma v3.0 + keywords** | **0.94 (0.16)** | **0.94 (0.16)** | **0.94 (0.17)** | **0.92 (0.19)** |
| *14 dev calls, F1 v2.5 → v3.0 + keywords* | 0.97 → 0.97 | 0.97 → 0.94 | 0.89 → 0.94 | 0.85 → 0.92 |

- **Per category (held-out):**
  - every threat, abuse, third-party disclosure and missing grievance channel was found, all with precision 1.00;
  - the weak spot is **shaming, at recall 0.50**: both misses were phrasings the rules had never seen.
- **Most errors come from the rules, not the speech-to-text.** On the exact script text, the rules score 0.96. Call hours come from call metadata and are exact.
- **Mono recordings are risky:** diarization found one speaker on 9 of 26 calls, so we recommend dual-channel recording.
- **Latency:** about 20 s per call, end to end.

## Limits
- The data is synthetic (a contest rule): clean TTS voices and a small held-out set.
- No price per call is quoted, because Gnani does not publish rates.
- The LLM reviewer was not used for any measured number.
- This is not legal advice.

Code: `vaani_audit/` (CLI, FastAPI and dashboard). All 150 repo tests pass, with a labelled no-key MOCK mode.

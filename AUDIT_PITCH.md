# Vaani Audit: every collection call audited, in Indian languages, with evidence

**Yarra Vivek, solo entry · Gnani.ai Great Indian AI Internship Challenge · built on Gnani Prisma (STT) + Timbre (TTS)**

## Problem
RBI's rules for loan-recovery calls are explicit. The agent must identify themselves, the lender and the
purpose, and call only between 08:00 and 19:00. There must be no threats, abuse, intimidation or public
shaming, the debt must never be disclosed to third parties, and the borrower must be told how to complain.
Lenders are answerable for their recovery agents, but compliance teams can listen to only about **1–2% of
calls**. Those calls are in Hindi, Telugu and code-mixed speech, over noisy narrow-band phone lines. The other
98% are never checked.

## Buyer and ROI
**Buyer:** the Head of Collections QA or the Chief Compliance Officer at banks, NBFCs, microfinance lenders
and collection agencies. These are the same BFSI accounts that already buy Gnani's voice agents and speech
analytics. **Value:**
1. Audit coverage goes from ~2% sampled to 100%, and humans review only the calls that were flagged.
2. Each finding carries a timestamp and a verbatim quote, so it is audit-ready evidence, not just a score.
3. Each agent gets a coaching card, and Timbre speaks the compliant phrasing in the call's own language.

**Cost:** cost per call = audio minutes × Gnani Prisma's per-minute price. Gnani does not publish a rate
card, so we quote no rupee figure. Dual-channel calls send both legs, so they are billed as twice the call
length. Our 26 synthetic calls are 17.0 minutes long (39 s on average).

## How Gnani's models are used (live API)
* **Prisma v3.0 Batch STT:** the whole call is transcribed with timestamps. It is sent `keywords` (lender,
  agent names, product, legal and threat words in Latin, Devanagari and Telugu scripts), a `topic`, and
  per-language codes (`hi-IN,en-IN` for code-mixed calls). The job echo confirmed keywords and topic were
  accepted on every v3.0 job. We found that the live API names the field `keywords`; the documented
  `keyterms` is silently dropped (details in `vaani_audit/prisma.py`).
* **Speaker handling:**
  * Dual-channel recordings: each leg is transcribed in the same Batch job, so roles are exact.
  * Mono recordings: Prisma diarization plus a documented role heuristic (lender and agent-name cues).
* **Rules:** a deterministic RBI checklist produces each finding with a timestamp and a verbatim quote. An
  optional LLM may only *add* a finding, and only if its quote is literally in the cited agent turn (enforced
  in code).
* **Timbre v3.0:**
  * voiced all synthetic calls, with two voices per call and `<shouting>` for angry turns;
  * speaks every coaching rephrase in the call's language;
  * narrated the demo video.

## Measured results (live Gnani API, 9 Nov 2026; raw transcripts in `results/audit/raw*`)
The dataset is 26 synthetic calls: 14 dev calls used to write the rules, and **12 held-out** calls written by
a separate author and never used for tuning. They span Hindi, Telugu, Hinglish and Telugu-English. Each was
put through a simulated phone line (8 kHz, G.711, pink noise). F1 is micro-averaged over 6 categories; CER is
the character error rate of the transcript.

| held-out, dual-channel | clean line | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| Prisma v2.5 · F1 (CER) | 0.94 (0.18) | 0.94 (0.19) | 0.92 (0.20) | 0.92 (0.22) |
| **Prisma v3.0 + keywords** · F1 (CER) | **0.94 (0.16)** | **0.94 (0.16)** | **0.94 (0.17)** | **0.92 (0.19)** |
| *dev set, v2.5 → v3.0 + keywords (F1)* | 0.97 → 0.97 | 0.97 → 0.94 | 0.89 → 0.94 | 0.85 → 0.92 |

* **Per category (held-out, v3.0 + keywords, clean):**
  * threats 5/5 found, abuse 4/4, third-party disclosure 3/3, missing grievance channel 6/6, all with
    precision 1.00;
  * missing identity/lender/purpose: recall 1.00, precision 0.80;
  * **shaming: recall 0.50**.
  * Call hours come from call metadata and are exact.
* **What limits accuracy is mostly the rules, not the speech.** On the exact script text, the rules score
  F1 0.96 on held-out. Both missed shaming cases were new phrasings: a "courteous letter to your school
  principal", and a defaulter notice pasted on the house wall. The one STT-caused error was a misheard lender
  name, which produced a false "no disclosure" flag. Prisma v3.0 cuts CER on every condition. On the noisier
  dev conditions (5 dB and 0 dB) it also gives higher F1 (0.94 vs 0.89, and 0.92 vs 0.85). On held-out, both
  models score the same at clean, 10 dB and 0 dB; v3.0 is ahead only at 5 dB (0.94 vs 0.92). These are clean
  TTS voices, so real agents will be harder.
* **Mono recordings are risky.** Prisma diarization returned a single speaker on **9 of 26** clean mono calls
  (role accuracy 0.81), and held-out F1 dropped to 0.92. Our recommendation is dual-channel recording.
* **Latency:** a single-call live audit took **~20 s** end to end on an idle key (Batch job 19 s). It took
  29–51 s while the benchmark was also running. Batch jobs for 6–14 dual-channel calls, run in parallel, each
  finished in 15–63 s.

## Limits (honest)
* Synthetic data only (a contest rule): 26 calls, with clean TTS voices, so the confidence intervals are wide.
  The 12-call held-out set is small.
* A lexicon misses new phrasings. The quote-verified LLM reviewer exists, but it was **not** used in any
  measured number because no LLM key was available.
* Not legal advice. The checklist paraphrases RBI guidance. The agent-name check needs the dialer's agent
  roster.

Code: `vaani_audit/` (CLI, FastAPI and dashboard, 36 tests; all 150 repo tests pass), with a no-key MOCK mode that is labelled on
every screen and response.

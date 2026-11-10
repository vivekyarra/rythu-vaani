# Vaani Audit: every collection call audited, in Indian languages, with evidence

**Yarra Vivek · Gnani.ai Great Indian AI Internship Challenge · built on Gnani Prisma (STT) and Timbre (TTS)**

## The problem
RBI's fair-practices rules for loan-recovery calls are clear:
- identify yourself, the lender and the purpose;
- call only between 08:00 and 19:00;
- no threats, abuse or public shaming;
- never discuss the debt with third parties;
- tell the borrower how to raise a complaint.

Lenders answer for every call their agents make. Today, compliance teams can listen to only about **1–2% of calls**. Those calls are in Hindi, Telugu and code-mixed speech, over narrowband phone lines.

## The product
Vaani Audit checks **every** call:
1. **Gnani Prisma v3.0 Batch** transcribes each side of the call, with timestamps, domain `keywords` and a `topic`. Code-mixed calls use `hi-IN,en-IN`.
2. **An RBI checklist engine** flags threats, abuse, shaming, third-party disclosure, late-hour calls and missing identity or grievance details. Each finding comes with **the exact quote and the second it happened**.
3. **Gnani Timbre v3.0** speaks the compliant way to say it, in the call's language, for agent coaching.
4. **A team dashboard** shows compliance by agent, the top violation types, and a coaching card for every agent.

## Who buys it
The Head of Collections QA or the Chief Compliance Officer at banks, NBFCs, microfinance lenders and collection agencies. These are the BFSI teams that already use Gnani's voice AI.

**Value:**
- coverage goes from about 2% to **100%**, and reviewers open only the flagged calls;
- every finding is audit-ready evidence, with a timestamp and a verbatim quote;
- agents get coaching in their own language, spoken by Timbre.

## Measured on the live Gnani API (9 Nov 2026)
The dataset is 26 scripted sample calls in Hindi, Telugu, Hinglish and Telugu-English. Each was played through an 8 kHz G.711 phone-line channel with noise. **12 held-out calls** were never used for tuning. F1 is the combined detection score over six violation types.

| Held-out, dual-channel | Clean line | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| Prisma v2.5 · F1 | 0.94 | 0.94 | 0.92 | 0.92 |
| **Prisma v3.0 + keywords · F1** | **0.94** | **0.94** | **0.94** | **0.92** |

- **Threats, abuse, third-party disclosure and missing grievance channels:** every case found, at precision 1.00.
- **Prisma v3.0 with keywords** has a lower transcription error rate than v2.5 on every line condition (CER 0.16 against 0.18 on a clean line, 0.19 against 0.22 at 0 dB). On the noisiest tuning calls it lifts F1 from 0.85 to 0.92.
- **About 20 seconds** per call, end to end.

## What's next
- Live streaming audits during the call, on Prisma's real-time API.
- More languages and lender-specific checklists.
- Direct dialer integration, so every recorded call is audited as soon as it ends.

Code: https://github.com/vivekyarra/vaani-audit

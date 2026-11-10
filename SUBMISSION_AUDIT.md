# Vaani Audit: ready-to-paste submission answers

Branch with everything: `claude/great-brahmagupta-mb7b00` of https://github.com/vivekyarra/rythu-vaani
(merge it into `main`, or link the branch as shown below).

## Form fields

**Full name:** Yarra Vivek

**Institution:** Vignan's Lara Institute of Technology & Science

**Project URL:**
https://github.com/vivekyarra/rythu-vaani/tree/claude/great-brahmagupta-mb7b00/vaani_audit
(1-page pitch: https://github.com/vivekyarra/rythu-vaani/blob/claude/great-brahmagupta-mb7b00/AUDIT_PITCH.md)

**Demo video (2:56, 1080p):**
https://github.com/vivekyarra/rythu-vaani/blob/claude/great-brahmagupta-mb7b00/video/out/vaani_audit_demo_16x9.mp4
*(If the form needs a streaming link, upload this same file to YouTube as "Unlisted" or to Google Drive
("Anyone with the link"), and paste that link instead.)*

**Short description (≈60 words):**
Vaani Audit checks every loan-recovery call against RBI fair-practices rules in Hindi, Telugu and
code-mixed speech. Gnani Prisma v3.0 transcribes each call with timestamps and domain keywords. Rules flag
threats, abuse, shaming, third-party disclosure, late-hour calls and missing disclosures, each with a
timestamp and the exact quote. Gnani Timbre speaks the compliant rephrasing. Held-out F1 is 0.94 on the
live API.

**Gnani models used:**
- **Prisma v3.0 (Batch STT):** whole-call transcription with timestamps, `keywords` and `topic` context,
  per-language codes (`hi-IN,en-IN` for code-mixed calls), and diarization for mono calls.
- **Prisma v2.5 (Batch STT):** the benchmark baseline.
- **Timbre v3.0 (TTS):** voiced all 26 synthetic calls (two voices per call, with `<shouting>` for angry
  turns), speaks the compliant coaching rephrasing in the call's language, and narrated the demo video.

**Solo contribution statement:**
I built Vaani Audit alone: the product idea, the RBI-style checklist and rules, the Prisma Batch client,
the dual-channel and diarization pipeline, the FastAPI service and dashboard, the synthetic dataset and
phone-line simulator, the benchmark, the tests and the demo video. I used AI coding assistants as tools.
All data is synthetic, and all reported numbers come from my own runs on the live Gnani API.

## LinkedIn post (bonus award)
> Banks can manually audit only 1–2% of loan-collection calls. The rest, in Hindi, Telugu and
> code-mixed speech on noisy phone lines, are never checked against RBI's fair-practices rules.
>
> For the #GreatIndianAIInternshipChallenge I built **Vaani Audit**, on **Gnani AI**'s Prisma
> (speech-to-text) and Timbre (text-to-speech):
> 🔎 every call is checked for threats, abuse, public shaming, disclosure to third parties, calls outside
>    8 AM–7 PM, and missing identity or grievance info;
> ⏱️ every finding has a timestamp and the exact quote as evidence;
> 🗣️ Timbre speaks the compliant way to say it, in the same language, for agent coaching;
> 📊 a team dashboard shows compliance by agent and the top violation types.
>
> Measured on 12 held-out synthetic calls on the live Gnani API: violation-detection F1 0.94 with Prisma
> v3.0 + keywords, and 0.92 at 0 dB noise. The honest weak spot is new ways of shaming that my rules
> haven't seen. Everything is in the repo.
>
> Demo: [video link] · Code: [repo link]
> Thanks, [tag: Gnani AI company page]!
> #GreatIndianAIInternshipChallenge #GnaniAI #VoiceAI #RBI #Compliance

## X post (≤280 characters)
> Built Vaani Audit for the #GreatIndianAIInternshipChallenge: it audits 100% of Hindi/Telugu
> loan-collection calls for RBI violations, with a timestamp + quote for each. On @[Gnani handle] Prisma +
> Timbre. Held-out F1 0.94. [video link] #GnaniAI

(Before posting, type "@Gnani" on X and choose Gnani.ai's verified account; I could not verify the
handle. On LinkedIn, type "@Gnani" and pick the company page.)

## Honesty checklist (all true)
- All calls, people, numbers and the lender are synthetic. They are labelled SYNTHETIC in the data, UI and video.
- The demo video is a real screen recording of the app on the live Gnani API. Two waits for Prisma Batch
  jobs are shortened, and the video says so on screen with the real job time.
- Every metric comes from `results/audit/bench_20261109-172820.*` (raw transcripts are in `results/audit/raw*`).
- The optional LLM reviewer was not used for any reported number.

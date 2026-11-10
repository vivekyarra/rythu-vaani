# Vaani Audit: collection-call compliance auditor (Gnani Prisma + Timbre)

> **Everything here is synthetic.** The lender "Navdhan Finance", its agents and its borrowers are fictional.
> No real people, phone numbers, account numbers or IDs appear anywhere. Calls were scripted and voiced
> with Gnani Timbre.

One-page pitch: [`../AUDIT_PITCH.md`](../AUDIT_PITCH.md). Measured results:
[`../results/audit/`](../results/audit/). Demo video: [`../video/out/`](../video/out/).

## What it does
1. **Ingest** a call recording (WAV) and its metadata: call start time (IST) and agent ID from the dialer.
   * A **stereo WAV** is treated as a dual-channel recording (channel 0 = agent, channel 1 = customer).
   * A **mono WAV** goes through Prisma's diarization.
2. **Transcribe** with **Gnani Prisma v3.0 Batch**, which returns segments with `start_time`, `end_time` and
   `speaker_id`. Context is sent as `keywords` (up to 200) and a `topic`, see `audit.py`. The language code
   is per language, e.g. `hi-IN,en-IN` for Hinglish.
   * For stereo, both legs go into **one** Batch job and roles come from the channel.
   * For mono, roles come from a documented heuristic in `roles.py`. The speaker who names the lender or the
     agent's own name (from the roster) and talks about EMI/loan is the agent, with a bonus for speaking
     first.
3. **Check** each call against the RBI-style checklist in `checklist.py` with deterministic rules
   (`rules.py`). The lexicons cover Devanagari, Telugu script and romanised/English, because Prisma writes
   code-mixed English words in Latin script. Every finding has a **timestamp** and the **verbatim
   transcript quote** of its segment.
   * Optional `llm.py` reviewer: it can only *add* findings. Each one must cite an agent segment index and a
     quote that is literally in that segment; anything else is dropped in code. Timestamps always come
     from the segment, never from the LLM. Off by default; set `ANTHROPIC_API_KEY` and pass `--llm`.
     **No measured number uses it.**
4. **Score** the call (100 minus 25 per critical category and 10 per major one) and **coach** the agent:
   fixed, reviewed rephrasings per category and language (`coaching.py`), spoken by **Gnani Timbre v3.0**
   in the call's language.
5. **Dashboard:** compliance rate by agent, top violation types, per-call evidence with audio seek, and a
   coaching card for each agent.

| check | kind | severity |
|---|---|---|
| Identity, lender and purpose stated (`NO_DISCLOSURE`) | call | major |
| Call within 08:00–19:00 (`CALL_HOURS`, from metadata) | call | major |
| No threats / intimidation (`THREAT`) | span | critical |
| Respectful language (`ABUSE`) | span | critical |
| No public shaming (`SHAMING`) | span | critical |
| No disclosure to third parties (`THIRD_PARTY`) | span | critical |
| Grievance channel offered (`NO_GRIEVANCE`) | call | major |

## Run it
```bash
pip install -r requirements.txt
export GNANI_API_KEY=...              # read ONLY from the environment; without it: MOCK mode
python -m vaani_audit serve           # http://127.0.0.1:8100  (dashboard + API)
python -m vaani_audit audit call.wav --agent AG-101 --language hi-IN --time 2026-10-13T20:15:00+05:30
python -m vaani_audit synth           # voice the 26 scripts with Timbre and build the phone-line WAVs
python -m vaani_audit bench           # P/R per category x condition x system -> results/audit/bench_*.md
python -m vaani_audit populate        # audit every synthetic call into the dashboard store
pytest                                # 150 tests, all offline (MOCK)
```
API: `GET /api/status`, `GET /api/dashboard`, `GET /api/calls`, `GET /api/calls/{id}`,
`GET /api/calls/{id}/audio`, `POST /api/audit` (multipart: `file` or `sample_id`, plus `agent_id`,
`language`, `call_time`), `GET /api/agents/{id}/coaching`, `POST /api/coach/speak`.

**MOCK mode** (no key): nothing calls Gnani. A sample call's "transcript" is its script, uploads get a
placeholder, and coaching audio is beeps. Every response carries `"mode": "mock"` and `"mock": true`, and
the UI shows a red MOCK banner.

## Data and evaluation
* `data/audit/dev_calls.json`: 14 calls written first and used to write and tune the rules.
* `data/audit/heldout_calls.json`: 12 calls written by a **separate author** (an independent sub-agent).
  That author saw only `SCRIPT_FORMAT.md`, the category definitions, and no rules. The rules were never
  changed after held-out results were computed.
  * *Disclosure:* while writing the rules I saw the author's summary (label counts, and that some calls
    include a phone handover). While debugging the batch client I also saw one held-out transcript (hi_h02).
    No rule was written from them, but the held-out set is not perfectly blind.
* `data/audit/calls_truth.json`: ground-truth turn spans, measured from the rendered audio.
* Phone line: `rythu_vaani.audio.degrade_to_phone` (8 kHz, 300–3400 Hz, G.711 μ-law, pink noise at
  10/5/0 dB, each leg with its own noise). "clean" means the phone line with no added noise.
* Matching:
  * span findings must overlap the labelled turn (±1 s);
  * call-level findings count once per call;
  * micro P/R/F1 is over the 6 audio categories (`CALL_HOURS` comes from metadata and is exact).

### Measured results (live API, 2026-11-09)
`results/audit/bench_20261109-172820.md` has every system × condition × category. Held-out, micro
precision / recall / **F1** (CER in brackets):

| channels | system | clean | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| dual | Prisma v2.5 | 0.96 / 0.92 / **0.94** (0.18) | 0.96 / 0.92 / **0.94** (0.19) | 0.92 / 0.92 / **0.92** (0.20) | 0.92 / 0.92 / **0.92** (0.22) |
| dual | Prisma v3.0 | 0.96 / 0.92 / **0.94** (0.14) | 0.96 / 0.92 / **0.94** (0.14) | 0.96 / 0.92 / **0.94** (0.15) | 0.92 / 0.92 / **0.92** (0.18) |
| dual | **v3.0 + keywords/topic** | 0.96 / 0.92 / **0.94** (0.16) | 0.96 / 0.92 / **0.94** (0.16) | 0.96 / 0.92 / **0.94** (0.17) | 0.92 / 0.92 / **0.92** (0.19) |
| mono | Prisma v2.5 | 0.96 / 0.88 / **0.92** (0.18) | 0.96 / 0.92 / **0.94** (0.19) | 0.92 / 0.88 / **0.90** (0.20) | 0.88 / 0.85 / **0.86** (0.24) |
| mono | Prisma v3.0 | 0.96 / 0.88 / **0.92** (0.14) | 0.96 / 0.92 / **0.94** (0.15) | 0.92 / 0.92 / **0.92** (0.16) | 0.88 / 0.88 / **0.88** (0.23) |
| mono | **v3.0 + keywords/topic** | 0.96 / 0.88 / **0.92** (0.16) | 0.96 / 0.92 / **0.94** (0.16) | 0.96 / 0.92 / **0.94** (0.17) | 0.96 / 0.88 / **0.92** (0.25) |
| – | rules on the exact script (oracle) | 1.00 / 0.92 / **0.96** | | | |

Dev set, dual-channel F1, v2.5 → v3.0 + keywords: clean 0.97 → 0.97, 10 dB 0.97 → 0.94, 5 dB
0.89 → 0.94, 0 dB 0.85 → 0.92. Without keywords, v3.0 scores 0.87 / 0.92 / 0.89 / 0.85: on dev, the context
is what recovers the lender and agent names under noise.

**Analysis (honest):**
* **The rules limit accuracy, not Prisma.** On the exact text, held-out shaming recall is 0.50. The two
  misses were new phrasings: a "courteous letter" to the borrower's school principal (verb form
  తెలియజేయాల్సి, word లేఖ), and a defaulter notice pasted on the house wall (notice అంటించాల్సి). Adding them
  now would leak the held-out set, so a v2 lexicon needs a fresh held-out set.
* **One STT-caused error on held-out:** Prisma misheard the lender name in a Telugu-English call, which
  produced a false "no disclosure" finding (precision 0.80 for that category).
* **v3.0 vs v2.5:** CER is lower on every condition (0.14–0.19 vs 0.18–0.22). On these clean TTS voices,
  detection F1 is close on held-out, and v3.0 + keywords is ahead on the noisier dev conditions. Real agents,
  with accents and cross-talk, will be harder for both.
* **Keywords were confirmed** in every v3.0 job's config echo. We found that the documented `keyterms`
  field is silently dropped by the live Batch API, while `keywords` is accepted (see `prisma.py`).
* **Mono diarization:** single-speaker output on 9/26 calls on a clean line, 1/26 at 10 dB, 3/26 at 5 dB and
  6/26 at 0 dB, the same for every model. Role accuracy was 0.81 (clean) and 0.96 (10 dB). Mono recordings
  are supported, but dual-channel is recommended.
* **Latency:** a live single-call audit takes ~20 s (Batch job 19 s) on an idle key, and 29–51 s while other
  jobs are queued. For 26 dual-channel calls, 4 parallel language jobs each finished in 15–63 s.
* **Cost:** Gnani publishes no per-minute price. Cost is audio minutes × that price, and dual-channel means
  2× the call length.

## Files
`prisma.py` Batch client and mock · `audit.py` pipeline · `rules.py` and `checklist.py` the RBI rules ·
`roles.py` diarization-to-roles · `llm.py` quote-verified reviewer · `coaching.py` rephrasings ·
`synth.py` dataset rendering · `bench.py` evaluation · `store.py` dashboard aggregation · `api.py` ·
`cli.py` · `web/index.html`.

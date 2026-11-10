# vaani_audit

Collection-call compliance auditor on Gnani Prisma and Timbre. Overview, demo and results: [main README](../README.md) and [pitch](../PITCH.md).

The sample lender is "Navdhan Finance". Its agents and borrowers are scripted samples, voiced with Gnani Timbre.

## Pipeline
1. **Ingest** a call recording (WAV) with its call start time (IST) and agent ID from the dialer.
   * A **stereo WAV** is a dual-channel recording: channel 0 is the agent, channel 1 is the customer.
   * A **mono WAV** goes through Prisma's diarization.
2. **Transcribe** with **Gnani Prisma v3.0 Batch**. It returns segments with `start_time`, `end_time` and `speaker_id`. Context goes in as `keywords` (up to 200) and a `topic` (see `audit.py`). The language code is per language, for example `hi-IN,en-IN` for Hinglish.
   * Stereo: both sides go into **one** Batch job, and the channel gives the role.
   * Mono: `roles.py` picks the agent. That is the speaker who names the lender or the agent's own name (from the roster) and talks about the EMI or loan, with a bonus for speaking first.
   * The live Batch API reads context from the `keywords` field (`prisma.py`).
3. **Check** each call against the RBI checklist in `checklist.py`, with deterministic rules in `rules.py`. The lexicons cover Devanagari, Telugu script and Latin script, because Prisma writes code-mixed English words in Latin script. Every finding has a **timestamp** and the **verbatim quote** of its segment.
   * An optional reviewer in `llm.py` can only *add* findings. Each one must cite an agent segment and a quote that is literally in that segment; the code drops anything else. Timestamps always come from the segment. Turn it on with `ANTHROPIC_API_KEY` and `--llm`.
4. **Score** the call (100, minus 25 per critical category and 10 per major one) and **coach** the agent. `coaching.py` holds a reviewed rephrasing per category and language, spoken by **Gnani Timbre v3.0** in the call's language.
5. **Dashboard:** compliance rate by agent, top violation types, per-call evidence with audio seek, and a coaching card for each agent.

| Check | Kind | Severity |
|---|---|---|
| Identity, lender and purpose stated (`NO_DISCLOSURE`) | call | major |
| Call within 08:00–19:00 (`CALL_HOURS`, from metadata) | call | major |
| No threats or intimidation (`THREAT`) | span | critical |
| Respectful language (`ABUSE`) | span | critical |
| No public shaming (`SHAMING`) | span | critical |
| No disclosure to third parties (`THIRD_PARTY`) | span | critical |
| Grievance channel offered (`NO_GRIEVANCE`) | call | major |

## Run it
```bash
pip install -r requirements.txt
export GNANI_API_KEY=...              # read only from the environment
python -m vaani_audit serve           # http://127.0.0.1:8100 (dashboard and API)
python -m vaani_audit audit call.wav --agent AG-101 --language hi-IN --time 2026-10-13T20:15:00+05:30
python -m vaani_audit synth           # voice the 26 scripts with Timbre and render the phone-line WAVs
python -m vaani_audit bench           # P/R per category x condition x model -> results/audit/bench_*.md
python -m vaani_audit populate        # audit every sample call into the dashboard store
pytest                                # 150 tests, offline
```

**API:** `GET /api/status`, `GET /api/dashboard`, `GET /api/calls`, `GET /api/calls/{id}`, `GET /api/calls/{id}/audio`, `POST /api/audit` (multipart: `file` or `sample_id`, plus `agent_id`, `language`, `call_time`), `GET /api/agents/{id}/coaching`, `POST /api/coach/speak`.

Without `GNANI_API_KEY`, the service runs in an offline mode for development and tests: sample calls use their scripts as transcripts.

## Evaluation
* `data/audit/dev_calls.json`: 14 calls used to build the rules.
* `data/audit/heldout_calls.json`: 12 calls written separately from the rules, from `SCRIPT_FORMAT.md` and the category definitions only. They were never used for tuning.
* `data/audit/calls_truth.json`: labelled turn spans, measured from the rendered audio.
* Phone line: `rythu_vaani.audio.degrade_to_phone` (8 kHz, 300–3400 Hz, G.711 μ-law, pink noise at 10, 5 and 0 dB, with separate noise on each side). "Clean" is the phone line with no added noise.
* Matching:
  * span findings must overlap the labelled turn (±1 s);
  * call-level findings count once per call;
  * micro P/R/F1 is over the six audio categories (`CALL_HOURS` comes from metadata and is exact).

### Results (live API, 2026-11-09)
`results/audit/bench_20261109-172820.md` has every model × condition × category. Held-out micro precision / recall / **F1**, dual-channel:

| Model | Clean | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| Prisma v2.5 | 0.96 / 0.92 / **0.94** | 0.96 / 0.92 / **0.94** | 0.92 / 0.92 / **0.92** | 0.92 / 0.92 / **0.92** |
| Prisma v3.0 | 0.96 / 0.92 / **0.94** | 0.96 / 0.92 / **0.94** | 0.96 / 0.92 / **0.94** | 0.92 / 0.92 / **0.92** |
| **v3.0 + keywords/topic** | 0.96 / 0.92 / **0.94** | 0.96 / 0.92 / **0.94** | 0.96 / 0.92 / **0.94** | 0.92 / 0.92 / **0.92** |

* Tuning calls, dual-channel F1, v2.5 → v3.0 + keywords: clean 0.97 → 0.97, 10 dB 0.97 → 0.94, 5 dB 0.89 → 0.94, 0 dB 0.85 → 0.92. Keywords help Prisma keep lender and agent names under noise.
* Character error rate, v2.5 → v3.0 + keywords: 0.18 → 0.16 (clean), 0.22 → 0.19 (0 dB).
* Dual-channel recordings give exact roles. Mono recordings use diarization plus role detection.
* A single-call live audit takes about 20 s.

## Files
`prisma.py` Batch client · `audit.py` pipeline · `rules.py` and `checklist.py` RBI rules · `roles.py` diarization to roles · `llm.py` quote-verified reviewer · `coaching.py` rephrasings · `synth.py` dataset rendering · `bench.py` evaluation · `store.py` dashboard aggregation · `api.py` · `cli.py` · `web/index.html`.

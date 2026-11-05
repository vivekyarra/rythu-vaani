# Rythu Vaani (రైతు వాణి): a Telugu voice helpline for farmers

A farmer in a village near Guntur calls from a basic phone over a noisy line and asks, in Telugu
or Telugu-English mix, *"గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?"* ("what's the chilli price at
Guntur market?"). Rythu Vaani transcribes the question with **Gnani Prisma**, works out what is being
asked, answers from a knowledge base, and speaks the answer back in Telugu with **Gnani Timbre**.

Built by Yarra Vivek (B.Tech CSE 2027, Guntur, Andhra Pradesh) as a solo entry for Gnani AI's
Great Indian AI Internship Challenge.

> **All data in this repository is synthetic.** Prices, scheme names and eligibility rules are
> invented for the demo. No real phone numbers, account numbers, Aadhaar, PAN or recorded calls are
> used anywhere.

## Problem and target users

Farmers in the Guntur-Palnadu belt (chilli, cotton, paddy, red gram, maize) make daily decisions
that depend on three kinds of information:

1. **Mandi prices**: what is my crop fetching today at Guntur, Tenali or Narasaraopet, and is it up or down?
2. **Crop advice**: pests, disease, fertilizer, sowing windows.
3. **Scheme eligibility**: am I eligible for insurance, seed subsidy or a crop loan? Am I excluded as a tenant farmer?

Much of this information lives in English apps and websites. Many of the people who need it are
older farmers or tenant farmers who are more comfortable speaking Telugu than typing it, and who
often call from feature phones over congested 2G/landline paths. A voice helpline is a better fit
than an app for them.

**Target users:** small and tenant farmers in Tier-2/3 towns and villages of coastal Andhra
Pradesh, plus the field staff at village agriculture centres who answer their calls.

## Architecture

```
 caller (phone / browser mic / WAV upload)
        │  Telugu or Telugu-English speech, <= 30 s
        ▼
 [optional] phone-line simulator ── 8 kHz · noise @ SNR · 300-3400 Hz band-pass · G.711 mu-law
        │
        ▼
 Gnani Prisma v3.0 STT  ── POST https://api.vachana.ai/stt/v3 (multipart, te-IN, keyterms + topic)
        │  Telugu-script transcript
        ▼
 NLU (rythu_vaani/nlu.py): deterministic, testable
        │  intent ∈ {mandi_price, crop_advice, scheme_info, clarify_crop, greeting, fallback}
        │  slots: crop, market, topic, scheme, acres, tenant
        ▼
 Knowledge base (data/kb.json + rythu_vaani/kb.py): synthetic prices, advice, scheme rules
        │  reply in Telugu (+ English gloss for the screen)
        ▼
 Gnani Timbre v2.5 TTS ── POST https://api.vachana.ai/api/v1/tts/inference (te-IN, voice Varuni, 8 kHz WAV)
        │
        ▼
 spoken Telugu reply → caller
```

| Path | What it is |
|---|---|
| `rythu_vaani/gnani.py` | Prisma STT and Timbre TTS clients, request builders, retries, the labelled `MockGnaniClient` |
| `rythu_vaani/nlu.py` | Intent and slot parser (Telugu script, transliterated English, romanised Telugu) |
| `rythu_vaani/kb.py`, `data/kb.json` | Synthetic knowledge base and answer templates |
| `rythu_vaani/audio.py` | WAV I/O, telephone-channel simulation, WER/CER |
| `rythu_vaani/pipeline.py` | audio → STT → NLU → KB → TTS |
| `rythu_vaani/api.py`, `web/index.html` | FastAPI backend and a single-page web UI (record/upload/type, playback) |
| `rythu_vaani/whatsapp.py` | WhatsApp channel: Telugu voice note in, Telugu voice note back (setup: `WHATSAPP.md`) |
| `rythu_vaani/cli.py` | CLI demo |
| `scripts/noise_benchmark.py` | Noise-robustness benchmark (WER/CER/intent accuracy per SNR) |
| `tests/` | pytest suite (runs fully offline in MOCK mode) |

### Why a deterministic NLU?

A helpline that reads out prices and eligibility must be predictable and auditable. Rules
keyed on Telugu stems (matched by prefix, so `గుంటూరులో` → `గుంటూరు`, `పత్తికి` → `పత్తి`) are
easy to test, easy for a Telugu-speaking field officer to extend, and they never invent a price.
Prisma returns English loan words in Telugu script (`రేటు`, `లోన్`, `మార్కెట్`), so the cue lists
include those forms as well as Latin text for typed input. An LLM step could be added later for
paraphrases. Evon (Gnani's open-weight reasoning model) would be a natural fit, but it is available
only on request and is not used here.

## Gnani models used, and how

| Model | Use | Request details (from docs.gnani.ai) |
|---|---|---|
| **Prisma v3.0** (speech-to-text) | Transcribes the caller's Telugu question | `POST https://api.vachana.ai/stt/v3`, header `X-API-Key-ID`, multipart `audio_file` (<= 30 s), `model=prisma-v3.0`, `language_code=te-IN`, `keyterms` (the helpline's crop, market and scheme words) and `topic`. `format=transcribe` in the app, `verbatim` in the benchmark. The benchmark also runs Prisma v2.5 (field omitted, the default) for comparison. |
| **Timbre v2.5** (text-to-speech, Beta) | Speaks the Telugu reply. In the benchmark it also generates the clean synthetic test speech | `POST https://api.vachana.ai/api/v1/tts/inference`, JSON `{text, model:"timbre-v2.5", voice:"Varuni", language:"te-IN", speed, audio_config:{sample_rate:8000, num_channels:1, sample_width:2, encoding:"linear_pcm", container:"wav"}}`. The response body is raw WAV bytes. |

Telugu (`te-IN`) is listed as supported by both Prisma v2.5 and Timbre v2.5. Timbre v2.5 has
five Telugu voices: Suhana, Lehara, Lavanya, Yukti and Varuni. The docs don't list a separate
Telugu-English code-mix code, so code-mixed speech goes to Prisma as `te-IN`.

The API allows one active request per key, so calls are sequential. 429/5xx responses are
retried with exponential backoff, as the error docs recommend.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```

### MOCK mode vs real mode

* **No key in `.env` → MOCK mode, automatically.** The API is never called. STT returns the text
  you type as a hint (or a fixed sample sentence), and TTS returns three beeps. The web page shows
  a red **MOCK MODE** banner, every API response carries `"mode": "MOCK"` and a notice, and the CLI
  prints a MOCK banner. Mock output is for exercising the plumbing only. It is never a result.
* **`GNANI_API_KEY=...` in `.env` → real mode.** The key is read only from that environment
  variable. `.env` is gitignored.

### Run the web app

```bash
uvicorn rythu_vaani.api:app --reload
# open http://127.0.0.1:8000
```

Record (the browser converts it to 16 kHz WAV), upload a file, or type a question. Tick
**Simulate noisy 8 kHz phone line** to send your recording through the telephone-channel
simulator before Prisma sees it.

### Use it on WhatsApp

Farmers already use WhatsApp voice notes every day. With the WhatsApp channel turned on, a farmer
records a Telugu question and gets a Telugu voice note back. WhatsApp voice notes are OGG Opus,
which Prisma v3.0 accepts directly, and Timbre returns OGG Opus, so no audio conversion is needed.
Setup takes about 30 minutes with a free Meta test number: see [WHATSAPP.md](WHATSAPP.md).

### Run the CLI

```bash
python -m rythu_vaani.cli --text "గుంటూరులో మిర్చి ధర ఎంత?"
python -m rythu_vaani.cli --audio my_question.wav --phone --snr 10 --out reply.wav
# real key only: Timbre speaks the question, the phone line degrades it, Prisma transcribes it
python -m rythu_vaani.cli --say "పత్తికి పురుగు పట్టింది ఏం చేయాలి" --phone --snr 5
```

### Run the tests

```bash
pytest
```

The tests force MOCK mode, even if `.env` holds a key, and mock all HTTP. They cover intent
parsing, knowledge-base answers, the audio degradation pipeline, API request building, error
handling and retries, and the FastAPI endpoints.

## Noise-robustness benchmark

```bash
python scripts/noise_benchmark.py                       # pink noise at 20/10/5/0 dB
python scripts/noise_benchmark.py --noise hum --snrs 15 5
```

For each of the 10 synthetic caller questions in `data/benchmark_sentences.json`:

1. Timbre v2.5 synthesises clean 16 kHz Telugu speech (cached in `bench_cache/`).
2. Each condition is created: clean 16 kHz, phone with no noise, and phone with noise at every SNR.
   The phone channel is 8 kHz, noise at the target SNR, 300-3400 Hz band-pass, and G.711 mu-law.
   The script also reports the SNR measured after the channel, not just the nominal value.
3. Prisma transcribes each condition (`--stt v2.5`, `v3` or `v3-context`; `te-IN`, `verbatim`).
4. The script reports **WER**, **CER** (more informative for agglutinative Telugu) and
   **intent+slots accuracy** (does the helpline still give the right answer?).

Results are saved to `results/benchmark_<timestamp>.json` (with every transcript) and `.md`.
In MOCK mode the script runs the channel simulation on placeholder (non-speech) signals, prints
only the measured channel SNR, and saves nothing.

Caveat: TTS-generated speech is cleaner and more regular than real callers, so these numbers are
an optimistic baseline for the channel effect, not a field accuracy figure. The next step is to
add a set of read-aloud recordings by volunteers, still of synthetic questions.

## Results

Measured against the real Gnani API on 2026-11-02 (pink noise, Timbre voice Varuni). Raw
transcripts for every row are in `results/benchmark_*.json`.

**Held-out set** (`data/heldout_sentences.json`, 10 questions written *after* the NLU fixes and
never used to tune anything). Intent+slots correct = the helpline would give the right answer.

| condition | measured SNR (dB) | Prisma v2.5 | Prisma v3.0 | **v3.0 + keyterms/topic** | CER v2.5 → v3.0+ctx |
|---|---|---|---|---|---|
| clean 16k | - | 10/10 | 10/10 | **10/10** | 0.007 → 0.000 |
| phone, no noise | - | 9/10 | 9/10 | **10/10** | 0.012 → 0.000 |
| phone, 20 dB | 21.0 | 9/10 | 8/10 | **10/10** | 0.005 → 0.000 |
| phone, 10 dB | 11.1 | 9/10 | 9/10 | **10/10** | 0.007 → 0.000 |
| phone, 5 dB | 6.1 | 9/10 | 9/10 | **10/10** | 0.032 → 0.000 |
| phone, 0 dB | 1.1 | 6/10 | 7/10 | **10/10** | 0.170 → 0.035 |

The original set (`data/benchmark_sentences.json`) shows the same pattern: v3.0 + context gets
10/10 at every level, including 0 dB (v2.5: 7/10 after the NLU fixes).

What made the difference: Prisma v3.0's `keyterms` (the helpline's own crop, market and scheme
words, built from `data/kb.json` by `KnowledgeBase.stt_context()`) plus a one-paragraph `topic`
describing a farmer's call. Plain v3.0 without context was *not* better than v2.5 here, so the
context is doing the work. The app now uses v3.0 + context by default.

**Does the context make Prisma invent farm words?** 5 off-domain calls (weather, phone bill, bus
times, exam results, a greeting; `data/offdomain_sentences.json`): transcribed exactly at 10 and 5
dB. At 0 dB, 1 of 5 went wrong: "బస్సు" (bus) came out as "పత్తి" (cotton). The NLU then asks
which crop the caller means instead of answering, so it fails safe, but it is a real cost of
keyterms at extreme noise.

Honest caveats:
- The speech is Timbre TTS through a simulated phone line, not real callers. Real voices,
  accents and phones will be harder. These numbers are an optimistic baseline.
- 10 questions per set is small. One question is 10 percentage points.
- Some NLU fixes (fused words like "రెండెకరాలు", "లోనొస్తుందా") came from reading Prisma's
  transcripts on the original set, which is why the held-out set exists.

## Privacy and synthetic-data statement

* Only synthetic data is used: invented prices, invented scheme names and rules, and generated speech.
* No real phone numbers, account numbers, Aadhaar, PAN, personal names or recorded calls appear in
  the code, data or demo.
* Audio sent to the app is processed in memory and is not stored. Benchmark audio is synthetic
  and cached locally only.
* The API key lives only in a local, gitignored `.env`.
* Crop advice is deliberately generic (sticky traps, soil tests, certified seed). It always refers
  the farmer to the local agriculture officer and never prescribes a pesticide dose.

## Limitations and next steps

* Stateless single-turn dialogue: the caller must say crop + acreage in one sentence. Slot-filling
  across turns is the next step.
* Telugu reply text was written for the demo and should be reviewed by more native speakers and
  agriculture officers.
* Real deployment would swap `data/kb.json` for official mandi-price feeds and scheme rules, and
  put the pipeline behind a telephony provider over Prisma's realtime WebSocket.
* Test on real recorded phone calls from volunteers, not only TTS speech.

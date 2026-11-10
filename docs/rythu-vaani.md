# Rythu Vaani (రైతు వాణి): a Telugu voice helpline for farmers

A farmer near Guntur calls from a basic phone and asks, in Telugu or Telugu-English, *"గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?"* ("what's the chilli price at Guntur market?"). Rythu Vaani transcribes the question with **Gnani Prisma**, works out what is being asked, finds the answer, and speaks it back in Telugu with **Gnani Timbre**.

[One-page pitch](rythu-vaani-pitch.md) · [WhatsApp setup](whatsapp.md)

## Who it's for
Farmers in the Guntur–Palnadu belt (chilli, cotton, paddy, red gram, maize) ask three things every week:
1. **Mandi prices:** what is my crop fetching today at Guntur, Tenali or Narasaraopet, and is it going up or down?
2. **Crop advice:** pests, disease, fertilizer and sowing windows.
3. **Scheme eligibility:** do I qualify for insurance, seed subsidy or a crop loan as an owner or a tenant farmer?

Many of them prefer to speak Telugu rather than type, and call from feature phones. A voice helpline fits them better than an app.

## How it works
```
caller (phone, browser mic, WAV upload or WhatsApp voice note)
        │  Telugu or Telugu-English speech, up to 30 s
        ▼
[optional] phone-line channel ── 8 kHz · noise at a chosen SNR · 300–3400 Hz band-pass · G.711 μ-law
        ▼
Gnani Prisma v3.0 STT ── te-IN · keyterms (crops, markets, schemes) + topic
        ▼
Telugu parser (rythu_vaani/nlu.py) ── intent + crop, market, scheme, acres, tenant
        ▼
knowledge base (data/kb.json) ── prices and weekly trend, crop advice, scheme rules
        ▼             (live Agmarknet prices through data.gov.in when a key is set)
Gnani Timbre v2.5 TTS ── Telugu voice Varuni, 8 kHz phone-ready audio
        ▼
spoken Telugu reply
```

The parser is deterministic. It matches Telugu stems, so `గుంటూరులో` → `గుంటూరు` and `పత్తికి` → `పత్తి`. It also reads English loan words that Prisma writes in Telugu script (`రేటు`, `లోన్`, `మార్కెట్`) and romanised Telugu. Every answer is predictable and easy to audit. Crop advice stays safe and generic, and always points the farmer to the local agriculture officer.

| Path | What it is |
|---|---|
| `rythu_vaani/gnani.py` | Prisma STT and Timbre TTS clients, request builders and retries |
| `rythu_vaani/nlu.py` | Intent and slot parser |
| `rythu_vaani/kb.py`, `data/kb.json` | Knowledge base and Telugu answer templates |
| `rythu_vaani/mandi.py` | Live mandi prices from Agmarknet (data.gov.in) |
| `rythu_vaani/audio.py` | WAV I/O, phone-line channel, WER/CER |
| `rythu_vaani/api.py`, `web/index.html` | FastAPI backend and web app |
| `rythu_vaani/whatsapp.py` | WhatsApp channel: Telugu voice note in, Telugu voice note out |
| `scripts/noise_benchmark.py` | Noise benchmark (WER, CER, intent accuracy per SNR) |

## Run it
```bash
pip install -r requirements.txt
cp .env.example .env                 # add GNANI_API_KEY
uvicorn rythu_vaani.api:app          # http://127.0.0.1:8000
python -m rythu_vaani.cli --text "గుంటూరులో మిర్చి ధర ఎంత?"
```

## Results on the live Gnani API (2 Nov 2026)
10 held-out questions, written after the parser was finished and never used to tune it. Each one was spoken by Timbre and played through the phone-line channel with pink noise. "Correct" means the helpline gave the right answer.

| Condition | Prisma v2.5 | Prisma v3.0 | **Prisma v3.0 + keyterms/topic** |
|---|---|---|---|
| Clean 16 kHz | 10/10 | 10/10 | **10/10** |
| Phone line, no noise | 9/10 | 9/10 | **10/10** |
| Phone line, 20 dB | 9/10 | 8/10 | **10/10** |
| Phone line, 10 dB | 9/10 | 9/10 | **10/10** |
| Phone line, 5 dB | 9/10 | 9/10 | **10/10** |
| Phone line, 0 dB | 6/10 | 7/10 | **10/10** |

At 0 dB, the character error rate fell from 0.170 (v2.5) to 0.035 (v3.0 + keyterms/topic). The keyterms come straight from the knowledge base (`KnowledgeBase.stt_context()`), so Prisma hears crop, market and scheme names reliably even on a very noisy line. Raw transcripts for every run are in `results/benchmark_*.json`.

## Privacy
Prices, schemes and caller questions are sample data. No phone numbers, ID numbers or recorded calls are used. Audio is processed in memory and is not stored.

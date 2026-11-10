# HANDOFF: what Vivek must do before Nov 10, 2026, 11:59 PM IST

The code works end to end in MOCK mode and `pytest` passes. Nothing has been run against
the real Gnani API yet, and nothing has been pushed or posted.

## 1. Register and get a key (about 10 minutes)

1. Register for the Great Indian AI Internship Challenge on the official contest page, if you haven't already.
2. Sign up at **https://app.gnani.ai/voice** and create an API key.
3. In this folder:
   ```bash
   copy .env.example .env        # macOS/Linux: cp .env.example .env
   ```
   Open `.env` and set `GNANI_API_KEY=<your key>`. Never commit `.env`. It is already gitignored.

## 2. Install and check (about 5 minutes)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest                                    # always runs in MOCK mode, needs no key
python -m rythu_vaani.cli --text "గుంటూరులో మిర్చి ధర ఎంత?"   # now shows "mode: real"
```

Play `reply.wav`. It should be Timbre speaking Telugu, not beeps. If you get `HTTP 401`, check the key.
`HTTP 402` means you're out of credit. `HTTP 400` with a voice or model error means the API changed:
check docs.gnani.ai and fix `TTS_VOICE` / `TTS_MODEL` in `rythu_vaani/gnani.py`.

## 3. Run the noise benchmark (about 10-20 minutes, sequential API calls)

```bash
python scripts/noise_benchmark.py --limit 2      # quick sanity check first
python scripts/noise_benchmark.py                # full run: 10 sentences x 6 conditions = 60 STT + 10 TTS calls
```

Copy the table from `results/benchmark_<timestamp>.md` into the **Results** section of
`README.md`, replacing the TODO rows. Use only numbers from your own run. If the numbers are bad,
report them as they are. An honest weak result plus analysis is better than nothing.
Optional: `--noise hum` for a second table.

## 4. Proofread the Telugu (about 15 minutes)

Read the reply strings in `data/kb.json` and `rythu_vaani/kb.py` aloud. Fix anything that sounds
unnatural for a Guntur farmer, then run `pytest` again. Some tests check for key Telugu words, so
update them if you change those words.

## 5. Record the 60-second demo

```bash
uvicorn rythu_vaani.api:app
# open http://127.0.0.1:8000 and confirm the GREEN "LIVE" banner (not red MOCK)
```

Follow the shot list in `SUBMISSION.md`. Don't film MOCK mode, and don't edit transcripts.

## 6. Publish the code (your choice of repo)

```bash
git log --oneline                                # one local commit is already made
# create a public repo yourself on GitHub (e.g. vivekyarra/vaani-audit), then:
git remote add origin https://github.com/vivekyarra/<repo>.git
git push -u origin main
```

Before pushing, check that `git status` doesn't list `.env`, and that `git grep -i "api_key"` shows
only code that reads the variable.

## 7. Post and submit

1. Fill the placeholders in the LinkedIn and X drafts in `SUBMISSION.md` (demo link, repo link,
   your real benchmark line). Verify Gnani AI's LinkedIn page and X handle before tagging.
   Both posts must include `#GreatIndianAIInternshipChallenge` and `#GnaniAI`.
2. Post them.
3. Submit on the official contest form with the repo link, video link and post links
   **before Nov 10, 2026, 11:59 PM IST**. Aim for Nov 9 to leave time for upload problems.

## Things that were not verifiable without a key

- The exact success response of Timbre (the docs show only "raw audio bytes"). The client treats
  any non-JSON 200 body as audio.
- How well Prisma v2.5 handles 8 kHz telephone audio: the docs say input is resampled to 16 kHz but
  say nothing about telephony. That is exactly what the benchmark measures.
- Whether Prisma outputs English loan words in Telugu or Latin script for `te-IN`. The NLU accepts both.

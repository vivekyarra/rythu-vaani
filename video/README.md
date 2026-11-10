# Demo video toolkit

- `recorder/`: records the real web app with Playwright. `make_callers.py` makes synthetic Telugu caller
  questions with Timbre (voice Lavanya). `mic.js` is a virtual microphone that feeds that WAV into
  `getUserMedia`, so the app's own record -> `/api/call` path runs unchanged. `record_demo.py` drives the
  page, saves the screen video, the reply audio and event timings (`recording_log.json`).
  Note: Timbre WAVs have a placeholder frame count; compute duration from file size.
- `remotion/`: the 1080x1920 social video (hook, story, real-app calls, how it works, benchmark, end card).
  Put the screen recordings (`q*_price.mp4` etc.) and audio in `remotion/public/`, then
  `npm i && npx remotion render RythuVaani out.mp4`.
- Skills used: official `remotion-dev/skills` and `digitalsamba/claude-code-video-toolkit` (ffmpeg, playwright-recording); clone them, they are not vendored here.

## Vaani Audit demo video (`audit/`)

Outputs are committed in `video/out/`:
- `vaani_audit_demo_16x9.mp4`: 1920×1080, 2:56;
- `vaani_audit_vertical_9x16.mp4`: 1080×1920, 58 s.

Everything in the video is real. Rebuild it with `GNANI_API_KEY` set:

```bash
python -m vaani_audit serve --port 8100 &              # live API, the server must report mode=live
python video/audit/build_assets.py                     # Timbre narration (voice Tarika), real call clips
python video/audit/record_audit_demo.py                # Playwright screen recording of the live app + audio-event log
python video/audit/build_assets.py                     # converts the recording to MP4
python video/audit/build_timeline.py                   # src/timeline.json from the log, narration and newest bench
cd video/audit && npm i && npx remotion render src/index.ts AuditDemo out/vaani_audit_demo_16x9.mp4
npx remotion render src/index.ts AuditVertical out/vaani_audit_vertical_9x16.mp4
```

How it works:
- Playwright records without sound, so the recorder logs every `<audio>` play and pause in the page.
- The composition replays exactly those clips (the real call MP3s and the real Timbre coaching WAV) at the
  same moments.
- Waits for Prisma Batch jobs are cut, and an on-screen label gives the real job time.
- English captions come from the narration text, plus English translations of the synthetic Hindi and
  Telugu turns.
- Fonts are system fonts (`fonts-inter`, `fonts-noto-core`): the Remotion headless browser cannot fetch
  Google Fonts through this environment's proxy.
- Skills followed: `remotion-dev/skills` and `digitalsamba/claude-code-video-toolkit` (playwright-recording,
  ffmpeg, motion-craft: blur-in titles, no bounce on UI, read-time holds).

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

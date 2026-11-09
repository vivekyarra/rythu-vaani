"""Record the real Rythu Vaani web app answering 3 synthetic Telugu calls.

Chrome's fake microphone plays each Timbre-generated question into the app's Record button,
so the run goes through the real path: browser mic -> /api/call -> Prisma STT -> NLU -> Timbre TTS.
The reply audio returned by that same call is saved so it can be synced over the silent screen video.
"""
import base64, json, time, wave, pathlib, shutil
import sys
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')

D = pathlib.Path(__file__).parent
URL = "http://127.0.0.1:8000/"
CALLS = [
    {"id": "q1_price", "phone": False, "snr": None},
    {"id": "q2_loan", "phone": True, "snr": "5"},
    {"id": "q3_pest", "phone": False, "snr": None},
]

CURSOR_JS = r"""
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__cursor';
  c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.5L16 20l-3 1.5-3.5-7.5L4 18z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position:'fixed', left:'-50px', top:'-50px', zIndex:2147483647, pointerEvents:'none', transition:'none'});
  document.body.appendChild(c);
  const ring = document.createElement('div');
  Object.assign(ring.style, {position:'fixed', width:'44px', height:'44px', borderRadius:'50%', border:'3px solid #2f7d32',
    zIndex:2147483646, pointerEvents:'none', opacity:0});
  document.body.appendChild(ring);
  document.addEventListener('mousemove', e => { c.style.left = (e.clientX - 4) + 'px'; c.style.top = (e.clientY - 2) + 'px'; });
  document.addEventListener('mousedown', e => {
    ring.style.left = (e.clientX - 22) + 'px'; ring.style.top = (e.clientY - 22) + 'px';
    ring.animate([{opacity:.9, transform:'scale(.4)'}, {opacity:0, transform:'scale(1.4)'}], {duration:450});
  });
});
"""

MIC_JS = (D / "mic.js").read_text(encoding="utf-8")


BIG_CSS_JS = r"""
window.addEventListener('DOMContentLoaded', () => {
  const st = document.createElement('style');
  st.textContent = `html{font-size:25px} body{font-size:25px!important} main{max-width:1040px!important;padding:28px!important}
    .card{padding:28px!important;border-radius:20px!important} h1{font-size:2.1rem!important}
    input[type=checkbox]{width:30px;height:30px;vertical-align:middle} select{font-size:24px;padding:6px}
    input[type=file]{font-size:20px} .te{font-size:1.25rem!important} audio{height:64px}`;
  document.head.appendChild(st);
});
"""


def wav_seconds(p):
    # Timbre streams WAV with a placeholder frame count (0x7FFFFFFF), so use the file size instead.
    with wave.open(str(p)) as w:
        bytes_per_sec = w.getframerate() * w.getsampwidth() * w.getnchannels()
    return (pathlib.Path(p).stat().st_size - 44) / bytes_per_sec


def glide(page, sel, steps=25):
    box = page.locator(sel).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
    page.wait_for_timeout(250)


def record(pw, call):
    wav = D / f"{call['id']}.wav"
    dur = wav_seconds(wav)
    vid_dir = D / "rec_tmp"
    shutil.rmtree(vid_dir, ignore_errors=True)
    browser = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page_dialogs = []
    ctx = browser.new_context(viewport={"width": 1080, "height": 1920},
                              record_video_dir=str(vid_dir), record_video_size={"width": 1080, "height": 1920},
                              permissions=["microphone"])
    ctx.add_init_script(BIG_CSS_JS)
    ctx.add_init_script(CURSOR_JS)
    ctx.add_init_script("window.__CALLER_B64 = '" + base64.b64encode(wav.read_bytes()).decode() + "';")
    ctx.add_init_script(MIC_JS)
    page = ctx.new_page()
    page.on("dialog", lambda d: (print("DIALOG", d.message, flush=True), d.dismiss()))
    page.on("console", lambda m: print("CONSOLE", m.type, m.text, flush=True))
    page.on("crash", lambda p: print("CRASH", flush=True))
    t0 = time.time()
    ev = {}
    print("goto", flush=True); page.goto(URL)
    page.wait_for_function("document.getElementById('status').textContent.startsWith('LIVE')", timeout=15000)
    page.mouse.move(540, 1100)
    page.wait_for_timeout(1200)
    if call["phone"]:
        glide(page, "#phone"); page.click("#phone"); page.wait_for_timeout(400)
        glide(page, "#snr"); page.select_option("#snr", call["snr"]); page.wait_for_timeout(700)
    print("live ok", flush=True)
    glide(page, "#rec")
    page.click("#rec")
    print("rec clicked", flush=True)
    ev["rec_start"] = time.time() - t0
    time.sleep(dur + 0.4)
    print("slept", page.evaluate("document.getElementById('rec').textContent"), flush=True)
    with page.expect_response(lambda r: "/api/call" in r.url, timeout=45000) as resp_info:
        page.click("#rec")
        ev["rec_stop"] = time.time() - t0
    data = resp_info.value.json()
    print("response", data.get("mode"), data.get("transcript"), flush=True)
    ev["response"] = time.time() - t0
    page.wait_for_selector("#out:not([hidden])")
    page.evaluate("document.getElementById('out').scrollIntoView({block:'center'})")
    page.mouse.move(1040, 1880, steps=10)
    reply = base64.b64decode(data["reply_audio_wav_b64"])
    (D / f"{call['id']}_reply.wav").write_bytes(reply)
    rdur = len(reply) and wav_seconds(D / f"{call['id']}_reply.wav")
    page.wait_for_timeout(int((rdur + 1.5) * 1000))
    ev["end"] = time.time() - t0
    vpath = page.video.path()
    ctx.close(); browser.close()
    shutil.move(vpath, D / f"{call['id']}_screen.webm")
    shutil.rmtree(vid_dir, ignore_errors=True)
    return {"id": call["id"], "question_seconds": dur, "reply_seconds": rdur, "events": ev,
            "mode": data.get("mode"), "transcript": data.get("transcript"), "intent": data.get("intent"),
            "slots": data.get("slots"), "reply_te": data.get("reply_te"), "reply_en": data.get("reply_en"),
            "phone_line": call["phone"], "snr_db": call["snr"]}


import sys
ONLY = sys.argv[1:]
with sync_playwright() as pw:
    log = [record(pw, c) for c in CALLS if not ONLY or c["id"] in ONLY]
json.dump(log, open(D / "recording_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in log:
    print(r["id"], r["mode"], "|", r["transcript"], "|", r["intent"], r["slots"], "|", round(r["events"]["response"] - r["events"]["rec_stop"], 2), "s")

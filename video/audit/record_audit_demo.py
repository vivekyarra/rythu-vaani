"""Screen-record the real Vaani Audit app running on the LIVE Gnani API (Playwright, 1920x1080).

Run the service first with GNANI_API_KEY set:  python -m vaani_audit serve --port 8100
Then:  python video/audit/record_audit_demo.py

Playwright records video without sound, so every <audio> playback in the page is logged
(which file, from which second, at which moment of the recording). The Remotion composition
replays exactly those clips at exactly those moments, so what you hear is the real call audio
and the real Timbre coaching audio the app played.
"""
import json
import pathlib
import shutil
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
D = pathlib.Path(__file__).parent
PUB = D / "public"
URL = "http://127.0.0.1:8100/"
ZOOM = 1.32

INIT_JS = r"""
window.__ev = [];
window.__t0 = performance.now();
const _play = HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.play = function() {
  window.__ev.push({type:'play', src: this.src, from: this.currentTime, at: (performance.now()-window.__t0)/1000});
  this.addEventListener('pause', () => window.__ev.push({type:'pause', src: this.src, at: (performance.now()-window.__t0)/1000}), {once:true});
  return _play.call(this);
};
window.addEventListener('DOMContentLoaded', () => {
  const st = document.createElement('style');
  st.textContent = `html{zoom:%ZOOM%} *{cursor:none!important} header .sub{display:none!important}`;
  document.head.appendChild(st);
  const c = document.createElement('div');
  c.innerHTML = '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.5L16 20l-3 1.5-3.5-7.5L4 18z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position:'fixed', left:'-50px', top:'-50px', zIndex:2147483647, pointerEvents:'none'});
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = (e.clientX-4)+'px'; c.style.top = (e.clientY-2)+'px'; });
});
""".replace("%ZOOM%", str(ZOOM))


NARR = json.loads((PUB / "narration.json").read_text()) if (PUB / "narration.json").exists() else {}
TRUTH = json.loads((pathlib.Path(__file__).resolve().parents[2] / "data/audit/calls_truth.json").read_text(encoding="utf-8"))


class Rec:
    """Keeps a log of marks (seconds since the video started) and paces actions to the narration."""

    def __init__(self, page):
        self.page, self.t0, self.marks, self.busy_until = page, time.time(), [], 0.0

    def now(self):
        return time.time() - self.t0

    def mark(self, name, **kw):
        self.marks.append({"name": name, "at": round(self.now(), 2), **kw})
        print(f"{self.now():6.1f}s  {name}", flush=True)

    def say(self, key):
        """Narration line `key` starts now (it is laid over the video at this mark)."""
        self.hold()
        dur = NARR[key]["seconds"]
        self.mark("say", key=key, seconds=dur)
        self.busy_until = self.now() + dur + 0.25

    def hold(self):
        left = self.busy_until - self.now()
        if left > 0:
            self.wait(left)

    def glide(self, sel, steps=22, nth=0):
        loc = self.page.locator(sel).nth(nth)
        loc.scroll_into_view_if_needed()
        b = loc.bounding_box()
        self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=steps)
        self.page.wait_for_timeout(200)
        return loc

    def click(self, sel, nth=0):
        self.glide(sel, nth=nth).click()

    def wait(self, s):
        self.page.wait_for_timeout(int(s * 1000))


def scroll_to(page, sel, block="start"):
    page.evaluate(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{behavior:'smooth', block:'{block}'}})")
    page.wait_for_timeout(900)


def listen(r, sample, until_turn):
    """Play the real call recording in the page, from 0 to the end of turn `until_turn`."""
    end = TRUTH[sample]["turns"][until_turn]["end"] + 0.3
    r.hold()
    r.mark("listen", call=sample, seconds=end)
    r.page.evaluate("document.querySelector('#srcaudio').currentTime=0; document.querySelector('#srcaudio').play()")
    r.wait(end)
    r.page.evaluate("document.querySelector('#srcaudio').pause()")


def run_audit(r, sample):
    p = r.page
    r.mark("run", call=sample)
    with p.expect_response(lambda x: "/api/audit" in x.url, timeout=180000) as resp:
        r.click("#run")
    res = resp.value.json()
    r.mark("result", call=sample, mode="mock" if res["mock"] else "live", job_wall_s=res["stt"]["job_wall_s"],
           audit_wall_s=res.get("audit_wall_s"))
    p.wait_for_selector(".bigscore")
    return res


def coach_audio(res, category):
    rr = httpx.post(URL + "api/coach/speak", json={"category": category, "agent_id": res["agent_id"],
                                                    "language": res["language"]}, timeout=60)
    out = PUB / f"coach_{res['call_id']}_{category}.wav"
    out.write_bytes(rr.content)
    return out.name, bytes.fromhex(rr.headers["x-text"]).decode()


def hear(r, res, category, log):
    fname, text = coach_audio(res, category)
    r.hold()
    r.mark("coach", file=fname, text=text, category=category)
    r.click("[data-speak]", nth=[f["category"] for f in res["findings"]].index(category))
    r.page.wait_for_function("[...document.querySelectorAll('[data-speak]')].every(b=>!b.disabled)", timeout=60000)
    r.mark("coach_end")
    log["coach"].append({"file": fname, "call": res["call_id"], "category": category, "text": text})


def evidence(r, res, category):
    p = r.page
    seekable = [f for f in res["findings"] if f["category"] != "CALL_HOURS"]
    i = [f["category"] for f in seekable].index(category)
    f = seekable[i]
    r.hold()
    r.mark("evidence", call=res["call_id"], start=f["start"], seconds=f["end"] - f["start"] + 0.4)
    r.click("[data-seek]", nth=i)
    r.wait(0.4)
    p.evaluate("document.querySelectorAll('.finding')[%d].scrollIntoView({behavior:'smooth',block:'center'})"
               % [x["category"] for x in res["findings"]].index(category))
    r.wait(f["end"] - f["start"])
    p.evaluate("document.querySelector('#player').pause()")


def main():
    st = httpx.get(URL + "api/status").json()
    assert st["mode"] == "live", "start the server with GNANI_API_KEY set: the demo must show the live API"
    PUB.mkdir(exist_ok=True)
    tmp = D / "rec_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    log = {"live": True, "results": {}, "coach": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(tmp),
                                  record_video_size={"width": 1920, "height": 1080})
        ctx.add_init_script(INIT_JS)
        page = ctx.new_page()
        r = Rec(page)
        page.goto(URL)
        page.wait_for_selector("#agentbars .bar")
        page.mouse.move(900, 500)
        r.mark("dashboard")
        r.wait(0.8)
        r.say("d_intro")
        r.wait(2.5)
        r.click('nav button[data-tab="live"]'); r.wait(0.8)
        page.select_option("#sample", "hi_d02"); r.wait(0.5)

        # ---- 1. Hindi call: 8:15 PM, police threat, neighbourhood shaming, no grievance channel
        listen(r, "hi_d02", 2)
        r.say("d_run")
        res = run_audit(r, "hi_d02")
        log["results"]["hi_d02"] = res
        r.wait(0.8)
        r.say("d_result")
        r.wait(1.2)
        scroll_to(page, ".turns", "center")
        r.wait(2.0)
        scroll_to(page, ".finding", "start")
        evidence(r, res, "THREAT")
        r.say("d_coach")
        hear(r, res, "THREAT", log)
        r.wait(0.6)

        # ---- 2. Telugu call: farmer called a liar, tractor seizure + police threat, no grievance channel
        r.click('nav button[data-tab="live"]'); r.wait(0.6)
        page.evaluate("window.scrollTo({top:0})")
        page.select_option("#sample", "te_d02"); r.wait(0.4)
        r.say("d_telugu")
        listen(r, "te_d02", 2)
        res = run_audit(r, "te_d02")
        log["results"]["te_d02"] = res
        r.wait(0.8)
        r.say("d_telugu_res")
        scroll_to(page, ".turns", "center")
        r.wait(2.2)
        scroll_to(page, ".finding", "start")
        r.hold()

        # ---- 3. Team dashboard + coaching card
        r.click('nav button[data-tab="team"]'); r.wait(0.6)
        r.say("d_team")
        r.glide("#agentbars .bar", nth=0); r.wait(1.6)
        r.glide("#violbars .bar", nth=1); r.wait(1.6)
        r.click("[data-coach]", nth=2)
        page.wait_for_selector("#coach .finding")
        r.mark("coaching card")
        r.hold()
        r.wait(2.0)
        r.mark("end")
        events = page.evaluate("window.__ev")
        vpath = page.video.path()
        ctx.close()
        browser.close()
    shutil.move(vpath, PUB / "demo_screen.webm")
    shutil.rmtree(tmp, ignore_errors=True)
    log["marks"], log["audio_events"] = r.marks, events
    (D / "recording_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", PUB / "demo_screen.webm")


if __name__ == "__main__":
    main()

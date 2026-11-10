"""Assemble src/timeline.json for the Remotion composition from REAL inputs only:

* recording_log.json  - marks + audio playback events of the live screen recording
* public/narration.json - Timbre narration lines and their measured durations
* the newest results/audit/bench_*.json - measured benchmark numbers

    python video/audit/build_timeline.py
"""
import json
import pathlib
import re

D = pathlib.Path(__file__).parent
ROOT = D.parents[1]
PUB = D / "public"
FPS = 30
f = lambda s: int(round(s * FPS))  # noqa: E731

NARR = json.loads((PUB / "narration.json").read_text())
LOG = json.loads((D / "recording_log.json").read_text(encoding="utf-8"))
TRUTH = json.loads((ROOT / "data/audit/calls_truth.json").read_text(encoding="utf-8"))
BENCH = json.loads(sorted((ROOT / "results/audit").glob("bench_*.json"))[-1].read_text(encoding="utf-8"))
HOOK = json.loads((PUB / "hook.json").read_text())

# English translations of the synthetic call turns heard in the video (scripts in data/audit/dev_calls.json)
TRANSLATIONS = {
    "hi_d02": ["Hello, this is Amit from Navdhan Finance, about your gold-loan instalment.",
               "Why are you calling so late at night?",
               "You haven't paid for three months. Pay by tomorrow, or we'll bring the police to your house."],
    "te_d02": ["Hello, this is Suresh from Navdhan Finance, calling about your tractor-loan dues.",
               "Go on... this month's harvest money hasn't come in yet.",
               "Same excuse every time. You're a big liar."],
}
LANG = {"hi_d02": "Hindi", "te_d02": "Telugu"}
COACH_EN = {"THREAT": "I understand things are hard right now. Your EMI is pending. You can pay today, "
                      "or we can make an easy payment plan for you."}

DISPLAY = [(r"\bR B I\b", "RBI"), (r"\bA P I\b", "API"), (r"\bL L M\b", "LLM"), (r"\bA M\b", "AM"), (r"\bP M\b", "PM"),
           (r"eight AM", "8 AM"), (r"seven PM", "7 PM"), (r"eight fifteen PM", "8:15 PM"), (r"\bPrisma v3\b", "Prisma v3.0"),
           (r"one or two percent", "1–2%"), (r"point (\d\d)", r"0.\1"), (r"zero decibels", "0 dB")]


def display(text):
    for a, b in DISPLAY:
        text = re.sub(a, b, text)
    return text


def chunks(text, max_words=12):
    """Split a narration line into caption chunks at sentence / clause boundaries."""
    out = []
    for sent in re.split(r"(?<=[.!?:])\s+", display(text)):
        words = sent.split()
        while len(words) > max_words:
            cut = next((i + 1 for i in range(max_words - 1, 3, -1) if words[i].endswith(",")), max_words)
            out.append(" ".join(words[:cut]))
            words = words[cut:]
        if words:
            out.append(" ".join(words))
    return out


def narr_caps(key, start_s):
    n = NARR[key]
    parts = chunks(n["text"])
    total = sum(len(p) for p in parts)
    caps, t = [], start_s
    for p in parts:
        d = n["seconds"] * len(p) / total
        caps.append({"from": f(t), "to": f(t + d), "text": p})
        t += d
    return caps


class Cut:
    def __init__(self):
        self.t, self.scenes, self.audio, self.captions = 0.0, [], [], []

    def narr(self, key, at):
        self.audio.append({"src": f"{key}.wav", "from": f(at), "dur": f(NARR[key]["seconds"]) + 2})
        self.captions += narr_caps(key, at)
        return NARR[key]["seconds"]

    def scene(self, kind, dur, **kw):
        self.scenes.append({"kind": kind, "from": f(self.t), "dur": f(dur), **kw})
        self.t += dur

    def demo(self, a, b, crop=None, note=None):
        """Recording seconds [a, b) -> output. Narration, call audio and Timbre audio follow the log."""
        off = self.t - a
        sc = {"startFrom": f(a)}
        if crop:
            sc["crop"] = crop
        if note:
            sc["note"] = note
        self.scene("demo", b - a, **sc)
        for m in LOG["marks"]:
            if m["name"] == "say" and a <= m["at"] < b:
                self.narr(m["key"], m["at"] + off)
        ev = LOG["audio_events"]
        coach_files = iter(c["file"] for c in LOG["coach"])
        coach_map = {}
        for i, e in enumerate(ev):
            if e["type"] != "play":
                continue
            end = next((x["at"] for x in ev[i + 1:] if x["type"] == "pause" and x["src"] == e["src"]), e["at"] + 15)
            s, t = max(e["at"], a), min(end, b)
            if t <= s:
                continue
            src = e["src"]
            if "/api/calls/" in src:
                cid = src.split("/api/calls/")[1].split("/")[0]
                pos = e["from"] + (s - e["at"])
                self.audio.append({"src": f"{cid}.mp3", "from": f(s + off), "dur": f(t - s), "startFrom": f(pos)})
                for k, turn in enumerate(TRUTH[cid]["turns"]):
                    ts, te = turn["start"] - pos + s, turn["end"] - pos + s
                    if te <= s or ts >= t or k >= len(TRANSLATIONS[cid]):
                        continue
                    who = "Agent" if turn["speaker"] == "agent" else "Borrower"
                    self.captions.append({"from": f(max(ts, s) + off), "to": f(min(te, t) + off),
                                          "label": f"{who} ({LANG[cid]})", "text": TRANSLATIONS[cid][k]})
            else:  # blob: the Timbre coaching audio fetched by the page
                if src not in coach_map:
                    coach_map[src] = next(coach_files)
                fn = coach_map[src]
                c = next(c for c in LOG["coach"] if c["file"] == fn)
                self.audio.append({"src": fn, "from": f(s + off), "dur": f(t - s)})
                self.captions.append({"from": f(s + off), "to": f(t + off), "label": "Timbre, compliant version",
                                      "text": COACH_EN.get(c["category"], "")})

    def done(self):
        self.captions.sort(key=lambda c: c["from"])
        for a, b in zip(self.captions, self.captions[1:]):  # no overlaps: later caption wins
            a["to"] = min(a["to"], b["from"])
        return {"scenes": self.scenes, "audio": self.audio, "captions": [c for c in self.captions if c["to"] > c["from"]],
                "duration": f(self.t)}


def mark(name, call=None):
    return next(m["at"] for m in LOG["marks"] if m["name"] == name and (call is None or m.get("call") == call))


def say_at(key):
    return next(m["at"] for m in LOG["marks"] if m["name"] == "say" and m["key"] == key)


# ---------------------------------------------------------------- results (measured)
R = BENCH["results"]
H = "heldout"
CONDS = [("clean", "Phone line, no added noise"), ("10dB", "10 dB SNR"), ("5dB", "5 dB SNR"), ("0dB", "0 dB SNR")]


def micro(key, field="f1"):
    return R[key][H]["micro"][field]


rows = []
for c, label in CONDS:
    vals = []
    for sysk, name in (("v2.5|stereo", "Prisma v2.5"), ("v3.0+ctx|stereo", "v3.0 + keywords")):
        k = f"{sysk.split('|')[0]}|stereo|{c}"
        v = micro(k) if k in R else None
        vals.append({"sys": name, "v": v, "label": "n/a" if v is None else f"{v:.2f}"})
    rows.append({"cond": label, "vals": vals})

diar = BENCH.get("diarization", {}).get("v3.0+ctx|mono|clean", {})
oracle_f1 = R["oracle"][H]["micro"]["f1"]
lat = BENCH["latency"].get("v3.0+ctx|stereo|clean", {})
v3c, v3z = micro("v3.0+ctx|stereo|clean"), micro("v3.0+ctx|stereo|0dB")
v2c, v2z = micro("v2.5|stereo|clean"), micro("v2.5|stereo|0dB")
mono_f1 = micro("v3.0+ctx|mono|clean") if "v3.0+ctx|mono|clean" in R else None
n_held = len([t for t in TRUTH.values() if t["split"] == H])

cer = lambda k: R[k][H]["cer"]  # noqa: E731
shaming_r = R["oracle"][H]["categories"]["SHAMING"]["recall"]
nd_p = R["v3.0+ctx|stereo|clean"][H]["categories"]["NO_DISCLOSURE"]["precision"]
results = {
    "title": "Measured on the live Gnani API",
    "subtitle": f"{n_held} held-out synthetic calls, never used for tuning · micro F1 over 6 violation categories · dual-channel",
    "chartLabel": "VIOLATION DETECTION F1 (HIGHER IS BETTER)",
    "rowsAt": 0.8,
    "rows": rows,
    "factsAt": 3.5,
    "facts": [
        {"big": f"{cer('v2.5|stereo|clean'):.2f} → {cer('v3.0+ctx|stereo|clean'):.2f}",
         "small": "character error rate, Prisma v2.5 → v3.0 + keywords (phone line, no added noise)"},
        {"big": f"{oracle_f1:.2f}", "small": f"F1 of the rules on the exact script: shaming recall only {shaming_r:.2f}, "
                                            f"false 'no disclosure' flags (precision {nd_p:.2f}) are the main errors"},
        {"big": f"{diar.get('single_speaker_calls', 0)} / {diar.get('calls', 0)}",
         "small": f"mono calls where diarization found one speaker (mono F1 {mono_f1:.2f}): dual-channel recording fixes roles"},
    ],
}
f2 = lambda x: f"{x:.2f}".replace("0.", "point ")  # noqa: E731
NARR_RESULTS = (f"On {n_held} held-out calls never used for tuning, F1 is {f2(v3c)} with Prisma v3 and keywords, "
                f"and {f2(v3z)} at zero decibels. The weak spot is the rules: new ways of shaming were caught only half the time.")
NARR_CLOSE = "Every call audited, with evidence. Built solo by Yarra Vivek, on Gnani AI."

if __name__ == "__main__":
    import sys
    if "--print-narration" in sys.argv:
        print(json.dumps({"n_results": NARR_RESULTS, "n_close": NARR_CLOSE}))
        raise SystemExit
    assert LOG["live"] and all(not r["mock"] for r in LOG["results"].values()), "recording must be from the live API"
    T = {
        "hook": {"native": "“तीन महीने से पैसा नहीं दिया है। कल तक पैसे नहीं दिए तो पुलिस लेकर आपके घर आएंगे।”",
                 "english": "You haven't paid in three months. Pay by tomorrow, or we bring the police to your house.",
                 "time": "8:15 PM", "language": "HINDI", "clipSec": HOOK["seconds"], "wave": HOOK["wave"],
                 "stamps": ["Threat", "After 7 PM"], "stampAt": 3.2, "punchAt": HOOK["seconds"] + 0.3,
                 "punch": "Nobody at the bank will ever hear this call."},
        "problem": {"listAt": 0.0, "listStep": 1.6,
                    "rules": ["Identify yourself, the lender, the purpose", "Call only 8 AM – 7 PM", "No threats or intimidation",
                              "No abuse, no public shaming", "Never disclose the debt to others", "Offer a grievance channel"]},
        "title": {"tagline": "Every collection call audited. In Hindi, Telugu and code-mixed speech. With evidence.",
                  "sub": "Built on Gnani Prisma (speech-to-text) and Timbre (text-to-speech)"},
        "demoLabel": "LIVE Gnani API · real screen recording · synthetic calls",
        "arch": {"boxes": [
            {"t": "Call recording + metadata", "s": "WAV, dual-channel or mono\ncall time, agent ID", "gnani": False},
            {"t": "Gnani Prisma v3.0 Batch", "s": "each leg transcribed\nkeywords + topic\ntimestamps", "gnani": True},
            {"t": "RBI checklist rules", "s": "deterministic\nevery finding = time + verbatim quote", "gnani": False},
            {"t": "Optional LLM reviewer", "s": "may only ADD findings\nwhose quote is in the transcript", "gnani": False},
            {"t": "Scorecard · coaching", "s": "team dashboard\nGnani Timbre speaks the fix", "gnani": True}],
            "boxAt": [0.3, 2.5, 7.0, 11.0, 15.0], "noteAt": 15.5,
            "note": "Mono recordings: Prisma diarization + a documented role heuristic. Agent name check uses the dialer's agent roster."},
        "results": results,
        "close": {"line": "100% of calls audited, not 2%.",
                  "limits": "Limits: synthetic calls only (contest rule) · 12 held-out calls is a small test set ·\n"
                            "rules miss novel phrasings (see per-category table) · not legal advice.",
                  "credit": "Built solo by Yarra Vivek · Vignan's Lara Institute of Technology & Science",
                  "url": "github.com/vivekyarra/rythu-vaani · vaani_audit/"},
    }

    # ------------------------------------------------ main 16:9 cut
    m = Cut()
    m.audio.append({"src": "hook.wav", "from": 0, "dur": f(HOOK["seconds"]) + 3})
    m.scene("hook", HOOK["seconds"] + 2.0)
    t0 = m.t
    d = m.narr("n_hook", t0 + 0.2)
    d2 = m.narr("n_rules", t0 + 0.2 + d + 0.3)
    T["problem"]["listAt"] = d + 0.4
    m.scene("problem", d + d2 + 0.7)
    m.narr("n_title", m.t + 0.3)
    m.scene("title", NARR["n_title"]["seconds"] + 0.6)
    m.demo(mark("dashboard") + 0.3, mark("run", "hi_d02") + NARR["d_run"]["seconds"] + 0.3)
    wait = lambda c: next(x for x in LOG["marks"] if x["name"] == "result" and x["call"] == c)["job_wall_s"]  # noqa: E731
    m.demo(mark("result", "hi_d02") - 0.4, mark("coach_end") + 0.4, note=f"⏩ wait cut · real Prisma Batch job: {wait('hi_d02'):.0f} s")
    m.demo(say_at("d_telugu") - 0.3, mark("run", "te_d02") + 0.8)
    m.demo(mark("result", "te_d02") - 0.4, say_at("d_telugu_res") + NARR["d_telugu_res"]["seconds"] + 0.3,
           note=f"⏩ wait cut · real Prisma Batch job: {wait('te_d02'):.0f} s")
    m.demo(say_at("d_team") - 0.2, max(mark("coaching card") + 2.0, say_at("d_team") + NARR["d_team"]["seconds"] + 0.3))
    m.narr("n_arch", m.t + 0.3)
    m.scene("arch", NARR["n_arch"]["seconds"] + 0.5)
    if "n_results" in NARR:
        m.narr("n_results", m.t + 0.3)
        m.scene("results", NARR["n_results"]["seconds"] + 0.8)
    else:
        m.scene("results", 14)
    if "n_close" in NARR:
        m.narr("n_close", m.t + 0.2)
    m.scene("close", max(5.0, NARR.get("n_close", {}).get("seconds", 0) + 1.2))
    T["main"] = m.done()

    # ------------------------------------------------ vertical 9:16 cut (45-60 s)
    v = Cut()
    v.audio.append({"src": "hook.wav", "from": 0, "dur": f(HOOK["seconds"]) + 3})
    v.captions.append({"from": 0, "to": f(HOOK["seconds"]), "label": "Agent (Hindi)", "text": T["hook"]["english"]})
    v.scene("hook", HOOK["seconds"] + 2.2)
    v.scene("title", 3.2)
    crop = {"x": 90, "y": 0, "scale": 1080 / 1250}
    v.demo(mark("result", "hi_d02") - 0.9, mark("coach_end") + 0.4, crop=crop)
    v.scene("results", 9.0)
    v.scene("close", 5.0)
    T["vertical"] = v.done()

    (D / "src" / "timeline.json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
    print("main", round(T["main"]["duration"] / FPS, 1), "s  vertical", round(T["vertical"]["duration"] / FPS, 1), "s")

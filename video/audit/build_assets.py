"""Build audio assets for the demo video (needs GNANI_API_KEY): Timbre narration, real call clips.

  python video/audit/build_assets.py            # narration (cached by text) + call audio + hook clip

Narration is spoken by Gnani Timbre v3.0 (voice Tarika, en-IN). Lines whose text changed are re-synthesised.
The hook clip is cut from the real phone-line render of synthetic call hi_d02 (agent turn 2).
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rythu_vaani.audio import read_wav, write_wav  # noqa: E402

D = pathlib.Path(__file__).parent
PUB = D / "public"
VOICE = "Tarika"
FAST = {"n_hook", "n_rules", "n_title", "n_arch", "n_results", "n_close"}  # non-demo lines at Timbre speed 1.12
SPEED = 1.12

LINES = {
    "n_hook": "Calls like this are rarely caught. Compliance teams can manually audit only one or two percent of collection calls.",
    "n_rules": "R B I's rules are clear. Identify yourself and the lender. Call only from eight A M to seven P M. No threats, abuse or shaming. Never tell anyone else about the debt. And offer a grievance channel.",
    "n_title": "Vaani Audit checks every call, in Hindi, Telugu and code-mixed speech, with Gnani's Prisma speech-to-text and Timbre voices.",
    "d_intro": "This is a real run on the live Gnani A P I. First, a synthetic Hindi call, made at eight fifteen P M.",
    "d_run": "Gnani Prisma transcribes both sides of the call, agent and borrower, and timestamps every turn.",
    "d_result": "Each violation comes with the exact quote, and the second it happened. Click it, and you hear the evidence.",
    "d_coach": "For coaching, Timbre speaks the compliant way to say it, in the same language.",
    "d_telugu": "The same works in Telugu. Listen to this agent and a farmer.",
    "d_telugu_res": "He called the farmer a liar, threatened to seize his tractor, and gave no grievance channel. All flagged, with evidence.",
    "d_team": "Managers see compliance by agent, the top violation types, and a coaching card for every agent.",
    "n_arch": "Under the hood: Prisma v3 Batch transcribes each leg of the call, with domain keywords and a topic. Deterministic R B I rules produce every finding, with a timestamp and a verbatim quote. An optional L L M may only add a finding whose quote is really in the transcript.",
}


def wav_seconds(data: bytes) -> float:
    x, sr = read_wav(data)
    return len(x) / sr


def narration(extra: dict | None = None):
    from rythu_vaani.gnani import GnaniClient
    key = os.environ.get("GNANI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GNANI_API_KEY is not set: narration must be real Timbre audio")
    c = GnaniClient(key)
    meta_p = PUB / "narration.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    lines = {**LINES, **(extra or {})}
    for k, text in lines.items():
        speed = SPEED if k in FAST else 1.0
        h = hashlib.sha256(f"{VOICE}|{speed}|{text}".encode()).hexdigest()[:16]
        if meta.get(k, {}).get("hash") == h and (PUB / f"{k}.wav").exists():
            continue
        from rythu_vaani.audio import _fix_streamed_wav_sizes
        w = _fix_streamed_wav_sizes(c.synthesize(text, language="en-IN", sample_rate=24000, voice=VOICE, model="timbre-v3.0", speed=speed))
        (PUB / f"{k}.wav").write_bytes(w)
        meta[k] = {"hash": h, "text": text, "seconds": round(wav_seconds(w), 3)}
        print(k, meta[k]["seconds"], "s")
    meta_p.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return meta


def call_audio():
    truth = json.loads((ROOT / "data/audit/calls_truth.json").read_text(encoding="utf-8"))
    for cid in ("hi_d02", "te_d02"):
        shutil.copy(ROOT / f"data/audit/audio/{cid}.mp3", PUB / f"{cid}.mp3")
    # hook: the threat turn of hi_d02 from the phone-line WAV (8 kHz G.711)
    t = truth["hi_d02"]["turns"][2]
    x, sr = read_wav((ROOT / ".vaani-audit-cache/calls/clean/hi_d02.wav").read_bytes())
    clip = x[int((t["start"] - 0.05) * sr): int((t["end"] + 0.15) * sr)]
    (PUB / "hook.wav").write_bytes(write_wav(clip, sr))
    n = 90
    env = np.array([np.sqrt(np.mean(c ** 2)) for c in np.array_split(clip, n)])
    env = (env / env.max()).round(3).tolist()
    (PUB / "hook.json").write_text(json.dumps({"seconds": round(len(clip) / sr, 3), "wave": env}))


if __name__ == "__main__":
    PUB.mkdir(exist_ok=True)
    call_audio()
    narration()
    # The recording must contain the screen video as MP4 for OffthreadVideo
    webm = PUB / "demo_screen.webm"
    if webm.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-crf", "18",
                        "-preset", "medium", "-r", "30", "-pix_fmt", "yuv420p", str(PUB / "demo_screen.mp4")], check=True)
        print("converted demo_screen.mp4")

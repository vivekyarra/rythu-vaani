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
# One narrator for the whole film, always at the same speed (mixing speeds made it sound like two people).
# It must not be a voice used by an agent in the demo calls (Prakash = Amit, Devansh = Suresh).
VOICE = os.environ.get("NARRATOR_VOICE", "Avinash")
SPEED = 1.0
GAP = 0.18  # pause between caption chunks, seconds

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
    "d_card": "Open any agent, and you get their coaching card: what went wrong, and the right way to say it.",
    "n_arch": "Under the hood, Prisma v3 Batch transcribes each side of the call, with domain keywords. Deterministic R B I rules produce every finding, with a timestamp and a verbatim quote.",
}


def wav_seconds(data: bytes) -> float:
    x, sr = read_wav(data)
    return len(x) / sr


def chunks(text, max_words=12):
    """Split a line into caption-sized chunks at sentence / clause boundaries (spoken form)."""
    import re
    out = []
    for sent in re.split(r"(?<=[.!?:])\s+", text.strip()):
        words = sent.split()
        while len(words) > max_words:
            cut = next((i + 1 for i in range(max_words - 1, 3, -1) if words[i].endswith(",")), max_words)
            if len(words) - cut <= 3:  # never leave a 1-3 word tail on its own (e.g. "calls.")
                break
            out.append(" ".join(words[:cut]))
            words = words[cut:]
        if words:
            out.append(" ".join(words))
    return out


def trim_silence(x, sr, thresh=0.01, pad=0.04):
    """Cut leading/trailing silence so chunk timings are the speech itself."""
    idx = np.where(np.abs(x) > thresh * max(1e-9, np.abs(x).max()))[0]
    if len(idx) == 0:
        return x
    a, b = max(0, idx[0] - int(pad * sr)), min(len(x), idx[-1] + int(pad * sr))
    return x[a:b]


def narration(extra: dict | None = None):
    """Each caption chunk is synthesised on its own and joined with a short pause, so every
    subtitle starts and ends exactly with its words (chunk timings are stored in narration.json)."""
    from rythu_vaani.audio import _fix_streamed_wav_sizes
    from rythu_vaani.gnani import GnaniClient
    key = os.environ.get("GNANI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GNANI_API_KEY is not set: narration must be real Timbre audio")
    c = GnaniClient(key)
    meta_p = PUB / "narration.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    lines = {**LINES, **(extra or {})}
    for k, text in lines.items():
        h = hashlib.sha256(f"{VOICE}|{SPEED}|{GAP}|{chunks(text)}".encode()).hexdigest()[:16]
        if meta.get(k, {}).get("hash") == h and (PUB / f"{k}.wav").exists():
            continue
        parts, segs, sr = [], [], None
        for ch in chunks(text):
            w = _fix_streamed_wav_sizes(c.synthesize(ch, language="en-IN", sample_rate=24000, voice=VOICE,
                                                     model="timbre-v3.0", speed=SPEED))
            x, sr = read_wav(w)
            x = trim_silence(x, sr)
            segs.append({"text": ch, "seconds": round(len(x) / sr, 3)})
            parts += [x, np.zeros(int(GAP * sr))]
        audio = np.concatenate(parts[:-1])
        (PUB / f"{k}.wav").write_bytes(write_wav(audio, sr))
        meta[k] = {"hash": h, "voice": VOICE, "text": text, "seconds": round(len(audio) / sr, 3),
                   "gap": GAP, "chunks": segs}
        print(k, meta[k]["seconds"], "s", len(segs), "chunks")
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
    if (ROOT / ".vaani-audit-cache/calls/clean/hi_d02.wav").exists():
        call_audio()
    else:  # the phone-line render cache is not in git; the committed call clips are reused
        assert all((PUB / n).exists() for n in ("hi_d02.mp3", "te_d02.mp3", "hook.wav", "hook.json"))
    # n_results / n_close are written from the measured benchmark numbers in build_timeline.py
    extra = json.loads(subprocess.run([sys.executable, str(D / "build_timeline.py"), "--print-narration"],
                                      capture_output=True, text=True, check=True).stdout)
    narration(extra)
    # The recording must contain the screen video as MP4 for OffthreadVideo
    webm = PUB / "demo_screen.webm"
    if webm.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-crf", "18",
                        "-preset", "medium", "-r", "30", "-pix_fmt", "yuv420p", str(PUB / "demo_screen.mp4")], check=True)
        print("converted demo_screen.mp4")

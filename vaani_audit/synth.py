"""Build the SYNTHETIC call dataset: voice each scripted turn with Gnani Timbre, mix two voices into
one call, record ground-truth turn spans, then simulate the phone line at several noise levels.

* Agent voice: from the roster (Timbre v3.0 voices described by Gnani as "for collections and BFSI").
* Borrower-side voice: a different Timbre v3.0 voice, chosen deterministically per call.
* ``style: angry`` agent turns get Timbre v3.0's ``<shouting>`` audio tag.
* Turn gaps 0.35-0.75 s (seeded). Ground-truth start/end of every turn is measured from the actual
  sample counts of the rendered audio (Timbre WAV headers carry a placeholder frame count, so lengths
  are computed from the PCM payload, see rythu_vaani.audio._fix_streamed_wav_sizes).
* Phone line: rythu_vaani.audio.degrade_to_phone (8 kHz, 300-3400 Hz, G.711 mu-law, pink noise).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zlib
from pathlib import Path

import numpy as np

from rythu_vaani.audio import degrade_to_phone, power, read_wav, resample, write_wav

from . import config

SR = 16000
TTS_MODEL = "timbre-v3.0"
CH_AGENT, CH_BORROWER = "ch0", "ch1"  # dual-channel convention: channel 0 = agent leg, channel 1 = customer leg
CONDITIONS = {"clean": None, "10dB": 10.0, "5dB": 5.0, "0dB": 0.0}  # "clean" = phone line, no added noise
TTS_LANG = {"hi-IN": "hi-IN", "hi-en": "hi-IN", "te-IN": "te-IN", "te-en": "te-IN"}


def load_scripts(split: str | None = None) -> list[dict]:
    calls = []
    for f in ("dev_calls.json", "heldout_calls.json"):
        p = config.DATA / f
        if p.exists():
            calls += json.loads(p.read_text(encoding="utf-8"))
    return [c for c in calls if split in (None, c["split"])]


def borrower_voice(call: dict) -> str:
    voices = config.roster()["borrower_voices"]
    ag = config.agent(call["agent_id"])
    pool = voices["m"] if ag.get("gender") == "f" else voices["f"] + voices["m"]
    return pool[zlib.crc32(call["id"].encode()) % len(pool)]


def _tts_cached(tts, text: str, voice: str, language: str) -> np.ndarray:
    key = hashlib.sha256(f"{TTS_MODEL}|{voice}|{language}|{text}".encode()).hexdigest()[:24]
    path = config.CACHE / "tts" / f"{key}.wav"
    if path.exists() and not getattr(tts, "mock", False):
        data = path.read_bytes()
    else:
        data = tts.synthesize(text, language=language, sample_rate=SR, voice=voice, model=TTS_MODEL)
        if not getattr(tts, "mock", False):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    x, sr = read_wav(data)
    return resample(x, sr, SR)


def _level(x: np.ndarray, dbfs: float) -> np.ndarray:
    p = power(x)
    return x if p == 0 else (x * np.sqrt(10 ** (dbfs / 10) / p)).astype(np.float32)


def render_call(call: dict, tts, tracks: bool = False):
    """Mono mix + ground-truth spans. With ``tracks=True`` also the agent-only and borrower-only legs
    (same length, silence where the other party speaks), i.e. a dual-channel recording."""
    rng = np.random.default_rng(zlib.crc32(call["id"].encode()))
    ag_voice, b_voice = config.agent(call["agent_id"])["voice"], borrower_voice(call)
    lang = TTS_LANG[call["language"]]
    parts, spans, t = [np.zeros(int(0.4 * SR), np.float32)], [], 0.4
    legs = {"agent": [parts[0]], "borrower": [parts[0]]}
    for i, turn in enumerate(call["turns"]):
        is_agent = turn["speaker"] == "agent"
        text = turn["text"]
        if is_agent and turn.get("style") == "angry":
            text = "<shouting> " + text
        x = _tts_cached(tts, text, ag_voice if is_agent else b_voice, lang)
        x = _level(x, -20.0 if is_agent else -22.0)
        spans.append({"turn": i, "speaker": turn["speaker"], "start": round(t, 3),
                      "end": round(t + len(x) / SR, 3), "text": turn["text"]})
        gap = float(rng.uniform(0.35, 0.75))
        parts += [x, np.zeros(int(gap * SR), np.float32)]
        for who, leg in legs.items():
            leg += [x if who == turn["speaker"] else np.zeros_like(x), np.zeros(int(gap * SR), np.float32)]
        t += len(x) / SR + gap
    mix = np.concatenate(parts)
    peak = float(np.max(np.abs(mix)))
    gain = 0.95 / peak if peak > 0.95 else 1.0
    mix = (mix * gain).astype(np.float32)
    if tracks:
        return mix, spans, {k: (np.concatenate(v) * gain).astype(np.float32) for k, v in legs.items()}
    return mix, spans


def build(calls: list[dict] | None = None, tts=None, out: Path | None = None, mp3: bool = True) -> dict:
    """Render every call and every phone condition. Returns {call_id: truth} and writes truth JSON."""
    calls = calls or load_scripts()
    tts = tts or config.tts_client()
    out = out or config.CACHE / "calls"
    truth = {}
    for call in calls:
        mix, spans, legs = render_call(call, tts, tracks=True)
        for cond, snr in CONDITIONS.items():
            y = degrade_to_phone(mix, SR, snr, noise="pink", seed=zlib.crc32(f"{call['id']}{cond}".encode()))
            p = out / cond / f"{call['id']}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(write_wav(y, 8000))
            # dual-channel recording: each leg gets its own phone line and its own noise
            chans = []
            for ch, who in ((CH_AGENT, "agent"), (CH_BORROWER, "borrower")):
                yc = degrade_to_phone(legs[who], SR, snr, noise="pink",
                                      seed=zlib.crc32(f"{call['id']}{cond}{who}".encode()))
                (out / cond / f"{call['id']}.{ch}.wav").write_bytes(write_wav(yc, 8000))
                chans.append(yc)
            (out / cond / f"{call['id']}.stereo.wav").write_bytes(write_stereo(np.stack(chans, axis=1), 8000))
        if mp3 and not getattr(tts, "mock", False):
            config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "clean" / f"{call['id']}.wav"),
                            "-ac", "1", "-b:a", "32k", str(config.AUDIO_DIR / f"{call['id']}.mp3")], check=True)
        truth[call["id"]] = {
            "id": call["id"], "split": call["split"], "language": call["language"],
            "agent_id": call["agent_id"], "call_time": call["call_time"], "summary": call.get("summary", ""),
            "voices": {"agent": config.agent(call["agent_id"])["voice"], "borrower": borrower_voice(call),
                       "model": TTS_MODEL},
            "duration_s": round(len(mix) / SR, 2), "turns": spans, "labels": call["labels"],
            "mock_audio": bool(getattr(tts, "mock", False)),
        }
    return truth


def write_stereo(x: np.ndarray, sr: int) -> bytes:
    import io
    from scipy.io import wavfile
    buf = io.BytesIO()
    wavfile.write(buf, sr, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    return buf.getvalue()


def split_stereo(data: bytes) -> tuple[bytes, bytes] | None:
    """Stereo WAV -> (channel 0 WAV, channel 1 WAV); None for mono input."""
    import io
    from scipy.io import wavfile
    from rythu_vaani.audio import _fix_streamed_wav_sizes
    try:
        sr, x = wavfile.read(io.BytesIO(_fix_streamed_wav_sizes(data)))
    except Exception:  # not a parseable WAV: let Prisma (or the mock) decide
        return None
    if x.ndim != 2 or x.shape[1] < 2:
        return None
    x = x.astype(np.float32) / (32768.0 if x.dtype == np.int16 else 1.0)
    return write_wav(x[:, 0], sr), write_wav(x[:, 1], sr)


def truth_path() -> Path:
    return config.DATA / "calls_truth.json"


def load_truth() -> dict:
    return json.loads(truth_path().read_text(encoding="utf-8"))


def script_segments(t: dict):
    """Ground-truth script as Prisma-like segments (used by the oracle evaluation and MOCK mode)."""
    from .prisma import Segment
    return [Segment(s["start"], s["end"], s["text"], 1 if s["speaker"] == "agent" else 2)
            for s in t["turns"]]

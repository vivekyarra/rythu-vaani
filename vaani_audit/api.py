"""FastAPI service + web dashboard for Vaani Audit.

    uvicorn vaani_audit.api:app --port 8100

Without GNANI_API_KEY the service runs in MOCK mode: it never calls Gnani, transcripts of sample
calls are their scripts, coaching audio is beeps, and every response says ``"mode": "mock"``.
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from . import config, store
from .audit import audit_audio
from .coaching import TTS_LANG, lang_key, rephrase
from .prisma import MODEL_V3

WEB = Path(__file__).parent / "web"
UPLOADS = config.CACHE / "uploads"
app = FastAPI(title="Vaani Audit", version="0.1.0")


def mode() -> str:
    return "mock" if config.is_mock() else "live"


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {"mode": mode(), "stt": f"Gnani Prisma Batch {MODEL_V3} (diarization, keywords, topic)",
            "tts": "Gnani Timbre v3.0", "synthetic_data": True, "calls": len(store.load_all())}


@app.get("/api/calls")
def calls():
    return [store.summary(a) for a in store.load_all()]


@app.get("/api/calls/{call_id}")
def call(call_id: str):
    a = store.get(call_id)
    if not a:
        raise HTTPException(404, "no such call")
    return a


@app.get("/api/calls/{call_id}/audio")
def call_audio(call_id: str):
    if not store._SAFE.match(call_id):
        raise HTTPException(404)
    for p, mt in ((config.AUDIO_DIR / f"{call_id}.mp3", "audio/mpeg"), (UPLOADS / f"{call_id}.wav", "audio/wav"),
                  (config.CACHE / "calls" / "clean" / f"{call_id}.wav", "audio/wav")):
        if p.exists():
            return FileResponse(p, media_type=mt)
    raise HTTPException(404, "no audio for this call")


@app.get("/api/dashboard")
def dashboard():
    return {"mode": mode(), **store.team(store.load_all())}


@app.get("/api/agents/{agent_id}/coaching")
def agent_coaching(agent_id: str):
    return store.coaching(agent_id, store.load_all())


@app.get("/api/samples")
def samples():
    """Synthetic sample calls that can be (re-)audited live from the UI."""
    from .synth import load_scripts
    out = []
    for c in load_scripts():
        if (config.AUDIO_DIR / f"{c['id']}.mp3").exists() or (config.CACHE / "calls" / "clean" / f"{c['id']}.wav").exists():
            out.append({"id": c["id"], "language": c["language"], "agent_id": c["agent_id"],
                        "call_time": c["call_time"], "summary": c.get("summary", ""), "split": c["split"]})
    return out


def _sample_wav(sample_id: str) -> bytes:
    wav = config.CACHE / "calls" / "clean" / f"{sample_id}.stereo.wav"  # dual-channel recording
    if wav.exists():
        return wav.read_bytes()
    mp3 = config.AUDIO_DIR / f"{sample_id}.mp3"
    if not mp3.exists():
        raise HTTPException(404, "no such sample")
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp3), "-ar", "8000", "-ac", "1", "-f", "wav", "-"],
                          capture_output=True, check=True).stdout


@app.post("/api/audit")
async def audit(file: UploadFile | None = File(None), sample_id: str = Form(""), agent_id: str = Form(...),
                language: str = Form(...), call_time: str = Form(""), call_id: str = Form("")):
    if language not in TTS_LANG and language not in ("hi-IN", "te-IN"):
        raise HTTPException(400, "language must be hi-IN, te-IN, hi-en or te-en")
    mock_script = None
    if file is not None:
        audio = await file.read()
        if not audio.startswith(b"RIFF"):
            raise HTTPException(400, "upload a WAV file")
    elif sample_id:
        audio = _sample_wav(sample_id)
        if config.is_mock():
            from .synth import load_truth, script_segments
            mock_script = script_segments(load_truth()[sample_id])
    else:
        raise HTTPException(400, "send a WAV file or a sample_id")
    # re-auditing a sample replaces its stored audit (keeps team numbers honest); uploads get a new id
    cid = call_id or sample_id or f"upload-{time.strftime('%Y%m%d-%H%M%S')}"
    if not store._SAFE.match(cid):
        raise HTTPException(400, "bad call_id")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / f"{cid}.wav").write_bytes(audio)
    t0 = time.monotonic()
    result = audit_audio(audio, {"call_id": cid, "agent_id": agent_id, "language": language,
                                 "call_time": call_time or None, "synthetic": True},
                         mock_script=mock_script)
    result["audit_wall_s"] = round(time.monotonic() - t0, 2)
    store.save(result)
    return result


class SpeakReq(BaseModel):
    category: str
    agent_id: str
    language: str


@app.post("/api/coach/speak")
def coach_speak(req: SpeakReq):
    ag = config.agent(req.agent_id)
    try:
        text = rephrase(req.category, req.language, ag["name"], config.lender()["name"], ag.get("gender", "m"))
    except KeyError:
        raise HTTPException(400, "unknown category")
    voice = config.roster()["coach_voice"][ag.get("gender", "m")]
    key = hashlib.sha256(f"{voice}|{req.language}|{text}|{mode()}".encode()).hexdigest()[:20]
    p = config.CACHE / "coach" / f"{key}.wav"
    if not p.exists():
        tts = config.tts_client()
        data = tts.synthesize(text, language=TTS_LANG[lang_key(req.language)], sample_rate=24000,
                              voice=voice, model="timbre-v3.0")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    from rythu_vaani.audio import _fix_streamed_wav_sizes
    return Response(_fix_streamed_wav_sizes(p.read_bytes()), media_type="audio/wav",
                    headers={"X-Mode": mode(), "X-Text": text.encode("utf-8").hex()})

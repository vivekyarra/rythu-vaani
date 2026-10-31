"""FastAPI app: `uvicorn rythu_vaani.api:app --reload`, then open http://127.0.0.1:8000"""
from __future__ import annotations

import base64

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import gnani
from .config import ROOT, get_client
from .gnani import GnaniError
from .pipeline import CallResult, PipelineError, handle_audio, handle_text

app = FastAPI(title="Rythu Vaani", description="Telugu voice helpline for farmers (Gnani Prisma + Timbre)")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def client_dep():
    return get_client()


class TextQuery(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def _payload(res: CallResult) -> dict:
    d = res.to_dict()
    d["reply_audio_wav_b64"] = base64.b64encode(res.reply_wav).decode()
    if res.mode == "MOCK":
        d["notice"] = ("MOCK MODE: no GNANI_API_KEY set. The transcript is a typed/sample hint, not speech "
                       "recognition, and the reply audio is beeps, not Timbre speech.")
    return d


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/status")
def status(client=Depends(client_dep)):
    return {
        "mode": "MOCK" if client.mock else "real",
        "stt_model": gnani.STT_MODEL,
        "tts_model": gnani.TTS_MODEL,
        "tts_voice": gnani.TTS_VOICE,
        "language": gnani.LANGUAGE,
    }


@app.post("/api/text")
def ask_text(q: TextQuery, client=Depends(client_dep)):
    try:
        return _payload(handle_text(q.text, client))
    except GnaniError as exc:
        raise HTTPException(502, f"Gnani API error: {exc}") from exc


@app.post("/api/call")
async def ask_audio(
    audio: UploadFile = File(...),
    phone_line: bool = Form(False),
    snr_db: float | None = Form(None),
    mock_transcript: str | None = Form(None),
    client=Depends(client_dep),
):
    data = await audio.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "upload too large")
    try:
        res = handle_audio(data, client, audio.filename or "audio.wav", phone_line=phone_line,
                           snr_db=snr_db, mock_hint=mock_transcript)
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    except GnaniError as exc:
        raise HTTPException(502, f"Gnani API error: {exc}") from exc
    return _payload(res)

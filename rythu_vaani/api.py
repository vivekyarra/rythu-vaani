"""FastAPI app: `uvicorn rythu_vaani.api:app --reload`, then open http://127.0.0.1:8000"""
from __future__ import annotations

import base64
import hmac
import json

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import gnani
from .config import ROOT, get_client
from .gnani import GnaniError
from .pipeline import CallResult, PipelineError, handle_audio, handle_text
from .whatsapp import WhatsAppBot, WhatsAppClient, WhatsAppSettings, parse_webhook, verify_signature

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
        "stt_model": gnani.STT_MODEL_V3,
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


# ---- WhatsApp channel (see rythu_vaani/whatsapp.py and WHATSAPP.md) ----

_bot: WhatsAppBot | None = None


def whatsapp_bot_dep() -> WhatsAppBot:
    global _bot
    if _bot is None:
        settings = WhatsAppSettings.from_env()
        if settings is None:
            raise HTTPException(503, "WhatsApp is not configured (set the WHATSAPP_* variables in .env)")
        _bot = WhatsAppBot(WhatsAppClient(settings), get_client())
    return _bot


@app.get("/whatsapp/webhook", response_class=PlainTextResponse)
def whatsapp_verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    settings = WhatsAppSettings.from_env()
    if settings is None:
        raise HTTPException(503, "WhatsApp is not configured")
    if mode == "subscribe" and hmac.compare_digest(token, settings.verify_token):
        return challenge
    raise HTTPException(403, "verification failed")


@app.post("/whatsapp/webhook")
async def whatsapp_incoming(request: Request, tasks: BackgroundTasks, bot: WhatsAppBot = Depends(whatsapp_bot_dep)):
    body = await request.body()
    if not verify_signature(bot.wa._s.app_secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise HTTPException(400, "body is not JSON") from exc
    # Answer Meta straight away (it retries slow webhooks); do the speech work afterwards.
    for msg in parse_webhook(payload):
        if bot.is_new(msg.id):
            tasks.add_task(bot.handle, msg)
    return {"ok": True}

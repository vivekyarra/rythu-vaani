"""WhatsApp channel: a farmer sends a Telugu voice note (or text) and gets a Telugu voice note back.

Uses the WhatsApp Business Cloud API (Meta Graph API):
  * webhook verification: GET ?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
  * incoming messages:    POST JSON, signed with X-Hub-Signature-256 (HMAC-SHA256 of the raw body)
  * download a voice note: GET /{media_id} -> {"url"}, then GET url (both with the bearer token)
  * reply:                 POST /{phone_number_id}/media (upload OGG Opus), then /messages (audio + text)

WhatsApp voice notes are OGG Opus. Prisma v3.0 accepts them as they are, and Timbre can return
OGG Opus, so no audio conversion happens anywhere.

Settings (environment / .env only, never in code):
  WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET,
  optional GRAPH_API_VERSION (default below).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from .gnani import GnaniError
from .kb import KnowledgeBase, default_kb
from .pipeline import CallResult, PipelineError, handle_audio, handle_text

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com"
DEFAULT_GRAPH_VERSION = "v21.0"
MAX_TEXT_CHARS = 500  # same cap as the web API

NOT_UNDERSTOOD_TE = ("క్షమించండి, మీ వాయిస్ మెసేజ్ సరిగ్గా అందలేదు. "
                     "30 సెకన్ల లోపు, పంట పేరు చెప్పి మళ్ళీ అడగండి.")
UNSUPPORTED_TE = "నమస్కారం! దయచేసి మీ ప్రశ్నను వాయిస్ మెసేజ్‌గా లేదా టెక్స్ట్‌గా పంపండి."


@dataclass
class WhatsAppSettings:
    token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    graph_version: str = DEFAULT_GRAPH_VERSION

    @classmethod
    def from_env(cls) -> "WhatsAppSettings | None":
        vals = {k: os.environ.get(k, "").strip() for k in
                ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET")}
        if not all(vals.values()):
            return None
        return cls(vals["WHATSAPP_TOKEN"], vals["WHATSAPP_PHONE_NUMBER_ID"], vals["WHATSAPP_VERIFY_TOKEN"],
                   vals["WHATSAPP_APP_SECRET"], os.environ.get("GRAPH_API_VERSION", "").strip()
                   or DEFAULT_GRAPH_VERSION)


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header ("sha256=<hex>") against the raw request body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass
class IncomingMessage:
    id: str
    sender: str  # WhatsApp ID (phone number without +)
    type: str  # "text", "audio", or anything else WhatsApp sends
    text: str | None = None
    media_id: str | None = None
    mime_type: str | None = None


def parse_webhook(payload: dict) -> list[IncomingMessage]:
    """Messages from a webhook payload. Delivery/read status updates are ignored."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []) or []:
                audio = m.get("audio") or {}
                out.append(IncomingMessage(
                    id=m.get("id", ""), sender=m.get("from", ""), type=m.get("type", ""),
                    text=(m.get("text") or {}).get("body"),
                    media_id=audio.get("id"), mime_type=audio.get("mime_type"),
                ))
    return out


class WhatsAppClient:
    def __init__(self, settings: WhatsAppSettings, http: httpx.Client | None = None):
        self._s = settings
        self._http = http or httpx.Client(timeout=30)
        self._auth = {"Authorization": f"Bearer {settings.token}"}
        self._base = f"{GRAPH_BASE}/{settings.graph_version}"

    def _check(self, resp: httpx.Response, what: str) -> httpx.Response:
        if resp.status_code >= 400:
            raise WhatsAppError(f"{what}: HTTP {resp.status_code}: {resp.text[:300]}")
        return resp

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = self._check(self._http.get(f"{self._base}/{media_id}", headers=self._auth), "media lookup").json()
        data = self._check(self._http.get(meta["url"], headers=self._auth), "media download").content
        return data, meta.get("mime_type", "")

    def upload_media(self, data: bytes, mime_type: str, filename: str) -> str:
        resp = self._http.post(f"{self._base}/{self._s.phone_number_id}/media", headers=self._auth,
                               files={"file": (filename, data, mime_type)},
                               data={"messaging_product": "whatsapp", "type": mime_type})
        return self._check(resp, "media upload").json()["id"]

    def _send(self, body: dict, what: str) -> dict:
        resp = self._http.post(f"{self._base}/{self._s.phone_number_id}/messages", headers=self._auth,
                               json={"messaging_product": "whatsapp", **body})
        return self._check(resp, what).json()

    def mark_read(self, message_id: str) -> None:
        self._send({"status": "read", "message_id": message_id}, "mark read")

    def send_text(self, to: str, body: str) -> dict:
        return self._send({"recipient_type": "individual", "to": to, "type": "text",
                           "text": {"body": body}}, "send text")

    def send_audio(self, to: str, media_id: str) -> dict:
        return self._send({"recipient_type": "individual", "to": to, "type": "audio",
                           "audio": {"id": media_id}}, "send audio")


class WhatsAppError(RuntimeError):
    pass


def format_reply(res: CallResult, heard: bool) -> str:
    """Text that goes with the voice reply: what we heard, the Telugu answer, and an English gloss."""
    parts = [f"🎤 మీరు అడిగింది: {res.transcript}"] if heard else []
    parts += [res.reply_te, f"_{res.reply_en}_"]
    if res.mode == "MOCK":
        parts.insert(0, "[MOCK MODE: no Gnani key on the server. This is not a real transcription.]")
    return "\n\n".join(parts)


class WhatsAppBot:
    """Turns one incoming message into a text reply plus a Timbre voice note."""

    def __init__(self, wa: WhatsAppClient, gnani_client, kb: KnowledgeBase | None = None, seen_cap: int = 1000):
        self.wa = wa
        self.gnani = gnani_client
        self.kb = kb or default_kb()
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._seen_cap = seen_cap
        # Gnani allows one active request per key: serialise calls rather than trip 429s.
        self._lock = threading.Lock()

    def is_new(self, message_id: str) -> bool:
        """Meta can deliver the same webhook more than once; answer each message once."""
        with self._lock:
            if message_id in self._seen:
                return False
            self._seen[message_id] = None
            if len(self._seen) > self._seen_cap:
                self._seen.popitem(last=False)
            return True

    def handle(self, msg: IncomingMessage) -> None:
        try:
            self.wa.mark_read(msg.id)
        except WhatsAppError as exc:  # cosmetic only, keep going
            log.warning("mark_read failed: %s", exc)
        with self._lock:
            try:
                res, heard = self._answer(msg)
            except (GnaniError, PipelineError) as exc:
                log.warning("could not answer %s: %s", msg.id, exc)
                self.wa.send_text(msg.sender, NOT_UNDERSTOOD_TE)
                return
        if res is None:
            self.wa.send_text(msg.sender, UNSUPPORTED_TE)
            return
        self.wa.send_text(msg.sender, format_reply(res, heard))
        if res.mode != "MOCK":  # mock audio is beeps: never send it as if it were speech
            media_id = self.wa.upload_media(res.reply_wav, "audio/ogg", "rythu_vaani_reply.ogg")
            self.wa.send_audio(msg.sender, media_id)

    def _answer(self, msg: IncomingMessage) -> tuple[CallResult | None, bool]:
        if msg.type == "text" and msg.text and msg.text.strip():
            return handle_text(msg.text.strip()[:MAX_TEXT_CHARS], self.gnani, self.kb, tts_container="ogg"), False
        if msg.type == "audio" and msg.media_id:
            data, mime = self.wa.download_media(msg.media_id)
            filename = "voice.ogg" if "ogg" in (mime or msg.mime_type or "ogg") else "voice.bin"
            return handle_audio(data, self.gnani, filename, kb=self.kb, tts_container="ogg"), True
        return None, False

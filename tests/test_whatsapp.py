import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from rythu_vaani import api
from rythu_vaani.gnani import GnaniError, MockGnaniClient, STTResult
from rythu_vaani.whatsapp import (NOT_UNDERSTOOD_TE, UNSUPPORTED_TE, IncomingMessage, WhatsAppBot, WhatsAppClient,
                                  WhatsAppSettings, parse_webhook, verify_signature)

SETTINGS = WhatsAppSettings("tok", "PNID", "verify-me", "app-secret", "v21.0")
OGG = b"OggS fake opus reply"


def sign(body: bytes, secret: str = "app-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def webhook(*messages, statuses=()):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"},
        "messages": list(messages), "statuses": list(statuses)}}]}]}


AUDIO_MSG = {"from": "919000000001", "id": "wamid.A1", "type": "audio",
             "audio": {"id": "MEDIA1", "mime_type": "audio/ogg; codecs=opus", "voice": True}}
TEXT_MSG = {"from": "919000000001", "id": "wamid.T1", "type": "text", "text": {"body": "గుంటూరులో మిర్చి ధర ఎంత"}}


class FakeGraph:
    """Records every Graph API call and answers like the Cloud API does."""

    def __init__(self):
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path, request))
        assert request.headers["authorization"] == "Bearer tok"
        if request.method == "GET" and path == "/v21.0/MEDIA1":
            return httpx.Response(200, json={"url": "https://lookaside.example/MEDIA1", "mime_type": "audio/ogg"})
        if request.method == "GET" and request.url.host == "lookaside.example":
            return httpx.Response(200, content=b"OggS caller voice note")
        if path == "/v21.0/PNID/media":
            return httpx.Response(200, json={"id": "UPLOADED1"})
        if path == "/v21.0/PNID/messages":
            return httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]})
        return httpx.Response(404, json={"error": "unexpected"})

    def sent(self):
        return [json.loads(r.content) for m, p, r in self.calls if p.endswith("/messages")]


class FakeRealGnani:
    """Stands in for the real client (mock=False) without touching the network."""

    mock = False

    def __init__(self, transcript="గుంటూరులో మిర్చి ధర ఎంత", fail=False):
        self.transcript, self.fail, self.stt_calls, self.tts_calls = transcript, fail, [], []

    def transcribe(self, audio, filename="audio.wav", **kw):
        if self.fail:
            raise GnaniError("HTTP 400: audio too long", 400)
        self.stt_calls.append((audio, filename, kw))
        return STTResult(self.transcript, kw.get("model") or "prisma-v2.5", "r1")

    def synthesize(self, text, language="te-IN", sample_rate=8000, container="wav"):
        self.tts_calls.append((text, sample_rate, container))
        return OGG


def make_bot(gnani_client):
    graph = FakeGraph()
    wa = WhatsAppClient(SETTINGS, http=httpx.Client(transport=httpx.MockTransport(graph)))
    return WhatsAppBot(wa, gnani_client), graph


def test_signature():
    body = b'{"x":1}'
    assert verify_signature("app-secret", body, sign(body))
    assert not verify_signature("app-secret", body, sign(body, "other"))
    assert not verify_signature("app-secret", body + b" ", sign(body))
    assert not verify_signature("app-secret", body, None)


def test_parse_webhook_ignores_status_updates():
    msgs = parse_webhook(webhook(AUDIO_MSG, TEXT_MSG, statuses=[{"id": "wamid.X", "status": "read"}]))
    assert [(m.type, m.media_id, m.text) for m in msgs] == [
        ("audio", "MEDIA1", None), ("text", None, "గుంటూరులో మిర్చి ధర ఎంత")]
    assert parse_webhook(webhook(statuses=[{"id": "s"}])) == []


def test_voice_note_round_trip():
    gn = FakeRealGnani()
    bot, graph = make_bot(gn)
    bot.handle(parse_webhook(webhook(AUDIO_MSG))[0])

    audio, filename, kw = gn.stt_calls[0]
    assert audio == b"OggS caller voice note" and filename == "voice.ogg"  # sent to Prisma as-is
    assert kw["model"] == "prisma-v3.0" and kw["keyterms"] and kw["topic"]
    assert gn.tts_calls[0][2] == "ogg"  # Timbre returns OGG Opus, no conversion

    sent = graph.sent()
    assert sent[0] == {"messaging_product": "whatsapp", "status": "read", "message_id": "wamid.A1"}
    text = sent[1]["text"]["body"]
    assert sent[1]["to"] == "919000000001" and "మిర్చి" in text and "14,200" in text and "🎤" in text
    assert sent[2]["type"] == "audio" and sent[2]["audio"] == {"id": "UPLOADED1"}
    upload = next(r for m, p, r in graph.calls if p.endswith("/media"))
    assert b"audio/ogg" in upload.content and OGG in upload.content


def test_text_message_gets_voice_reply_without_transcript_line():
    gn = FakeRealGnani()
    bot, graph = make_bot(gn)
    bot.handle(parse_webhook(webhook(TEXT_MSG))[0])
    assert gn.stt_calls == []
    sent = graph.sent()
    assert "🎤" not in sent[1]["text"]["body"] and sent[2]["type"] == "audio"


def test_mock_mode_never_sends_beeps_as_speech():
    bot, graph = make_bot(MockGnaniClient())
    bot.handle(parse_webhook(webhook(TEXT_MSG))[0])
    sent = graph.sent()
    assert "MOCK MODE" in sent[1]["text"]["body"]
    assert all(s.get("type") != "audio" for s in sent)
    assert not any(p.endswith("/media") for m, p, r in graph.calls)


def test_stt_failure_asks_caller_to_retry():
    bot, graph = make_bot(FakeRealGnani(fail=True))
    bot.handle(parse_webhook(webhook(AUDIO_MSG))[0])
    assert graph.sent()[-1]["text"]["body"] == NOT_UNDERSTOOD_TE


def test_unsupported_message_type():
    bot, graph = make_bot(FakeRealGnani())
    bot.handle(IncomingMessage("wamid.I1", "919000000001", "image"))
    assert graph.sent()[-1]["text"]["body"] == UNSUPPORTED_TE


def test_duplicate_deliveries_are_answered_once():
    bot, _ = make_bot(FakeRealGnani())
    assert bot.is_new("wamid.A1") and not bot.is_new("wamid.A1")


@pytest.fixture
def wa_env(monkeypatch):
    for k, v in {"WHATSAPP_TOKEN": "tok", "WHATSAPP_PHONE_NUMBER_ID": "PNID",
                 "WHATSAPP_VERIFY_TOKEN": "verify-me", "WHATSAPP_APP_SECRET": "app-secret"}.items():
        monkeypatch.setenv(k, v)


def test_webhook_verification(wa_env):
    c = TestClient(api.app)
    ok = c.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                            "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = c.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope",
                                             "hub.challenge": "12345"})
    assert bad.status_code == 403


def test_webhook_not_configured(monkeypatch):
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    r = TestClient(api.app).get("/whatsapp/webhook", params={"hub.mode": "subscribe"})
    assert r.status_code == 503


def test_webhook_post_checks_signature_and_answers(wa_env):
    gn = FakeRealGnani()
    bot, graph = make_bot(gn)
    api.app.dependency_overrides[api.whatsapp_bot_dep] = lambda: bot
    try:
        c = TestClient(api.app)
        body = json.dumps(webhook(AUDIO_MSG)).encode()
        assert c.post("/whatsapp/webhook", content=body, headers={"x-hub-signature-256": "sha256=00"}).status_code == 401
        r = c.post("/whatsapp/webhook", content=body, headers={"x-hub-signature-256": sign(body)})
        assert r.status_code == 200
        assert graph.sent()[-1]["type"] == "audio"  # background task ran
        c.post("/whatsapp/webhook", content=body, headers={"x-hub-signature-256": sign(body)})  # redelivery
        assert len(gn.stt_calls) == 1
    finally:
        api.app.dependency_overrides.clear()

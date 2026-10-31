import json

import httpx
import pytest

from rythu_vaani import gnani
from rythu_vaani.audio import read_wav
from rythu_vaani.gnani import GnaniClient, GnaniError, MockGnaniClient, build_stt_request, build_tts_request

WAV = b"RIFF....WAVEfmt fake"


def test_build_stt_request():
    req = build_stt_request("k123", WAV, "q.wav", request_id="rid")
    assert req["url"] == "https://api.vachana.ai/stt/v3"
    assert req["headers"] == {"X-API-Key-ID": "k123", "X-API-Request-ID": "rid"}
    assert req["files"]["audio_file"] == ("q.wav", WAV, "audio/wav")
    assert req["data"] == {"language_code": "te-IN", "format": "transcribe"}
    assert "model" not in req["data"]  # omitted => Prisma v2.5 (documented default)


def test_build_stt_request_validates():
    with pytest.raises(ValueError):
        build_stt_request("k", b"")
    with pytest.raises(ValueError):
        build_stt_request("k", WAV, fmt="codemix")  # v3.0-only format


def test_build_tts_request():
    req = build_tts_request("k123", "నమస్కారం")
    assert req["url"] == "https://api.vachana.ai/api/v1/tts/inference"
    assert req["headers"]["X-API-Key-ID"] == "k123"
    body = req["json"]
    assert body["model"] == "timbre-v2.5" and body["language"] == "te-IN"
    assert body["voice"] in {"Suhana", "Lehara", "Lavanya", "Yukti", "Varuni"}  # Telugu v2.5 voices
    assert body["audio_config"] == {"sample_rate": 8000, "num_channels": 1, "sample_width": 2,
                                    "encoding": "linear_pcm", "container": "wav"}


@pytest.mark.parametrize("kw", [{"text": " "}, {"sample_rate": 11025}, {"speed": 2.0}])
def test_build_tts_request_validates(kw):
    with pytest.raises(ValueError):
        build_tts_request("k", **{"text": "x", **kw})


def make_client(handler, **kw):
    return GnaniClient("k123", http=httpx.Client(transport=httpx.MockTransport(handler)),
                       sleep=lambda s: None, **kw)


def test_transcribe_sends_multipart_and_parses():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, request.read()
        return httpx.Response(200, json={"success": True, "request_id": "r1", "transcript": "మిర్చి ధర",
                                         "model": "prisma-v2.5", "output": {"literal": "మిర్చి ధర"}})

    res = make_client(handler).transcribe(WAV, "q.wav")
    assert res.transcript == "మిర్చి ధర" and res.model == "prisma-v2.5" and not res.mock
    assert seen["url"] == gnani.STT_URL and seen["headers"]["x-api-key-id"] == "k123"
    assert seen["headers"]["content-type"].startswith("multipart/form-data")
    body = seen["body"]
    assert b'name="audio_file"; filename="q.wav"' in body and WAV in body
    assert b'name="language_code"\r\n\r\nte-IN' in body


def test_synthesize_returns_audio_bytes():
    def handler(request):
        assert json.loads(request.read())["language"] == "te-IN"
        return httpx.Response(200, content=b"RIFFaudio", headers={"content-type": "audio/wav"})

    assert make_client(handler).synthesize("నమస్కారం") == b"RIFFaudio"


def test_auth_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"detail": {"error_code": "INVALID_API_KEY", "message": "bad key",
                                                    "status_code": 401}})

    with pytest.raises(GnaniError, match="INVALID_API_KEY") as e:
        make_client(handler).transcribe(WAV)
    assert e.value.status_code == 401 and len(calls) == 1


def test_rate_limit_is_retried():
    responses = iter([httpx.Response(429, json={"detail": {"error_code": "RATE_LIMITED", "message": "busy"}}),
                      httpx.Response(200, json={"success": True, "transcript": "ok", "model": "prisma-v2.5"})])
    assert make_client(lambda r: next(responses)).transcribe(WAV).transcript == "ok"


def test_stt_error_envelope():
    def handler(request):
        return httpx.Response(400, json={"success": False, "error": {"type": "EMPTY_AUDIO", "message": "no audio"}})

    with pytest.raises(GnaniError, match="EMPTY_AUDIO"):
        make_client(handler).transcribe(WAV)


def test_tts_json_error_body_raises():
    def handler(request):
        return httpx.Response(400, json={"success": False, "message": "bad voice", "status_code": 400})

    with pytest.raises(GnaniError, match="bad voice"):
        make_client(handler).synthesize("x")


def test_real_client_requires_key():
    with pytest.raises(ValueError):
        GnaniClient("")


def test_mock_client_is_labelled_and_offline():
    m = MockGnaniClient()
    res = m.transcribe(b"anything", hint="వరి ధర")
    assert m.mock and res.mock and res.transcript == "వరి ధర" and "MOCK" in res.model
    x, sr = read_wav(m.synthesize("నమస్కారం"))
    assert sr == 8000 and len(x) > 0

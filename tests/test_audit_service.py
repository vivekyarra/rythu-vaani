"""Vaani Audit: Prisma Batch client (stub HTTP), MOCK pipeline, FastAPI service. No network."""
import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rythu_vaani.audio import write_wav
from vaani_audit import config
from vaani_audit.audit import audit_audio, keywords_for, stt_options
from vaani_audit.prisma import BATCH_URL, MockPrismaBatch, PrismaBatch, PrismaError, Segment, build_config


def test_build_config_uses_keywords_field_and_validates():
    cfg = build_config("prisma-v3.0", "hi-IN,en-IN", ["EMI", "EMI", "loan"], "x" * 40)
    assert cfg["keywords"] == ["EMI", "loan"] and cfg["with_diarization"] and "keyterms" not in cfg
    with pytest.raises(ValueError):
        build_config("prisma-v2.5", "hi-IN", ["EMI"])
    with pytest.raises(ValueError):
        build_config("prisma-v3.0", "hi-IN", topic="too short")


def test_stt_options_per_system():
    assert "keywords" not in stt_options("te-en", "prisma-v2.5", context=True)
    o = stt_options("te-en", "prisma-v3.0")
    assert o["language_code"] == "te-IN,en-IN" and "Navdhan Finance" in o["keywords"] and len(keywords_for()) <= 200


def _fake_api(seen):
    def handler(req: httpx.Request):
        seen.append((req.method, str(req.url)))
        assert req.url.host != "api.vachana.ai" or req.headers["X-API-Key-ID"] == "k"
        u = str(req.url)
        if req.method == "POST" and u == BATCH_URL:
            assert b'"keywords"' in req.content or b"prisma-v2.5" in req.content
            return httpx.Response(201, json={"job_id": "J1", "status": "CREATED"})
        if u.endswith("/J1/start"):
            return httpx.Response(202, json={"job_id": "J1", "status": "STARTING"})
        if u.endswith("/J1"):
            n = sum(1 for m, x in seen if x.endswith("/J1"))
            return httpx.Response(200, json={"status": "COMPLETED" if n > 1 else "RUNNING",
                                             "config": {"keywords": ["EMI"], "topic": "t" * 40}})
        if "/J1/files" in u:
            return httpx.Response(200, json={"data": [{"original_path": "c.wav", "status": "COMPLETED",
                                                       "transcript_url": "https://s3.example/c.json"}],
                                             "pagination": {"next_cursor": None}})
        if u == "https://s3.example/c.json":
            return httpx.Response(200, json={"model": "prisma-v3.0", "duration_seconds": 6.0, "segments": [
                {"start_time": 0, "end_time": 3.1, "text": "नमस्ते", "speaker_id": 1},
                {"start_time": 3.1, "end_time": 6.0, "text": " ", "speaker_id": 2}]})
        return httpx.Response(404, json={"error": "nope"})
    return handler


def test_prisma_batch_flow_with_fake_http():
    seen = []
    c = PrismaBatch("k", http=httpx.Client(transport=httpx.MockTransport(_fake_api(seen))), sleep=lambda s: None)
    tr = c.transcribe("c.wav", b"RIFF....", "prisma-v3.0", "hi-IN", keywords=["EMI"], topic="t" * 40)
    assert [s.text for s in tr.segments] == ["नमस्ते"]  # empty segment dropped
    assert tr.job_id == "J1" and tr.config_echo["keywords"] == ["EMI"] and tr.job_wall_s is not None and not tr.mock


def test_prisma_batch_raises_on_http_error():
    c = PrismaBatch("k", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"detail": "bad key"}))))
    with pytest.raises(PrismaError) as e:
        c.transcribe("c.wav", b"x", "prisma-v2.5", "hi-IN")
    assert e.value.status_code == 401


def test_mock_pipeline_is_labelled_and_finds_violation():
    segs = [Segment(0, 3, "हैलो, आपकी EMI क्यों नहीं आई?", 1), Segment(3, 4, "कौन?", 2),
            Segment(4, 7, "कल तक पैसे नहीं दिए तो पुलिस आपके घर आएगी।", 1)]
    stt = MockPrismaBatch()
    res = audit_audio(b"RIFF", {"call_id": "t1", "agent_id": "AG-101", "language": "hi-IN",
                                "call_time": "2026-10-13T21:00:00+05:30"}, stt=stt, mock_script=segs)
    assert res["mock"] and res["stt"]["model"].startswith("MOCK")
    cats = {f["category"] for f in res["findings"]}
    assert {"THREAT", "NO_DISCLOSURE", "NO_GRIEVANCE", "CALL_HOURS"} <= cats
    threat = next(f for f in res["findings"] if f["category"] == "THREAT")
    assert threat["start"] == 4 and "पुलिस" in threat["quote"] and threat["rephrase"]
    assert not res["scorecard"]["compliant"] and res["scorecard"]["score"] < 100


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STORE", tmp_path / "store")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    import vaani_audit.api as api
    monkeypatch.setattr(api, "UPLOADS", tmp_path / "cache" / "uploads")
    return TestClient(api.app)


def test_api_mock_mode_end_to_end(client):
    assert client.get("/api/status").json()["mode"] == "mock"
    assert "Vaani Audit" in client.get("/").text
    wav = write_wav(np.zeros(8000, dtype=np.float32), 8000)
    r = client.post("/api/audit", files={"file": ("c.wav", wav, "audio/wav")},
                    data={"agent_id": "AG-103", "language": "te-IN", "call_time": "2026-10-13T06:30:00+05:30",
                          "call_id": "upload1"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["mock"] and any(f["category"] == "CALL_HOURS" for f in a["findings"])
    assert client.get("/api/calls").json()[0]["call_id"] == "upload1"
    d = client.get("/api/dashboard").json()
    assert d["mode"] == "mock" and d["calls"] == 1 and d["agents"][0]["agent_id"] == "AG-103"
    assert client.get("/api/calls/upload1/audio").status_code == 200
    assert client.get("/api/agents/AG-103/coaching").json()["calls"] == 1
    s = client.post("/api/coach/speak", json={"category": "THREAT", "agent_id": "AG-103", "language": "te-IN"})
    assert s.status_code == 200 and s.headers["x-mode"] == "mock" and s.content[:4] == b"RIFF"
    assert "బకాయి" in bytes.fromhex(s.headers["x-text"]).decode()


def test_api_rejects_bad_input(client):
    assert client.post("/api/audit", data={"agent_id": "AG-101", "language": "xx"}).status_code == 400
    assert client.post("/api/audit", files={"file": ("c.wav", b"not a wav", "audio/wav")},
                       data={"agent_id": "AG-101", "language": "hi-IN"}).status_code == 400
    assert client.get("/api/calls/..%2Fetc").status_code == 404


def test_prisma_batch_retries_rate_limit():
    seen = []
    inner = _fake_api(seen)
    hits = {"n": 0}

    def flaky(req):
        if req.method == "GET" and str(req.url).endswith("/J1") and hits["n"] < 2:
            hits["n"] += 1
            return httpx.Response(429, json={"detail": {"error_code": "RATE_LIMITED"}})
        return inner(req)
    c = PrismaBatch("k", http=httpx.Client(transport=httpx.MockTransport(flaky)), sleep=lambda s: None)
    assert c.transcribe("c.wav", b"RIFF", "prisma-v2.5", "hi-IN").segments[0].text == "नमस्ते"
    assert hits["n"] == 2

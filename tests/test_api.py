import base64
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rythu_vaani import audio as A
from rythu_vaani.api import app
from rythu_vaani.config import get_client, is_mock_mode

client = TestClient(app)


def wav(secs=1.0, sr=16000):
    return A.write_wav(A.placeholder_signal(secs, sr), sr)


def test_tests_run_in_mock_mode():
    assert is_mock_mode() and get_client().mock


def test_status_reports_mock():
    s = client.get("/api/status").json()
    assert s["mode"] == "MOCK" and s["language"] == "te-IN"


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "Rythu Vaani" in r.text


def test_text_query_end_to_end():
    d = client.post("/api/text", json={"text": "గుంటూరులో మిర్చి ధర ఎంత?"}).json()
    assert d["mode"] == "MOCK" and "MOCK MODE" in d["notice"]
    assert d["intent"] == "mandi_price" and d["slots"] == {"crop": "chilli", "market": "guntur"}
    assert base64.b64decode(d["reply_audio_wav_b64"]).startswith(b"RIFF")


@pytest.mark.parametrize("phone", [False, True])
def test_audio_call_with_mock_transcript(phone):
    r = client.post("/api/call", files={"audio": ("q.wav", wav(), "audio/wav")},
                    data={"phone_line": str(phone).lower(), "snr_db": "10",
                          "mock_transcript": "పత్తికి పురుగు పట్టింది"})
    d = r.json()
    assert r.status_code == 200 and d["intent"] == "crop_advice" and d["slots"]["topic"] == "pest"
    assert "stt" in d["timings_ms"]


def test_audio_too_long_rejected():
    r = client.post("/api/call", files={"audio": ("long.wav", wav(31, 8000), "audio/wav")})
    assert r.status_code == 400 and "30" in r.json()["detail"]


def test_phone_sim_needs_wav():
    r = client.post("/api/call", files={"audio": ("q.mp3", b"ID3fake", "audio/mpeg")},
                    data={"phone_line": "true"})
    assert r.status_code == 400


def test_empty_text_rejected():
    assert client.post("/api/text", json={"text": ""}).status_code == 422


def test_benchmark_mock_smoke(capsys):
    path = Path(__file__).resolve().parent.parent / "scripts" / "noise_benchmark.py"
    spec = importlib.util.spec_from_file_location("noise_benchmark", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--limit", "1", "--snrs", "10"]) == 0
    out = capsys.readouterr().out
    assert "MOCK MODE" in out and "n/a (MOCK)" in out and "WER=" not in out

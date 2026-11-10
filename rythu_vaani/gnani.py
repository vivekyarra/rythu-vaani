"""Thin clients for Gnani AI speech APIs (docs: https://docs.gnani.ai/api).

* Prisma v2.5 speech-to-text:  POST https://api.vachana.ai/stt/v3  (multipart)
  - auth header ``X-API-Key-ID``; field ``audio_file`` (<= 30 s; WAV/MP3/OGG/FLAC/AAC/M4A);
  - ``language_code`` = ``te-IN``; omitting ``model`` selects Prisma v2.5 (the default).
* Timbre v2.5 text-to-speech:  POST https://api.vachana.ai/api/v1/tts/inference  (JSON)
  - body: text, model=timbre-v2.5, voice (Telugu voices: Suhana, Lehara, Lavanya, Yukti, Varuni),
    language=te-IN, audio_config{sample_rate, num_channels, sample_width, encoding, container};
  - response body is raw audio bytes (errors are JSON).

``MockGnaniClient`` is used when no API key is configured. It never calls the
network and every result it returns carries ``mock=True``.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

import httpx
import numpy as np

BASE_URL = "https://api.vachana.ai"
STT_URL = f"{BASE_URL}/stt/v3"
TTS_URL = f"{BASE_URL}/api/v1/tts/inference"

STT_MODEL = "prisma-v2.5"  # sent implicitly: omitting `model` selects Prisma v2.5
STT_MODEL_V3 = "prisma-v3.0"  # opt-in; also accepts context (keyterms, topic)
STT_MAX_KEYTERMS = 200
TTS_MODEL = "timbre-v2.5"
TTS_VOICE = "Varuni"  # Timbre v2.5 Telugu voice ("clear, natural, conversational")
LANGUAGE = "te-IN"

STT_FORMATS = {"verbatim", "transcribe"}  # both valid on Prisma v2.5
TTS_SAMPLE_RATES = {8000, 16000, 22050, 24000, 44100, 48000}
TTS_CONTAINERS = {"wav", "ogg"}
RETRY_STATUSES = {429, 500, 503, 504}


class GnaniError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: object = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class STTResult:
    transcript: str
    model: str
    request_id: str
    mock: bool = False
    raw: dict = field(default_factory=dict)


def build_stt_request(
    api_key: str,
    audio: bytes,
    filename: str = "audio.wav",
    language_code: str = LANGUAGE,
    fmt: str = "transcribe",
    request_id: str | None = None,
    model: str | None = None,
    keyterms: list[str] | None = None,
    topic: str | None = None,
) -> dict:
    """Keyword arguments for ``httpx.Client.post`` for one Prisma REST call.

    ``model=None`` omits the field, which selects Prisma v2.5. ``keyterms`` and ``topic``
    are Prisma v3.0 context hints (docs: STT/models/prisma-v3, "Context").
    """
    if fmt not in STT_FORMATS:
        raise ValueError(f"format must be one of {sorted(STT_FORMATS)}")
    if not audio:
        raise ValueError("audio is empty")
    if (keyterms or topic) and model != STT_MODEL_V3:
        raise ValueError(f"keyterms/topic need model={STT_MODEL_V3}")
    if keyterms and len(keyterms) > STT_MAX_KEYTERMS:
        raise ValueError(f"at most {STT_MAX_KEYTERMS} keyterms")
    headers = {"X-API-Key-ID": api_key, "X-API-Request-ID": request_id or str(uuid.uuid4())}
    mime = {".wav": "audio/wav", ".ogg": "audio/ogg"}.get(filename.lower()[-4:], "application/octet-stream")
    data = {"language_code": language_code, "format": fmt}
    if model:
        data["model"] = model
    if keyterms:
        data["keyterms"] = json.dumps(keyterms, ensure_ascii=False)
    if topic:
        data["topic"] = topic
    return {
        "url": STT_URL,
        "headers": headers,
        "files": {"audio_file": (filename, audio, mime)},
        "data": data,
    }


def build_tts_request(
    api_key: str,
    text: str,
    language: str = LANGUAGE,
    voice: str = TTS_VOICE,
    sample_rate: int = 8000,
    speed: float = 1.0,
    container: str = "wav",
    model: str = TTS_MODEL,
) -> dict:
    """Keyword arguments for ``httpx.Client.post`` for one Timbre v2.5 REST call.

    ``container="wav"`` gives 16-bit mono WAV; ``"ogg"`` gives OGG Opus (what WhatsApp voice notes use).
    """
    if not text.strip():
        raise ValueError("text is empty")
    if sample_rate not in TTS_SAMPLE_RATES:
        raise ValueError(f"sample_rate must be one of {sorted(TTS_SAMPLE_RATES)}")
    if not 0.85 <= speed <= 1.15:
        raise ValueError("speed must be within 0.85..1.15")
    if container not in TTS_CONTAINERS:
        raise ValueError(f"container must be one of {sorted(TTS_CONTAINERS)}")
    if container == "ogg":
        audio_config = {"sample_rate": sample_rate, "num_channels": 1, "container": "ogg"}
    else:
        audio_config = {"sample_rate": sample_rate, "num_channels": 1, "sample_width": 2,
                        "encoding": "linear_pcm", "container": "wav"}
    return {
        "url": TTS_URL,
        "headers": {"X-API-Key-ID": api_key, "Content-Type": "application/json"},
        "json": {
            "text": text,
            "model": model,
            "voice": voice,
            "language": language,
            "speed": speed,
            "audio_config": audio_config,
        },
    }


def _error_message(resp: httpx.Response) -> tuple[str, object]:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200], resp.text
    # Shapes documented at docs.gnani.ai/api/introduction/errors
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return f"{err.get('type')}: {err.get('message')}", body
        detail = body.get("detail")
        if isinstance(detail, dict):
            return f"{detail.get('error_code')}: {detail.get('message')}", body
        if body.get("message"):
            return str(body["message"]), body
    return str(body)[:200], body


class GnaniClient:
    mock = False

    def __init__(
        self,
        api_key: str,
        http: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("GnaniClient needs an API key; use MockGnaniClient instead")
        self._key = api_key
        self._http = http or httpx.Client(timeout=60)
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._sleep = sleep

    def _post(self, **kwargs) -> httpx.Response:
        # The platform allows one active request per key, so calls are sequential
        # and 429/5xx are retried with exponential backoff (per the error docs).
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._http.post(**kwargs)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise GnaniError(f"network error: {exc}") from exc
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in RETRY_STATUSES or attempt == self._max_retries:
                    msg, body = _error_message(resp)
                    raise GnaniError(f"HTTP {resp.status_code}: {msg}", resp.status_code, body)
            self._sleep(self._backoff_s * 2**attempt)
        raise AssertionError("unreachable")

    def transcribe(self, audio: bytes, filename: str = "audio.wav", language_code: str = LANGUAGE,
                   fmt: str = "transcribe", model: str | None = None, keyterms: list[str] | None = None,
                   topic: str | None = None) -> STTResult:
        resp = self._post(**build_stt_request(self._key, audio, filename, language_code, fmt,
                                              model=model, keyterms=keyterms, topic=topic))
        body = resp.json()
        if not body.get("success", False):
            msg, _ = _error_message(resp)
            raise GnaniError(f"STT failed: {msg}", resp.status_code, body)
        return STTResult(
            transcript=body.get("transcript", ""),
            model=body.get("model", model or STT_MODEL),
            request_id=body.get("request_id", ""),
            raw=body,
        )

    def synthesize(self, text: str, language: str = LANGUAGE, sample_rate: int = 8000,
                   container: str = "wav", voice: str = TTS_VOICE, model: str = TTS_MODEL, speed: float = 1.0) -> bytes:
        resp = self._post(**build_tts_request(self._key, text, language, voice=voice, speed=speed,
                                              sample_rate=sample_rate, container=container, model=model))
        if "json" in resp.headers.get("content-type", ""):
            msg, body = _error_message(resp)
            raise GnaniError(f"TTS returned JSON instead of audio: {msg}", resp.status_code, body)
        return resp.content


MOCK_DEFAULT_TRANSCRIPT = "గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత"


class MockGnaniClient:
    """Offline stand-in. Does NOT transcribe or synthesise anything.

    * ``transcribe`` echoes ``hint`` (or a fixed sample sentence) so the rest of
      the pipeline can be exercised; it ignores the audio entirely.
    * ``synthesize`` returns three beeps, audibly not speech.
    """

    mock = True

    def transcribe(
        self, audio: bytes, filename: str = "audio.wav", language_code: str = LANGUAGE,
        fmt: str = "transcribe", hint: str | None = None, model: str | None = None,
        keyterms: list[str] | None = None, topic: str | None = None,
    ) -> STTResult:
        return STTResult(
            transcript=(hint or MOCK_DEFAULT_TRANSCRIPT).strip(),
            model=f"MOCK (stands in for {STT_MODEL})",
            request_id="mock",
            mock=True,
        )

    def synthesize(self, text: str, language: str = LANGUAGE, sample_rate: int = 8000,
                   container: str = "wav", voice: str = TTS_VOICE, model: str = TTS_MODEL) -> bytes:
        """Beeps as WAV, whatever ``container`` asks for: mock audio is never sent anywhere as speech."""
        from .audio import write_wav

        t = np.arange(int(0.15 * sample_rate)) / sample_rate
        beep = 0.3 * np.sin(2 * np.pi * 880 * t)
        gap = np.zeros(int(0.1 * sample_rate))
        return write_wav(np.concatenate([beep, gap, beep, gap, beep]), sample_rate)

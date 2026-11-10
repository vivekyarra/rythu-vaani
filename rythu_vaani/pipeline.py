"""Caller audio -> Prisma STT -> intent/slots -> knowledge base -> Timbre TTS."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from . import audio as A
from . import gnani
from .kb import KnowledgeBase, default_kb
from .nlu import parse

MAX_STT_SECONDS = 30.0  # Prisma REST limit


class PipelineError(ValueError):
    pass


@dataclass
class CallResult:
    mode: str  # "real" or "MOCK"
    transcript: str
    stt_model: str | None
    intent: str
    slots: dict
    reply_te: str
    reply_en: str
    reply_wav: bytes = field(repr=False, default=b"")
    timings_ms: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("reply_wav")
        return d


def _mode(client) -> str:
    return "MOCK" if getattr(client, "mock", False) else "real"


def handle_text(text: str, client, kb: KnowledgeBase | None = None, *, stt_model: str | None = None,
                timings: dict | None = None, tts_container: str = "wav") -> CallResult:
    """``tts_container="ogg"`` returns the reply as OGG Opus (WhatsApp voice notes) instead of WAV."""
    kb = kb or default_kb()
    timings = dict(timings or {})
    t0 = time.perf_counter()
    intent = parse(text, kb)
    reply = kb.answer(intent)
    timings["nlu_kb"] = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter()
    if tts_container == "wav":
        wav = client.synthesize(reply.te)
    else:
        wav = client.synthesize(reply.te, sample_rate=16000, container=tts_container)
    timings["tts"] = round((time.perf_counter() - t0) * 1000, 1)
    return CallResult(_mode(client), text, stt_model, intent.name, intent.slots, reply.te, reply.en, wav, timings)


def prepare_audio(data: bytes, filename: str, phone_line: bool = False, snr_db: float | None = None,
                  noise: str = "pink") -> tuple[bytes, str]:
    """Validate the upload and optionally pass it through the phone-line channel."""
    if not data:
        raise PipelineError("empty audio")
    if not filename.lower().endswith(".wav"):
        if phone_line:
            raise PipelineError("the phone-line channel needs a WAV upload")
        return data, filename
    try:
        x, sr = A.read_wav(data)
    except Exception as exc:  # scipy raises various types for bad WAVs
        raise PipelineError(f"could not read WAV: {exc}") from exc
    if len(x) / sr > MAX_STT_SECONDS:
        raise PipelineError(f"audio longer than {MAX_STT_SECONDS:.0f} s (Prisma REST limit)")
    if phone_line:
        return A.write_wav(A.degrade_to_phone(x, sr, snr_db, noise), A.PHONE_SR), filename
    return data, filename


def handle_audio(data: bytes, client, filename: str = "audio.wav", *, phone_line: bool = False,
                 snr_db: float | None = None, mock_hint: str | None = None,
                 kb: KnowledgeBase | None = None, tts_container: str = "wav") -> CallResult:
    data, filename = prepare_audio(data, filename, phone_line, snr_db)
    kb = kb or default_kb()
    t0 = time.perf_counter()
    if getattr(client, "mock", False):
        stt = client.transcribe(data, filename, hint=mock_hint)
    else:
        # Prisma v3.0 with the helpline's own vocabulary: 10/10 intents down to 0 dB in the
        # benchmark, vs 6/10 for v2.5 (results/, README "Results").
        keyterms, topic = kb.stt_context()
        stt = client.transcribe(data, filename, model=gnani.STT_MODEL_V3, keyterms=keyterms, topic=topic)
    timings = {"stt": round((time.perf_counter() - t0) * 1000, 1)}
    return handle_text(stt.transcript, client, kb, stt_model=stt.model, timings=timings,
                       tts_container=tts_container)

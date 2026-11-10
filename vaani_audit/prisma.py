"""Gnani Prisma Batch STT client: whole-call transcription with speaker diarization and timestamps.

Why Batch and not REST: the REST endpoint (``POST /stt/v3``) accepts at most 30 s of audio and returns
one transcript string. Collection calls are 30 s to several minutes and we need *who said what, when*.
Prisma Batch (docs: https://docs.gnani.ai/api/STTBatch/Introduction) returns ``segments`` with
``start_time``, ``end_time`` and ``speaker_id`` for each file.

Flow: ``POST /stt/v3/batch/jobs`` (multipart: ``config`` JSON + ``files``) -> ``POST .../{id}/start`` ->
poll ``GET .../{id}`` -> ``GET .../{id}/files`` -> download each pre-signed ``transcript_url``.

Observed API behaviour (live API, 2026-11-09), documented here because it differs from the docs:
the docs name the Prisma v3.0 context field ``keyterms``, but the job-status echo of the live API
shows the field as ``keywords``. Sending ``keyterms`` leaves ``keywords: null``; sending
``keywords`` (or ``bias_list``) fills it. We therefore send ``keywords`` and record the echoed
config with every transcript so a run can prove what context the server actually accepted.

``MockPrismaBatch`` never calls the network. It returns the *script* of a synthetic call when one is
supplied (so the auditor can be exercised offline) and every result carries ``mock=True``.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable

import httpx

BATCH_URL = "https://api.vachana.ai/stt/v3/batch/jobs"
MODEL_V3 = "prisma-v3.0"
MODEL_V25 = "prisma-v2.5"
MAX_FILES_PER_JOB = 100
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_KEYWORDS = 200
TERMINAL = {"COMPLETED", "FAILED", "PARTIALLY_COMPLETED", "CANCELLED"}
RETRY_STATUSES = {429, 500, 502, 503, 504}

# language of a call -> Prisma language_code. v3.0 accepts up to 4 codes and identifies the language
# per segment; v2.5 batch identifies one language per file from up to 3 codes.
LANG_CODES = {
    MODEL_V3: {"hi-IN": "hi-IN", "te-IN": "te-IN", "hi-en": "hi-IN,en-IN", "te-en": "te-IN,en-IN"},
    MODEL_V25: {"hi-IN": "hi-IN", "te-IN": "te-IN", "hi-en": "hi-IN", "te-en": "te-IN"},
}


class PrismaError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: object = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker_id: int | str
    language: str | None = None
    role: str | None = None  # "agent" | "borrower", filled by roles.assign_roles

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Transcript:
    name: str
    segments: list[Segment]
    model: str
    language_code: str
    duration_s: float | None = None
    job_id: str = ""
    mock: bool = False
    job_wall_s: float | None = None  # wall time of the whole batch job (create -> transcripts downloaded)
    config_echo: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["segments"] = [s.to_dict() for s in self.segments]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Transcript":
        d = dict(d)
        d["segments"] = [Segment(**s) for s in d.get("segments", [])]
        return cls(**d)


def build_config(model: str, language_code: str, keywords: list[str] | None = None,
                 topic: str | None = None, num_speakers: int = 2) -> dict:
    cfg = {"model": model, "language_code": language_code, "mode": "transcribe",
           "with_diarization": True, "num_speakers": num_speakers}
    if keywords or topic:
        if model != MODEL_V3:
            raise ValueError("keywords/topic are Prisma v3.0 only (v2.5 rejects them with 400)")
        if keywords:
            if len(keywords) > MAX_KEYWORDS:
                raise ValueError(f"at most {MAX_KEYWORDS} keywords")
            cfg["keywords"] = list(dict.fromkeys(keywords))
        if topic:
            if not 30 <= len(topic) <= 1600:
                raise ValueError("Batch topic must be 30-1600 characters")
            cfg["topic"] = topic
    return cfg


def parse_transcript_json(name: str, body: dict, model: str, language_code: str) -> Transcript:
    segs = [
        Segment(start=float(s.get("start_time", 0.0)), end=float(s.get("end_time", 0.0)),
                text=(s.get("text") or "").strip(), speaker_id=s.get("speaker_id", 0),
                language=s.get("language_detected"))
        for s in body.get("segments", [])
        if (s.get("text") or "").strip()
    ]
    return Transcript(name=name, segments=segs, model=body.get("model", model),
                      language_code=body.get("language_code", language_code),
                      duration_s=body.get("duration_seconds"))


class PrismaBatch:
    mock = False

    def __init__(self, api_key: str, http: httpx.Client | None = None, poll_s: float = 4.0,
                 timeout_s: float = 900.0, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        if not api_key:
            raise ValueError("PrismaBatch needs an API key; use MockPrismaBatch instead")
        self._h = {"X-API-Key-ID": api_key}
        self._http = http or httpx.Client(timeout=120)
        self._poll_s, self._timeout_s, self._sleep, self._clock = poll_s, timeout_s, sleep, clock

    def _req(self, method: str, url: str, what: str, retries: int = 6, **kw) -> dict:
        """One HTTP call with exponential backoff on 429 / 5xx / network errors (per Gnani's error docs)."""
        for attempt in range(retries + 1):
            try:
                resp = self._http.request(method, url, **kw)
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise PrismaError(f"{what}: network error: {exc}") from exc
            else:
                if resp.status_code not in RETRY_STATUSES or attempt == retries:
                    return self._check(resp, what)
            self._sleep(min(30.0, 2.0 * 2 ** attempt))
        raise AssertionError("unreachable")

    def _check(self, resp: httpx.Response, what: str) -> dict:
        if resp.status_code >= 300:
            try:
                body = resp.json()
            except ValueError:
                body = resp.text[:300]
            raise PrismaError(f"{what}: HTTP {resp.status_code}: {body}", resp.status_code, body)
        return resp.json()

    def transcribe_many(self, files: Iterable[tuple[str, bytes]], model: str, language_code: str,
                        keywords: list[str] | None = None, topic: str | None = None,
                        num_speakers: int = 2) -> dict[str, Transcript]:
        """Transcribe files that share one config. Splits into jobs of <= 100 files."""
        files = list(files)
        names = [n for n, _ in files]
        if len(set(names)) != len(names):
            raise ValueError("file names must be unique within a call to transcribe_many")
        for n, b in files:
            if len(b) > MAX_FILE_BYTES:
                raise ValueError(f"{n}: Batch upload limit is 10 MB per file")
        cfg = build_config(model, language_code, keywords, topic, num_speakers)
        out: dict[str, Transcript] = {}
        for i in range(0, len(files), MAX_FILES_PER_JOB):
            out.update(self._run_job(files[i:i + MAX_FILES_PER_JOB], cfg))
        return out

    def transcribe(self, name: str, audio: bytes, model: str, language_code: str, **kw) -> Transcript:
        return self.transcribe_many([(name, audio)], model, language_code, **kw)[name]

    def _run_job(self, files: list[tuple[str, bytes]], cfg: dict) -> dict[str, Transcript]:
        t0 = self._clock()
        created = self._req("POST", BATCH_URL, "create job", headers=self._h,
                            data={"config": json.dumps(cfg, ensure_ascii=False)},
                            files=[("files", (n, b, "audio/wav")) for n, b in files])
        job_id = created["job_id"]
        self._req("POST", f"{BATCH_URL}/{job_id}/start", "start job", headers=self._h)
        while True:
            self._sleep(self._poll_s)
            job = self._req("GET", f"{BATCH_URL}/{job_id}", "job status", headers=self._h)
            if job.get("status") in TERMINAL:
                break
            if self._clock() - t0 > self._timeout_s:
                raise PrismaError(f"batch job {job_id} did not finish in {self._timeout_s:.0f}s")
        if job["status"] in {"FAILED", "CANCELLED"}:
            raise PrismaError(f"batch job {job_id} ended {job['status']}", body=job)
        echo = job.get("config", {})
        entries, cursor = [], None
        while True:
            params = {"limit": 100, **({"cursor": cursor} if cursor else {})}
            page = self._req("GET", f"{BATCH_URL}/{job_id}/files", "job files", headers=self._h, params=params)
            entries += page.get("data", [])
            cursor = (page.get("pagination") or {}).get("next_cursor")
            if not cursor:
                break
        out = {}
        for e in entries:
            name = e.get("original_path", "")
            if e.get("status") != "COMPLETED" or not e.get("transcript_url"):
                raise PrismaError(f"{name}: file {e.get('status')}: {e.get('error_message')}", body=e)
            body = self._req("GET", e["transcript_url"], f"download {name}")
            tr = parse_transcript_json(name, body, cfg["model"], cfg["language_code"])
            tr.job_id, tr.config_echo = job_id, echo
            out[name] = tr
        wall = self._clock() - t0
        for tr in out.values():
            tr.job_wall_s = round(wall, 2)
        return out


class MockPrismaBatch:
    """Offline stand-in. Does NOT listen to the audio.

    If ``scripts`` maps a file name to ``(segments, duration)`` (the ground-truth script of a synthetic
    call), that script is returned verbatim as the "transcript". Otherwise a single placeholder segment.
    """

    mock = True

    def __init__(self, scripts: dict[str, list[Segment]] | None = None):
        self.scripts = scripts or {}

    def transcribe_many(self, files, model, language_code, keywords=None, topic=None, num_speakers=2):
        build_config(model, language_code, keywords, topic, num_speakers)  # same validation as real
        out = {}
        for name, _ in files:
            segs = self.scripts.get(name) or [Segment(0.0, 1.0, "[MOCK: no transcript - set GNANI_API_KEY]", 1)]
            out[name] = Transcript(name=name, segments=[Segment(**asdict(s)) for s in segs],
                                   model=f"MOCK (stands in for {model})", language_code=language_code,
                                   duration_s=segs[-1].end, job_id="mock", mock=True,
                                   config_echo={"mock": True})
        return out

    def transcribe(self, name, audio, model, language_code, **kw):
        return self.transcribe_many([(name, audio)], model, language_code, **kw)[name]

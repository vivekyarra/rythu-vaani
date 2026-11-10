"""Paths and runtime mode. The Gnani key is read ONLY from the GNANI_API_KEY environment variable
(optionally loaded from a gitignored .env by rythu_vaani.config). No key -> MOCK mode."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from rythu_vaani.config import ROOT, get_api_key  # noqa: F401  (loads .env without overriding env)

DATA = ROOT / "data" / "audit"
AUDIO_DIR = DATA / "audio"            # committed MP3 copies of the synthetic calls (for the dashboard)
STORE = Path(os.environ.get("VAANI_AUDIT_STORE", str(DATA / "store")))  # audited calls (JSON)
CACHE = ROOT / ".vaani-audit-cache"  # gitignored: Timbre turn cache, WAV renders, raw transcripts
RESULTS = ROOT / "results" / "audit"


def is_mock() -> bool:
    return get_api_key() is None


@lru_cache(maxsize=1)
def roster() -> dict:
    return json.loads((DATA / "agents.json").read_text(encoding="utf-8"))


def agent(agent_id: str) -> dict:
    a = roster()["agents"].get(agent_id)
    if not a:
        return {"id": agent_id, "name": agent_id, "gender": "m", "aliases": [], "voice": "Prakash"}
    return {"id": agent_id, **a}


def lender() -> dict:
    return roster()["lender"]


def stt_client():
    from .prisma import MockPrismaBatch, PrismaBatch

    key = get_api_key()
    return PrismaBatch(key) if key else MockPrismaBatch()


def tts_client():
    from rythu_vaani.gnani import GnaniClient, MockGnaniClient

    key = get_api_key()
    return GnaniClient(key) if key else MockGnaniClient()

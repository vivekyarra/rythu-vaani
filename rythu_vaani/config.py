"""Runtime configuration.

The Gnani API key is read ONLY from the GNANI_API_KEY environment variable,
which is normally populated from a local, gitignored `.env` file.
When the key is missing or empty the app runs in MOCK mode.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# Does not override variables that are already set (tests rely on this).
load_dotenv(ROOT / ".env", override=False)


def get_api_key() -> str | None:
    key = os.environ.get("GNANI_API_KEY", "").strip()
    return key or None


def is_mock_mode() -> bool:
    return get_api_key() is None


def get_client():
    """Real Gnani client when a key is configured, otherwise the labelled mock."""
    from .gnani import GnaniClient, MockGnaniClient

    key = get_api_key()
    return GnaniClient(key) if key else MockGnaniClient()

"""Optional LLM reviewer that can ADD findings the lexicon missed, but can never invent one.

Guard rails (enforced in code, not by prompt):
* the LLM must return, for each finding, a ``segment`` index and a ``quote``;
* the finding is kept only if the segment exists, is an AGENT segment, the category is a span
  category of the checklist, and the quote is literally contained in that segment's transcript text
  (after the same normalisation the rules use);
* the timestamp is taken from the segment, never from the LLM;
* kept findings are marked ``source="llm"`` so the UI shows them as model-suggested.

Off by default. Enabled when ``ANTHROPIC_API_KEY`` is set and ``use_llm=True``.
None of the measured results in AUDIT_PITCH.md use the LLM (no key was available for the runs).
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

import httpx

from .checklist import CHECKS, SPAN_CATEGORIES
from .rules import Finding, norm

DEFAULT_MODEL = os.environ.get("VAANI_AUDIT_LLM_MODEL", "claude-sonnet-5-5")

PROMPT = """You audit an Indian loan-collection call for RBI fair-practices violations.
Segments (index | speaker role | text):
{segments}

Categories (agent behaviour only):
{categories}

Return ONLY a JSON array. Each item: {{"category": <one of the categories>, "segment": <index>,
"quote": <exact words copied from that segment>, "reason": <short English>}}.
Only report violations clearly present in an AGENT segment. If none, return []."""


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _anthropic_call(prompt: str, model: str = DEFAULT_MODEL) -> str:
    resp = httpx.post(
        os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages"),
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    resp.raise_for_status()
    return "".join(b.get("text", "") for b in resp.json().get("content", []))


def verify(raw: list, segments: list[dict]) -> list[Finding]:
    """Keep only findings whose quote is literally in the cited agent segment."""
    kept = []
    for item in raw if isinstance(raw, list) else []:
        try:
            cat, idx, quote = item["category"], int(item["segment"]), str(item["quote"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if cat not in SPAN_CATEGORIES or not 0 <= idx < len(segments) or len(norm(quote)) < 3:
            continue
        seg = segments[idx]
        if seg.get("role") != "agent" or norm(quote) not in norm(seg["text"]):
            continue
        kept.append(Finding(cat, seg["start"], seg["end"], seg["text"], matched=quote,
                            note=str(item.get("reason", ""))[:200], source="llm"))
    return kept


def review(segments: list[dict], complete: Callable[[str], str] | None = None) -> list[Finding]:
    complete = complete or _anthropic_call
    listing = "\n".join(f"{i} | {s.get('role')} | {s['text']}" for i, s in enumerate(segments))
    cats = "\n".join(f"- {c}: {CHECKS[c].rule}" for c in SPAN_CATEGORIES)
    text = complete(PROMPT.format(segments=listing, categories=cats))
    m = re.search(r"\[.*\]", text, re.S)
    try:
        raw = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        raw = []
    return verify(raw, segments)

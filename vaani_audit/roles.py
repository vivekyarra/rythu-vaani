"""Map Prisma's diarized ``speaker_id`` labels to call roles (agent vs borrower side).

Prisma Batch labels speakers 1, 2, ... but does not know which one is the collection agent.
Heuristic (documented, deterministic): score each speaker on agent cues and pick the highest:
  +3  mentions the lender (from the roster's aliases)
  +3  says the agent's own name (from dialer metadata: which agent placed the call)
  +1  per segment mentioning debt words (EMI, loan, payment ...), capped at 3
  +1  speaks first (outbound collection calls are opened by the agent in our recordings)
Everyone else is ``borrower`` side (the borrower or whoever picked up the phone).
If a recording is dual-channel (agent and customer on separate channels), use the channel instead:
that is exact and needs no heuristic.
"""
from __future__ import annotations

from collections import defaultdict

from .rules import DEBT, _has_alias, norm


def assign_roles(segments: list[dict], agent_aliases: list[str], lender_aliases: list[str]) -> dict:
    """Sets ``seg['role']`` in place. Returns {'agent_speaker': id, 'scores': {id: score}}."""
    if not segments:
        return {"agent_speaker": None, "scores": {}}
    scores: dict = defaultdict(float)
    debt_hits: dict = defaultdict(int)
    for seg in segments:
        sid, t = seg["speaker_id"], norm(seg["text"])
        scores[sid] += 0
        if _has_alias(t, lender_aliases):
            scores[sid] += 3
        if agent_aliases and _has_alias(t, agent_aliases):
            scores[sid] += 3
        if DEBT.search(t) and debt_hits[sid] < 3:
            debt_hits[sid] += 1
            scores[sid] += 1
    scores[segments[0]["speaker_id"]] += 1
    agent = max(scores, key=lambda k: (scores[k], -list(scores).index(k)))
    for seg in segments:
        seg["role"] = "agent" if seg["speaker_id"] == agent else "borrower"
    return {"agent_speaker": agent, "scores": dict(scores)}

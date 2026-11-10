"""Audited calls as one JSON file each, plus team-level aggregation for the dashboard."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import config
from .checklist import CHECKS
from .coaching import coaching_card

_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def _dir() -> Path:
    d = Path(config.STORE)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(audit: dict) -> None:
    if not _SAFE.match(audit["call_id"]):
        raise ValueError("bad call_id")
    (_dir() / f"{audit['call_id']}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")


def get(call_id: str) -> dict | None:
    if not _SAFE.match(call_id):
        return None
    p = _dir() / f"{call_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_all() -> list[dict]:
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in _dir().glob("*.json")),
                  key=lambda a: a.get("call_time") or "")


def summary(a: dict) -> dict:
    return {k: a.get(k) for k in ("call_id", "agent_id", "agent_name", "language", "call_time", "mock", "synthetic")} | {
        "score": a["scorecard"]["score"], "compliant": a["scorecard"]["compliant"],
        "violations": sorted({f["category"] for f in a["findings"]}),
        "duration_s": a["stt"].get("duration_s"), "model": a["stt"].get("model")}


def team(audits: list[dict]) -> dict:
    by_agent = defaultdict(list)
    for a in audits:
        by_agent[a["agent_id"]].append(a)
    cat_calls = Counter(c for a in audits for c in {f["category"] for f in a["findings"]})
    agents = []
    for aid, items in sorted(by_agent.items()):
        ag = config.agent(aid)
        comp = sum(1 for a in items if a["scorecard"]["compliant"])
        agents.append({"agent_id": aid, "name": ag["name"], "team": ag.get("team"), "calls": len(items),
                       "compliant": comp, "compliance_rate": round(comp / len(items), 3),
                       "avg_score": round(sum(a["scorecard"]["score"] for a in items) / len(items), 1),
                       "critical": sum(a["scorecard"]["critical"] for a in items),
                       "top": Counter(f["category"] for a in items for f in a["findings"]).most_common(2)})
    n = len(audits)
    comp = sum(1 for a in audits if a["scorecard"]["compliant"])
    return {
        "calls": n, "compliant": comp, "compliance_rate": round(comp / n, 3) if n else None,
        "critical_calls": sum(1 for a in audits if a["scorecard"]["critical"]),
        "audio_minutes": round(sum((a["stt"].get("duration_s") or 0) for a in audits) / 60, 1),
        "agents": agents,
        "violations": [{"category": c, "title": CHECKS[c].title, "severity": CHECKS[c].severity, "calls": k}
                       for c, k in cat_calls.most_common()],
        "mock": any(a.get("mock") for a in audits),
    }


def coaching(agent_id: str, audits: list[dict]) -> dict:
    ag = config.agent(agent_id)
    return coaching_card(ag, [a for a in audits if a["agent_id"] == agent_id])

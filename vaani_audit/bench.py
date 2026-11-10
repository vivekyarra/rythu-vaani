"""Measure violation detection on the scripted sample calls: precision / recall per checklist category,
per phone-line condition, per STT system. Held-out calls are reported separately and were never
used to write or tune the rules.

Matching:
* span categories (THREAT, ABUSE, SHAMING, THIRD_PARTY): a predicted finding is a true positive if
  its segment overlaps the ground-truth turn (+-1.0 s tolerance). One prediction per labelled turn;
  further predictions of the same category overlapping an already-matched turn are ignored
  (diarization can split one turn into two segments); all others are false positives.
* call categories (NO_DISCLOSURE, NO_GRIEVANCE): present / absent per call.
* CALL_HOURS comes from call metadata, not audio; it is reported once, not per condition.

Also reported: CER of the transcript vs the script, role accuracy of the diarization + role
heuristic (share of script turns whose best-overlapping segment has the right role), and Batch
job wall time.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from rythu_vaani.audio import cer

from . import config
from .audit import audit_transcript, stt_options
from .checklist import AUDIO_CATEGORIES, SPAN_CATEGORIES
from .prisma import MODEL_V25, MODEL_V3, Transcript
from .synth import CONDITIONS, script_segments

TOL = 1.0
SYSTEMS = {
    "v2.5": {"model": MODEL_V25, "context": False},
    "v3.0": {"model": MODEL_V3, "context": False},
    "v3.0+ctx": {"model": MODEL_V3, "context": True},
}


def _overlap(a0, a1, b0, b1, tol=TOL) -> bool:
    return a0 < b1 + tol and b0 < a1 + tol


def match_call(truth: dict, findings: list[dict]) -> dict[str, dict]:
    """Per-category tp/fp/fn counts for one call."""
    out = {c: {"tp": 0, "fp": 0, "fn": 0} for c in AUDIO_CATEGORIES}
    labels = truth["labels"]
    for cat in SPAN_CATEGORIES:
        gts = [truth["turns"][l["turn"]] for l in labels if l["category"] == cat]
        preds = [f for f in findings if f["category"] == cat]
        matched = set()
        for p in preds:
            hit = next((i for i, g in enumerate(gts) if _overlap(p["start"], p["end"], g["start"], g["end"])), None)
            if hit is None:
                out[cat]["fp"] += 1
            elif hit not in matched:
                matched.add(hit)
                out[cat]["tp"] += 1
        out[cat]["fn"] += len(gts) - len(matched)
    for cat in ("NO_DISCLOSURE", "NO_GRIEVANCE"):
        g = any(l["category"] == cat for l in labels)
        p = any(f["category"] == cat for f in findings)
        out[cat]["tp" if g and p else "fp" if p else "fn" if g else "tn"] = 1
    return out


def role_accuracy(truth: dict, segments: list[dict]) -> float:
    ok = 0
    for t in truth["turns"]:
        best, best_ov = None, 0.0
        for s in segments:
            ov = min(t["end"], s["end"]) - max(t["start"], s["start"])
            if ov > best_ov:
                best, best_ov = s, ov
        ok += bool(best and best.get("role") == t["speaker"])
    return ok / len(truth["turns"])


def prf(c: dict) -> dict:
    tp, fp, fn = c["tp"], c["fp"], c["fn"]
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def evaluate(truths: dict, transcripts: dict[str, Transcript]) -> dict:
    """transcripts keyed by call id. Returns per-category PRF, micro PRF, CER, role accuracy."""
    agg = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    cers, roles, per_call = [], [], {}
    for cid, tr in transcripts.items():
        t = truths[cid]
        a = audit_transcript(tr, {"call_id": cid, "agent_id": t["agent_id"], "language": t["language"],
                                  "call_time": t["call_time"]})
        m = match_call(t, a["findings"])
        for cat, c in m.items():
            for k in ("tp", "fp", "fn"):
                agg[cat][k] += c.get(k, 0)
        ref = " ".join(x["text"] for x in t["turns"])
        cers.append(cer(ref, tr.text))
        roles.append(role_accuracy(t, a["segments"]))
        per_call[cid] = {"findings": [(f["category"], f["start"]) for f in a["findings"]],
                         "labels": t["labels"], "cer": cers[-1], "role_acc": roles[-1]}
    micro = {"tp": 0, "fp": 0, "fn": 0}
    for c in agg.values():
        for k in micro:
            micro[k] += c[k]
    return {"categories": {c: prf(agg[c]) for c in AUDIO_CATEGORIES}, "micro": prf(micro),
            "cer": sum(cers) / len(cers) if cers else None,
            "role_accuracy": sum(roles) / len(roles) if roles else None, "calls": per_call}


def oracle_transcripts(truths: dict) -> dict[str, Transcript]:
    return {cid: Transcript(name=cid, segments=script_segments(t), model="oracle (script text)",
                            language_code=t["language"], duration_s=t["duration_s"])
            for cid, t in truths.items()}


def run_stt(truths: dict, system: str, condition: str, channels: str = "mono", stt=None,
            cache: Path | None = None) -> dict[str, Transcript]:
    """Transcribe every call for one (system, condition, channels). One Batch job per language, run
    concurrently. ``channels="stereo"``: both legs of a call go into the same job, roles from channels.
    Raw transcripts are cached on disk (and committed under results/audit/raw*)."""
    from concurrent.futures import ThreadPoolExecutor

    from .audit import CH_AGENT, CH_BORROWER, merge_channels
    stt = stt or config.stt_client()
    cache = cache or config.RESULTS / ("raw" if channels == "mono" else "raw_stereo")
    out, todo = {}, defaultdict(list)
    for cid, t in truths.items():
        p = cache / system / condition / f"{cid}.json"
        if p.exists():
            out[cid] = Transcript.from_dict(json.loads(p.read_text(encoding="utf-8")))
        else:
            todo[t["language"]].append(cid)

    def job(lang, cids):
        opts = stt_options(lang, SYSTEMS[system]["model"], SYSTEMS[system]["context"])
        d = config.CACHE / "calls" / condition
        if channels == "mono":
            files = [(f"{cid}.wav", (d / f"{cid}.wav").read_bytes()) for cid in cids]
        else:
            files = [(f"{cid}.{ch}.wav", (d / f"{cid}.{ch}.wav").read_bytes()) for cid in cids for ch in (CH_AGENT, CH_BORROWER)]
        res = stt.transcribe_many(files, **opts)
        got = {}
        for cid in cids:
            if channels == "mono":
                tr = res[f"{cid}.wav"]
                tr.name = cid
            else:
                tr = merge_channels(cid, res[f"{cid}.{CH_AGENT}.wav"], res[f"{cid}.{CH_BORROWER}.wav"])
            got[cid] = tr
        return got

    with ThreadPoolExecutor(max_workers=4) as ex:
        for got in ex.map(lambda kv: job(*kv), list(todo.items())):
            for cid, tr in got.items():
                out[cid] = tr
                if not tr.mock:
                    p = cache / system / condition / f"{cid}.json"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(tr.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def run(systems=("v2.5", "v3.0+ctx"), conditions=tuple(CONDITIONS), channels=("stereo", "mono"), stt=None) -> dict:
    from .synth import load_truth
    truths = load_truth()
    splits = {s: {k: v for k, v in truths.items() if v["split"] == s} for s in ("dev", "heldout")}
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "tolerance_s": TOL, "results": {}, "latency": {},
              "diarization": {}}
    report["results"]["oracle"] = {s: evaluate(tr, oracle_transcripts(tr)) for s, tr in splits.items()}
    for ch in channels:
        for system in systems:
            for cond in conditions:
                trs = run_stt(truths, system, cond, ch, stt=stt)
                key = f"{system}|{ch}|{cond}"
                report["results"][key] = {s: evaluate(tt, {c: trs[c] for c in tt}) for s, tt in splits.items()}
                jobs = {}
                for tr in trs.values():
                    if tr.job_wall_s is not None:
                        jobs[tr.job_id] = tr.job_wall_s
                audio = sum(truths[c]["duration_s"] for c in trs)
                report["latency"][key] = {"jobs": len(jobs), "calls": len(trs), "audio_s": round(audio, 1),
                                          "job_wall_s": sorted(jobs.values()),
                                          "keywords_accepted": all(bool((t.config_echo or {}).get("keywords")) for t in trs.values())
                                          if SYSTEMS[system]["context"] else None}
                if ch == "mono":
                    report["diarization"][key] = {"single_speaker_calls": sum(
                        1 for t in trs.values() if len({s.speaker_id for s in t.segments}) < 2), "calls": len(trs)}
    return report


def _fmt(x, pct=True):
    if x is None:
        return "n/a"
    return f"{x:.2f}"


def to_markdown(rep: dict, split: str = "heldout") -> str:
    R = rep["results"]
    keys = [k for k in R if k != "oracle"]
    cats = AUDIO_CATEGORIES
    lines = [f"### {split} set: precision / recall per category", "",
             "| system | condition | " + " | ".join(cats) + " | micro P / R / F1 | CER | role acc |",
             "|---|---|" + "---|" * (len(cats) + 3)]
    def row(name, cond, ev):
        cells = []
        for c in cats:
            m = ev["categories"][c]
            cells.append(f"{_fmt(m['precision'])} / {_fmt(m['recall'])}")
        mi = ev["micro"]
        return (f"| {name} | {cond} | " + " | ".join(cells) +
                f" | {_fmt(mi['precision'])} / {_fmt(mi['recall'])} / {_fmt(mi['f1'])} | "
                f"{_fmt(ev['cer'])} | {_fmt(ev['role_accuracy'])} |")
    lines.append(row("oracle (script text)", "-", R["oracle"][split]))
    for k in keys:
        sysname, ch, cond = k.split("|")
        lines.append(row(f"{sysname} ({ch})", cond, R[k][split]))
    counts = R["oracle"][split]["categories"]
    lines += ["", "Labelled positives per category: " +
              ", ".join(f"{c} {counts[c]['tp'] + counts[c]['fn']}" for c in cats)]
    return "\n".join(lines)

"""The audit pipeline: call audio + metadata -> Prisma transcript -> roles -> checklist -> scorecard."""
from __future__ import annotations

from . import config
from .checklist import CHECKS, SEVERITY_PENALTY
from .coaching import TIP_EN, rephrase
from .prisma import LANG_CODES, MODEL_V3, Segment, Transcript

CH_AGENT, CH_BORROWER = "ch0", "ch1"
from .roles import assign_roles
from .rules import run_rules

# Prisma v3.0 context for collection calls: lender + product words and the legal/threat phrases we
# most need transcribed correctly. Sent as Batch `keywords` (see prisma.py for the field name).
DOMAIN_KEYWORDS = [
    "EMI", "loan", "overdue", "payment", "due date", "late fee", "restructuring", "credit bureau", "CIBIL",
    "grievance officer", "helpline", "complaint", "customer care", "branch", "loan agreement",
    "police", "arrest warrant", "jail", "court", "legal notice", "seize", "WhatsApp group", "neighbours",
    "किस्त", "बकाया", "लोन", "ईएमआई", "शिकायत", "शिकायत अधिकारी", "ग्रीवेंस ऑफिसर", "हेल्पलाइन",
    "पुलिस", "गिरफ्तार", "जेल", "वारंट", "मोहल्ले", "पड़ोसी", "रिश्तेदार", "बेशर्म", "धोखेबाज़",
    "బకాయి", "లోన్", "ఈఎంఐ", "ఫిర్యాదు", "గ్రీవెన్స్ ఆఫీసర్", "హెల్ప్‌లైన్", "పోలీస్", "అరెస్ట్", "జైలు",
    "వారెంట్", "జప్తు", "వాట్సాప్ గ్రూప్", "బంధువులు", "అబద్ధాలకోరు", "మోసగాడు",
]

TOPIC = ("A recorded phone call from a loan recovery agent of an Indian NBFC to a borrower about an "
         "overdue EMI. Hindi, Telugu or code-mixed with English. May include payment dates, "
         "grievance helpline, threats, police or legal words.")


def keywords_for(agent_id: str | None = None) -> list[str]:
    kw = [config.lender()["name"], *[a["name"] for a in config.roster()["agents"].values()], *DOMAIN_KEYWORDS]
    return list(dict.fromkeys(kw))[:200]


def stt_options(language: str, model: str = MODEL_V3, context: bool = True) -> dict:
    opts = {"model": model, "language_code": LANG_CODES[model][language]}
    if model == MODEL_V3 and context:
        opts.update(keywords=keywords_for(), topic=TOPIC)
    return opts


def scorecard(findings: list[dict]) -> dict:
    by_cat = {}
    for f in findings:
        by_cat.setdefault(f["category"], []).append(f)
    checks = [{"id": cid, "title": c.title, "severity": c.severity, "rule": c.rule,
               "passed": cid not in by_cat, "findings": len(by_cat.get(cid, []))}
              for cid, c in CHECKS.items()]
    score = max(0, 100 - sum(SEVERITY_PENALTY[CHECKS[c].severity] for c in by_cat))
    return {"score": score, "compliant": not findings, "checks": checks,
            "critical": sum(1 for f in findings if f["severity"] == "critical")}


def audit_transcript(tr: Transcript, meta: dict, use_llm: bool = False) -> dict:
    """``meta``: call_id, agent_id, language, call_time (ISO, IST)."""
    ag = config.agent(meta["agent_id"])
    lender = config.lender()
    segs = [s.to_dict() for s in sorted(tr.segments, key=lambda s: s.start)]
    if segs and all(s.get("role") for s in segs):  # dual-channel: role comes from the channel
        roles = {"method": "dual-channel (channel 0 = agent, channel 1 = customer)", "agent_speaker": CH_AGENT}
    else:
        roles = {"method": "Prisma diarization + role heuristic (mono)",
                 **assign_roles(segs, ag.get("aliases", []), lender["aliases"])}
    findings = run_rules(segs, ag.get("aliases", []), lender["aliases"], meta.get("call_time"))
    if use_llm:
        from .llm import llm_available, review
        if llm_available():
            seen = {(f.category, f.start) for f in findings}
            findings += [f for f in review(segs) if (f.category, f.start) not in seen]
    fdicts = sorted((f.to_dict() for f in findings), key=lambda f: (f["start"], f["category"]))
    for f in fdicts:
        f["tip"] = TIP_EN[f["category"]]
        f["rephrase"] = rephrase(f["category"], meta["language"], ag["name"], lender["name"], ag.get("gender", "m"))
    return {
        "call_id": meta["call_id"], "agent_id": ag["id"], "agent_name": ag["name"],
        "language": meta["language"], "call_time": meta.get("call_time"), "lender": lender["name"],
        "synthetic": meta.get("synthetic", True), "mock": tr.mock,
        "stt": {"model": tr.model, "language_code": tr.language_code, "job_id": tr.job_id,
                "job_wall_s": tr.job_wall_s, "duration_s": tr.duration_s,
                "keywords_accepted": bool((tr.config_echo or {}).get("keywords")),
                "topic_accepted": bool((tr.config_echo or {}).get("topic"))},
        "roles": roles, "segments": segs, "findings": fdicts, "scorecard": scorecard(fdicts),
    }


def merge_channels(name: str, agent: Transcript, borrower: Transcript) -> Transcript:
    """Two single-leg transcripts -> one time-ordered transcript with exact roles."""
    segs = [Segment(s.start, s.end, s.text, CH_AGENT, s.language, "agent") for s in agent.segments]
    segs += [Segment(s.start, s.end, s.text, CH_BORROWER, s.language, "borrower") for s in borrower.segments]
    segs.sort(key=lambda s: (s.start, s.end))
    durs = [d for d in (agent.duration_s, borrower.duration_s) if d]
    return Transcript(name=name, segments=segs, model=agent.model, language_code=agent.language_code,
                      duration_s=max(durs) if durs else None, job_id=agent.job_id, mock=agent.mock,
                      job_wall_s=agent.job_wall_s, config_echo=agent.config_echo)


def transcribe_call(stt, call_id: str, audio: bytes, language: str, model: str = MODEL_V3, context: bool = True,
                    mock_script: list | None = None) -> Transcript:
    """Stereo WAV -> both legs in ONE Batch job, roles from channels. Mono WAV -> Prisma diarization."""
    from .synth import split_stereo
    opts = stt_options(language, model, context)
    legs = split_stereo(audio)
    mock = getattr(stt, "mock", False)
    if legs:
        names = (f"{call_id}.{CH_AGENT}.wav", f"{call_id}.{CH_BORROWER}.wav")
        if mock and mock_script is not None:
            stt.scripts[names[0]] = [s for s in mock_script if s.speaker_id == 1]
            stt.scripts[names[1]] = [s for s in mock_script if s.speaker_id != 1]
        res = stt.transcribe_many(list(zip(names, legs)), **opts)
        return merge_channels(call_id, res[names[0]], res[names[1]])
    name = f"{call_id}.wav"
    if mock and mock_script is not None:
        stt.scripts[name] = mock_script
    return stt.transcribe(name, audio, **opts)


def audit_audio(audio: bytes, meta: dict, stt=None, model: str = MODEL_V3, context: bool = True,
                mock_script: list | None = None, use_llm: bool = False) -> dict:
    stt = stt or config.stt_client()
    tr = transcribe_call(stt, meta["call_id"], audio, meta["language"], model, context, mock_script)
    return audit_transcript(tr, meta, use_llm=use_llm)

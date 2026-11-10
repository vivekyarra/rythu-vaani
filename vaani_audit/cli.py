"""Vaani Audit command line.

  python -m vaani_audit audit CALL.wav --agent AG-101 --language hi-IN --time 2026-10-13T20:15:00+05:30
  python -m vaani_audit synth            # voice the synthetic scripts with Timbre, build phone-line WAVs
  python -m vaani_audit bench            # P/R per category x condition x STT system (writes results/audit/)
  python -m vaani_audit populate         # audit every synthetic call (v3.0+ctx, phone line) into the dashboard store
  python -m vaani_audit serve            # FastAPI + dashboard on http://127.0.0.1:8100
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import config


def _banner():
    m = "MOCK (no GNANI_API_KEY: transcripts are placeholders/scripts, audio is beeps)" if config.is_mock() else "LIVE Gnani API"
    print(f"[vaani-audit] mode: {m}", file=sys.stderr)


def cmd_audit(a):
    from .audit import audit_audio
    res = audit_audio(open(a.wav, "rb").read(), {"call_id": a.call_id or "cli", "agent_id": a.agent,
                                                  "language": a.language, "call_time": a.time},
                      use_llm=a.llm)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    sc = res["scorecard"]
    print(f"\nScore {sc['score']}/100  {'COMPLIANT' if sc['compliant'] else 'VIOLATIONS FOUND'}   STT: {res['stt']['model']}")
    for s in res["segments"]:
        print(f"  [{s['start']:6.1f}-{s['end']:6.1f}] {s['role']:8s} {s['text']}")
    print()
    for c in sc["checks"]:
        print(f"  {'PASS' if c['passed'] else 'FAIL'}  {c['title']}")
    for f in res["findings"]:
        print(f"\n  ! {f['category']} ({f['severity']}) at {f['start']:.1f}s  matched: {f['matched']!r}\n    \"{f['quote']}\"  {f['note']}")


def cmd_synth(a):
    from . import synth
    t = time.time()
    truth = synth.build()
    synth.truth_path().write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rendered {len(truth)} calls in {time.time() - t:.0f}s -> {config.CACHE / 'calls'}")


def cmd_bench(a):
    from . import bench
    rep = bench.run(systems=a.systems, conditions=a.conditions, channels=a.channels)
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    (config.RESULTS / f"bench_{ts}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    md = bench.to_markdown(rep, "heldout") + "\n\n" + bench.to_markdown(rep, "dev")
    (config.RESULTS / f"bench_{ts}.md").write_text(md, encoding="utf-8")
    print(md)


def cmd_populate(a):
    from . import bench, store
    from .audit import audit_transcript
    from .synth import load_truth
    truths = load_truth()
    trs = bench.run_stt(truths, a.system, a.condition, a.channels)
    for cid, tr in trs.items():
        t = truths[cid]
        res = audit_transcript(tr, {"call_id": cid, "agent_id": t["agent_id"], "language": t["language"],
                                    "call_time": t["call_time"]})
        res["split"] = t["split"]
        store.save(res)
    print(f"stored {len(trs)} audited calls in {config.STORE}")


def cmd_serve(a):
    import uvicorn
    uvicorn.run("vaani_audit.api:app", host=a.host, port=a.port)


def main(argv=None):
    from .bench import SYSTEMS
    from .synth import CONDITIONS
    p = argparse.ArgumentParser(prog="vaani-audit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("audit")
    s.add_argument("wav")
    s.add_argument("--agent", required=True)
    s.add_argument("--language", required=True, choices=["hi-IN", "te-IN", "hi-en", "te-en"])
    s.add_argument("--time", default=None, help="call start, ISO 8601 with offset")
    s.add_argument("--call-id", default="")
    s.add_argument("--llm", action="store_true", help="also run the optional quote-verified LLM reviewer")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_audit)
    sub.add_parser("synth").set_defaults(fn=cmd_synth)
    b = sub.add_parser("bench")
    b.add_argument("--systems", nargs="+", default=["v2.5", "v3.0+ctx"], choices=list(SYSTEMS))
    b.add_argument("--channels", nargs="+", default=["stereo", "mono"], choices=["stereo", "mono"])
    b.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=list(CONDITIONS))
    b.set_defaults(fn=cmd_bench)
    po = sub.add_parser("populate")
    po.add_argument("--system", default="v3.0+ctx", choices=list(SYSTEMS))
    po.add_argument("--condition", default="clean", choices=list(CONDITIONS))
    po.add_argument("--channels", default="stereo", choices=["stereo", "mono"])
    po.set_defaults(fn=cmd_populate)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8100)
    sv.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    _banner()
    a.fn(a)


if __name__ == "__main__":
    main()

"""Noise-robustness benchmark: Timbre TTS -> simulated noisy 8 kHz phone line -> Prisma STT.

For each synthetic caller sentence:
  1. synthesise clean 16 kHz Telugu speech with Timbre v2.5 (cached in bench_cache/),
  2. degrade it: 8 kHz, added noise at each SNR, 300-3400 Hz band-pass, G.711 mu-law,
  3. transcribe with Prisma v2.5 (te-IN, format=verbatim),
  4. score WER, CER and whether the helpline still gets the same intent + slots.

This is the Rythu Vaani-specific front end (farmer-helpline sentence sets, intent scoring,
KB keyterms) over the generic engine in ``vaani_bench`` (see ``python -m vaani_bench --help``).

Real mode (GNANI_API_KEY set) writes results/benchmark_<timestamp>.{json,md}.
MOCK mode runs the same degradation on placeholder (non-speech) fixtures, prints the
measured channel SNR only, and writes nothing: there is no WER without a real STT.

  python scripts/noise_benchmark.py                 # SNRs 20 10 5 0, pink noise
  python scripts/noise_benchmark.py --noise hum --snrs 15 5 --limit 3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rythu_vaani import audio as A  # noqa: E402
from rythu_vaani import gnani  # noqa: E402
from rythu_vaani.config import get_client  # noqa: E402
from rythu_vaani.kb import default_kb  # noqa: E402
from rythu_vaani.nlu import parse  # noqa: E402
from vaani_bench import core  # noqa: E402  (generic engine; this script adds the helpline specifics)

CLEAN_SR = core.CLEAN_SR
channel_snr_db = core.channel_snr_db


def conditions(snrs: list[float]) -> list[tuple[str, bool, float | None]]:
    """(label, through_phone_channel, snr_db)"""
    return core.parse_conditions(["clean", "phone"] + [f"{s:g}" for s in snrs], clean_label="clean 16k")


def run(args) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    client = get_client()
    sentences = json.loads((ROOT / "data" / args.sentences).read_text(encoding="utf-8"))["sentences"]
    sentences = sentences[: args.limit] if args.limit else sentences
    conds = conditions(args.snrs)
    kb = default_kb()
    stt_kwargs = {}
    if args.stt != "v2.5":
        stt_kwargs["model"] = gnani.STT_MODEL_V3
    if args.stt == "v3-context":
        stt_kwargs["keyterms"], stt_kwargs["topic"] = kb.stt_context()
    set_name = Path(args.sentences).stem

    if client.mock:
        print("=" * 70 + "\n MOCK MODE: no GNANI_API_KEY. Placeholder (non-speech) fixtures, no STT.\n"
              " Only the measured channel SNR is shown. No WER is reported or saved.\n" + "=" * 70)

    prefix = "clean" if set_name == "benchmark_sentences" else f"{set_name}_clean"
    items = core.items_from_sentences(
        sentences, client, cache_dir=ROOT / "bench_cache",
        cache_name=lambda i, _text: f"{prefix}_{i:02d}_{gnani.TTS_VOICE}.wav")

    def same_intent(ref: str, hyp: str) -> bool:
        r, h = parse(ref, kb), parse(hyp, kb)
        return (r.name, r.slots) == (h.name, h.slots)

    rows = core.evaluate(items, conds, client, noise=args.noise, fmt="verbatim",
                         stt_kwargs=stt_kwargs, intent_fn=same_intent)
    for r in rows:  # keep the original results/benchmark_*.json row shape
        r.pop("id", None)
    table = core.markdown_table(core.summarise(rows, conds), client.mock, intent=True)
    print("\n" + table)
    if client.mock:
        return 0

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stt_label = {"v2.5": gnani.STT_MODEL, "v3": gnani.STT_MODEL_V3,
                 "v3-context": f"{gnani.STT_MODEL_V3} + keyterms/topic"}[args.stt]
    stamp = f"{stamp}_{args.stt}_{set_name}"
    meta = {"date": stamp, "mode": "real", "stt": f"{stt_label} (te-IN, verbatim)", "sentences": args.sentences,
            "tts": f"{gnani.TTS_MODEL} voice {gnani.TTS_VOICE}", "noise": args.noise,
            "n_sentences": len(sentences),
            "channel": "8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law"}
    (out / f"benchmark_{stamp}.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False,
                                                            indent=2), encoding="utf-8")
    (out / f"benchmark_{stamp}.md").write_text(
        f"# Noise benchmark {stamp}\n\n" + "\n".join(f"- {k}: {v}" for k, v in meta.items()) + "\n\n" + table + "\n",
        encoding="utf-8")
    print(f"\nsaved results/benchmark_{stamp}.json and .md")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--snrs", type=float, nargs="+", default=[20, 10, 5, 0])
    p.add_argument("--noise", choices=A.NOISE_KINDS, default="pink")
    p.add_argument("--limit", type=int, default=0, help="only the first N sentences")
    p.add_argument("--stt", choices=["v2.5", "v3", "v3-context"], default="v2.5",
                   help="Prisma v2.5 (default), v3.0, or v3.0 with keyterms + topic from the KB")
    p.add_argument("--sentences", default="benchmark_sentences.json",
                   help="sentence file in data/ (use a held-out file to avoid tuning on the test set)")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

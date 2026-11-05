"""Noise-robustness benchmark: Timbre TTS -> simulated noisy 8 kHz phone line -> Prisma STT.

For each synthetic caller sentence:
  1. synthesise clean 16 kHz Telugu speech with Timbre v2.5 (cached in bench_cache/),
  2. degrade it: 8 kHz, added noise at each SNR, 300-3400 Hz band-pass, G.711 mu-law,
  3. transcribe with Prisma v2.5 (te-IN, format=verbatim),
  4. score WER, CER and whether the helpline still gets the same intent + slots.

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
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rythu_vaani import audio as A  # noqa: E402
from rythu_vaani import gnani  # noqa: E402
from rythu_vaani.config import get_client  # noqa: E402
from rythu_vaani.kb import default_kb  # noqa: E402
from rythu_vaani.nlu import parse  # noqa: E402

CLEAN_SR = 16000


def conditions(snrs: list[float]) -> list[tuple[str, bool, float | None]]:
    """(label, through_phone_channel, snr_db)"""
    return [("clean 16k", False, None), ("phone, no noise", True, None)] + [
        (f"phone, {s:g} dB", True, s) for s in snrs
    ]


def channel_snr_db(clean_phone: np.ndarray, noisy_phone: np.ndarray) -> float:
    """SNR actually present after the channel (band-pass + mu-law), measured, not nominal."""
    noise = noisy_phone - clean_phone
    pn = A.power(noise)
    return float("inf") if pn == 0 else 10 * np.log10(A.power(clean_phone) / pn)


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

    cache = ROOT / "bench_cache"
    if not client.mock:
        cache.mkdir(exist_ok=True)
    rows = []
    for i, ref in enumerate(sentences):
        if client.mock:
            clean = A.placeholder_signal(2.5, CLEAN_SR, seed=i)
        else:
            prefix = "clean" if set_name == "benchmark_sentences" else f"{set_name}_clean"
            path = cache / f"{prefix}_{i:02d}_{gnani.TTS_VOICE}.wav"
            if not path.exists():
                path.write_bytes(client.synthesize(ref, sample_rate=CLEAN_SR))
            clean, sr = A.read_wav(path.read_bytes())
            clean = A.resample(clean, sr, CLEAN_SR)
        phone_ref = A.degrade_to_phone(clean, CLEAN_SR, None, args.noise)
        ref_intent = parse(ref, kb)

        for label, phone, snr in conds:
            if not phone:
                wav, measured = A.write_wav(clean, CLEAN_SR), None
            else:
                y = A.degrade_to_phone(clean, CLEAN_SR, snr, args.noise, seed=i)
                measured = channel_snr_db(phone_ref, y) if snr is not None else None
                wav = A.write_wav(y, A.PHONE_SR)
            row = {"sentence": i, "condition": label, "snr_db": snr,
                   "measured_channel_snr_db": None if measured is None else round(measured, 1)}
            if not client.mock:
                t0 = time.perf_counter()
                stt = client.transcribe(wav, f"s{i}.wav", fmt="verbatim", **stt_kwargs)
                hyp_intent = parse(stt.transcript, kb)
                row.update(reference=ref, hypothesis=stt.transcript,
                           wer=round(A.wer(ref, stt.transcript), 4), cer=round(A.cer(ref, stt.transcript), 4),
                           intent_ok=(hyp_intent.name, hyp_intent.slots) == (ref_intent.name, ref_intent.slots),
                           latency_ms=round((time.perf_counter() - t0) * 1000))
            rows.append(row)
            print(f"[{i + 1}/{len(sentences)}] {label:<16} " + (
                f"WER={row['wer']:.2f} CER={row['cer']:.2f} intent_ok={row['intent_ok']}" if not client.mock
                else f"measured channel SNR={row['measured_channel_snr_db']} dB"))

    table = summarise(rows, conds, client.mock)
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


def summarise(rows: list[dict], conds, mock: bool) -> str:
    if mock:
        lines = ["| condition | mean measured channel SNR (dB) | WER |", "|---|---|---|"]
    else:
        lines = ["| condition | mean measured channel SNR (dB) | WER | CER | intent+slots correct |",
                 "|---|---|---|---|---|"]
    for label, _, _ in conds:
        rs = [r for r in rows if r["condition"] == label]
        snrs = [r["measured_channel_snr_db"] for r in rs if r["measured_channel_snr_db"] is not None]
        snr_s = f"{np.mean(snrs):.1f}" if snrs else "-"
        if mock:
            lines.append(f"| {label} | {snr_s} | n/a (MOCK) |")
        else:
            lines.append(f"| {label} | {snr_s} | {np.mean([r['wer'] for r in rs]):.3f} | "
                         f"{np.mean([r['cer'] for r in rs]):.3f} | "
                         f"{sum(r['intent_ok'] for r in rs)}/{len(rs)} |")
    return "\n".join(lines)


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

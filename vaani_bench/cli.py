"""vaani-bench command line.

  vaani-bench degrade in.wav out.wav --snr 5 --noise pink
  vaani-bench run --sentences my.json --lang te-IN --model v3 --snrs clean,phone,20,10,5,0
  vaani-bench run --audio-dir recordings/ --transcripts refs.json --model v3 --keyterms terms.txt

Without GNANI_API_KEY (environment variable or ./.env) ``run`` works in MOCK mode: the phone-line
simulation runs and is measured, but no STT is called and no WER/CER is reported.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from rythu_vaani import audio as A
from rythu_vaani import gnani

from . import __version__
from . import core

MODELS = {"v2.5": None, "v3": gnani.STT_MODEL_V3}  # None = omit `model`, which selects Prisma v2.5
DEFAULT_SNRS = "clean,phone,20,10,5,0"


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def cmd_degrade(a) -> int:
    x, sr = A.read_wav(Path(a.input).read_bytes())
    y, measured = core.degrade(x, sr, a.snr, a.noise, seed=a.seed)
    Path(a.output).write_bytes(A.write_wav(y, A.PHONE_SR))
    what = "phone line, no added noise" if a.snr is None else \
        f"phone line + {a.noise} noise at nominal {a.snr:g} dB"
    print(f"wrote {a.output}: {A.PHONE_SR} Hz mono, {len(y) / A.PHONE_SR:.2f} s, {what}"
          + ("" if measured is None else f", measured channel SNR {measured:.1f} dB"))
    return 0


def _get_client():
    # Load ./.env (the developer's project) without overriding an already-set variable.
    try:
        from dotenv import load_dotenv
        load_dotenv(Path.cwd() / ".env", override=False)
    except ImportError:
        pass
    from rythu_vaani.config import get_client
    return get_client()


def _helpline_intent_fn():
    """Rythu Vaani's farmer-helpline NLU: is the parsed intent + slots unchanged by the channel?"""
    from rythu_vaani.kb import default_kb
    from rythu_vaani.nlu import parse

    kb = default_kb()

    def same_intent(ref: str, hyp: str) -> bool:
        r, h = parse(ref, kb), parse(hyp, kb)
        return (r.name, r.slots) == (h.name, h.slots)
    return same_intent


def cmd_run(a) -> int:
    _utf8_stdout()
    conds = core.parse_conditions(a.snrs)
    keyterms = core.load_terms(a.keyterms) if a.keyterms else None
    if (keyterms or a.topic) and a.model != "v3":
        raise SystemExit("--keyterms/--topic are Prisma v3.0 context: add --model v3")
    if keyterms and len(keyterms) > gnani.STT_MAX_KEYTERMS:
        raise SystemExit(f"{a.keyterms}: {len(keyterms)} terms, Prisma accepts at most {gnani.STT_MAX_KEYTERMS}")
    stt_kwargs = {}
    if MODELS[a.model]:
        stt_kwargs["model"] = MODELS[a.model]
    if keyterms:
        stt_kwargs["keyterms"] = keyterms
    if a.topic:
        stt_kwargs["topic"] = a.topic

    client = _get_client()
    if client.mock:
        print("=" * 72 + "\n MOCK MODE: no GNANI_API_KEY. No STT/TTS is called. The phone-line simulation\n"
              " runs and its SNR is measured, but WER/CER are NOT measured (n/a).\n" + "=" * 72)

    if a.sentences:
        sentences = core.load_text_list(a.sentences)
        sentences = sentences[: a.limit] if a.limit else sentences
        items = core.items_from_sentences(sentences, client, lang=a.lang, voice=a.voice, cache_dir=a.cache_dir)
        source = f"{a.sentences} (text, synthesised with {gnani.TTS_MODEL} voice {a.voice})" if not client.mock \
            else f"{a.sentences} (MOCK: placeholder non-speech signals, no TTS)"
    else:
        items = core.items_from_audio_dir(a.audio_dir, a.transcripts)
        items = items[: a.limit] if a.limit else items
        source = f"{a.audio_dir} with references from {a.transcripts} (your recordings)"

    intent_fn = _helpline_intent_fn() if a.helpline_intent else None
    rows = core.evaluate(items, conds, client, noise=a.noise, lang=a.lang, fmt=a.format,
                         stt_kwargs=stt_kwargs, intent_fn=intent_fn)
    summary = core.summarise(rows, conds)
    table = core.markdown_table(summary, client.mock, intent=bool(intent_fn))
    print("\n" + table)

    stt = gnani.STT_MODEL if not MODELS[a.model] else MODELS[a.model]
    if keyterms or a.topic:
        stt += f" + context ({len(keyterms or [])} keyterms" + (", topic" if a.topic else "") + ")"
    meta = {
        "tool": f"vaani-bench {__version__}",
        "date": datetime.now().isoformat(timespec="seconds"),
        "mode": "MOCK" if client.mock else "real",
        "stt": "none (MOCK)" if client.mock else f"{stt} ({a.lang}, {a.format})",
        "input": source,
        "n_items": len(items),
        "noise": a.noise,
        "channel": "8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law",
        "conditions": "; ".join(c[0] for c in conds),
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"vaani-bench_{stamp}_{a.model}" + ("_MOCK" if client.mock else "")
    jpath, mpath = core.write_report(a.out, stem, meta, rows, summary, table,
                                     title=f"vaani-bench report {stamp}" + (" (MOCK)" if client.mock else ""))
    print(f"\nsaved {jpath} and {mpath}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vaani-bench", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"vaani-bench {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("degrade", help="simulate a noisy 8 kHz phone line on one WAV (no API needed)")
    d.add_argument("input", help="input WAV (any sample rate, mono or stereo)")
    d.add_argument("output", help="output WAV (8 kHz, 16-bit mono)")
    d.add_argument("--snr", type=float, default=None, help="noise SNR in dB (omit for no added noise)")
    d.add_argument("--noise", choices=A.NOISE_KINDS, default="pink")
    d.add_argument("--seed", type=int, default=0, help="noise random seed")
    d.set_defaults(func=cmd_degrade)

    r = sub.add_parser("run", help="benchmark Gnani Prisma STT across phone-line conditions",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--sentences", help='JSON list of sentences (or {"sentences": [...]}), spoken by Timbre TTS')
    src.add_argument("--audio-dir", help="directory of your own WAV recordings (use with --transcripts)")
    r.add_argument("--transcripts", help='JSON {"file.wav": "reference transcript", ...} for --audio-dir')
    r.add_argument("--lang", default=gnani.LANGUAGE, help="language code, e.g. te-IN, hi-IN (default te-IN)")
    r.add_argument("--model", choices=sorted(MODELS), default="v3", help="Prisma model (default v3)")
    r.add_argument("--keyterms", help="text file, one keyterm per line (Prisma v3.0 context)")
    r.add_argument("--topic", help="one-paragraph topic hint (Prisma v3.0 context)")
    r.add_argument("--snrs", default=DEFAULT_SNRS,
                   help=f"comma list of conditions: clean, phone, or SNR dB values (default {DEFAULT_SNRS})")
    r.add_argument("--noise", choices=A.NOISE_KINDS, default="pink")
    r.add_argument("--format", choices=sorted(gnani.STT_FORMATS), default="verbatim", help="Prisma output format")
    r.add_argument("--voice", default=gnani.TTS_VOICE,
                   help=f"Timbre voice for --sentences (default {gnani.TTS_VOICE}, a Telugu voice)")
    r.add_argument("--limit", type=int, default=0, help="only the first N items")
    r.add_argument("--out", default="vaani-bench-results", help="report directory")
    r.add_argument("--cache-dir", default=".vaani-bench-cache", help="TTS audio cache for --sentences")
    r.add_argument("--helpline-intent", action="store_true",
                   help="also score Rythu Vaani farmer-helpline intent+slots (Telugu farm questions only)")
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd == "run" and a.audio_dir and not a.transcripts:
        p.error("--audio-dir needs --transcripts")
    if a.cmd == "run" and a.sentences and a.transcripts:
        p.error("--transcripts only applies to --audio-dir")
    try:
        return a.func(a)
    except (ValueError, FileNotFoundError) as exc:
        p.error(str(exc))
    except gnani.GnaniError as exc:
        print(f"Gnani API error: {exc}", file=sys.stderr)
        return 1
    return 1

"""vaani-bench core: build inputs, push them through the phone-line simulator, transcribe, score.

All DSP (resampling, noise, 300-3400 Hz band-pass, G.711 mu-law) and WER/CER live in
``rythu_vaani.audio``; this module only orchestrates them. STT/TTS go through the Gnani
client from ``rythu_vaani.gnani`` (real or the labelled mock).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from rythu_vaani import audio as A
from rythu_vaani import gnani

CLEAN_SR = 16000
PRISMA_MAX_SECONDS = 30.0  # Prisma REST limit per file

# (label, through_phone_channel, nominal_snr_db)
Condition = tuple[str, bool, "float | None"]


@dataclass
class Item:
    """One utterance to benchmark: its reference transcript and clean audio."""
    id: str
    reference: str
    audio: np.ndarray
    sr: int


# ---------- conditions ----------

def parse_conditions(spec: str | list[str], clean_label: str = "clean") -> list[Condition]:
    """``"clean,phone,20,10,5,0"`` -> conditions. ``clean`` = original audio, ``phone`` = phone
    line without added noise, a number = phone line with noise at that SNR (dB)."""
    tokens = spec.split(",") if isinstance(spec, str) else list(spec)
    conds: list[Condition] = []
    for tok in (t.strip().lower() for t in tokens):
        if not tok:
            continue
        if tok == "clean":
            conds.append((clean_label, False, None))
        elif tok in ("phone", "phone-clean"):
            conds.append(("phone, no noise", True, None))
        else:
            try:
                snr = float(tok)
            except ValueError:
                raise ValueError(f"bad condition {tok!r}: use clean, phone or an SNR in dB") from None
            conds.append((f"phone, {snr:g} dB", True, snr))
    if not conds:
        raise ValueError("no conditions given")
    labels = [c[0] for c in conds]
    if len(set(labels)) != len(labels):
        raise ValueError(f"duplicate conditions in {spec!r}")
    return conds


# ---------- channel ----------

def channel_snr_db(clean_phone: np.ndarray, noisy_phone: np.ndarray) -> float:
    """SNR actually present after the channel (band-pass + mu-law), measured, not nominal."""
    noise = noisy_phone - clean_phone
    pn = A.power(noise)
    return float("inf") if pn == 0 else float(10 * np.log10(A.power(clean_phone) / pn))


def degrade(x: np.ndarray, sr: int, snr_db: float | None, noise: str = "pink",
            seed: int = 0) -> tuple[np.ndarray, float | None]:
    """Phone-line simulation. Returns (8 kHz audio, measured channel SNR or None if no noise)."""
    y = A.degrade_to_phone(x, sr, snr_db, noise, seed=seed)
    if snr_db is None:
        return y, None
    return y, channel_snr_db(A.degrade_to_phone(x, sr, None, noise), y)


# ---------- inputs ----------

def load_text_list(path: str | Path) -> list[str]:
    """Sentences from JSON: a list of strings, or ``{"sentences": [...]}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("sentences")
    if not isinstance(data, list) or not all(isinstance(s, str) and s.strip() for s in data):
        raise ValueError(f"{path}: expected a JSON list of non-empty strings or {{\"sentences\": [...]}}")
    return data


def load_terms(path: str | Path) -> list[str]:
    """Keyterms file: one term per line; blank lines and lines starting with # are ignored."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def items_from_audio_dir(audio_dir: str | Path, transcripts: str | Path) -> list[Item]:
    """Developer's own recordings: ``transcripts`` is JSON ``{"file.wav": "reference text", ...}``."""
    audio_dir = Path(audio_dir)
    refs = json.loads(Path(transcripts).read_text(encoding="utf-8"))
    if not isinstance(refs, dict) or not refs:
        raise ValueError(f"{transcripts}: expected a JSON object {{\"file.wav\": \"reference text\"}}")
    items = []
    for name, ref in refs.items():
        path = audio_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"{path} is listed in {transcripts} but does not exist")
        if path.suffix.lower() != ".wav":
            raise ValueError(f"{path}: only WAV input is supported (convert with ffmpeg first)")
        x, sr = A.read_wav(path.read_bytes())
        items.append(Item(id=name, reference=str(ref), audio=x, sr=sr))
    return items


def items_from_sentences(sentences: list[str], client, lang: str = gnani.LANGUAGE,
                         voice: str = gnani.TTS_VOICE, cache_dir: str | Path | None = None,
                         cache_name: Callable[[int, str], str] | None = None) -> list[Item]:
    """Text sentences -> clean 16 kHz speech via Timbre TTS (cached on disk).

    In MOCK mode no TTS is called: each item gets a speech-shaped placeholder signal (not speech),
    which is enough to exercise and measure the channel but not to score STT.
    """
    items = []
    cache = Path(cache_dir) if cache_dir else None
    for i, text in enumerate(sentences):
        if client.mock:
            x, sr = A.placeholder_signal(2.5, CLEAN_SR, seed=i), CLEAN_SR
        else:
            wav = None
            path = None
            if cache is not None:
                cache.mkdir(parents=True, exist_ok=True)
                name = cache_name(i, text) if cache_name else \
                    f"{lang}_{voice}_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}.wav"
                path = cache / name
                if path.exists():
                    wav = path.read_bytes()
            if wav is None:
                wav = client.synthesize(text, language=lang, sample_rate=CLEAN_SR, voice=voice)
                if path is not None:
                    path.write_bytes(wav)
            x, sr = A.read_wav(wav)
            x, sr = A.resample(x, sr, CLEAN_SR), CLEAN_SR
        items.append(Item(id=f"s{i:02d}", reference=text, audio=x, sr=sr))
    return items


# ---------- run ----------

def evaluate(items: list[Item], conds: list[Condition], client, *, noise: str = "pink",
             lang: str = gnani.LANGUAGE, fmt: str = "verbatim", stt_kwargs: dict | None = None,
             intent_fn: Callable[[str, str], bool] | None = None,
             log: Callable[[str], None] | None = print) -> list[dict]:
    """Every item x every condition -> one row. In MOCK mode STT is not called and rows carry
    only the measured channel SNR (a mock transcript would make WER meaningless)."""
    stt_kwargs = stt_kwargs or {}
    log = log or (lambda _msg: None)
    rows = []
    for i, item in enumerate(items):
        dur = len(item.audio) / item.sr
        if dur > PRISMA_MAX_SECONDS:
            log(f"warning: {item.id} is {dur:.1f} s; Prisma REST accepts at most {PRISMA_MAX_SECONDS:g} s")
        phone_ref = None
        for label, phone, snr in conds:
            if not phone:
                wav, measured = A.write_wav(item.audio, item.sr), None
            else:
                y = A.degrade_to_phone(item.audio, item.sr, snr, noise, seed=i)
                if snr is not None:
                    if phone_ref is None:
                        phone_ref = A.degrade_to_phone(item.audio, item.sr, None, noise)
                    measured = channel_snr_db(phone_ref, y)
                else:
                    measured = None
                wav = A.write_wav(y, A.PHONE_SR)
            row = {"sentence": i, "id": item.id, "condition": label, "snr_db": snr,
                   "measured_channel_snr_db": None if measured is None else round(measured, 1)}
            if not client.mock:
                row["reference"] = item.reference
                t0 = time.perf_counter()
                try:
                    stt = client.transcribe(wav, f"{Path(item.id).stem}.wav", language_code=lang,
                                            fmt=fmt, **stt_kwargs)
                except gnani.GnaniError as exc:
                    row.update(hypothesis=None, wer=None, cer=None, error=str(exc))
                    if intent_fn:
                        row["intent_ok"] = None
                else:
                    hyp = stt.transcript
                    row.update(hypothesis=hyp, wer=round(A.wer(item.reference, hyp), 4),
                               cer=round(A.cer(item.reference, hyp), 4))
                    if intent_fn:
                        row["intent_ok"] = bool(intent_fn(item.reference, hyp))
                row["latency_ms"] = round((time.perf_counter() - t0) * 1000)
            rows.append(row)
            prefix = f"[{i + 1}/{len(items)}] {label:<16} "
            if client.mock:
                log(prefix + f"measured channel SNR={row['measured_channel_snr_db']} dB")
            elif row.get("error"):
                log(prefix + f"ERROR {row['error']}")
            else:
                log(prefix + f"WER={row['wer']:.2f} CER={row['cer']:.2f}"
                    + (f" intent_ok={row['intent_ok']}" if intent_fn else ""))
    return rows


def summarise(rows: list[dict], conds: list[Condition]) -> list[dict]:
    """Per-condition means. WER/CER are None when nothing was scored (MOCK, or all errors)."""
    out = []
    for label, _, snr in conds:
        rs = [r for r in rows if r["condition"] == label]
        snrs = [r["measured_channel_snr_db"] for r in rs if r["measured_channel_snr_db"] is not None]
        scored = [r for r in rs if r.get("wer") is not None]
        s = {"condition": label, "snr_db": snr, "n": len(rs),
             "mean_measured_channel_snr_db": round(float(np.mean(snrs)), 1) if snrs else None,
             "wer": round(float(np.mean([r["wer"] for r in scored])), 3) if scored else None,
             "cer": round(float(np.mean([r["cer"] for r in scored])), 3) if scored else None,
             "errors": sum(1 for r in rs if r.get("error"))}
        if any("intent_ok" in r for r in rs):
            s["intent_ok"] = sum(1 for r in rs if r.get("intent_ok"))
        out.append(s)
    return out


def markdown_table(summary: list[dict], mock: bool, intent: bool = False) -> str:
    if mock:
        lines = ["| condition | mean measured channel SNR (dB) | WER | CER |", "|---|---|---|---|"]
    else:
        lines = ["| condition | mean measured channel SNR (dB) | WER | CER |"
                 + (" intent+slots correct |" if intent else ""),
                 "|---|---|---|---|" + ("---|" if intent else "")]
    for s in summary:
        snr = "-" if s["mean_measured_channel_snr_db"] is None else f"{s['mean_measured_channel_snr_db']:.1f}"
        if mock:
            lines.append(f"| {s['condition']} | {snr} | n/a (MOCK) | n/a (MOCK) |")
            continue
        fmt = lambda v: "-" if v is None else f"{v:.3f}"  # noqa: E731
        line = f"| {s['condition']} | {snr} | {fmt(s['wer'])} | {fmt(s['cer'])} |"
        if intent:
            line += f" {s.get('intent_ok', 0)}/{s['n']} |"
        lines.append(line)
    return "\n".join(lines)


def write_report(out_dir: str | Path, stem: str, meta: dict, rows: list[dict],
                 summary: list[dict], table: str, title: str | None = None) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jpath, mpath = out / f"{stem}.json", out / f"{stem}.md"
    jpath.write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, ensure_ascii=False,
                                indent=2), encoding="utf-8")
    md = f"# {title or stem}\n\n"
    if meta.get("mode") == "MOCK":
        md += ("> **MOCK MODE**: no GNANI_API_KEY, so no speech-to-text was called. Only the channel\n"
               "> simulation ran; WER/CER are not measured. Do not quote these as results.\n\n")
    md += "\n".join(f"- {k}: {v}" for k, v in meta.items()) + "\n\n" + table + "\n"
    errors = sum(s.get("errors", 0) for s in summary)
    if errors:
        md += f"\n{errors} STT call(s) failed; see `error` in the JSON rows. They are excluded from the means.\n"
    mpath.write_text(md, encoding="utf-8")
    return jpath, mpath

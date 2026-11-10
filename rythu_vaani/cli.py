"""CLI demo.

  python -m rythu_vaani.cli --text "గుంటూరులో మిర్చి ధర ఎంత?"
  python -m rythu_vaani.cli --audio question.wav --phone --snr 10 --out reply.wav
  python -m rythu_vaani.cli --say "పత్తికి పురుగు పట్టింది" --phone --snr 5   # real key: TTS -> phone line -> STT
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import get_client
from .gnani import GnaniError
from .pipeline import PipelineError, handle_audio, handle_text


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Telugu output on Windows consoles
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Rythu Vaani helpline demo")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="typed question (skips STT)")
    src.add_argument("--audio", type=Path, help="caller audio file (<= 30 s)")
    src.add_argument("--say", help="synthesise this question with Timbre, then run it through STT like a caller")
    p.add_argument("--phone", action="store_true", help="run the audio through a noisy 8 kHz phone-line model")
    p.add_argument("--snr", type=float, default=None, help="noise SNR in dB for --phone")
    p.add_argument("--mock-transcript", help="MOCK mode only: transcript to pretend STT returned")
    p.add_argument("--out", type=Path, default=Path("reply.wav"), help="where to save the spoken reply")
    a = p.parse_args(argv)

    client = get_client()
    if client.mock:
        print("=" * 64 + "\n MOCK MODE: GNANI_API_KEY not set. No Gnani API is called.\n"
              " Transcripts are hints you supply; reply audio is beeps.\n" + "=" * 64)
    try:
        if a.text:
            res = handle_text(a.text, client)
        else:
            if a.say:
                audio, name = client.synthesize(a.say, sample_rate=16000), "say.wav"
                hint = a.mock_transcript or a.say
            else:
                audio, name, hint = a.audio.read_bytes(), a.audio.name, a.mock_transcript
            res = handle_audio(audio, client, name, phone_line=a.phone, snr_db=a.snr, mock_hint=hint)
    except (PipelineError, GnaniError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    a.out.write_bytes(res.reply_wav)
    tag = "[MOCK] " if res.mode == "MOCK" else ""
    print(f"mode       : {res.mode}")
    print(f"heard      : {tag}{res.transcript}")
    print(f"intent     : {res.intent} {res.slots}")
    print(f"reply (te) : {res.reply_te}")
    print(f"reply (en) : {res.reply_en}")
    print(f"timings ms : {res.timings_ms}")
    print(f"audio      : {a.out} {'(beeps, mock)' if res.mode == 'MOCK' else '(Timbre te-IN)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

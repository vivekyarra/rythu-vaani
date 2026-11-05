import json

import numpy as np
import pytest

from rythu_vaani import audio as A
from rythu_vaani import gnani
from vaani_bench import cli, core


def in_band_signal(sr=16000, secs=2.0):
    """Tones inside the 300-3400 Hz phone band, so the band-pass does not eat signal power."""
    t = np.arange(int(sr * secs)) / sr
    return (0.05 * sum(np.sin(2 * np.pi * f * t) for f in (500, 900, 1400, 2100, 2900))).astype(np.float32)


def write_wav(path, x, sr):
    path.write_bytes(A.write_wav(x, sr))
    return path


# ---------- degrade ----------

@pytest.mark.parametrize("snr", [20, 10, 5, 0])
def test_degrade_hits_requested_snr_white(snr):
    y, measured = core.degrade(in_band_signal(), 16000, snr, "white")
    assert len(y) == 16000  # 2 s at 8 kHz
    # Noise is added at the nominal SNR before the band-pass, which then removes the
    # out-of-band part of white noise (~1 dB), so the measured line SNR sits just above nominal.
    assert measured == pytest.approx(snr, abs=1.5)


@pytest.mark.parametrize("snr", [20, 10, 5, 0])
def test_degrade_hits_requested_snr_pink_speechlike(snr):
    _, measured = core.degrade(A.placeholder_signal(2.5, 16000), 16000, snr, "pink")
    assert measured == pytest.approx(snr, abs=1.5)


def test_degrade_without_noise_reports_no_snr():
    y, measured = core.degrade(in_band_signal(), 16000, None)
    assert measured is None and len(y) == 16000


def test_degrade_cli_writes_8k_wav(tmp_path, capsys):
    src = write_wav(tmp_path / "in.wav", in_band_signal(sr=22050, secs=1.0), 22050)
    out = tmp_path / "out.wav"
    assert cli.main(["degrade", str(src), str(out), "--snr", "5", "--noise", "white"]) == 0
    y, sr = A.read_wav(out.read_bytes())
    assert sr == A.PHONE_SR and len(y) == 8000
    printed = capsys.readouterr().out
    measured = float(printed.split("measured channel SNR ")[1].split(" dB")[0])
    assert measured == pytest.approx(5, abs=1.5)


def test_degrade_cli_no_noise(tmp_path, capsys):
    src = write_wav(tmp_path / "in.wav", in_band_signal(), 16000)
    out = tmp_path / "out.wav"
    assert cli.main(["degrade", str(src), str(out)]) == 0
    assert A.read_wav(out.read_bytes())[1] == 8000
    assert "no added noise" in capsys.readouterr().out


# ---------- conditions ----------

def test_parse_conditions():
    conds = core.parse_conditions("clean,phone,20,5,0")
    assert conds == [("clean", False, None), ("phone, no noise", True, None), ("phone, 20 dB", True, 20.0),
                     ("phone, 5 dB", True, 5.0), ("phone, 0 dB", True, 0.0)]
    with pytest.raises(ValueError):
        core.parse_conditions("clean,loud")
    with pytest.raises(ValueError):
        core.parse_conditions("10,10")


# ---------- WER / CER ----------

def test_wer_cer_edits():
    assert A.wer("a b c d", "a b c d") == 0
    assert A.wer("a b c d", "a b c") == pytest.approx(0.25)          # deletion
    assert A.wer("a b c d", "a b x c d") == pytest.approx(0.25)      # insertion
    assert A.wer("a b c d", "a x c y") == pytest.approx(0.5)         # substitutions
    assert A.wer("a b", "c d e f") == pytest.approx(2.0)             # WER can exceed 1
    assert A.cer("abcd", "abcd") == 0 and A.cer("abcd", "abc") == pytest.approx(0.25)
    assert A.cer("ab cd", "abcd") == 0                               # CER ignores spaces


def test_wer_cer_telugu_normalisation():
    ref = "తెనాలిలో వరి రేటు ఎంత ఉంది"
    assert A.wer(ref, "తెనాలిలో వరి రేటు ఎంత ఉంది?") == 0         # punctuation ignored
    assert A.wer(ref, "తెనాలిలో వరి ధర ఎంత ఉంది") == pytest.approx(0.2)
    assert A.cer("వరి", "వర") > 0                                     # vowel sign counts


def test_summarise_means_and_errors():
    conds = core.parse_conditions("clean,10")
    rows = [
        {"condition": "clean", "measured_channel_snr_db": None, "wer": 0.0, "cer": 0.0},
        {"condition": "clean", "measured_channel_snr_db": None, "wer": 0.5, "cer": 0.2},
        {"condition": "phone, 10 dB", "measured_channel_snr_db": 11.0, "wer": 1.0, "cer": 0.4},
        {"condition": "phone, 10 dB", "measured_channel_snr_db": 12.0, "wer": None, "cer": None, "error": "x"},
    ]
    s = core.summarise(rows, conds)
    assert s[0]["wer"] == 0.25 and s[0]["cer"] == 0.1 and s[0]["mean_measured_channel_snr_db"] is None
    assert s[1]["wer"] == 1.0 and s[1]["mean_measured_channel_snr_db"] == 11.5 and s[1]["errors"] == 1


# ---------- run (CLI) ----------

def _reports(out_dir):
    js = list(out_dir.glob("vaani-bench_*.json"))
    mds = list(out_dir.glob("vaani-bench_*.md"))
    assert len(js) == 1 and len(mds) == 1
    return json.loads(js[0].read_text(encoding="utf-8")), mds[0].read_text(encoding="utf-8")


def test_run_mock_sentences_writes_labelled_reports(tmp_path, capsys):
    sents = tmp_path / "s.json"
    sents.write_text(json.dumps(["మిర్చి ధర ఎంత", "పత్తికి ఎరువు ఎప్పుడు వేయాలి"], ensure_ascii=False),
                     encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(["run", "--sentences", str(sents), "--snrs", "clean,phone,10,0", "--out", str(out),
                     "--cache-dir", str(tmp_path / "cache")]) == 0
    printed = capsys.readouterr().out
    assert "MOCK MODE" in printed and "n/a (MOCK)" in printed and "WER=" not in printed
    report, md = _reports(out)
    assert report["meta"]["mode"] == "MOCK" and "MOCK" in md
    assert len(report["rows"]) == 2 * 4
    assert all(s["wer"] is None and s["cer"] is None for s in report["summary"])
    by_cond = {s["condition"]: s for s in report["summary"]}
    assert by_cond["phone, 10 dB"]["mean_measured_channel_snr_db"] == pytest.approx(10, abs=1.5)
    assert by_cond["clean"]["mean_measured_channel_snr_db"] is None
    assert not (tmp_path / "cache").exists()  # MOCK never synthesises or caches audio


def test_run_mock_audio_dir(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    write_wav(rec / "q1.wav", in_band_signal(), 16000)
    write_wav(rec / "q2.wav", A.placeholder_signal(1.5, 48000), 48000)
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"q1.wav": "one two", "q2.wav": "three"}), encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(["run", "--audio-dir", str(rec), "--transcripts", str(refs), "--lang", "hi-IN",
                     "--snrs", "phone,5", "--out", str(out)]) == 0
    report, md = _reports(out)
    assert report["meta"]["mode"] == "MOCK" and report["meta"]["n_items"] == 2
    assert {r["id"] for r in report["rows"]} == {"q1.wav", "q2.wav"}


def test_run_audio_dir_missing_file(tmp_path):
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"nope.wav": "x"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["run", "--audio-dir", str(tmp_path), "--transcripts", str(refs)])


def test_run_keyterms_need_v3(tmp_path):
    terms = tmp_path / "t.txt"
    terms.write_text("మిర్చి\n# comment\n\nపత్తి\n", encoding="utf-8")
    assert core.load_terms(terms) == ["మిర్చి", "పత్తి"]
    sents = tmp_path / "s.json"
    sents.write_text('["x"]', encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["run", "--sentences", str(sents), "--model", "v2.5", "--keyterms", str(terms)])


class FakeRealClient:
    """Network-free stand-in for the real client: drops the last word of the reference."""
    mock = False

    def __init__(self, refs):
        self.refs, self.calls = refs, []

    def transcribe(self, audio, filename, language_code, fmt, **kw):
        self.calls.append({"filename": filename, "lang": language_code, "fmt": fmt, **kw})
        ref = self.refs[filename]
        return gnani.STTResult(transcript=" ".join(ref.split()[:-1]), model="fake", request_id="t")


def test_run_scores_wer_cer_with_real_client_path(tmp_path, monkeypatch):
    rec = tmp_path / "rec"
    rec.mkdir()
    write_wav(rec / "a.wav", in_band_signal(), 16000)
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"a.wav": "ab cd ef gh"}), encoding="utf-8")
    terms = tmp_path / "t.txt"
    terms.write_text("ab\ncd\n", encoding="utf-8")
    fake = FakeRealClient({"a.wav": "ab cd ef gh"})
    monkeypatch.setattr(cli, "_get_client", lambda: fake)
    out = tmp_path / "out"
    assert cli.main(["run", "--audio-dir", str(rec), "--transcripts", str(refs), "--model", "v3",
                     "--keyterms", str(terms), "--topic", "test topic", "--snrs", "clean,5",
                     "--out", str(out)]) == 0
    report, md = _reports(out)
    assert report["meta"]["mode"] == "real" and "MOCK" not in md
    assert all(s["wer"] == 0.25 and s["cer"] == 0.25 for s in report["summary"])
    assert len(fake.calls) == 2
    assert fake.calls[0]["model"] == gnani.STT_MODEL_V3 and fake.calls[0]["keyterms"] == ["ab", "cd"]
    assert fake.calls[0]["topic"] == "test topic" and fake.calls[0]["fmt"] == "verbatim"
    assert "intent" not in md  # generic tool: no helpline intent unless asked


def test_helpline_intent_option(tmp_path, monkeypatch):
    rec = tmp_path / "rec"
    rec.mkdir()
    write_wav(rec / "a.wav", in_band_signal(), 16000)
    ref = "గుంటూరులో మిర్చి ధర ఎంత"
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"a.wav": ref}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cli, "_get_client", lambda: FakeRealClient({"a.wav": ref + " ఉంది"}))
    out = tmp_path / "out"
    assert cli.main(["run", "--audio-dir", str(rec), "--transcripts", str(refs), "--snrs", "phone",
                     "--helpline-intent", "--out", str(out)]) == 0
    report, md = _reports(out)
    assert report["rows"][0]["intent_ok"] is True and "intent+slots correct" in md

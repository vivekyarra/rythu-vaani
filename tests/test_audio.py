import numpy as np
import pytest
from scipy.signal import welch

from rythu_vaani import audio as A


def tone(sr=16000, secs=1.0, f=440):
    t = np.arange(int(sr * secs)) / sr
    return (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)


def test_wav_roundtrip():
    x = tone()
    y, sr = A.read_wav(A.write_wav(x, 16000))
    assert sr == 16000 and np.max(np.abs(x - y)) < 1e-4


@pytest.mark.parametrize("kind", A.NOISE_KINDS)
@pytest.mark.parametrize("snr", [20, 10, 5, 0])
def test_add_noise_hits_target_snr(kind, snr):
    x = A.placeholder_signal(2.0, 8000)
    y = A.add_noise(x, snr, kind, 8000, np.random.default_rng(1))
    measured = 10 * np.log10(A.power(x) / A.power(y - x))
    assert measured == pytest.approx(snr, abs=0.01)


def test_degrade_is_8k_and_band_limited():
    rng = np.random.default_rng(0)
    x = rng.standard_normal(16000).astype(np.float32) * 0.1  # broadband 16 kHz input
    y = A.degrade_to_phone(x, 16000, None)
    assert len(y) == 8000  # 1 s at 8 kHz
    f, p = welch(y, fs=8000, nperseg=512)
    in_band = p[(f > 500) & (f < 3000)].mean()
    assert p[f < 100].mean() < in_band / 100
    assert p[f > 3800].mean() < in_band / 10


def test_degrade_noise_increases_as_snr_drops():
    x = A.placeholder_signal(2.0, 16000)
    ref = A.degrade_to_phone(x, 16000, None)
    errs = [A.power(A.degrade_to_phone(x, 16000, s) - ref) for s in (20, 10, 0)]
    assert errs[0] < errs[1] < errs[2]


def test_degrade_is_deterministic_per_seed():
    x = A.placeholder_signal(1.0, 16000)
    assert np.array_equal(A.degrade_to_phone(x, 16000, 5, seed=3), A.degrade_to_phone(x, 16000, 5, seed=3))


def test_mulaw_roundtrip_small_error():
    x = tone(8000)
    assert np.max(np.abs(A.mulaw_roundtrip(x) - x)) < 0.02


def test_wer_and_cer():
    assert A.wer("మిర్చి ధర ఎంత", "మిర్చి ధర ఎంత?") == 0
    assert A.wer("మిర్చి ధర ఎంత", "మిర్చి రేటు ఎంత") == pytest.approx(1 / 3)
    assert A.wer("a b c d", "a c d e") == pytest.approx(0.5)
    assert A.cer("ధర", "ధర") == 0 and A.cer("abcd", "abed") == pytest.approx(0.25)
    assert A.wer("", "") == 0 and A.wer("", "x") == 1

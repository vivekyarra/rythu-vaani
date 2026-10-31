"""Audio utilities: WAV I/O, telephone-channel simulation and WER/CER scoring.

Telephone simulation (``degrade_to_phone``):
  1. resample to 8 kHz (narrowband telephony rate),
  2. add noise at a target SNR (measured against the 8 kHz speech signal),
  3. band-pass 300-3400 Hz (classic PSTN voice band),
  4. G.711 mu-law encode/decode (8-bit companding used on Indian landline/2G paths).
"""
from __future__ import annotations

import io
from math import gcd

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, resample_poly, sosfiltfilt

from .nlu import normalize_text

PHONE_SR = 8000
NOISE_KINDS = ("white", "pink", "hum")


# ---------- WAV I/O ----------

def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    """Decode WAV bytes to mono float32 in [-1, 1]."""
    sr, x = wavfile.read(io.BytesIO(data))
    if x.dtype == np.int16:
        x = x / 32768.0
    elif x.dtype == np.int32:
        x = x / 2147483648.0
    elif x.dtype == np.uint8:
        x = (x.astype(np.float64) - 128) / 128.0
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    return x, int(sr)


def write_wav(x: np.ndarray, sr: int) -> bytes:
    """Encode mono float audio as 16-bit PCM WAV bytes."""
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    wavfile.write(buf, sr, pcm)
    return buf.getvalue()


def duration_s(data: bytes) -> float:
    x, sr = read_wav(data)
    return len(x) / sr


# ---------- channel simulation ----------

def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x.astype(np.float32)
    g = gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


def make_noise(n: int, kind: str, sr: int, rng: np.random.Generator) -> np.ndarray:
    if kind == "white":
        return rng.standard_normal(n)
    if kind == "pink":  # Paul Kellet's economy 1/f filter on white noise
        return lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                       [1, -2.494956002, 2.017265875, -0.522189400], rng.standard_normal(n))
    if kind == "hum":  # 50 Hz mains hum + harmonics (Indian grid) + light hiss
        t = np.arange(n) / sr
        hum = sum(np.sin(2 * np.pi * 50 * k * t + rng.uniform(0, 6.28)) / k for k in (1, 2, 3, 5, 7))
        return hum + 0.1 * rng.standard_normal(n)
    raise ValueError(f"noise kind must be one of {NOISE_KINDS}")


def power(x: np.ndarray) -> float:
    return float(np.mean(np.asarray(x, dtype=np.float64) ** 2))


def add_noise(x: np.ndarray, snr_db: float, kind: str = "pink", sr: int = PHONE_SR,
              rng: np.random.Generator | None = None) -> np.ndarray:
    """Return ``x + noise`` with the noise scaled so that 10*log10(Ps/Pn) == snr_db."""
    rng = rng or np.random.default_rng(0)
    noise = make_noise(len(x), kind, sr, rng)
    ps, pn = power(x), power(noise)
    if ps == 0 or pn == 0:
        return x.astype(np.float32)
    noise *= np.sqrt(ps / (pn * 10 ** (snr_db / 10)))
    return (x + noise).astype(np.float32)


def telephone_band(x: np.ndarray, sr: int = PHONE_SR) -> np.ndarray:
    sos = butter(4, [300, 3400], btype="bandpass", fs=sr, output="sos")
    return sosfiltfilt(sos, x).astype(np.float32)


def mulaw_roundtrip(x: np.ndarray, mu: int = 255) -> np.ndarray:
    """G.711-style mu-law compand, quantise to 8 bits, expand."""
    x = np.clip(x, -1.0, 1.0)
    y = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    q = np.round((y + 1) / 2 * mu) / mu * 2 - 1
    return (np.sign(q) * np.expm1(np.abs(q) * np.log1p(mu)) / mu).astype(np.float32)


def degrade_to_phone(x: np.ndarray, sr: int, snr_db: float | None, noise: str = "pink",
                     seed: int = 0) -> np.ndarray:
    """Simulate a noisy narrowband phone call. Returns 8 kHz audio. ``snr_db=None`` adds no noise."""
    y = resample(x, sr, PHONE_SR)
    if snr_db is not None:
        y = add_noise(y, snr_db, noise, PHONE_SR, np.random.default_rng(seed))
    y = telephone_band(y)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0.99:  # avoid hard clipping before companding
        y = y * (0.99 / peak)
    return mulaw_roundtrip(y)


def placeholder_signal(seconds: float = 2.0, sr: int = 16000, seed: int = 0) -> np.ndarray:
    """Speech-shaped placeholder (syllable-rate AM tones) for MOCK runs. Not speech."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f0 = 140 + 30 * np.sin(2 * np.pi * 0.7 * t)
    voiced = sum(np.sin(2 * np.pi * k * np.cumsum(f0) / sr) / k for k in range(1, 8))
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 4 * t + rng.uniform(0, 6.28)))
    return (0.2 * voiced * envelope).astype(np.float32)


# ---------- scoring ----------

def _edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, ai in enumerate(a, 1):
        cur = [i]
        for j, bj in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ai != bj)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize_text(reference).split(), normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate (spaces removed). Useful for agglutinative Telugu."""
    ref = list(normalize_text(reference).replace(" ", ""))
    hyp = list(normalize_text(hypothesis).replace(" ", ""))
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)

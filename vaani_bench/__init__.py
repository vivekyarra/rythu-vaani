"""vaani-bench: test a voice agent's speech-to-text on noisy Indian phone lines.

Simulates a narrowband call (8 kHz, noise at a chosen SNR, 300-3400 Hz band-pass, G.711 mu-law),
runs Gnani Prisma STT on each condition and reports WER/CER per condition with the SNR measured
after the channel. Reuses the DSP and API client from ``rythu_vaani``.
"""
__version__ = "0.1.0"

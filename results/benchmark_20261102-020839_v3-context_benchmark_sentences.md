# Noise benchmark 20261102-020839_v3-context_benchmark_sentences

- date: 20261102-020839_v3-context_benchmark_sentences
- mode: real
- stt: prisma-v3.0 + keyterms/topic (te-IN, verbatim)
- sentences: benchmark_sentences.json
- tts: timbre-v2.5 voice Varuni
- noise: pink
- n_sentences: 10
- channel: 8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law

| condition | mean measured channel SNR (dB) | WER | CER | intent+slots correct |
|---|---|---|---|---|
| clean 16k | - | 0.098 | 0.000 | 10/10 |
| phone, no noise | - | 0.144 | 0.006 | 10/10 |
| phone, 20 dB | 21.1 | 0.084 | 0.008 | 10/10 |
| phone, 10 dB | 11.2 | 0.050 | 0.000 | 10/10 |
| phone, 5 dB | 6.3 | 0.000 | 0.000 | 10/10 |
| phone, 0 dB | 1.3 | 0.039 | 0.015 | 10/10 |

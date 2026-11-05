# Noise benchmark 20261102-020810_v3_benchmark_sentences

- date: 20261102-020810_v3_benchmark_sentences
- mode: real
- stt: prisma-v3.0 (te-IN, verbatim)
- sentences: benchmark_sentences.json
- tts: timbre-v2.5 voice Varuni
- noise: pink
- n_sentences: 10
- channel: 8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law

| condition | mean measured channel SNR (dB) | WER | CER | intent+slots correct |
|---|---|---|---|---|
| clean 16k | - | 0.126 | 0.034 | 9/10 |
| phone, no noise | - | 0.126 | 0.034 | 9/10 |
| phone, 20 dB | 21.1 | 0.166 | 0.058 | 8/10 |
| phone, 10 dB | 11.2 | 0.206 | 0.051 | 8/10 |
| phone, 5 dB | 6.3 | 0.190 | 0.065 | 9/10 |
| phone, 0 dB | 1.3 | 0.361 | 0.169 | 6/10 |

# Noise benchmark 20261102-020912_v3-context_offdomain_sentences

- date: 20261102-020912_v3-context_offdomain_sentences
- mode: real
- stt: prisma-v3.0 + keyterms/topic (te-IN, verbatim)
- sentences: offdomain_sentences.json
- tts: timbre-v2.5 voice Varuni
- noise: pink
- n_sentences: 5
- channel: 8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law

| condition | mean measured channel SNR (dB) | WER | CER | intent+slots correct |
|---|---|---|---|---|
| clean 16k | - | 0.000 | 0.000 | 5/5 |
| phone, no noise | - | 0.000 | 0.000 | 5/5 |
| phone, 10 dB | 10.2 | 0.000 | 0.000 | 5/5 |
| phone, 5 dB | 5.2 | 0.000 | 0.000 | 5/5 |
| phone, 0 dB | 0.2 | 0.050 | 0.033 | 4/5 |

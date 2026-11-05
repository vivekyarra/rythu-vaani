# Noise benchmark 20261102-020712_v3_heldout_sentences

- date: 20261102-020712_v3_heldout_sentences
- mode: real
- stt: prisma-v3.0 (te-IN, verbatim)
- sentences: heldout_sentences.json
- tts: timbre-v2.5 voice Varuni
- noise: pink
- n_sentences: 10
- channel: 8 kHz, noise added at nominal SNR, 300-3400 Hz band-pass, G.711 mu-law

| condition | mean measured channel SNR (dB) | WER | CER | intent+slots correct |
|---|---|---|---|---|
| clean 16k | - | 0.201 | 0.061 | 10/10 |
| phone, no noise | - | 0.065 | 0.025 | 9/10 |
| phone, 20 dB | 21.0 | 0.240 | 0.061 | 8/10 |
| phone, 10 dB | 11.1 | 0.190 | 0.061 | 9/10 |
| phone, 5 dB | 6.1 | 0.190 | 0.066 | 9/10 |
| phone, 0 dB | 1.1 | 0.255 | 0.158 | 7/10 |

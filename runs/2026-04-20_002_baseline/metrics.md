# Metrics — Haunted.musicxml

**Overall composite:** 0.421
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | note_F1 | mel_L1 | mel_L1_raw | composite |
|---|---:|---:|---:|---:|---:|---:|
| vocals | 0.751 | 0.021 | 0.016 | 1.205 | 1.997 | **0.369** |
| piano | 0.781 | 0.032 | 0.022 | 0.367 | 0.463 | **0.414** |
| guitar | 0.756 | 0.317 | 0.035 | 0.374 | 0.592 | **0.492** |
| bass | 0.700 | 0.140 | 0.007 | 0.426 | 0.377 | **0.409** |
| _mix | 0.788 | 0.351 | nan | 0.931 | 0.906 | **0.489** |
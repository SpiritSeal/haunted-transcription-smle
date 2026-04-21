# Metrics — Haunted.musicxml

**Overall composite:** 0.473
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.916 | 0.192 | 0.252 | 0.021 | 0.503 | 0.410 | **0.512** |
| piano | 0.801 | 0.142 | 0.119 | 0.019 | 0.277 | 0.332 | **0.457** |
| guitar | 0.759 | 0.323 | 0.333 | 0.040 | 0.397 | 1.030 | **0.495** |
| bass | 0.714 | 0.170 | 0.157 | 0.020 | 0.428 | 0.385 | **0.426** |
| _mix | 0.784 | 0.376 | 0.348 | nan | 0.937 | 0.895 | **0.495** |
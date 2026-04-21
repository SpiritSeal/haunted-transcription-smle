# Metrics — Haunted.musicxml

**Overall composite:** 0.472
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.916 | 0.192 | 0.252 | 0.021 | 0.503 | 0.410 | **0.512** |
| piano | 0.800 | 0.135 | 0.101 | 0.016 | 0.269 | 0.313 | **0.455** |
| guitar | 0.759 | 0.326 | 0.347 | 0.039 | 0.397 | 1.030 | **0.496** |
| bass | 0.714 | 0.170 | 0.157 | 0.020 | 0.428 | 0.385 | **0.426** |
| _mix | 0.784 | 0.378 | 0.352 | nan | 0.937 | 0.895 | **0.496** |
# Metrics — Haunted.musicxml

**Overall composite:** 0.436
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.753 | 0.180 | 0.014 | 0.016 | 1.301 | 2.379 | **0.415** |
| piano | 0.805 | 0.048 | 0.037 | 0.022 | 0.379 | 0.485 | **0.428** |
| guitar | 0.753 | 0.303 | 0.299 | 0.033 | 0.381 | 0.936 | **0.486** |
| bass | 0.701 | 0.154 | 0.124 | 0.007 | 0.429 | 0.370 | **0.414** |
| _mix | 0.788 | 0.359 | 0.352 | nan | 0.932 | 0.906 | **0.492** |
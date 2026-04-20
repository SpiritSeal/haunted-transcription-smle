# Metrics — Haunted.musicxml

**Overall composite:** 0.436
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.773 | 0.180 | 0.007 | 0.016 | 1.256 | 2.057 | **0.425** |
| piano | 0.793 | 0.043 | 0.024 | 0.018 | 0.360 | 0.430 | **0.422** |
| guitar | 0.759 | 0.288 | 0.311 | 0.037 | 0.374 | 0.574 | **0.485** |
| bass | 0.700 | 0.157 | 0.140 | 0.007 | 0.426 | 0.377 | **0.414** |
| _mix | 0.786 | 0.352 | 0.338 | nan | 0.921 | 0.884 | **0.489** |
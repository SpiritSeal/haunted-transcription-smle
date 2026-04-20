# Metrics — Haunted.musicxml

**Overall composite:** 0.426
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | note_F1 | mel_L1 | mel_L1_raw | composite |
|---|---:|---:|---:|---:|---:|---:|
| vocals | 0.773 | 0.007 | 0.016 | 1.256 | 2.057 | **0.373** |
| piano | 0.793 | 0.024 | 0.018 | 0.360 | 0.430 | **0.416** |
| guitar | 0.759 | 0.311 | 0.037 | 0.374 | 0.574 | **0.492** |
| bass | 0.738 | 0.120 | 0.003 | 0.296 | 0.298 | **0.422** |
| _mix | 0.784 | 0.331 | nan | 0.925 | 0.885 | **0.482** |
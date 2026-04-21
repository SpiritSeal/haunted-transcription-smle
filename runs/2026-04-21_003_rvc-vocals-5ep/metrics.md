# Metrics — Haunted.musicxml

**Overall composite:** 0.466
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.916 | 0.193 | 0.252 | 0.021 | 0.503 | 0.410 | **0.512** |
| piano | 0.800 | 0.135 | 0.101 | 0.016 | 0.269 | 0.313 | **0.455** |
| guitar | 0.747 | 0.299 | 0.301 | 0.036 | 0.387 | 0.852 | **0.483** |
| bass | 0.739 | 0.097 | 0.130 | 0.003 | 0.300 | 0.249 | **0.415** |
| _mix | 0.780 | 0.356 | 0.335 | nan | 0.948 | 0.906 | **0.487** |
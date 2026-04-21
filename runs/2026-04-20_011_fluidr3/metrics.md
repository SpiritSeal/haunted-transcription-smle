# Metrics — Haunted.musicxml

**Overall composite:** 0.442
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.777 | 0.192 | 0.000 | 0.021 | 1.359 | 2.444 | **0.428** |
| piano | 0.820 | 0.063 | 0.068 | 0.036 | 0.374 | 0.502 | **0.442** |
| guitar | 0.747 | 0.299 | 0.301 | 0.036 | 0.387 | 0.852 | **0.483** |
| bass | 0.738 | 0.098 | 0.115 | 0.000 | 0.301 | 0.290 | **0.415** |
| _mix | 0.785 | 0.365 | 0.336 | nan | 0.932 | 0.894 | **0.492** |
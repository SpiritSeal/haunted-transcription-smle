# Metrics — Haunted.musicxml

**Overall composite:** 0.573
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.916 | 0.909 | 0.192 | 0.021 | 0.503 | 0.194 | **0.618** |
| piano | 0.801 | 0.799 | 0.142 | 0.019 | 0.277 | 0.331 | **0.548** |
| guitar | 0.769 | 0.757 | 0.382 | 0.041 | 0.396 | 0.186 | **0.612** |
| bass | 0.714 | 0.651 | 0.170 | 0.020 | 0.428 | 0.202 | **0.513** |
| _mix | 0.785 | 0.786 | 0.388 | nan | 0.939 | 0.000 | **0.630** |
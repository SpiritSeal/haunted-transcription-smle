# Metrics — Haunted.musicxml

**Overall composite:** 0.553
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.777 | 0.794 | 0.192 | 0.021 | 1.359 | 0.194 | **0.543** |
| piano | 0.801 | 0.799 | 0.142 | 0.019 | 0.277 | 0.331 | **0.548** |
| guitar | 0.766 | 0.756 | 0.386 | 0.038 | 0.400 | 0.210 | **0.609** |
| bass | 0.714 | 0.651 | 0.170 | 0.020 | 0.428 | 0.202 | **0.513** |
| _mix | 0.784 | 0.786 | 0.401 | nan | 0.939 | 0.000 | **0.633** |
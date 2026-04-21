# Metrics — Haunted.musicxml

**Overall composite:** 0.535
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.774 | 0.790 | 0.188 | 0.024 | 1.180 | 0.205 | **0.544** |
| piano | 0.827 | 0.807 | 0.045 | 0.025 | 0.397 | 0.688 | **0.471** |
| guitar | 0.771 | 0.759 | 0.382 | 0.041 | 0.394 | 0.184 | **0.613** |
| bass | 0.703 | 0.645 | 0.171 | 0.009 | 0.431 | 0.201 | **0.510** |
| _mix | 0.781 | 0.785 | 0.401 | nan | 0.928 | 0.000 | **0.633** |
# Metrics — Haunted.musicxml

**Overall composite:** 0.548
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.773 | 0.792 | 0.193 | 0.021 | 1.353 | 0.190 | **0.543** |
| piano | 0.800 | 0.793 | 0.135 | 0.016 | 0.269 | 0.312 | **0.547** |
| guitar | 0.759 | 0.745 | 0.326 | 0.039 | 0.397 | 0.236 | **0.585** |
| bass | 0.739 | 0.683 | 0.097 | 0.003 | 0.300 | 0.167 | **0.515** |
| _mix | 0.780 | 0.780 | 0.372 | nan | 0.951 | 0.000 | **0.623** |
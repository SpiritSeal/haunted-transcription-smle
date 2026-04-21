# Metrics — Haunted.musicxml

**Overall composite:** 0.669
**XML valid:** False

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.847 | 0.876 | 0.313 | 0.519 | 0.426 | 0.021 | **0.712** |
| piano | 0.889 | 0.945 | 0.025 | 0.083 | 0.402 | 0.734 | **0.516** |
| guitar | 0.873 | 0.916 | 0.450 | 0.508 | 0.310 | 0.139 | **0.747** |
| bass | 0.920 | 0.940 | 0.361 | 0.439 | 0.506 | 0.262 | **0.703** |
| _mix | 0.903 | 0.911 | 0.399 | nan | 0.882 | 0.002 | **0.684** |
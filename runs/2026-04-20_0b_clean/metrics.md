# Metrics — Haunted.musicxml

**Overall composite:** 0.472
**XML valid:** False

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.791 | 0.142 | 0.173 | 0.213 | 0.437 | 0.416 | **0.487** |
| piano | 0.816 | 0.042 | 0.030 | 0.053 | 0.414 | 0.418 | **0.436** |
| guitar | 0.715 | 0.234 | 0.233 | 0.059 | 0.388 | 0.714 | **0.455** |
| bass | 0.826 | 0.204 | 0.223 | 0.136 | 0.298 | 0.258 | **0.509** |
| _mix | 0.813 | 0.323 | 0.324 | nan | 0.895 | 0.937 | **0.492** |
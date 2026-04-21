# Run 2026-04-21_001_mt3-piano — MT3 ismir2021 piano model replaces basic-pitch on piano stem

## Metrics summary

# Metrics — Haunted.musicxml

**Overall composite:** 0.445
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.773 | 0.193 | 0.000 | 0.021 | 1.353 | 2.438 | **0.426** |
| piano | 0.800 | 0.135 | 0.101 | 0.016 | 0.269 | 0.313 | **0.455** |
| guitar | 0.747 | 0.299 | 0.301 | 0.036 | 0.387 | 0.852 | **0.483** |
| bass | 0.738 | 0.098 | 0.115 | 0.000 | 0.301 | 0.290 | **0.415** |
| _mix | 0.779 | 0.354 | 0.337 | nan | 0.948 | 0.906 | **0.486** |

## What I heard (listening A/B vs stems)
- Vocals:
- Piano:
- Guitar:
- Bass:
- Drums:

## Regressions vs previous run
-

## Try next
-

## Keep / revert

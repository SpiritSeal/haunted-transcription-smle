# Run 2026-04-20_008_vocal-onset-snap — Snap CREPE vocal starts to nearest detected vocal-stem onset (tol 80ms) before 16th quantize

## Metrics summary

# Metrics — Haunted.musicxml

**Overall composite:** 0.438
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.775 | 0.184 | 0.004 | 0.025 | 1.254 | 2.060 | **0.428** |
| piano | 0.792 | 0.043 | 0.024 | 0.018 | 0.360 | 0.429 | **0.421** |
| guitar | 0.758 | 0.287 | 0.314 | 0.037 | 0.374 | 0.571 | **0.484** |
| bass | 0.738 | 0.103 | 0.120 | 0.003 | 0.296 | 0.298 | **0.417** |
| _mix | 0.784 | 0.353 | 0.329 | nan | 0.925 | 0.884 | **0.489** |

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

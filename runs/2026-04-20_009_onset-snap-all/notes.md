# Run 2026-04-20_009_onset-snap-all — Extend onset-to-audio snapping to piano and guitar (not just vocals)

## Metrics summary

# Metrics — Haunted.musicxml

**Overall composite:** 0.438
**XML valid:** True

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.775 | 0.182 | 0.004 | 0.025 | 1.265 | 2.058 | **0.427** |
| piano | 0.792 | 0.038 | 0.018 | 0.020 | 0.360 | 0.427 | **0.420** |
| guitar | 0.759 | 0.298 | 0.321 | 0.037 | 0.375 | 0.524 | **0.488** |
| bass | 0.738 | 0.103 | 0.120 | 0.003 | 0.296 | 0.298 | **0.417** |
| _mix | 0.784 | 0.348 | 0.339 | nan | 0.924 | 0.885 | **0.487** |

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

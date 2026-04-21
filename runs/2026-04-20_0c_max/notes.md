# Run 2026-04-20_0c_max — Piano RH/LH split, CREPE vocal melody, chord filter first introduced.

Retroactive eval of git commit `1262f93` (2026-04-20). Artifacts extracted from git
tree; metrics computed with current `eval.py` (post-hoc, so scoring pipeline
did not exist at the time of this commit).

## Metrics summary

# Metrics — Haunted.musicxml

**Overall composite:** 0.467
**XML valid:** False

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.754 | 0.133 | 0.018 | 0.048 | 1.299 | 2.346 | **0.408** |
| piano | 0.863 | 0.048 | 0.052 | 0.114 | 0.370 | 0.377 | **0.470** |
| guitar | 0.763 | 0.245 | 0.253 | 0.078 | 0.365 | 0.688 | **0.482** |
| bass | 0.847 | 0.165 | 0.181 | 0.167 | 0.378 | 0.330 | **0.509** |
| _mix | 0.786 | 0.324 | 0.216 | nan | 0.906 | 0.895 | **0.481** |

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

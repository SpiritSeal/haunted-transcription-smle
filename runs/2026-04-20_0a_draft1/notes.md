# Run 2026-04-20_0a_draft1 — First auto-transcription (basic-pitch on Demucs-v3 stems, float-quantize via pretty_midi → music21). No chord symbols, no effect matching.

Retroactive eval of git commit `8dbcc0b` (2026-04-20). Artifacts extracted from git
tree; metrics computed with current `eval.py` (post-hoc, so scoring pipeline
did not exist at the time of this commit).

## Metrics summary

# Metrics — Haunted.musicxml

**Overall composite:** 0.603
**XML valid:** False

`mel_L1` is computed *after* matching production effects (EQ + plate reverb + loudness) onto the synth so it scores note content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is the pre-match diagnostic.

| stem | chroma | onset_F1 | (synth) | note_F1 | mel_L1 | (raw) | composite |
|---|---:|---:|---:|---:|---:|---:|---:|
| vocals | 0.847 | 0.313 | 0.322 | 0.519 | 0.426 | 0.417 | **0.623** |
| piano | 0.889 | 0.025 | 0.037 | 0.083 | 0.402 | 0.419 | **0.466** |
| guitar | 0.873 | 0.450 | 0.514 | 0.508 | 0.310 | 0.882 | **0.675** |
| bass | 0.920 | 0.361 | 0.377 | 0.439 | 0.506 | 0.566 | **0.647** |
| _mix | 0.903 | 0.399 | 0.404 | nan | 0.882 | 0.929 | **0.552** |

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

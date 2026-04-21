# Run 2026-04-21_003_rvc-vocals-5ep — RVC voice conversion (5-epoch Seann Bowe fine-tune)

## Metrics summary (best run of the session)

Overall composite: **0.466** (+0.021 vs prior best).

| stem | chroma | onset_F1 | note_F1 | mel_L1 | composite |
|---|---:|---:|---:|---:|---:|
| vocals | **0.916** | 0.193 | 0.021 | **0.503** | **0.512** |
| piano | 0.800 | 0.135 | 0.016 | 0.269 | 0.455 |
| guitar | 0.747 | 0.299 | 0.036 | 0.387 | 0.483 |
| bass | 0.739 | 0.097 | 0.003 | 0.300 | 0.415 |
| _mix | 0.780 | 0.356 | — | 0.948 | 0.487 |

Vocal chroma jumped from 0.773 to 0.916 (+0.143). Vocal mel_L1 dropped from 1.353
to 0.503 (-63%). Every other stem is unchanged from run 013 because RVC only
touched the vocal render.

## What I heard (listening A/B vs stems)
- Vocals: **listen to `audio/vocals.wav` vs `stems/smle - Haunted (ft Seann Bowe)-vocals.mp3`**
  — this should sound much more like Seann Bowe than the Choir Aahs synth.
- Piano, Guitar, Bass, Drums: unchanged from run 012.

## Regressions vs previous run
- None — RVC only touches vocal synth, other stems untouched.

## Try next
- Longer RVC training (continuing in background to 60 epochs).
- Build a FAISS index (`added_*.index`) for RVC to reduce tonal leakage.
- MT3 multi-instrument on guitar stem.

## Keep / revert

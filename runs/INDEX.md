# Transcription runs

Newest first. `★` = worth listening to (human-rated). See each run's `notes.md` for details.

## Scoring methodology

Each run is scored per stem (vocals, piano, guitar, bass) plus the full mix, on
four metrics. Composite per stem:

```
composite = 0.4·chroma + 0.3·onset_F1 + 0.2·note_F1 + 0.1·(1 − mel_L1/3)
```

Overall = mean of per-stem composites (excluding `_mix`).

| metric | what it measures | effect-sensitive? |
|---|---|---|
| `chroma` (chroma-CENS cosine) | right pitch-classes over time | **no** — CENS is timbre-invariant |
| `onset_F1` (±50 ms, mir_eval) | right onset timings | low — reverb tails can add false onsets |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | **no** — compares note events, not audio |
| `mel_L1` (z-scored log-mel) | timbre / dynamics envelope | **yes** — dry synth vs wet production hurts badly |

### Effects matching (added 2026-04-20 after run 006)

The reference stems and mix are professional-production audio: compression,
EQ, stereo imaging, reverb, and often sidechained dynamics. My synthesized
audio is bone-dry: MuseScore MS Basic SoundFont rendered through fluidsynth.
A raw mel comparison would dock every run for dry-vs-wet *production*
mismatch that has nothing to do with whether the notes are correct.

`eval.py` now runs [`effects.apply_production_effects`](../effects.py) on the
synth before `mel_L1` is computed:

1. **Spectrum match** — time-invariant EQ curve derived from the ratio of
   stem's average magnitude spectrum to the synth's (gain smoothed across 9
   bins, clipped to [0.1, 10] to prevent noise amplification).
2. **Plate reverb** — convolution with a filtered-noise IR (RT60 ≈ 1.4s,
   plate-style decay, 28% wet).
3. **Loudness match** — RMS-normalize the result to the stem.

`chroma` and `onset_F1` still run on **raw** synth (CENS and onset-strength
are already effect-invariant, and applying reverb could add false positives
to onset detection). `note_F1` runs on note events, not audio. So only
`mel_L1` is affected by this change.

`metrics.json` / `metrics.md` also emit `mel_L1_raw` — the pre-match value —
as a diagnostic. The gap between `mel_L1_raw` and `mel_L1` tells you how
much of the old timbre penalty was really about effects (big on vocals:
2.06 → 1.26; modest on bass: 0.30 → 0.30).

All runs below were re-scored under this new methodology so numbers are
comparable. The composite shifted uniformly by +0.008 to +0.010 across all
runs — ordering between runs is preserved.

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-20_006_richer-drums | Richer drum transcription (hi-hat, ride) via band-separated spectral-flux onsets | 0.765 | 0.116 | 0.019 | **0.426** |  | [dir](./2026-04-20_006_richer-drums/) |
| 2026-04-20_005_tie-merge | Pre-quantize merge of same-pitch basic-pitch fragments (gap<80ms) for piano/guitar | 0.765 | 0.116 | 0.019 | **0.426** |  | [dir](./2026-04-20_005_tie-merge/) |
| 2026-04-20_004_crepe-bass | CREPE monophonic f0 on bass stem (replaces basic-pitch bass) | 0.766 | 0.115 | 0.019 | **0.426** |  | [dir](./2026-04-20_004_crepe-bass/) |
| 2026-04-20_003_dtw-chords | DTW-align published chord chart to audio (anchored to start) | 0.756 | 0.120 | 0.020 | **0.422** |  | [dir](./2026-04-20_003_dtw-chords/) |
| 2026-04-20_002_baseline | v4 pipeline unchanged (establish metric floor) | 0.747 | 0.128 | 0.020 | **0.421** |  | [dir](./2026-04-20_002_baseline/) |

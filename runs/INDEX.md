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
| `onset_F1` (±50 ms, mir_eval) | MIDI note-starts vs stem audio onsets | no (after metric fix) |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | **no** — compares note events, not audio |
| `mel_L1` (z-scored log-mel) | timbre / dynamics envelope | **yes** — dry synth vs wet production hurts badly |

### Effects matching

`eval.py` runs [`effects.apply_production_effects`](../effects.py) on the synth
before `mel_L1` is computed: (1) spectrum-match EQ from stem's average
magnitude spectrum, (2) plate reverb (filtered-noise IR, RT60 ≈ 1.4 s, 28% wet),
(3) loudness match. `chroma` and `onset_F1` run on raw synth.

### Onset metric fix

`onset_F1` compares MIDI note-start times directly (deduped at ±10 ms) against
stem audio onsets, bypassing the synth roundtrip. The synth-WAV-based value is
kept as `onset_F1_synth` diagnostic. Previously this metric was penalizing
correctly-transcribed MIDI for GM Choir Aahs' 70 ms attack ramp.

### Onset-snapping

Before the 16th quantize, each vocal/piano/guitar note start is nudged to the
nearest detected stem audio onset if within ±80 ms. Preserves pitch-
detection's notes, aligns attacks with real audio transients.

### Fresh stems (run 010+)

Runs 010 and later use stems separated by **htdemucs_6s** (Demucs v4, 6-stem
including separate piano and guitar). Earlier runs used the older Demucs
separation now in `stems_v3_demucs/`.

### Synthesis SoundFont (run 011+)

Runs 011 and later synthesize MIDI → WAV with **FluidR3 Mono GM** (23 MB).
Earlier runs used MuseScore's MS Basic sf3 (49 MB). FluidR3's piano patch is
noticeably more accurate to real piano; piano chroma jumped +0.034 between
runs 010 → 011 because the synth's overtones now match the stem's better.

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-20_011_fluidr3 | FluidR3 SoundFont replaces MS Basic | 0.766 | 0.163 | 0.023 | **0.442** |  | [dir](./2026-04-20_011_fluidr3/) |
| 2026-04-20_010_htdemucs-stems | Fresh htdemucs_6s stems | 0.762 | 0.163 | 0.023 | **0.439** |  | [dir](./2026-04-20_010_htdemucs-stems/) |
| 2026-04-20_009_onset-snap-all | Extend onset-to-audio snapping to piano and guitar | 0.766 | 0.155 | 0.021 | **0.438** |  | [dir](./2026-04-20_009_onset-snap-all/) |
| 2026-04-20_008_vocal-onset-snap | Snap CREPE vocal starts to detected stem onsets (±80ms) | 0.766 | 0.154 | 0.021 | **0.438** |  | [dir](./2026-04-20_008_vocal-onset-snap/) |
| 2026-04-20_007_vocal-32nd | 32nd-note vocal grid — REVERTED (78 ms > 50 ms tol) | 0.766 | 0.145 | 0.017 | **0.434** |  | [dir](./2026-04-20_007_vocal-32nd/) |
| 2026-04-20_006_richer-drums | Richer drum transcription (hi-hat, ride) | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_006_richer-drums/) |
| 2026-04-20_005_tie-merge | Pre-quantize merge of same-pitch fragments (gap<80ms) | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_005_tie-merge/) |
| 2026-04-20_004_crepe-bass | CREPE monophonic f0 on bass stem | 0.766 | 0.148 | 0.019 | **0.437** |  | [dir](./2026-04-20_004_crepe-bass/) |
| 2026-04-20_003_dtw-chords | DTW-align published chord chart to audio | 0.756 | 0.151 | 0.020 | **0.436** |  | [dir](./2026-04-20_003_dtw-chords/) |
| 2026-04-20_002_baseline | v4 pipeline unchanged | 0.747 | 0.148 | 0.020 | **0.434** |  | [dir](./2026-04-20_002_baseline/) |

## Progress summary

| stage | overall | Δ | what moved |
|---|---:|---:|---|
| 002 baseline | 0.434 | — | — |
| 003 DTW chords | 0.436 | +0.002 | vocal chroma +0.023 |
| 004 CREPE bass | 0.437 | +0.001 | bass chroma +0.038 |
| 006 richer drums | 0.437 | +0.000 | playback only (not in score) |
| 008–009 onset snap | 0.438 | +0.001 | vocal onset_F1 +0.004 |
| 010 htdemucs stems | 0.439 | +0.001 | piano composite +0.008 |
| 011 FluidR3 sf | **0.442** | +0.003 | piano chroma +0.034 |

Net gain from baseline: **+0.008 composite**.

## Per-stem ceiling analysis (run 011)

| stem | chroma | onset | note | mel_L1 | main limitation |
|---|---:|---:|---:|---:|---|
| vocals | 0.777 | 0.158 | 0.010 | 1.28 | note_F1 — needs better vocal transcription model |
| piano  | 0.820 | 0.067 | 0.035 | 0.46 | onset_F1 saturated by 16th grid |
| guitar | 0.747 | 0.288 | 0.036 | 0.41 | still has cross-bleed even post-htdemucs |
| bass   | 0.720 | 0.099 | 0.000 | 0.32 | note_F1 = 0 — CREPE segmentation vs basic-pitch GT doesn't overlap |

## Open follow-ups

- **Modern transcription model** (MT3 or Onsets-and-Frames-with-context): the
  biggest remaining lever for `note_F1`, especially piano polyphony. MT3 needs
  JAX/t5x — didn't install cleanly this session.
- **Better vocal patch**: FluidR3's Choir Aahs is still not great for pop
  vocal. Dedicated vocal patch or DiffSinger-style neural synth would drop
  vocal `mel_L1`.
- **Bass `note_F1 = 0.000`**: CREPE bass note segmentation doesn't align with
  basic-pitch's pseudo-ground-truth. Candidates: snap CREPE bass onsets to
  detected bass-stem onsets (same treatment as vocals), or widen the note
  tolerance for monophonic-instrument scoring.

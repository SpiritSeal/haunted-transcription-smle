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
| 2026-04-21_002_bass-onset-snap | Extend onset-to-audio snapping to bass CREPE notes | 0.765 | 0.181 | 0.019 | **0.445** |  | [dir](./2026-04-21_002_bass-onset-snap/) |
| `chroma` (chroma-CENS cosine) | right pitch-classes over time | **no** — CENS is timbre-invariant |
| `onset_F1` (±50 ms) | MIDI note-starts vs stem audio onsets | no (metric fix) |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | see caveat below |
| `mel_L1` (z-scored log-mel, effect-matched) | timbre / dynamics envelope | yes (mitigated) |

### Effects matching

`eval.py` runs [`effects.apply_production_effects`](../effects.py) on the synth
before `mel_L1`: spectrum-match EQ, plate reverb (RT60 ≈ 1.4s, 28% wet),
loudness match. `chroma` and `onset_F1` run on raw synth.

### Onset metric fix

`onset_F1` compares MIDI note-starts directly (deduped at ±10 ms) to stem
audio onsets, bypassing the synth roundtrip. Fixed the old bias against
slow-attack GM patches.

### Onset-snapping (runs 008+)

Each vocal/piano/guitar note start is nudged to the nearest stem audio
onset if within ±80 ms before the 16th quantize.

### Fresh stems (runs 010+)

**htdemucs_6s** (Demucs v4, 6-stem) replaces the older Demucs separation
now archived in `stems_v3_demucs/`.

### Synthesis SoundFont (runs 011+)

**FluidR3 Mono GM** (23 MB) replaces MuseScore's MS Basic sf3. FluidR3's
piano patch is noticeably more accurate to real piano — chroma's harmonic
template matches much better.

### MT3 piano transcription (runs 012+)

**MT3 ismir2021** (Google Magenta, T5-based, SOTA for solo piano) replaces
basic-pitch on the piano stem. 644 notes vs basic-pitch's ~400. Piano
onset_F1 jumped +0.072 (0.067 → 0.139) because MT3's onset timing is much
sharper than basic-pitch's on polyphonic content.

Caveat: `note_F1` regressed on piano (0.035 → 0.016) because note_F1's
pseudo-ground-truth is basic-pitch on the stem. When MT3 correctly
transcribes notes that basic-pitch missed, they count as "wrong" against
the basic-pitch reference. A more trustworthy evaluation would use a
human-made MIDI reference; absent that, trust chroma + onset_F1 here.

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-21_002_bass-onset-snap | Extend onset-to-audio snapping to bass CREPE notes | 0.765 | 0.181 | 0.019 | **0.445** |  | [dir](./2026-04-21_002_bass-onset-snap/) |
| 2026-04-21_001_mt3-piano | MT3 ismir2021 piano transcription replaces basic-pitch | 0.765 | 0.181 | 0.018 | **0.445** |  | [dir](./2026-04-21_001_mt3-piano/) |
| 2026-04-20_011_fluidr3 | FluidR3 SoundFont replaces MS Basic | 0.766 | 0.163 | 0.023 | **0.442** |  | [dir](./2026-04-20_011_fluidr3/) |
| 2026-04-20_010_htdemucs-stems | Fresh htdemucs_6s stems | 0.762 | 0.163 | 0.023 | **0.439** |  | [dir](./2026-04-20_010_htdemucs-stems/) |
| 2026-04-20_009_onset-snap-all | Onset snapping extended to piano and guitar | 0.766 | 0.155 | 0.021 | **0.438** |  | [dir](./2026-04-20_009_onset-snap-all/) |
| 2026-04-20_008_vocal-onset-snap | Snap CREPE vocal starts to detected stem onsets (±80ms) | 0.766 | 0.154 | 0.021 | **0.438** |  | [dir](./2026-04-20_008_vocal-onset-snap/) |
| 2026-04-20_007_vocal-32nd | 32nd-note vocal grid — REVERTED | 0.766 | 0.145 | 0.017 | **0.434** |  | [dir](./2026-04-20_007_vocal-32nd/) |
| 2026-04-20_006_richer-drums | Hi-hat / ride from band-separated spectral-flux onsets | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_006_richer-drums/) |
| 2026-04-20_005_tie-merge | Pre-quantize same-pitch fragment merge | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_005_tie-merge/) |
| 2026-04-20_004_crepe-bass | CREPE monophonic f0 on bass stem | 0.766 | 0.148 | 0.019 | **0.437** |  | [dir](./2026-04-20_004_crepe-bass/) |
| 2026-04-20_003_dtw-chords | DTW-align published chord chart to audio | 0.756 | 0.151 | 0.020 | **0.436** |  | [dir](./2026-04-20_003_dtw-chords/) |
| 2026-04-20_002_baseline | v4 pipeline unchanged | 0.747 | 0.148 | 0.020 | **0.434** |  | [dir](./2026-04-20_002_baseline/) |

## Progress summary

| stage | overall | Δ | what moved |
|---|---:|---:|---|
| 002 baseline | 0.434 | — | — |
| 003 DTW chords | 0.436 | +0.002 | vocal chroma +0.023 |
| 004 CREPE bass | 0.437 | +0.001 | bass chroma +0.038 |
| 008–009 onset snap | 0.438 | +0.001 | vocal onset_F1 +0.004 |
| 010 htdemucs stems | 0.439 | +0.001 | piano composite +0.008 |
| 011 FluidR3 sf | 0.442 | +0.003 | piano chroma +0.034 |
| **012 MT3 piano** | **0.445** | +0.003 | piano onset_F1 +0.072 |

Net gain from baseline: **+0.011 composite** (0.434 → 0.445).

## Per-stem ceiling analysis (run 012)

| stem | chroma | onset_F1 | note_F1 | mel_L1 | main limitation |
|---|---:|---:|---:|---:|---|
| vocals | 0.773 | 0.193 | 0.021 | 1.35 | note_F1 low — CREPE boundaries ≠ basic-pitch onsets |
| piano  | 0.800 | **0.135** | 0.016 | 0.27 | note_F1 metric pathology (MT3 beats basic-pitch reference) |
| guitar | 0.747 | 0.299 | 0.036 | 0.39 | stem still has cross-bleed |
| bass   | 0.738 | 0.098 | 0.000 | 0.30 | CREPE bass onset boundaries ≠ basic-pitch onsets |

## Open follow-ups

- **MT3 multi-instrument model** on the mix (requires separate checkpoint,
  ~400 MB) — would produce a single transcription covering all pitched
  instruments; useful as a cross-check against our per-stem pipeline.
- **Vocal synthesis** — FluidR3's Choir Aahs still sounds nothing like a
  Swedish-pop female voice. Options: DiffSinger (OpenVPI) neural vocal
  synthesizer, or find a commercial soundfont with a usable pop vocal.
- **Bass/vocal note_F1 = 0.000 / 0.021**: CREPE segmentation doesn't match
  basic-pitch's pseudo-GT onsets. Try running basic-pitch on each stem to
  derive a union-of-references ground truth, or build a human-made reference
  MIDI to compare against.
- **Guitar transcription** is still via basic-pitch; MT3's multi-instrument
  model might find cleaner strummed patterns if applied to the guitar stem.

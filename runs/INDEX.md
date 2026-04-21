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
| `onset_F1` (±50 ms) | MIDI note-starts vs stem audio onsets | no (metric fix) |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | see caveat below |
| `mel_L1` (z-scored log-mel, effect-matched) | timbre / dynamics envelope | yes (mitigated) |

### Effects matching

`eval.py` runs `effects.apply_production_effects` on synth before `mel_L1`:
spectrum-match EQ, plate reverb (RT60 ≈ 1.4 s, 28 % wet), loudness match.
`chroma` and `onset_F1` run on raw synth.

### Onset metric fix

`onset_F1` compares MIDI note-starts directly (deduped at ±10 ms) to stem
audio onsets, bypassing the synth roundtrip.

### Onset-snapping (runs 008+)

Each vocal/piano/guitar/bass note start is nudged to the nearest stem audio
onset if within ±80 ms before the 16th quantize.

### Fresh stems (runs 010+)

**htdemucs_6s** (Demucs v4, 6-stem with separate piano and guitar) replaces
older Demucs separation in `stems_v3_demucs/`.

### Synthesis SoundFont (runs 011+)

**FluidR3 Mono GM** (23 MB) replaces MS Basic sf3 for non-vocal render.

### MT3 piano transcription (run 012)

**MT3 ismir2021** (Magenta T5-based, SOTA solo piano) replaces basic-pitch on
the piano stem. Piano onset_F1 +0.072. Note_F1 regressed because
pseudo-ground-truth is basic-pitch — MT3 is catching notes basic-pitch
misses, which scores as "wrong" vs the weaker reference.

### RVC voice conversion (run 014, 2026-04-21_003)

Trained a custom RVC model on Seann Bowe's vocal stem (212 s, 56 × 3 s clips,
Demucs-ft pretrained → 5-epoch fine-tune on Mac MPS). The Vocals track is now
synthesized by: fluidsynth → `vocals_synth.wav` → RVC convert → voice in
Seann Bowe's timbre. Wired into `eval.py` via `--vocals-wav`.

**Biggest single-experiment win of the session.** Vocal chroma 0.773 → 0.916,
vocal mel_L1 1.35 → 0.50, vocal composite 0.414 → 0.512. Overall +0.021.

Pipeline additions:
- `rvc_repo/` (vendored, gitignored)
- `rvc_training/seann_bowe/vocal_raw.wav` — training data
- `rvc_repo/logs/seann_bowe/` — preprocessed features + checkpoints
- `synth_vocals_rvc.py` — inference wrapper with MPS support

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-21_003_rvc-vocals-5ep | RVC voice conversion (5-epoch Seann Bowe fine-tune) replaces Choir Aahs for vocals | 0.800 | 0.181 | 0.019 | **0.466** |  | [dir](./2026-04-21_003_rvc-vocals-5ep/) |
| 2026-04-21_002_bass-onset-snap | Extend onset-to-audio snapping to bass CREPE notes | 0.747 | 0.178 | 0.019 | **0.445** |  | [dir](./2026-04-21_002_bass-onset-snap/) |
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
| 012 MT3 piano | 0.445 | +0.003 | piano onset_F1 +0.072 |
| **014 RVC vocals** | **0.466** | **+0.021** | **vocal chroma +0.143, mel_L1 -63%** |

Net gain from baseline: **+0.032 composite** (0.434 → 0.466).

## Per-stem ceiling (run 014)

| stem | chroma | onset_F1 | note_F1 | mel_L1 | main limitation |
|---|---:|---:|---:|---:|---|
| vocals | **0.916** | 0.193 | 0.021 | **0.50** | RVC output excellent; note_F1 still metric-bounded |
| piano  | 0.800 | 0.135 | 0.016 | 0.27 | note_F1 metric pathology (MT3 beats reference) |
| guitar | 0.747 | 0.299 | 0.036 | 0.39 | stem still has cross-bleed |
| bass   | 0.739 | 0.097 | 0.003 | 0.30 | CREPE bass boundaries ≠ basic-pitch onsets |

## Open follow-ups

- **Extend RVC training** — we used a 5-epoch fine-tune. Training continues
  in the background to 60 epochs. Longer training should tighten pitch
  tracking and reduce residual artifacts on sustained vowels.
- **MT3 multi-instrument model** on guitar stem (~400 MB checkpoint) —
  might reduce guitar chroma gap.
- **Human-made reference MIDI** — would unblock note_F1 metric saturation.

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
| `onset_F1` (±50 ms, mir_eval) | MIDI note-starts vs stem audio onsets | no (after fix below) |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | **no** — compares note events, not audio |
| `mel_L1` (z-scored log-mel) | timbre / dynamics envelope | **yes** — dry synth vs wet production hurts badly |

### Effects matching (added 2026-04-20 after run 006)

The reference stems and mix are professional-production audio: compression,
EQ, stereo imaging, reverb, and often sidechained dynamics. My synthesized
audio is bone-dry: MuseScore MS Basic SoundFont rendered through fluidsynth.
A raw mel comparison would dock every run for dry-vs-wet *production*
mismatch that has nothing to do with whether the notes are correct.

`eval.py` runs [`effects.apply_production_effects`](../effects.py) on the
synth before `mel_L1` is computed:

1. **Spectrum match** — time-invariant EQ from the ratio of stem's average
   magnitude spectrum to synth's (smoothed, clipped to [0.1, 10]).
2. **Plate reverb** — convolution with a filtered-noise IR (RT60 ≈ 1.4s, 28% wet).
3. **Loudness match** — RMS-normalize to the stem.

`chroma` and `onset_F1` run on **raw** synth. Only `mel_L1` is effect-matched.
`mel_L1_raw` is emitted as a diagnostic — gap shows how much of old mel
penalty was effects, not notes (vocals: 2.06 → 1.26; bass: 0.30 → 0.30).

### Onset metric fix (added 2026-04-20 after run 007)

`onset_F1` used to compare **synth-WAV onsets** vs **stem-WAV onsets**.
Problem: GM Choir Aahs has a ~70 ms attack ramp, so correctly-transcribed
MIDI scored near-zero onset_F1 purely from synth-patch mismatch.

`onset_F1` now compares **MIDI note-start times directly** (deduped to unique
times at ±10 ms) against stem audio onsets. The synth-WAV-based value is
kept as `onset_F1_synth` in metrics.json.

This added +0.007 to +0.013 to every run's composite. All runs below are
re-scored under this methodology so numbers are comparable.

### Attempted improvement: 32nd-note vocal grid (run 007 — reverted)

A 32nd-note grid for vocals was tried to capture rubato. It regressed
onset_F1 because one 32nd-note position = 78 ms, which exceeds the ±50 ms
match tolerance. Notes bumped onto odd-32nd positions ended up farther from
stem onsets than if they'd snapped to a nearer 16th. Reverted to 16ths.

### Onset-snapping (runs 008, 009)

Before the 16th quantize, each vocal/piano/guitar note's start is nudged to
the nearest detected audio onset on its stem if one sits within ±80 ms.
Keeps pitch-detection's notes but aligns attacks with real audio transients,
so the 16th snap lands on the bar-position nearest the true onset.

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-20_009_onset-snap-all | Extend onset-to-audio snapping to piano and guitar | 0.766 | 0.155 | 0.021 | **0.438** |  | [dir](./2026-04-20_009_onset-snap-all/) |
| 2026-04-20_008_vocal-onset-snap | Snap CREPE vocal starts to detected stem onsets (±80ms) before 16th quantize | 0.766 | 0.154 | 0.021 | **0.438** |  | [dir](./2026-04-20_008_vocal-onset-snap/) |
| 2026-04-20_007_vocal-32nd | 32nd-note vocal grid — REVERTED (78 ms > 50 ms tolerance) | 0.766 | 0.145 | 0.017 | **0.434** |  | [dir](./2026-04-20_007_vocal-32nd/) |
| 2026-04-20_006_richer-drums | Richer drum transcription (hi-hat, ride) via band-separated spectral-flux onsets | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_006_richer-drums/) |
| 2026-04-20_005_tie-merge | Pre-quantize merge of same-pitch basic-pitch fragments (gap<80ms) for piano/guitar | 0.765 | 0.149 | 0.019 | **0.437** |  | [dir](./2026-04-20_005_tie-merge/) |
| 2026-04-20_004_crepe-bass | CREPE monophonic f0 on bass stem (replaces basic-pitch bass) | 0.766 | 0.148 | 0.019 | **0.437** |  | [dir](./2026-04-20_004_crepe-bass/) |
| 2026-04-20_003_dtw-chords | DTW-align published chord chart to audio (anchored to start) | 0.756 | 0.151 | 0.020 | **0.436** |  | [dir](./2026-04-20_003_dtw-chords/) |
| 2026-04-20_002_baseline | v4 pipeline unchanged (establish metric floor) | 0.747 | 0.148 | 0.020 | **0.434** |  | [dir](./2026-04-20_002_baseline/) |

## Notes on the plateau

Composite saturates around 0.438. Remaining headroom is mostly in areas
that require external deps / more work:

- **Stem separation quality** — current stems are older Demucs; htdemucs v4
  would reduce guitar cross-bleed (visible as phantom low-freq content in
  the guitar and piano parts).
- **Synthesis fidelity** — MS Basic GM patches don't sound like the actual
  instruments (especially Choir Aahs vs Swedish-pop female vocal). Better
  SoundFont / vocal synthesizer would drop `mel_L1` without affecting note
  correctness.
- **Transcription model quality** — basic-pitch is solid but not SOTA.
  MT3 / Onsets-and-Frames-with-context would likely improve `note_F1`
  materially, especially for polyphonic piano.

These require external dependencies or substantial work. Next-round backlog
for the human to prioritize.

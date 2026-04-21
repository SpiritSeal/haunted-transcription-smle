# Transcription runs

Newest first. `★` = worth listening to (human-rated). See each run's `notes.md` for details.

## Scoring methodology

### Composite v2 (runs 011+)

Each run is scored per stem (vocals, piano, guitar, bass) + the mix, on six
metrics. v2 was introduced after human A/B revealed v1 was missing a
phenomenon that clearly affects perceived quality: phantom notes emitted
during sections where the reference stem is silent ("weird artifacts
during non-guitar synth sections"). v1 didn't penalize these because the
reference stem has cross-bleed too — so basic-pitch-vs-basic-pitch
rewarded them as "matching the reference."

```
composite_v2 = 0.35·chroma_active
             + 0.05·chroma              (raw, for continuity with v1)
             + 0.25·onset_F1
             + 0.10·note_F1             (downweighted — metric is pathological)
             + 0.15·(1 − fp_silence)    (NEW: silence discipline)
             + 0.10·(1 − mel_L1/3)
```

| metric | what it measures | effect-sensitive? |
|---|---|---|
| `chroma` (chroma-CENS cosine) | right pitch-classes over time | **no** — CENS is timbre-invariant |
| `chroma_active` (NEW v2) | chroma computed **only** where the stem has ≥ peak−30 dB energy | no |
| `onset_F1` (±50 ms) | MIDI note-starts vs stem audio onsets | no (metric fix) |
| `note_F1` (±50 ms / ±50 ¢) | right notes vs basic-pitch pseudo-GT on stem | see caveat below |
| `fp_silence` (NEW v2) | fraction of hyp note-starts during reference-silent frames. **Lower is better.** | no |
| `mel_L1` (z-scored log-mel, effect-matched) | timbre / dynamics envelope | yes (mitigated) |

**Why v2:** draft1's piano `fp_silence = 0.734` — 73 % of its piano
notes land in stem-silent regions (pure cross-bleed phantoms). Under v1
that produced no penalty; under v2 it pulls piano composite down to
0.516. Draft1 guitar `fp_silence = 0.139` matches the user's listening
intuition: "main theme is great, but weird artifacts during non-guitar
sections."

### Composite v1 (runs 002–010)

```
composite_v1 = 0.4·chroma + 0.3·onset_F1 + 0.2·note_F1 + 0.1·(1 − mel_L1/3)
```

Rows 002–010 in the Runs table below show v1 scores; rows 011+ show v2.
They are **not** directly comparable. For apples-to-apples deltas see
the per-comparison `notes.md`.

Overall = mean of per-stem composites (excluding `_mix`).

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

### Guitar chord_filter removed (run 015, 2026-04-21_004)

Human A/B: "guitar from 8dbcc0b sounds more accurate." Root cause: runs
003+ applied `chord_filter` to guitar, which requires diatonic notes to be
≥2 sixteenths long. Guitar parts are dominated by 1-sixteenth strums,
arpeggio picks, and rhythmic chicks — this filter was dropping ~150
legitimate articulations per run, flattening the guitar into a drone.

Fix: guitar pipeline no longer runs `chord_filter` (matches 8dbcc0b's
behaviour). `velocity_floor=35` + `cap_polyphony(3)` are sufficient noise
control. Guitar note count 417 → 563. Guitar composite 0.483 → 0.496;
guitar onset_F1 +0.027; overall +0.003.

### Bass reverted to basic-pitch (run 016, 2026-04-21_005)

Retroactive eval showed draft1 (basic-pitch bass) had bass chroma 0.920
vs CREPE's 0.739. CREPE is monophonic — discards octave doublings and
grace notes that basic-pitch catches polyphonically. Since `note_F1` is
metric-pathological (see caveat), the reason CREPE was originally
chosen no longer holds: switching back to basic-pitch is net positive.
Bass onset_F1 0.097 → 0.170, note_F1 0.003 → 0.020, composite 0.415 →
0.426. Overall +0.003.

Tried widening pitch range (runs 006/007: E1–G3 → B0–G4) — no chroma
win, extra pitch room caught cross-bleed noise and hurt mel_L1. Kept
narrow E1–G3 with onset-snap.

### Piano chord_filter removed (run 018, 2026-04-21_008)

Same reasoning as guitar. MT3 already does SOTA pre-filtering; stacking
`chord_filter` on top dropped piano's arpeggio passing tones. Piano
composite 0.455 → 0.457. Overall +0.001.

### Guitar premerge removed (run 019, 2026-04-21_009)

Tested removing 80ms same-pitch premerge — the 16th-grid
`merge_same_pitch` afterwards already coalesces fragments. Result:
neutral (-0.001 guitar composite, 0.000 overall). Kept for code
simplicity — one fewer preprocessing stage.

### Guitar merge_same_pitch removed (run 020, 2026-04-21_010)

**Second-largest single-experiment gain of the session.** Human A/B
after run 019: "draft1 still sounds more accurate." Duration histogram
analysis vs draft1 revealed the culprit: `merge_same_pitch(gap_tol_16=1)`
was fusing adjacent same-pitch strums — e.g. four quarter-note Bm
strums in one measure — into a single long held note. Draft1 had 506
× 1-sixteenth guitar notes; current (019) had only 315, and 30+ notes
longer than 8 sixteenths where there shouldn't be any. Full-measure
pads where there should be rhythmic chugs.

Fix: remove `merge_same_pitch` from guitar pipeline entirely. Note
count 563 → 873 (matches draft1's 855 within 2 %). Guitar onset_F1
0.323 → 0.386 (+0.063), composite 0.495 → 0.517 (+0.022), overall
+0.005.

## Runs

| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |
|---|---|---:|---:|---:|---:|:-:|---|
| 2026-04-21_013_demucs-v3-full | Full pipeline on demucs-v3 stems (draft1 era). basic-pitch all 4 stems, draft1-verbatim guitar, no RVC. | 0.768 | 0.196 | 0.025 | **0.535** |  | [dir](./2026-04-21_013_demucs-v3-full/) |
| 2026-04-21_012_guitar-draft1-verbatim | Guitar pipeline = draft1 verbatim: quantize + cap_poly(3), no silence-gate/snap/range-filter | 0.800 | 0.222 | 0.025 | **0.573** |  | [dir](./2026-04-21_012_guitar-draft1-verbatim/) |
| 2026-04-21_011_draft1-guitar-silgate | Use draft1 guitar.mid directly + silence-gate phantoms + tighter onset-snap. New scoring v2 adds chroma_active + fp_silence. | 0.805 | 0.229 | 0.024 | **0.579** |  | [dir](./2026-04-21_011_draft1-guitar-silgate/) |
| 2026-04-21_010_guitar-no-merge | Guitar: remove merge_same_pitch — preserve rhythmic strums (draft1 has 506 1-16th notes, current only 315) | 0.799 | 0.223 | 0.024 | **0.478** |  | [dir](./2026-04-21_010_guitar-no-merge/) |
| 2026-04-21_009_guitar-no-premerge | Guitar: remove premerge_gap_ms=80 — let 16th-grid merge handle sustains | 0.797 | 0.207 | 0.025 | **0.473** |  | [dir](./2026-04-21_009_guitar-no-premerge/) |
| 2026-04-21_008_piano-unfilter-bass-fix | Remove chord_filter from piano + settle bass at basic-pitch narrow+snap | 0.797 | 0.208 | 0.025 | **0.473** |  | [dir](./2026-04-21_008_piano-unfilter-bass-fix/) |
| 2026-04-21_007_bass-wider-snap | Basic-pitch bass: wider range (B0-G4) + min_len=1 + keep onset-snap | 0.799 | 0.195 | 0.023 | **0.468** |  | [dir](./2026-04-21_007_bass-wider-snap/) |
| 2026-04-21_006_bass-wider | Widen bass pitch range (B0-G4) + min_len=1 + no onset-snap — match 8dbcc0b bass | 0.799 | 0.197 | 0.023 | **0.469** |  | [dir](./2026-04-21_006_bass-wider/) |
| 2026-04-21_005_bass-basic-pitch | Revert bass from CREPE monophonic to basic-pitch polyphonic — bass chroma 0.739 → ? | 0.797 | 0.206 | 0.024 | **0.472** |  | [dir](./2026-04-21_005_bass-basic-pitch/) |
| 2026-04-21_004_guitar-unfilter | Remove chord_filter from guitar — restores 150+ rhythmic 16th-note articulations | 0.789 | 0.213 | 0.020 | **0.469** |  | [dir](./2026-04-21_004_guitar-unfilter/) |
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
| 2026-04-20_0d_xml-fix | Pre-harness: MusicXML structural fixes + vocal polyphony merge (git 80245f0) | 0.753 | 0.171 | 0.020 | **0.436** |  | [dir](./2026-04-20_0d_xml-fix/) |
| 2026-04-20_0c_max | Pre-harness: Piano RH/LH split, CREPE vocal, chord filter first introduced (git 1262f93) | 0.807 | 0.148 | 0.102 | **0.467** |  | [dir](./2026-04-20_0c_max/) |
| 2026-04-20_0b_clean | Pre-harness: chord detection added, first cleanup pass (git 8fbd2ac) | 0.787 | 0.155 | 0.115 | **0.472** |  | [dir](./2026-04-20_0b_clean/) |
| 2026-04-20_0a_draft1 | Pre-harness: first auto-transcription — raw basic-pitch + float-quantize (git 8dbcc0b) [XML-invalid] | 0.882 | 0.287 | 0.387 | **0.603** |  | [dir](./2026-04-20_0a_draft1/) |

### Caveat on pre-harness runs (0a–0d)

These rows are **retroactive** — evaluated with the current `eval.py` against
commits from before the eval harness existed. Their scores look high relative
to later runs, but that's partly an artifact of the metric:

- **`note_F1` favors basic-pitch-derived transcriptions.** The pseudo-ground-
  truth in `eval.py` is itself basic-pitch on the stem. Runs 0a–0c used
  basic-pitch directly for the output, so they "agree" with the reference
  by construction. Later runs replaced basic-pitch with CREPE (vocals/bass),
  MT3 (piano), and RVC-derived audio — outputs that diverge from the
  reference even when they're closer to the true performance. This drops
  `note_F1` even as the human-perceived quality rises.
- **XML validity.** `0a_draft1` and `0b_clean` fail musicxml structural
  validation (overfull measures from float-quantize round-tripping). They
  sound fuller, but won't open correctly in many editors — the v4 rewrite
  (run 002) fixed that at the cost of note density.
- **`0a_draft1` is the user's preferred-sounding guitar.** That listening
  judgment is what prompted the `run 015_guitar-unfilter` fix — removing
  `chord_filter` restored most of the guitar articulation without the XML
  validity regression.

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
| 014 RVC vocals | 0.466 | +0.021 | vocal chroma +0.143, mel_L1 -63% |
| 015 guitar unfilter | 0.469 | +0.003 | guitar onset_F1 +0.027, composite +0.013 |
| 016 bass basic-pitch | 0.472 | +0.003 | bass onset_F1 +0.073, composite +0.011 |
| 018 piano unfilter | 0.473 | +0.001 | piano onset_F1 +0.007 |
| 019 guitar no-premerge | 0.473 | +0.000 | code simplification, neutral |
| **020 guitar no-merge** | **0.478** | **+0.005** | **guitar onset_F1 +0.063, composite +0.022** |

Net gain from baseline: **+0.044 composite** (0.434 → 0.478).

## Per-stem ceiling (run 020)

| stem | chroma | onset_F1 | note_F1 | mel_L1 | main limitation |
|---|---:|---:|---:|---:|---|
| vocals | **0.916** | 0.192 | 0.021 | **0.50** | RVC output excellent; note_F1 still metric-bounded |
| piano  | 0.801 | 0.142 | 0.019 | 0.28 | note_F1 metric pathology (MT3 beats reference) |
| guitar | 0.766 | 0.386 | 0.038 | 0.40 | rhythmic density now matches draft1; stem cross-bleed only |
| bass   | 0.714 | 0.170 | 0.020 | 0.43 | basic-pitch back; chroma plateaued ~0.72 vs draft1 0.92 |

## Open follow-ups

- **Extend RVC training** — we used a 5-epoch fine-tune. Training continues
  in the background to 60 epochs. Longer training should tighten pitch
  tracking and reduce residual artifacts on sustained vowels.
- **MT3 multi-instrument model** on guitar stem (~400 MB checkpoint) —
  might reduce guitar chroma gap.
- **Human-made reference MIDI** — would unblock `note_F1` metric
  saturation. This is the single biggest ceiling on measured quality:
  basic-pitch-as-reference artificially favors basic-pitch-based
  pipelines (see caveat above). A 2–3 hour manual transcription pass on
  one song would give a trustworthy upper bound on all stems at once.
- **Bass chroma ceiling.** Plateaued at ~0.72. Draft1 hit 0.92 largely
  because it emitted ~2× more notes (many spurious), and chroma-CENS
  rewards "any pitch-class present" per time window. Closing this gap
  would require either richer bass note density (accept false positives)
  or better bass stem separation.

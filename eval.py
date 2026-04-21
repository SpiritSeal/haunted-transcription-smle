"""Evaluate a transcription run against the original stems + mix.

Usage: eval.py <musicxml_path> <run_dir>

For each instrument in the score, renders MIDI → WAV via fluidsynth, then
compares the synthesized audio to the matching stem on four metrics:

  - chroma_cosine   (right pitch-classes per bar)
  - onset_f1        (right onset timing, ±50ms)
  - note_f1         (right notes at right time, ±50ms / ±50¢; uses basic-pitch
                    on the stem as pseudo-ground-truth)
  - mel_l1          (timbre/dynamics proxy; log-mel L1, z-scored — lower=better)

Also runs a mix-level comparison against the original mp3.

Writes <run_dir>/metrics.json and metrics.md with a human-readable table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import librosa
import mir_eval
import pretty_midi
import music21

from midi_utils import (stem_paths, mix_path, render_per_track,
                        DEFAULT_SF2, TRACK_TO_STEM, validate_musicxml)
from effects import apply_production_effects, dereverb


# ------------------------------------------------------------------ #

SR = 22050
HOP = 2048
ONSET_TOL = 0.05        # ±50 ms
NOTE_ONSET_TOL = 0.05   # ±50 ms
NOTE_PITCH_TOL = 0.5    # ±50 cents ~= ±0.5 semitone


def load_audio(path, sr=SR):
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y


def _stem_active_mask(y: np.ndarray, hop: int = HOP,
                      db_floor: float = -30.0) -> np.ndarray:
    """Boolean per-frame mask: True where the stem has meaningful energy.
    Threshold is relative to the stem's own peak RMS — catches the
    "non-guitar sections" where basic-pitch was still emitting notes
    from cross-bleed."""
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-10))
    return db > (db.max() + db_floor)


def chroma_cosine(y_ref: np.ndarray, y_hyp: np.ndarray,
                  active_only: bool = False) -> float:
    """Mean cosine similarity of chroma-CENS over time (truncate to shorter).
    If `active_only`, restrict comparison to frames where the reference
    has meaningful energy — this stops a hypothesis from scoring high by
    emitting notes during reference-silent sections."""
    c_ref = librosa.feature.chroma_cens(y=y_ref, sr=SR, hop_length=HOP)
    c_hyp = librosa.feature.chroma_cens(y=y_hyp, sr=SR, hop_length=HOP)
    n = min(c_ref.shape[1], c_hyp.shape[1])
    if n == 0:
        return 0.0
    c_ref, c_hyp = c_ref[:, :n], c_hyp[:, :n]
    dot = (c_ref * c_hyp).sum(axis=0)
    nr = np.linalg.norm(c_ref, axis=0)
    nh = np.linalg.norm(c_hyp, axis=0)
    mask = (nr > 1e-6) & (nh > 1e-6)
    if active_only:
        ref_active = _stem_active_mask(y_ref)[:n]
        mask = mask & ref_active
    if not mask.any():
        return 0.0
    return float(np.mean(dot[mask] / (nr[mask] * nh[mask])))


def fp_silence_rate(stem_audio: np.ndarray,
                    hyp_pm: pretty_midi.PrettyMIDI) -> float:
    """Fraction of hypothesis note-onsets that fall during frames where the
    reference stem is silent. High = many phantom notes (false positives)
    in regions where nothing is actually playing on this stem.

    0.0 = perfect silence discipline; 1.0 = every note is a phantom.
    """
    active = _stem_active_mask(stem_audio)
    starts = [n.start for inst in hyp_pm.instruments if not inst.is_drum
              for n in inst.notes]
    if not starts:
        return 0.0
    # frame index = t*SR/HOP
    fp = 0
    for t in starts:
        fi = int(t * SR / HOP)
        if 0 <= fi < len(active):
            # tolerance window: ±1 frame (~93 ms at HOP=2048)
            lo = max(0, fi - 1); hi = min(len(active), fi + 2)
            if not active[lo:hi].any():
                fp += 1
        else:
            fp += 1
    return fp / len(starts)


def onset_f1(y_ref: np.ndarray, y_hyp: np.ndarray) -> float:
    """[legacy] Audio-vs-audio onset comparison. Kept as diagnostic — biased
    against synths with slow attacks (e.g. Choir Aahs shifts onsets ~70ms
    later than the note-on), which unfairly penalizes transcriptions whose
    MIDI is correct but whose synth patch is not a perfect timbral match.
    Prefer onset_f1_midi() for scoring transcription quality."""
    ref_on = librosa.onset.onset_detect(y=y_ref, sr=SR, units="time", backtrack=True)
    hyp_on = librosa.onset.onset_detect(y=y_hyp, sr=SR, units="time", backtrack=True)
    if len(ref_on) == 0 and len(hyp_on) == 0:
        return 1.0
    if len(ref_on) == 0 or len(hyp_on) == 0:
        return 0.0
    f, _, _ = mir_eval.onset.f_measure(ref_on, hyp_on, window=ONSET_TOL)
    return float(f)


def onset_f1_midi(stem_audio: np.ndarray, hyp_pm: pretty_midi.PrettyMIDI) -> float:
    """Compare MIDI note-onsets directly (de-duplicated to unique times at
    ±10 ms) against audio onsets detected on the stem. This bypasses the
    synth roundtrip, so the score reflects the transcription, not the
    SoundFont's attack envelope."""
    ref_on = librosa.onset.onset_detect(y=stem_audio, sr=SR, units="time", backtrack=True)
    # Collapse near-simultaneous MIDI starts to a single onset event (chord
    # note-ons at the same tick should count as one onset).
    midi_on = sorted({round(n.start, 3)
                      for inst in hyp_pm.instruments if not inst.is_drum
                      for n in inst.notes})
    # de-dupe within 10 ms
    dedup = []
    for t in midi_on:
        if not dedup or t - dedup[-1] > 0.010:
            dedup.append(t)
    if len(ref_on) == 0 and len(dedup) == 0:
        return 1.0
    if len(ref_on) == 0 or len(dedup) == 0:
        return 0.0
    f, _, _ = mir_eval.onset.f_measure(
        np.asarray(ref_on), np.asarray(dedup), window=ONSET_TOL
    )
    return float(f)


def mel_l1(y_ref: np.ndarray, y_hyp: np.ndarray) -> float:
    """Log-mel L1 after per-bin z-scoring. 0 = identical, larger = more
    dissimilar. Unbounded above but typically < 5 for similar timbres.

    NOTE: callers should pass effect-matched audio for y_hyp so this metric
    scores note content, not production-effect mismatch. See
    effects.apply_production_effects."""
    def featurize(y):
        m = librosa.feature.melspectrogram(y=y, sr=SR, n_mels=64, hop_length=HOP)
        return np.log1p(m)
    m_ref = featurize(y_ref)
    m_hyp = featurize(y_hyp)
    n = min(m_ref.shape[1], m_hyp.shape[1])
    if n == 0:
        return 10.0
    m_ref, m_hyp = m_ref[:, :n], m_hyp[:, :n]
    # per-bin z-score using ref stats
    mu = m_ref.mean(axis=1, keepdims=True)
    sd = m_ref.std(axis=1, keepdims=True) + 1e-6
    m_ref_z = (m_ref - mu) / sd
    m_hyp_z = (m_hyp - mu) / sd
    return float(np.mean(np.abs(m_ref_z - m_hyp_z)))


def _pm_notes_to_intervals_pitches(notes):
    if not notes:
        return (np.zeros((0, 2)), np.zeros(0))
    intervals = np.array([[n.start, n.end] for n in notes])
    pitches = np.array([librosa.midi_to_hz(n.pitch) for n in notes])
    return intervals, pitches


def note_f1(stem_pm: pretty_midi.PrettyMIDI, hyp_pm: pretty_midi.PrettyMIDI) -> float:
    """Pitch+onset overlap F1 per mir_eval.transcription.
    `stem_pm` is the pseudo-ground-truth from basic-pitch on the stem audio.
    """
    ref_notes = [n for inst in stem_pm.instruments if not inst.is_drum for n in inst.notes]
    hyp_notes = [n for inst in hyp_pm.instruments if not inst.is_drum for n in inst.notes]
    ref_iv, ref_p = _pm_notes_to_intervals_pitches(ref_notes)
    hyp_iv, hyp_p = _pm_notes_to_intervals_pitches(hyp_notes)
    if len(ref_notes) == 0 and len(hyp_notes) == 0:
        return 1.0
    if len(ref_notes) == 0 or len(hyp_notes) == 0:
        return 0.0
    # onset-only matching (no offset tolerance) — our durations are heavily
    # quantized which unfairly penalizes offset-strict scoring.
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_iv, ref_p, hyp_iv, hyp_p,
        onset_tolerance=NOTE_ONSET_TOL,
        pitch_tolerance=NOTE_PITCH_TOL * 100,   # mir_eval expects cents
        offset_ratio=None,
    )
    return float(f)


# ------------------------------------------------------------------ #

def musicxml_to_pm(xml_path: Path) -> pretty_midi.PrettyMIDI:
    """Convert a music21-parsed score to a single pretty_midi with one
    instrument per Part, using the part name as instrument.name."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        score = music21.converter.parse(str(xml_path))

    # Use music21's built-in MIDI writer, then reload via pretty_midi.
    # This preserves tempo, durations, and part names.
    tmp_mid = xml_path.with_suffix(".eval.mid")
    score.write("midi", fp=str(tmp_mid))
    pm = pretty_midi.PrettyMIDI(str(tmp_mid))
    # music21 assigns part names as Instrument.name — verify
    part_names = [p.partName for p in score.parts]
    for i, inst in enumerate(pm.instruments):
        if i < len(part_names):
            inst.name = part_names[i] or inst.name
    tmp_mid.unlink(missing_ok=True)
    return pm


# ------------------------------------------------------------------ #

def stem_note_ground_truth(stem_audio_path: Path, cache_dir: Path) -> pretty_midi.PrettyMIDI:
    """Run basic-pitch on the stem to get pseudo-ground-truth notes; cache by
    stem path so repeated eval runs are fast."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{stem_audio_path.stem}_gt.mid"
    if cache_file.exists():
        return pretty_midi.PrettyMIDI(str(cache_file))
    from basic_pitch.inference import predict
    from basic_pitch import build_icassp_2022_model_path, FilenameSuffix
    model_path = build_icassp_2022_model_path(FilenameSuffix.onnx)
    _mo, midi_data, _notes = predict(
        str(stem_audio_path),
        model_or_model_path=model_path,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=80,
    )
    midi_data.write(str(cache_file))
    return midi_data


# ------------------------------------------------------------------ #

def evaluate(xml_path: Path, run_dir: Path, sf2: Path = DEFAULT_SF2,
             vocals_wav: Path | None = None):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    gt_cache = Path(".cache/stem_gt")

    # 0. Validate the musicxml structurally.
    ok, issues = validate_musicxml(xml_path)
    if not ok:
        print("WARN: musicxml validity issues:")
        for i in issues[:5]:
            print(" -", i)

    # 1. Convert score → pretty_midi, render per-track WAVs.
    print("[eval] musicxml → MIDI → per-track WAVs...")
    pm = musicxml_to_pm(xml_path)
    track_wavs = render_per_track(pm, audio_dir, sf2=sf2)

    # Optional: replace the Vocals-track WAV with an externally-rendered one
    # (e.g., RVC voice-converted output).
    if vocals_wav is not None and vocals_wav.exists():
        import shutil
        # Find the track whose name routes to the vocals stem
        for track_name in list(track_wavs.keys()):
            if TRACK_TO_STEM.get(track_name) == "vocals":
                dst = track_wavs[track_name]
                shutil.copy(str(vocals_wav), str(dst))
                print(f"[eval] replaced {track_name} render with {vocals_wav}")
                break

    # 2. Group tracks by stem (RH + LH both map to piano stem).
    by_stem: dict[str, list[str]] = {}
    for track_name in track_wavs:
        if track_name == "_mix":
            continue
        stem = TRACK_TO_STEM.get(track_name, None)
        if stem is None:
            continue
        by_stem.setdefault(stem, []).append(track_name)

    # 3. For each stem, compute metrics.
    stems = stem_paths(os.environ.get("STEMS_DIR", "stems"))
    results: dict[str, dict[str, float]] = {}

    for stem_name, tracks in by_stem.items():
        if stem_name not in stems:
            continue
        stem_audio = load_audio(stems[stem_name])
        # Mix the track WAVs for this stem (piano RH+LH go together).
        track_audio = []
        for t in tracks:
            y, _ = librosa.load(str(track_wavs[t]), sr=SR, mono=True)
            track_audio.append(y)
        # pad to same length
        L = max(len(a) for a in track_audio)
        mixed = sum(np.pad(a, (0, L - len(a))) for a in track_audio)
        if np.max(np.abs(mixed)) > 0:
            mixed = mixed / np.max(np.abs(mixed)) * 0.7

        # Effect-match the synth to the reference before spectral comparison.
        # Chroma-CENS and onset detection are effect-invariant so we run them
        # on raw synth; mel_L1 would penalize dry-synth-vs-wet-stem mismatch,
        # so we run it on the effect-matched signal instead.
        print(f"[eval] scoring stem: {stem_name}  (matching effects)")
        matched = apply_production_effects(mixed, stem_audio, SR)

        ch     = chroma_cosine(stem_audio, mixed)
        ch_act = chroma_cosine(stem_audio, mixed, active_only=True)
        ml     = mel_l1(stem_audio, matched)
        ml_raw = mel_l1(stem_audio, mixed)        # kept for diagnostics
        on_syn = onset_f1(stem_audio, mixed)      # legacy synth-based
        # Build a hyp PrettyMIDI from just the tracks that route to this stem
        _hyp_for_onset = pretty_midi.PrettyMIDI(initial_tempo=95.7)
        for inst in pm.instruments:
            if inst.name in tracks:
                _new = pretty_midi.Instrument(program=inst.program, name=inst.name)
                _new.notes = list(inst.notes)
                _hyp_for_onset.instruments.append(_new)
        on     = onset_f1_midi(stem_audio, _hyp_for_onset)
        fp_sil = fp_silence_rate(stem_audio, _hyp_for_onset)

        # Note F1 — basic-pitch on the stem to get pseudo-ground-truth
        try:
            gt_pm = stem_note_ground_truth(stems[stem_name], gt_cache)
            hyp_pm = pretty_midi.PrettyMIDI(initial_tempo=95.7)
            for inst in pm.instruments:
                if inst.name in tracks:
                    new = pretty_midi.Instrument(program=inst.program, name=inst.name)
                    new.notes = list(inst.notes)
                    hyp_pm.instruments.append(new)
            nf = note_f1(gt_pm, hyp_pm)
        except Exception as e:
            print(f"  note_f1 failed: {e}")
            nf = float("nan")

        results[stem_name] = {
            "chroma_cosine":  ch,
            "chroma_active":  ch_act,      # chroma computed only on stem-active frames
            "onset_f1":       on,          # MIDI-onset-vs-stem-audio-onset
            "onset_f1_synth": on_syn,      # diagnostic: synth-WAV-vs-stem-WAV
            "note_f1":        nf,
            "mel_l1":         ml,          # effect-matched
            "mel_l1_raw":     ml_raw,      # diagnostic: pre-effect-match
            "fp_silence":     fp_sil,      # note-starts in stem-silent regions
        }

    # 4. Mix-level comparison against original mp3 (with effect matching).
    mix = mix_path()
    if mix is not None and "_mix" in track_wavs:
        print("[eval] scoring mix... (matching effects)")
        y_mix = load_audio(mix)
        y_syn, _ = librosa.load(str(track_wavs["_mix"]), sr=SR, mono=True)
        y_syn_matched = apply_production_effects(y_syn, y_mix, SR)
        results["_mix"] = {
            "chroma_cosine":  chroma_cosine(y_mix, y_syn),
            "chroma_active":  chroma_cosine(y_mix, y_syn, active_only=True),
            "onset_f1":       onset_f1_midi(y_mix, pm),
            "onset_f1_synth": onset_f1(y_mix, y_syn),
            "note_f1":        float("nan"),
            "mel_l1":         mel_l1(y_mix, y_syn_matched),
            "mel_l1_raw":     mel_l1(y_mix, y_syn),
            "fp_silence":     fp_silence_rate(y_mix, pm),
        }

    # 5. Composite per stem. v2 weighting reflects lessons from retroactive
    # eval of draft1 (git 8dbcc0b): chroma_active beats plain chroma because
    # phantom notes during silent stem sections shouldn't count; fp_silence
    # directly penalizes cross-bleed phantoms; note_f1 downweighted because
    # it's pathological (basic-pitch pseudo-GT favors basic-pitch pipelines).
    #
    #   composite = 0.35·chroma_active
    #             + 0.25·onset_F1
    #             + 0.10·note_F1
    #             + 0.15·(1 − fp_silence)       ← NEW: silence discipline
    #             + 0.10·(1 − mel_L1/3)
    #             + 0.05·chroma                 ← raw chroma kept for cont.
    def composite(m):
        ml_norm = min(m["mel_l1"] / 3.0, 1.0)
        parts = []
        if "chroma_active" in m and not np.isnan(m["chroma_active"]):
            parts.append(0.35 * m["chroma_active"])
        if not np.isnan(m["chroma_cosine"]):
            parts.append(0.05 * m["chroma_cosine"])
        if not np.isnan(m["onset_f1"]):      parts.append(0.25 * m["onset_f1"])
        if not np.isnan(m["note_f1"]):       parts.append(0.10 * m["note_f1"])
        if "fp_silence" in m and not np.isnan(m["fp_silence"]):
            parts.append(0.15 * (1 - m["fp_silence"]))
        parts.append(0.10 * (1 - ml_norm))
        return sum(parts)
    for k, m in results.items():
        m["composite"] = composite(m)

    # 6. Overall score — mean of per-stem composites (excluding _mix).
    stem_comps = [m["composite"] for k, m in results.items() if k != "_mix"]
    overall = float(np.mean(stem_comps)) if stem_comps else 0.0

    payload = {
        "xml_path":     str(xml_path),
        "soundfont":    str(sf2),
        "overall":      overall,
        "per_stem":     results,
        "xml_valid":    ok,
        "xml_issues":   issues[:10],
    }
    (run_dir / "metrics.json").write_text(json.dumps(payload, indent=2))

    # Human-readable
    lines = [f"# Metrics — {xml_path.name}", "",
             f"**Overall composite:** {overall:.3f}",
             f"**XML valid:** {ok}",
             "",
             "`mel_L1` is computed *after* matching production effects "
             "(EQ + plate reverb + loudness) onto the synth so it scores note "
             "content, not dry-synth-vs-wet-stem mismatch. `mel_L1_raw` is "
             "the pre-match diagnostic.",
             ""]
    lines.append("| stem | chroma | chroma_active | onset_F1 | note_F1 | mel_L1 | fp_silence | composite |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for k, m in results.items():
        lines.append(
            f"| {k} | {m['chroma_cosine']:.3f} | "
            f"{m.get('chroma_active', float('nan')):.3f} | "
            f"{m['onset_f1']:.3f} | {m['note_f1']:.3f} | "
            f"{m['mel_l1']:.3f} | "
            f"{m.get('fp_silence', float('nan')):.3f} | "
            f"**{m['composite']:.3f}** |"
        )
    (run_dir / "metrics.md").write_text("\n".join(lines))
    print(f"[eval] wrote {run_dir/'metrics.json'}  overall={overall:.3f}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("xml", type=Path)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--sf2", type=Path, default=DEFAULT_SF2)
    ap.add_argument("--vocals-wav", type=Path, default=None,
                    help="Override the vocal render with this WAV (e.g. RVC output)")
    args = ap.parse_args()
    evaluate(args.xml, args.run_dir, args.sf2, vocals_wav=args.vocals_wav)

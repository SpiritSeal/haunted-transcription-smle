"""Assembly v4 — build music21 score *directly* from integer 16th-note indices.

v3 wrote pretty_midi files (with float-second timestamps), then re-parsed them
through music21, which introduced quantization drift and produced measures with
wrong total durations (confirmed: 62 overfull measures in v3). v4 skips MIDI
entirely for the score and builds Measure objects from integer grid positions
so every measure sums to exactly 4 quarter notes by construction.

A separate pretty_midi file is still emitted for playback.
"""
from __future__ import annotations

from pathlib import Path
from fractions import Fraction
import json
import numpy as np
import pretty_midi
import music21
from music21 import (stream, note, chord as m21chord, meter, key,
                     tempo as m21tempo, metadata, instrument, clef, harmony,
                     duration as m21dur, pitch as m21pitch)

MIDI_DIR = Path("midi")

# ---- grid ---------------------------------------------------------------
grid = np.load("grid.npz", allow_pickle=True)
ANCHOR     = float(grid["first_downbeat"])
MEDIAN_INT = float(grid["median_interval"])
BPM        = 60.0 / MEDIAN_INT
SIXTEENTH  = MEDIAN_INT / 4
KEY_NAME, KEY_MODE = "B", "minor"
PRE_MEASURES = int(np.floor(ANCHOR / (MEDIAN_INT * 4)))
GRID_ORIGIN  = ANCHOR - PRE_MEASURES * 4 * MEDIAN_INT

def snap16(t): return int(round((t - GRID_ORIGIN) / SIXTEENTH))
def idx_to_sec(i): return GRID_ORIGIN + i * SIXTEENTH

THIRTY_SECOND = SIXTEENTH / 2
def snap32(t): return int(round((t - GRID_ORIGIN) / THIRTY_SECOND))
def idx32_to_sec(i): return GRID_ORIGIN + i * THIRTY_SECOND

# Canonical quarter-length for one sixteenth.
QL16 = Fraction(1, 4)

# ---- chord labels -------------------------------------------------------
chord_data = json.loads(Path("chords.json").read_text())
ch_origin  = float(chord_data["origin_sec"])
ch_beat    = float(chord_data["beat_interval_sec"])
per_beat   = chord_data["per_beat_labels"]

CHORD_PCS = {
    'Bm':  {11, 2, 6},  'A':  {9, 1, 4},  'G':  {7, 11, 2},
    'D':   {2, 6, 9},   'Em': {4, 7, 11}, 'F#m':{6, 9, 1},  'N': set(),
}
DIATONIC_BM = {11, 1, 2, 4, 6, 7, 9}

def chord_at_sec(t):
    b = int((t - ch_origin) / ch_beat)
    b = max(0, min(b, len(per_beat) - 1))
    return per_beat[b]

def is_chord_tone(p, label): return (p % 12) in CHORD_PCS.get(label, set())
def is_diatonic(p): return (p % 12) in DIATONIC_BM

# ---- note cleanup primitives -------------------------------------------

def quantize(notes, min_len_16=1, velocity_floor=25, pitch_lo=0, pitch_hi=127,
             *, grid=16):
    """Snap notes to the N-th-note grid (default 16th). Use grid=32 for
    32nd-note resolution — finer, better for rubato-heavy vocals."""
    snap = snap16 if grid == 16 else snap32
    out = []
    for n in notes:
        if n.velocity < velocity_floor: continue
        if n.pitch < pitch_lo or n.pitch > pitch_hi: continue
        s = snap(n.start); e = snap(n.end)
        if e - s < min_len_16: e = s + min_len_16
        if s < 0: continue
        out.append([s, e, int(n.pitch), int(n.velocity)])
    return out

def merge_same_pitch(notes, gap_tol_16=1):
    by_pitch = {}
    for s, e, p, v in sorted(notes, key=lambda x: (x[2], x[0])):
        lst = by_pitch.setdefault(p, [])
        if lst and s - lst[-1][1] <= gap_tol_16:
            lst[-1][1] = max(lst[-1][1], e)
            lst[-1][3] = max(lst[-1][3], v)
        else:
            lst.append([s, e, p, v])
    return sorted([x for xs in by_pitch.values() for x in xs],
                  key=lambda x: (x[0], x[2]))

def drop_shorts(notes, min_len_16):
    return [n for n in notes if (n[1] - n[0]) >= min_len_16]

def chord_filter(notes, keep_velocity=70, min_len_16=1):
    out = []
    for s, e, p, v in notes:
        ch = chord_at_sec(idx_to_sec(s))
        if is_chord_tone(p, ch):
            out.append([s, e, p, v])
        elif is_diatonic(p) and (e - s) >= max(2, min_len_16):
            out.append([s, e, p, v])
        elif v >= keep_velocity:
            out.append([s, e, p, v])
    return out

def cap_polyphony_by_onset(notes, max_voices):
    by_onset = {}
    for n in notes:
        by_onset.setdefault(n[0], []).append(n)
    out = []
    for s, bucket in by_onset.items():
        bucket.sort(key=lambda x: (-x[3], x[2]))
        out.extend(bucket[:max_voices])
    return sorted(out, key=lambda x: (x[0], x[2]))

def load_stem_midi(name, premerge_gap_ms: float | None = None):
    """Load all pitched notes from stems's basic-pitch MIDI. If
    premerge_gap_ms is set, apply a pre-quantization same-pitch merge so
    sustained-note fragments become single notes before we snap to 16ths."""
    pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / f"{name}.mid"))
    notes = [n for inst in pm.instruments if not inst.is_drum for n in inst.notes]
    if premerge_gap_ms is not None:
        from midi_utils import merge_tied_notes
        notes = merge_tied_notes(notes, gap_ms=premerge_gap_ms)
    return notes

# ---- per-instrument pipelines ------------------------------------------

# Build per-stem onset tables once — used to nudge note starts onto audio
# onsets before 16th quantization. Keeps pitch detection's notes but aligns
# attacks with the real audio transients.
import librosa as _lb

def _load_stem_onsets(stem_name: str) -> np.ndarray:
    path = next(Path("stems").glob(f"*{stem_name}*.mp3"))
    y, _ = _lb.load(str(path), sr=22050, mono=True)
    return np.asarray(_lb.onset.onset_detect(y=y, sr=22050, units="time",
                                             backtrack=True))

_ONSETS = {name: _load_stem_onsets(name) for name in ("vocals", "piano", "guitar")}

def _snap_notes_to_onsets(notes, stem_name, tol=0.08):
    arr = _ONSETS.get(stem_name)
    if arr is None or len(arr) == 0:
        return notes
    def snap(t):
        i = int(np.searchsorted(arr, t))
        cands = []
        if i > 0:           cands.append(arr[i-1])
        if i < len(arr):    cands.append(arr[i])
        if not cands: return t
        nearest = min(cands, key=lambda x: abs(x - t))
        return float(nearest) if abs(nearest - t) <= tol else t
    out = []
    for n in notes:
        new_start = snap(n.start)
        # preserve duration: shift end by the same amount
        shift = new_start - n.start
        out.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch,
                                    start=new_start, end=n.end + shift))
    return out

voc_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "vocals_with_harmony.mid"))
_vox_raw = list(voc_pm.instruments[0].notes)
_vox_snapped = _snap_notes_to_onsets(_vox_raw, "vocals")
print(f"vocals: {sum(1 for a,b in zip(_vox_raw, _vox_snapped) if abs(a.start-b.start) > 1e-4)}/{len(_vox_raw)} starts snapped")

vox = quantize(_vox_snapped, min_len_16=1, velocity_floor=0,
               pitch_lo=48, pitch_hi=88)
vox = merge_same_pitch(vox, gap_tol_16=2)
vox = drop_shorts(vox, min_len_16=2)

# Bass — prefer CREPE monophonic track when available (clean f0 contour),
# fall back to basic-pitch. CREPE notes are already monophonic and high-
# confidence, so skip chord_filter.
_bass_crepe = MIDI_DIR / "bass_crepe.mid"
if _bass_crepe.exists():
    _pm = pretty_midi.PrettyMIDI(str(_bass_crepe))
    bass_raw = list(_pm.instruments[0].notes)
    print("bass: using CREPE contour")
else:
    bass_raw = load_stem_midi("bass")
bass = quantize(bass_raw, min_len_16=2, velocity_floor=0 if _bass_crepe.exists() else 30,
                pitch_lo=28, pitch_hi=55)
bass = merge_same_pitch(bass, gap_tol_16=2)
if not _bass_crepe.exists():
    bass = chord_filter(bass, keep_velocity=80, min_len_16=2)
bass = drop_shorts(bass, min_len_16=2)

piano_raw = load_stem_midi("piano", premerge_gap_ms=80)
piano_raw = _snap_notes_to_onsets(piano_raw, "piano")
piano = quantize(piano_raw, min_len_16=1, velocity_floor=30, pitch_lo=33, pitch_hi=96)
piano = merge_same_pitch(piano, gap_tol_16=1)
piano = chord_filter(piano, keep_velocity=75, min_len_16=1)
piano = cap_polyphony_by_onset(piano, max_voices=4)
piano = drop_shorts(piano, min_len_16=1)

guit_raw = load_stem_midi("guitar", premerge_gap_ms=80)
guit_raw = _snap_notes_to_onsets(guit_raw, "guitar")
guit = quantize(guit_raw, min_len_16=1, velocity_floor=35, pitch_lo=40, pitch_hi=84)
guit = merge_same_pitch(guit, gap_tol_16=1)
guit = chord_filter(guit, keep_velocity=85, min_len_16=1)
guit = cap_polyphony_by_onset(guit, max_voices=3)
guit = drop_shorts(guit, min_len_16=1)

piano_rh = [n for n in piano if n[2] >= 60]
piano_lh = [n for n in piano if n[2] <  60]

for label, lst in [("vocals", vox), ("bass", bass),
                   ("piano_rh", piano_rh), ("piano_lh", piano_lh),
                   ("guitar", guit)]:
    print(f"{label}: {len(lst)} notes")

# ---- score length in measures ------------------------------------------
all_lists = [vox, bass, piano_rh, piano_lh, guit]
last_16 = max((n[1] for lst in all_lists for n in lst), default=16)
N_MEASURES = max(8, (last_16 + 15) // 16)
print(f"total measures: {N_MEASURES}")

# ---- direct music21 score construction ---------------------------------

def notes_to_part(notes, part_name, m21inst, cl, n_measures, slots_per_bar=16):
    """Convert a list of (start_idx, end_idx, pitch, vel) tuples — at
    `slots_per_bar` granularity — into a music21 Part of n_measures × 4/4.

    Default 16ths. Use slots_per_bar=32 for 32nd-note resolution (better
    vocal rubato, costs more horizontal space)."""
    total_slots = n_measures * slots_per_bar
    slots_per_q = slots_per_bar // 4     # 4 (16ths) or 8 (32nds)
    sounding = [set() for _ in range(total_slots)]
    onsets = [set() for _ in range(total_slots)]
    for (s, e, p, v) in notes:
        if s >= total_slots: continue
        e = min(e, total_slots)
        if e <= s: continue
        onsets[s].add(p)
        for i in range(s, e):
            sounding[i].add(p)

    part = stream.Part()
    part.id = part_name
    part.partName = part_name
    part.partAbbreviation = part_name[:4]
    part.insert(0, m21inst)

    for m_idx in range(n_measures):
        measure = stream.Measure(number=m_idx + 1)
        if m_idx == 0:
            measure.insert(0, cl)
            measure.insert(0, key.Key(KEY_NAME, KEY_MODE))
            measure.insert(0, meter.TimeSignature("4/4"))
            measure.insert(0, m21tempo.MetronomeMark(number=round(BPM)))

        slot0 = m_idx * slots_per_bar
        i = 0
        while i < slots_per_bar:
            cur_set = frozenset(sounding[slot0 + i])
            j = i + 1
            while j < slots_per_bar:
                next_set = frozenset(sounding[slot0 + j])
                has_new_onset = bool(onsets[slot0 + j])
                if next_set != cur_set or has_new_onset:
                    break
                j += 1
            run_len = j - i
            ql = Fraction(run_len, slots_per_q)   # quarterLength
            pos_ql = Fraction(i, slots_per_q)
            if cur_set:
                if len(cur_set) == 1:
                    pitch = next(iter(cur_set))
                    n = note.Note()
                    n.pitch = m21pitch.Pitch(midi=pitch)
                    n.duration = m21dur.Duration(quarterLength=ql)
                else:
                    ch = m21chord.Chord()
                    for p in sorted(cur_set):
                        ch.add(m21pitch.Pitch(midi=p))
                    ch.duration = m21dur.Duration(quarterLength=ql)
                    n = ch
                measure.insert(pos_ql, n)
            else:
                r = note.Rest(quarterLength=ql)
                measure.insert(pos_ql, r)
            i = j
        part.append(measure)
    return part

INST = {
    "Vocals":    (instrument.Vocalist(),       clef.TrebleClef()),
    "Piano RH":  (instrument.Piano(),          clef.TrebleClef()),
    "Piano LH":  (instrument.Piano(),          clef.BassClef()),
    "Guitar":    (instrument.AcousticGuitar(), clef.Treble8vbClef()),
    "Bass":      (instrument.ElectricBass(),   clef.Bass8vbClef()),
}

score = stream.Score()
score.metadata = metadata.Metadata()
score.metadata.title = "Haunted"
score.metadata.composer = "smle (ft. Seann Bowe)"
score.metadata.movementName = "Auto-transcribed"

parts_data = [
    ("Vocals",   vox),
    ("Piano RH", piano_rh),
    ("Piano LH", piano_lh),
    ("Guitar",   guit),
    ("Bass",     bass),
]
for name, notes in parts_data:
    inst_obj, cl = INST[name]
    part = notes_to_part(notes, name, inst_obj, cl, N_MEASURES)
    score.append(part)

# ---- chord symbols on Vocals part --------------------------------------
vox_part = score.parts[0]
measures = list(vox_part.getElementsByClass(stream.Measure))
runs = chord_data["runs"]
prev_label = None
inserted = 0
for r in runs:
    label = r["chord"]
    if label == "N" or label == prev_label:
        prev_label = label
        continue
    start_sec = ch_origin + r["start_beat"] * ch_beat
    offset_ql = (start_sec - GRID_ORIGIN) / MEDIAN_INT
    m_idx    = int(offset_ql // 4)
    beat_in_m = offset_ql % 4
    if 0 <= m_idx < len(measures):
        sym = {'Bm':'Bm','A':'A','G':'G','D':'D','Em':'Em','F#m':'F#m'}.get(label, label)
        try:
            cs = harmony.ChordSymbol(sym)
            # Snap to nearest quarter beat
            measures[m_idx].insert(Fraction(round(beat_in_m * 4), 4), cs)
            inserted += 1
        except Exception as e:
            pass
    prev_label = label
print(f"{inserted} chord symbols inserted")

# Write MusicXML
xml_path = Path("Haunted.musicxml")
score.write("musicxml", fp=str(xml_path))
print(f"wrote {xml_path}")

# Also write a playback MIDI from our clean grid data (not via score.write)
def to_pm_notes(lst, program, name, grid=16):
    """grid=16 → indices are in 16ths; grid=32 → in 32nds (used for vocals)."""
    idx = idx_to_sec if grid == 16 else idx32_to_sec
    inst = pretty_midi.Instrument(program=program, name=name)
    for (s, e, p, v) in lst:
        inst.notes.append(pretty_midi.Note(velocity=int(v), pitch=int(p),
                                           start=idx(s), end=idx(e)))
    return inst

pm_out = pretty_midi.PrettyMIDI(initial_tempo=BPM)
pm_out.instruments.append(to_pm_notes(vox,      52, "Vocals"))
pm_out.instruments.append(to_pm_notes(piano_rh, 0,  "Piano RH"))
pm_out.instruments.append(to_pm_notes(piano_lh, 0,  "Piano LH"))
pm_out.instruments.append(to_pm_notes(guit,     25, "Guitar"))
pm_out.instruments.append(to_pm_notes(bass,     33, "Bass"))
pm_out.write(str(MIDI_DIR / "combined.mid"))

drums_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "drums.mid"))
full = pretty_midi.PrettyMIDI(initial_tempo=BPM)
for inst in pm_out.instruments:
    full.instruments.append(inst)
for inst in drums_pm.instruments:
    inst.notes = [pretty_midi.Note(velocity=n.velocity, pitch=n.pitch,
                                   start=idx_to_sec(snap16(n.start)),
                                   end=idx_to_sec(snap16(n.start)) + SIXTEENTH)
                  for n in inst.notes if snap16(n.start) >= 0]
    full.instruments.append(inst)
full.write(str(MIDI_DIR / "Haunted_full.mid"))
print("wrote playback MIDIs")

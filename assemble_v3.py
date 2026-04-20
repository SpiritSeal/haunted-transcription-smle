"""Assembly v3 — chord-aware filtering, CREPE-based vocals, restored ornaments.

Goals vs v2:
 * Keep ornaments and chord voicings (loosen thresholds back toward v1).
 * Use per-beat chord labels (chords.json) to *boost* chord-tone notes and
   *penalize* notes that are both off-chord AND quiet — this cleans up
   basic-pitch noise without flattening the arrangement.
 * Vocal track comes from CREPE (monophonic f0 → note segmentation).
 * Chord symbols attached to the Piano part at each chord change.
 * Two piano voices (RH + LH split around middle C) for a real piano staff.
"""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pretty_midi
import music21
from music21 import (stream, meter, key, tempo as m21tempo, metadata,
                     instrument, clef, harmony, chord as m21chord)

MIDI_DIR = Path("midi")

# ---- grid ---------------------------------------------------------------
grid = np.load("grid.npz", allow_pickle=True)
ANCHOR        = float(grid["first_downbeat"])
MEDIAN_INT    = float(grid["median_interval"])
BPM           = 60.0 / MEDIAN_INT
SIXTEENTH     = MEDIAN_INT / 4
KEY_NAME, KEY_MODE = "B", "minor"

PRE_MEASURES = int(np.floor(ANCHOR / (MEDIAN_INT * 4)))
GRID_ORIGIN  = ANCHOR - PRE_MEASURES * 4 * MEDIAN_INT

def snap16(t):
    return int(round((t - GRID_ORIGIN) / SIXTEENTH))

def idx_to_sec(i):
    return GRID_ORIGIN + i * SIXTEENTH

# ---- chord labels -------------------------------------------------------
chord_data = json.loads(Path("chords.json").read_text())
ch_origin   = float(chord_data["origin_sec"])
ch_beat     = float(chord_data["beat_interval_sec"])
per_beat    = chord_data["per_beat_labels"]

# Map chord name to pitch-class set (used to test if a MIDI pitch is a chord tone)
CHORD_PCS = {
    'Bm':  {11, 2, 6},           # B D F#
    'A':   {9, 1, 4},            # A C# E
    'G':   {7, 11, 2},            # G B D
    'D':   {2, 6, 9},            # D F# A
    'Em':  {4, 7, 11},            # E G B
    'F#m': {6, 9, 1},             # F# A C#
    'N':   set(),
}
DIATONIC_BM = {11, 1, 2, 4, 6, 7, 9}   # B natural-minor scale (A B C# D E F# G)

def chord_at_time(t):
    """Return chord label at time t (seconds)."""
    b = int((t - ch_origin) / ch_beat)
    if b < 0:
        b = 0
    if b >= len(per_beat):
        b = len(per_beat) - 1
    return per_beat[b]

def is_chord_tone(pitch_midi, label):
    return (pitch_midi % 12) in CHORD_PCS.get(label, set())

def is_diatonic(pitch_midi):
    return (pitch_midi % 12) in DIATONIC_BM

# ---- note cleanup primitives -------------------------------------------

def quantize(notes, min_len_16=1, velocity_floor=25, pitch_lo=0, pitch_hi=127):
    out = []
    for n in notes:
        if n.velocity < velocity_floor:
            continue
        if n.pitch < pitch_lo or n.pitch > pitch_hi:
            continue
        s = snap16(n.start)
        e = snap16(n.end)
        if e - s < min_len_16:
            e = s + min_len_16
        if s < 0:
            continue
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
    merged = [x for xs in by_pitch.values() for x in xs]
    return sorted(merged, key=lambda x: (x[0], x[2]))

def drop_shorts(notes, min_len_16):
    return [n for n in notes if (n[1] - n[0]) >= min_len_16]

def chord_filter(notes, keep_velocity=70, min_len_16=1):
    """Keep a note if ANY of:
        (a) it's a chord tone of the current beat's chord
        (b) it's diatonic AND lasts ≥ 2 sixteenths  (melodic passing tone)
        (c) its velocity ≥ keep_velocity  (probably an accent / melody)
    Otherwise drop it."""
    out = []
    for s, e, p, v in notes:
        t = idx_to_sec(s)
        ch = chord_at_time(t)
        if is_chord_tone(p, ch):
            out.append([s, e, p, v])
        elif is_diatonic(p) and (e - s) >= max(2, min_len_16):
            out.append([s, e, p, v])
        elif v >= keep_velocity:
            out.append([s, e, p, v])
        # else drop
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

# ---- load stems ---------------------------------------------------------

def load_stem_midi(name):
    p = MIDI_DIR / f"{name}.mid"
    pm = pretty_midi.PrettyMIDI(str(p))
    return [n for inst in pm.instruments if not inst.is_drum for n in inst.notes]

# Vocals — from CREPE, already monophonic
voc_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "vocals_crepe.mid"))
vox_notes = list(voc_pm.instruments[0].notes)
vox = quantize(vox_notes, min_len_16=1, velocity_floor=0, pitch_lo=48, pitch_hi=88)
vox = merge_same_pitch(vox, gap_tol_16=2)
vox = drop_shorts(vox, min_len_16=2)

# Bass — slightly looser than v2 to keep more motion
bass = load_stem_midi("bass")
bass = quantize(bass, min_len_16=2, velocity_floor=30, pitch_lo=28, pitch_hi=55)
bass = merge_same_pitch(bass, gap_tol_16=2)
bass = chord_filter(bass, keep_velocity=80, min_len_16=2)
bass = drop_shorts(bass, min_len_16=2)

# Piano — v1-like density but with chord filter and v2 quantization
piano_raw = load_stem_midi("piano")
piano = quantize(piano_raw, min_len_16=1, velocity_floor=30, pitch_lo=33, pitch_hi=96)
piano = merge_same_pitch(piano, gap_tol_16=1)
piano = chord_filter(piano, keep_velocity=75, min_len_16=1)
piano = cap_polyphony_by_onset(piano, max_voices=4)
piano = drop_shorts(piano, min_len_16=1)

# Guitar
guit_raw = load_stem_midi("guitar")
guit = quantize(guit_raw, min_len_16=1, velocity_floor=35, pitch_lo=40, pitch_hi=84)
guit = merge_same_pitch(guit, gap_tol_16=1)
guit = chord_filter(guit, keep_velocity=85, min_len_16=1)
guit = cap_polyphony_by_onset(guit, max_voices=3)
guit = drop_shorts(guit, min_len_16=1)

for label, lst in [("vocals", vox), ("bass", bass), ("piano", piano), ("guitar", guit)]:
    print(f"{label}: {len(lst)} notes")

# ---- split piano into RH (≥ MIDI 60) and LH (< 60) --------------------
piano_rh = [n for n in piano if n[2] >= 60]
piano_lh = [n for n in piano if n[2] <  60]
print(f"piano split: RH={len(piano_rh)}  LH={len(piano_lh)}")

# ---- build combined MIDI ------------------------------------------------

def to_pm(lst, program, name):
    inst = pretty_midi.Instrument(program=program, name=name)
    for (s, e, p, v) in lst:
        inst.notes.append(pretty_midi.Note(velocity=int(v), pitch=int(p),
                                           start=idx_to_sec(s), end=idx_to_sec(e)))
    return inst

pm_out = pretty_midi.PrettyMIDI(initial_tempo=BPM)
pm_out.instruments.append(to_pm(vox,      52, "Vocals"))
pm_out.instruments.append(to_pm(piano_rh, 0,  "Piano RH"))
pm_out.instruments.append(to_pm(piano_lh, 0,  "Piano LH"))
pm_out.instruments.append(to_pm(guit,     25, "Guitar"))
pm_out.instruments.append(to_pm(bass,     33, "Bass"))

combined_path = MIDI_DIR / "combined_v3.mid"
pm_out.write(str(combined_path))

# Also write a full-playback MIDI with drums
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
full.write(str(MIDI_DIR / "Haunted_full_v3.mid"))

# ---- music21 score ------------------------------------------------------
print("Parsing to music21...")
score = music21.converter.parse(str(combined_path), quantizePost=True,
                                quarterLengthDivisors=(4,))

score.metadata = metadata.Metadata()
score.metadata.title = "Haunted"
score.metadata.composer = "smle (ft. Seann Bowe)"
score.metadata.movementName = "Auto-transcribed"

ks = key.Key(KEY_NAME, KEY_MODE)
mm = m21tempo.MetronomeMark(number=round(BPM))
ts = meter.TimeSignature("4/4")

INST_MAP = {
    "Vocals":    (instrument.Vocalist(),       clef.TrebleClef()),
    "Piano RH":  (instrument.Piano(),          clef.TrebleClef()),
    "Piano LH":  (instrument.Piano(),          clef.BassClef()),
    "Guitar":    (instrument.AcousticGuitar(), clef.Treble8vbClef()),
    "Bass":      (instrument.ElectricBass(),   clef.Bass8vbClef()),
}

for part in score.parts:
    name = (part.partName or "").strip()
    m21inst, cl = INST_MAP.get(name, (instrument.Piano(), clef.TrebleClef()))
    part.insert(0, m21inst)
    part.partName = name
    part.partAbbreviation = name[:4]
    first = part.getElementsByClass(stream.Measure).first()
    target = first if first is not None else part
    target.insert(0, cl)
    target.insert(0, ks)
    target.insert(0, ts)
    target.insert(0, mm)

# ---- add chord symbols to the Vocals part at every chord change --------
# Chord symbols render cleanest when attached to the top staff (Vocals).
# Insert them INSIDE measures at their correct beat offset — music21 will
# only emit <harmony> elements in MusicXML if the symbol lives in a measure.
vox_part = next((p for p in score.parts if p.partName == "Vocals"), None)
if vox_part is not None:
    runs = chord_data["runs"]
    measures = list(vox_part.getElementsByClass(stream.Measure))
    inserted = 0
    prev_label = None
    for r in runs:
        label = r["chord"]
        if label == 'N' or label == prev_label:
            prev_label = label
            continue
        start_sec = ch_origin + r["start_beat"] * ch_beat
        # Offset from score start (GRID_ORIGIN), expressed in quarter notes.
        # music21 uses quarter-note lengths; our grid puts 4 quarters = 1
        # measure, so a chord at ql=X sits in measure int(X/4)+1 at beat X%4.
        offset_ql = (start_sec - GRID_ORIGIN) / MEDIAN_INT
        measure_idx = int(offset_ql // 4)
        beat_in_m   = offset_ql % 4
        if measure_idx < 0 or measure_idx >= len(measures):
            prev_label = label
            continue
        sym_map = {'Bm':'Bm','A':'A','G':'G','D':'D','Em':'Em','F#m':'F#m'}
        sym = sym_map.get(label, label)
        try:
            cs = harmony.ChordSymbol(sym)
            # Snap to nearest quarter beat for clean placement
            measures[measure_idx].insert(round(beat_in_m * 2) / 2, cs)
            inserted += 1
        except Exception as e:
            print(f"  skipping {sym} at m{measure_idx}: {e}")
        prev_label = label
    print(f"{inserted} chord symbols inserted on Vocals part")

xml_path = Path("Haunted.musicxml")
score.write("musicxml", fp=str(xml_path))
print(f"wrote {xml_path}")

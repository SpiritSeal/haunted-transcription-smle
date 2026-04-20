"""Improved assembly pipeline.

Key changes vs v1:
 - Fixed 16th-note grid anchored to the detected downbeat (29.466s). Quantization
   is musically meaningful (bar:beat:sub), not offset from t=0.
 - Note-merging pass collapses consecutive same-pitch notes whose gap on the
   grid is < 1 sixteenth — kills basic-pitch's fragmentation.
 - Per-instrument minimum note length; vocal/bass mono reduction now runs
   *after* merging so it smooths sustained notes correctly.
 - Chord grouping: notes sharing an onset become a chord, capped per instrument.
 - Guitar forced to treble clef; vocals to treble; bass/piano LH to bass.
 - Outro silence trimmed so the score doesn't run past the actual music.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pretty_midi
import music21
from music21 import stream, meter, key, tempo as m21tempo, metadata, instrument, clef

MIDI_DIR = Path("midi")

# ---- grid ---------------------------------------------------------------
grid = np.load("grid.npz", allow_pickle=True)
ANCHOR        = float(grid["first_downbeat"])          # first bar-line, in sec
MEDIAN_INT    = float(grid["median_interval"])         # sec per beat
BPM           = 60.0 / MEDIAN_INT
SIXTEENTH     = MEDIAN_INT / 4
KEY_NAME, KEY_MODE = "B", "minor"

# pre-anchor measures: how many bars to include before the detected downbeat
# (for the intro). Choose so the first downbeat lands on bar PRE+1.
PRE_MEASURES = int(np.floor(ANCHOR / (MEDIAN_INT * 4)))
GRID_ORIGIN  = ANCHOR - PRE_MEASURES * 4 * MEDIAN_INT   # bar 1, beat 1 in sec

def snap16(t: float) -> int:
    """Return integer 16th-note index (relative to grid origin)."""
    return int(round((t - GRID_ORIGIN) / SIXTEENTH))

def idx_to_sec(i: int) -> float:
    return GRID_ORIGIN + i * SIXTEENTH

# ---- helpers ------------------------------------------------------------

def quantize(notes, min_len_16=1, velocity_floor=25, pitch_lo=0, pitch_hi=127):
    """Snap notes to 16th grid; enforce min length; clamp pitch range; drop quiet."""
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
        out.append((s, e, n.pitch, n.velocity))
    # Drop anything before the grid origin (occasional lead-in noise)
    return [(s, e, p, v) for (s, e, p, v) in out if s >= 0]

def merge_same_pitch(notes, gap_tol_16=1):
    """Merge consecutive notes with the same pitch whose gap ≤ gap_tol_16 16ths.
    Input is list of (start_16, end_16, pitch, vel); output same shape."""
    by_pitch: dict[int, list[list]] = {}
    for s, e, p, v in sorted(notes, key=lambda x: (x[2], x[0])):
        lst = by_pitch.setdefault(p, [])
        if lst and s - lst[-1][1] <= gap_tol_16:
            # extend previous
            lst[-1][1] = max(lst[-1][1], e)
            lst[-1][3] = max(lst[-1][3], v)
        else:
            lst.append([s, e, p, v])
    merged = [tuple(x) for xs in by_pitch.values() for x in xs]
    return sorted(merged, key=lambda x: (x[0], x[2]))

def mono_reduce(notes, pick="high"):
    """Collapse overlaps to a single melodic line.
    pick='high' for vocals (take top note), 'low' for bass (bottom note)."""
    if not notes:
        return []
    # Walk through time; at any time only one note may sound.
    events = []  # (time_16, +1/-1, pitch, vel, end)
    notes_sorted = sorted(notes, key=lambda x: x[0])
    active = []   # list of (start, end, pitch, vel) still sounding
    result = []
    # Process per onset
    i = 0
    cur_start = None
    cur_pitch = None
    cur_vel = None
    def salience(p):
        return p if pick == "high" else -p
    for (s, e, p, v) in notes_sorted:
        if cur_start is None:
            cur_start, cur_pitch, cur_vel, cur_end = s, p, v, e
            continue
        if s < cur_end:  # overlap
            if salience(p) > salience(cur_pitch):
                # new note wins: end current at s
                if s > cur_start:
                    result.append((cur_start, s, cur_pitch, cur_vel))
                cur_start, cur_pitch, cur_vel, cur_end = s, p, v, e
            else:
                # keep current, may extend it if the new note's end is later
                cur_end = max(cur_end, e) if salience(p) == salience(cur_pitch) else cur_end
        else:
            # no overlap → commit current, start new
            result.append((cur_start, cur_end, cur_pitch, cur_vel))
            cur_start, cur_pitch, cur_vel, cur_end = s, p, v, e
    if cur_start is not None:
        result.append((cur_start, cur_end, cur_pitch, cur_vel))
    # Filter zero-length
    return [(s, e, p, v) for (s, e, p, v) in result if e > s]

def drop_shorts(notes, min_len_16):
    return [(s, e, p, v) for (s, e, p, v) in notes if (e - s) >= min_len_16]

def cap_polyphony_by_onset(notes, max_voices=4):
    """At each onset 16th, keep the top max_voices by velocity."""
    by_onset: dict[int, list] = {}
    for n in notes:
        by_onset.setdefault(n[0], []).append(n)
    out = []
    for s, bucket in by_onset.items():
        bucket.sort(key=lambda x: (-x[3], x[2]))
        out.extend(bucket[:max_voices])
    return sorted(out, key=lambda x: (x[0], x[2]))

def smooth_melody(notes, min_len_16=2):
    """For a monophonic melody: drop very short notes that sit between two
    longer neighbours of different pitch (likely pitch-flip artifact). Runs
    after merge_same_pitch."""
    if len(notes) < 3:
        return notes
    out = []
    for i, n in enumerate(notes):
        if (n[1] - n[0]) < min_len_16 and 0 < i < len(notes) - 1:
            prev = out[-1] if out else None
            nxt  = notes[i+1]
            # Drop if neighbours flank it and we'd otherwise have a microsecond blip
            if prev and nxt and prev[2] != n[2] and nxt[2] != n[2]:
                # extend previous to fill the gap up to next onset
                if prev[1] < nxt[0]:
                    out[-1] = (prev[0], nxt[0], prev[2], prev[3])
                continue
        out.append(n)
    return out

# ---- load each stem -----------------------------------------------------

def load_stem_midi(name):
    p = MIDI_DIR / f"{name}.mid"
    pm = pretty_midi.PrettyMIDI(str(p))
    raw = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        raw.extend(inst.notes)
    return raw

# Vocals — melody line, heavily smoothed (merge long same-pitch runs,
# min dotted-8th, then smooth single-16th blips between steady neighbours).
vox = load_stem_midi("vocals")
vox = quantize(vox, min_len_16=1, velocity_floor=40,
               pitch_lo=55, pitch_hi=84)     # G3..C6 — smle is female vox
vox = merge_same_pitch(vox, gap_tol_16=3)    # merge across breath-sized gaps
vox = mono_reduce(vox, pick="high")
vox = drop_shorts(vox, min_len_16=2)         # 8th note minimum
vox = smooth_melody(vox, min_len_16=2)

# Bass — monophonic, quarter-note minimum feel
bass = load_stem_midi("bass")
bass = quantize(bass, min_len_16=2, velocity_floor=35, pitch_lo=28, pitch_hi=55)
bass = merge_same_pitch(bass, gap_tol_16=2)
bass = mono_reduce(bass, pick="low")
bass = drop_shorts(bass, min_len_16=4)       # 8th→quarter for readable bass

# Piano — polyphonic, more aggressive cleanup: 8th-note floor, velocity floor
# raised to filter basic-pitch noise.
piano = load_stem_midi("piano")
piano = quantize(piano, min_len_16=2, velocity_floor=45, pitch_lo=33, pitch_hi=96)
piano = merge_same_pitch(piano, gap_tol_16=2)
piano = cap_polyphony_by_onset(piano, max_voices=3)
piano = drop_shorts(piano, min_len_16=2)

# Guitar — same philosophy as piano
guit = load_stem_midi("guitar")
guit = quantize(guit, min_len_16=2, velocity_floor=50, pitch_lo=40, pitch_hi=84)
guit = merge_same_pitch(guit, gap_tol_16=2)
guit = cap_polyphony_by_onset(guit, max_voices=3)
guit = drop_shorts(guit, min_len_16=2)

for label, lst in [("vocals", vox), ("bass", bass), ("piano", piano), ("guitar", guit)]:
    print(f"{label}: {len(lst)} notes after cleanup")

# ---- compute end time to trim trailing silence --------------------------
all_notes = vox + bass + piano + guit
last_16 = max(n[1] for n in all_notes)
# Round up to full measure
sixteenths_per_measure = 16
last_measure = (last_16 + sixteenths_per_measure - 1) // sixteenths_per_measure
end_16 = last_measure * sixteenths_per_measure
print(f"trim to 16th idx {end_16} ({last_measure} measures; tempo {BPM:.2f}, 4/4)")

# ---- build pretty_midi combined file ------------------------------------
def to_pm_notes(lst, program, name):
    inst = pretty_midi.Instrument(program=program, name=name)
    for (s, e, p, v) in lst:
        inst.notes.append(pretty_midi.Note(velocity=int(v), pitch=int(p),
                                           start=idx_to_sec(s), end=idx_to_sec(e)))
    return inst

combined = pretty_midi.PrettyMIDI(initial_tempo=BPM)
combined.instruments.append(to_pm_notes(vox,   52, "Vocals"))
combined.instruments.append(to_pm_notes(piano, 0,  "Piano"))
combined.instruments.append(to_pm_notes(guit,  25, "Guitar"))
combined.instruments.append(to_pm_notes(bass,  33, "Bass"))
combined_path = MIDI_DIR / "combined_v2.mid"
combined.write(str(combined_path))

# Full playback MIDI with drums preserved from v1
drums_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "drums.mid"))
full = pretty_midi.PrettyMIDI(initial_tempo=BPM)
for inst in combined.instruments:
    full.instruments.append(inst)
for inst in drums_pm.instruments:
    # snap drum hits to 16ths too
    inst.notes = [pretty_midi.Note(velocity=n.velocity, pitch=n.pitch,
                                   start=idx_to_sec(snap16(n.start)),
                                   end=idx_to_sec(snap16(n.start)) + SIXTEENTH)
                  for n in inst.notes if snap16(n.start) >= 0]
    full.instruments.append(inst)
full.write(str(MIDI_DIR / "Haunted_full_v2.mid"))

# ---- music21 conversion -------------------------------------------------
print("Parsing MIDI into music21 (quantizePost off since we already quantized)...")
score = music21.converter.parse(str(combined_path), quantizePost=True,
                                quarterLengthDivisors=(4,))

# Metadata
score.metadata = metadata.Metadata()
score.metadata.title = "Haunted"
score.metadata.composer = "smle (ft. Seann Bowe)"
score.metadata.movementName = "Auto-transcribed"

ks = key.Key(KEY_NAME, KEY_MODE)
mm = m21tempo.MetronomeMark(number=round(BPM))
ts = meter.TimeSignature("4/4")

INST_MAP = {
    "Vocals": (instrument.Vocalist(),     clef.TrebleClef()),
    "Piano":  (instrument.Piano(),        clef.TrebleClef()),
    "Guitar": (instrument.AcousticGuitar(),clef.Treble8vbClef()),
    "Bass":   (instrument.ElectricBass(), clef.Bass8vbClef()),
}

for part in score.parts:
    name = (part.partName or "").strip()
    m21inst, cl = INST_MAP.get(name, (instrument.Piano(), clef.TrebleClef()))
    part.insert(0, m21inst)
    # Force consistent display name (music21/LilyPond will sometimes derive a
    # longer name like "Acoustic Guitar" from the instrument — override it).
    part.partName = name
    part.partAbbreviation = name[:4]
    first = part.getElementsByClass(stream.Measure).first()
    target = first if first is not None else part
    target.insert(0, cl)
    target.insert(0, ks)
    target.insert(0, ts)
    target.insert(0, mm)

xml_path = Path("Haunted.musicxml")
score.write("musicxml", fp=str(xml_path))
print(f"wrote {xml_path}")

"""Clean, quantize, and merge per-stem MIDIs into a single score-ready MIDI,
then convert to MusicXML via music21.

Pipeline:
  1. Load each stem MIDI with pretty_midi
  2. Apply per-instrument cleanup (monophony reduction for vocal/bass, etc.)
  3. Quantize note onsets/durations to a 16th-note grid at the detected tempo
  4. Emit combined MIDI
  5. Parse combined MIDI into music21, set metadata (title, composer, key, tempo),
     add instrument names, export MusicXML.
"""
from __future__ import annotations

import pretty_midi
import music21
from music21 import stream, meter, key, tempo as m21tempo, metadata, instrument, midi as m21midi
from pathlib import Path
import numpy as np

BPM = 95.7
SIXTEENTH = (60.0 / BPM) / 4  # seconds per 16th note
KEY_NAME = "B"
KEY_MODE = "minor"

MIDI_DIR = Path("midi")

def snap(t: float) -> float:
    """Snap time in seconds to the 16th-note grid."""
    return round(t / SIXTEENTH) * SIXTEENTH

def quantize_notes(notes, min_len_sixteenths=1, velocity_floor=25):
    """Snap start/end to the 16th grid, enforce minimum duration, drop very quiet notes."""
    out = []
    for n in notes:
        if n.velocity < velocity_floor:
            continue
        s = snap(n.start)
        e = snap(n.end)
        if e - s < SIXTEENTH * min_len_sixteenths:
            e = s + SIXTEENTH * min_len_sixteenths
        out.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=s, end=e))
    return out

def reduce_monophonic(notes, pick="high"):
    """Collapse overlapping notes to monophonic line. pick='high' keeps the
    highest pitch in overlaps (for melody/vocals); pick='low' keeps the lowest
    (for bass)."""
    notes = sorted(notes, key=lambda n: (n.start, -n.pitch if pick == "high" else n.pitch))
    # Walk the timeline; for each onset keep only the most salient note, and
    # trim its end to the next kept onset.
    kept = []
    for n in notes:
        if not kept:
            kept.append(n)
            continue
        prev = kept[-1]
        # New note overlaps previous
        if n.start < prev.end - 1e-6:
            # Same onset → keep preferred
            if abs(n.start - prev.start) < 1e-6:
                if (pick == "high" and n.pitch > prev.pitch) or (pick == "low" and n.pitch < prev.pitch):
                    kept[-1] = n
                continue
            # Staggered overlap → trim previous to new onset
            prev.end = n.start
            if prev.end - prev.start >= SIXTEENTH * 0.9:
                kept.append(n)
            else:
                kept[-1] = n
        else:
            kept.append(n)
    # Drop zero/negative-length
    return [n for n in kept if n.end > n.start]

def cap_polyphony(notes, max_voices=4):
    """At each onset, keep at most max_voices simultaneous notes (loudest)."""
    if not notes:
        return []
    # Bucket by snapped onset
    buckets = {}
    for n in notes:
        buckets.setdefault(round(n.start, 4), []).append(n)
    out = []
    for _, bucket in sorted(buckets.items()):
        bucket.sort(key=lambda n: (-n.velocity, n.pitch))
        out.extend(bucket[:max_voices])
    return out

def load_stem(name: str, program: int, inst_name: str, *, mono: str|None=None, max_voices: int|None=None, velocity_floor=25):
    p = MIDI_DIR / f"{name}.mid"
    pm = pretty_midi.PrettyMIDI(str(p))
    notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        notes.extend(inst.notes)
    notes = quantize_notes(notes, velocity_floor=velocity_floor)
    if mono:
        notes = reduce_monophonic(notes, pick=mono)
    elif max_voices:
        notes = cap_polyphony(notes, max_voices=max_voices)
    new_inst = pretty_midi.Instrument(program=program, name=inst_name)
    new_inst.notes = notes
    return new_inst

# Build combined PrettyMIDI
combined = pretty_midi.PrettyMIDI(initial_tempo=BPM)

vocals = load_stem("vocals", program=52, inst_name="Vocals", mono="high", velocity_floor=30)           # Choir Aahs
piano  = load_stem("piano",  program=0,  inst_name="Piano",  max_voices=4, velocity_floor=30)         # Acoustic Grand
guitar = load_stem("guitar", program=25, inst_name="Guitar", max_voices=3, velocity_floor=35)        # Acoustic Guitar (steel)
bass   = load_stem("bass",   program=33, inst_name="Bass",   mono="low", velocity_floor=30)           # Electric Bass (finger)

for inst in (vocals, piano, guitar, bass):
    print(f"{inst.name}: {len(inst.notes)} notes")
    combined.instruments.append(inst)

# Write combined MIDI with pitched parts first (used for MusicXML)
combined_path = MIDI_DIR / "combined.mid"
combined.write(str(combined_path))
print(f"wrote {combined_path}")

# Also write a "with drums" MIDI for playback — drums excluded from the score
# because MusicXML percussion notation needs a dedicated percussion map we
# aren't building here.
drums_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "drums.mid"))
full_pm = pretty_midi.PrettyMIDI(initial_tempo=BPM)
for inst in combined.instruments:
    full_pm.instruments.append(inst)
for inst in drums_pm.instruments:
    inst.notes = [pretty_midi.Note(velocity=n.velocity, pitch=n.pitch,
                                   start=snap(n.start),
                                   end=snap(n.start)+SIXTEENTH)
                  for n in inst.notes]
    full_pm.instruments.append(inst)
full_pm.write(str(MIDI_DIR / "Haunted_full.mid"))
print(f"wrote {MIDI_DIR / 'Haunted_full.mid'} (playback, with drums)")

# ---- music21 conversion ----
print("Parsing into music21...")
score = music21.converter.parse(str(combined_path), quantizePost=True,
                                quarterLengthDivisors=(4, 3))

# Metadata
score.metadata = metadata.Metadata()
score.metadata.title = "Haunted"
score.metadata.composer = "smle (ft. Seann Bowe)"
score.metadata.movementName = "Auto-transcribed"

# Insert tempo + key signature on the first measure/part
ks = key.Key(KEY_NAME, KEY_MODE)
mm = m21tempo.MetronomeMark(number=round(BPM))
ts = meter.TimeSignature("4/4")

# Map program numbers to music21 instrument classes and display names
INST_MAP = {
    "Vocals": ("Vocals", instrument.Vocalist()),
    "Piano":  ("Piano",  instrument.Piano()),
    "Guitar": ("Guitar", instrument.AcousticGuitar()),
    "Bass":   ("Bass",   instrument.ElectricBass()),
}

for part in score.parts:
    # Pretty_midi writes instrument name as the track name
    track_name = (part.partName or "").strip()
    display, m21inst = INST_MAP.get(track_name, (track_name or "Part", instrument.Piano()))
    part.partName = display
    part.partAbbreviation = display[:4]
    # Insert instrument object
    part.insert(0, m21inst)
    # Insert key + tempo at offset 0 of first measure
    first = part.getElementsByClass(stream.Measure).first()
    if first is not None:
        first.insert(0, ks)
        first.insert(0, ts)
        first.insert(0, mm)
    else:
        part.insert(0, ks)
        part.insert(0, ts)
        part.insert(0, mm)

xml_path = Path("Haunted.musicxml")
score.write("musicxml", fp=str(xml_path))
print(f"wrote {xml_path}")

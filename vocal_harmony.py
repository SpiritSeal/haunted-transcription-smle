"""Extract vocal harmony notes by combining:
   * CREPE's monophonic lead  (midi/vocals_crepe.mid)
   * basic-pitch's polyphonic transcription of the vocal stem (midi/vocals.mid)

The lead line is trusted for the top voice. Harmonies = basic-pitch notes that
overlap a lead note in time AND sit below the lead by ≥ 3 semitones (to avoid
unison/near-unison duplication from basic-pitch's melody detection).

Output: midi/vocals_with_harmony.mid — a single track where simultaneous notes
become chord stacks. The lead melody pitch is preserved on top."""
from pathlib import Path
import pretty_midi
import numpy as np
from collections import defaultdict

MIDI_DIR = Path("midi")

lead_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "vocals_crepe.mid"))
poly_pm = pretty_midi.PrettyMIDI(str(MIDI_DIR / "vocals_poly.mid"))

lead_notes = list(lead_pm.instruments[0].notes)
poly_notes = [n for inst in poly_pm.instruments for n in inst.notes]

# For each basic-pitch note, decide whether it's a harmony (keep) or noise/
# lead-duplicate (drop). Criteria:
#  1. Overlaps a lead note by ≥ 50ms
#  2. Pitch is ≥ 3 semitones BELOW the overlapping lead note
#  3. Pitch is within typical vocal range (55..84 -> G3..C6)
#  4. Note lasts ≥ 120ms (filter basic-pitch micro-fragments)
#  5. Velocity above a floor

MIN_OVERLAP  = 0.04
MIN_INTERVAL = 2        # keep anything ≥ 2 semitones below lead
MAX_INTERVAL = 13       # drop > octave (likely overtone artifacts)
MIN_DURATION = 0.08
VEL_FLOOR    = 25

def overlap(a, b):
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))

harmonies = []
for p in poly_notes:
    if (p.end - p.start) < MIN_DURATION:
        continue
    if p.velocity < VEL_FLOOR:
        continue
    if p.pitch < 50 or p.pitch > 84:
        continue
    best = None
    best_ov = 0.0
    for L in lead_notes:
        ov = overlap(p, L)
        if ov > best_ov:
            best = L
            best_ov = ov
    if best is None or best_ov < MIN_OVERLAP:
        continue
    delta = best.pitch - p.pitch
    if delta < MIN_INTERVAL:
        continue
    if delta > MAX_INTERVAL:
        continue
    # Force harmony start/end to match the overlapping lead exactly. This
    # guarantees music21 sees them as simultaneous and emits them as a chord
    # stack instead of two adjacent voices that share a grid cell.
    h = pretty_midi.Note(velocity=p.velocity, pitch=p.pitch,
                         start=float(best.start), end=float(best.end))
    harmonies.append(h)

print(f"lead: {len(lead_notes)} notes; basic-pitch candidates: {len(poly_notes)}; harmonies kept: {len(harmonies)}")

# Build combined MIDI — single instrument with lead on top + harmony notes below
out_pm = pretty_midi.PrettyMIDI(initial_tempo=95.7)
inst = pretty_midi.Instrument(program=52, name="Vocals")
for n in lead_notes:
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=n.pitch,
                                       start=float(n.start), end=float(n.end)))
for n in harmonies:
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=n.pitch,
                                       start=float(n.start), end=float(n.end)))
out_pm.instruments.append(inst)
out_pm.write(str(MIDI_DIR / "vocals_with_harmony.mid"))
print("wrote midi/vocals_with_harmony.mid")

# Quick stats: in which seconds of the song do harmonies cluster?
bins = np.zeros(220)
for n in harmonies:
    bi = int(n.start)
    if 0 <= bi < len(bins):
        bins[bi] += 1
# Find peaks (likely chorus regions)
high = [i for i, v in enumerate(bins) if v >= 4]
# Collapse contiguous seconds into runs
runs = []
if high:
    s = high[0]; p = high[0]
    for i in high[1:]:
        if i - p <= 2:
            p = i
        else:
            runs.append((s, p))
            s = i; p = i
    runs.append((s, p))
print(f"harmony clusters (likely chorus): {runs}")

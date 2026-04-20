"""Extract a clean vocal melody from the vocals stem using CREPE (monophonic f0).

Pipeline:
  1. CREPE produces f0 + confidence at 10ms steps.
  2. Gate by confidence (>0.6) and zero out silent segments.
  3. Smooth f0 via 5-frame median.
  4. Convert to MIDI pitch, round to integer semitones.
  5. Segment into notes: contiguous runs of the same pitch become one note.
  6. Snap onsets/offsets to the beat grid (16ths).
"""
from pathlib import Path
import numpy as np
import crepe
import librosa
import pretty_midi

STEMS = Path("stems")
SR = 16000            # crepe's native sample rate
STEP_MS = 10
CONF_THR = 0.6
MIN_NOTE_MS = 80

vocal_path = next(STEMS.glob("*vocals*.mp3"))
print(f"loading {vocal_path.name}")
y, _sr = librosa.load(str(vocal_path), sr=SR, mono=True)

print("running CREPE (this may take ~1-2 min)...")
time, frequency, confidence, _ = crepe.predict(
    y, SR, step_size=STEP_MS,
    model_capacity="full",        # largest → most accurate
    viterbi=True,                 # temporal smoothing at the pitch level
    verbose=1,
)

freq = np.where(confidence > CONF_THR, frequency, 0.0)
# Gate additionally by a volume threshold — CREPE emits confident f0 even over soft breath
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=int(SR*STEP_MS/1000))[0]
rms_thr = np.percentile(rms, 35)
if len(rms) < len(freq):
    rms = np.pad(rms, (0, len(freq)-len(rms)))
freq = np.where(rms[:len(freq)] > rms_thr, freq, 0.0)

# Median-smooth to squash octave jumps / frame jitter
def median_smooth(x, k=5):
    pad = k // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    return np.array([np.median(xp[i:i+k]) for i in range(len(x))])

freq = median_smooth(freq, k=5)

# Convert to MIDI pitch (float), round; 0 Hz -> 0
midi = np.zeros_like(freq)
nz = freq > 0
midi[nz] = librosa.hz_to_midi(freq[nz])
midi_int = np.where(midi > 0, np.round(midi).astype(int), 0)

# Segment into notes — runs of the same integer pitch
notes = []   # (start_sec, end_sec, pitch)
cur_pitch = 0
cur_start = 0.0
for i, p in enumerate(midi_int):
    t = time[i]
    if p != cur_pitch:
        if cur_pitch > 0:
            notes.append((cur_start, t, int(cur_pitch)))
        cur_pitch = int(p)
        cur_start = t
if cur_pitch > 0:
    notes.append((cur_start, time[-1], int(cur_pitch)))

# Drop very short notes (<MIN_NOTE_MS)
notes = [(s, e, p) for (s, e, p) in notes if (e - s) * 1000 >= MIN_NOTE_MS]
print(f"{len(notes)} raw CREPE notes")

# Save MIDI
pm = pretty_midi.PrettyMIDI(initial_tempo=95.7)
inst = pretty_midi.Instrument(program=52, name="Vocals")  # Choir Aahs
for (s, e, p) in notes:
    if p < 40 or p > 90:
        continue
    inst.notes.append(pretty_midi.Note(velocity=90, pitch=p, start=float(s), end=float(e)))
pm.instruments.append(inst)
pm.write("midi/vocals_crepe.mid")
print("wrote midi/vocals_crepe.mid")
print(f"kept {len(inst.notes)} notes, pitch range {min(n.pitch for n in inst.notes)}..{max(n.pitch for n in inst.notes)}")

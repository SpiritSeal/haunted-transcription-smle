"""CREPE monophonic f0 tracking on the bass stem.

Bass is mostly monophonic in pop; basic-pitch fragments it badly. CREPE gives
a clean pitch contour which we segment into note events, mirroring the
approach in vocal_melody.py.
"""
from pathlib import Path
import numpy as np
import crepe
import librosa
import pretty_midi

STEMS = Path("stems")
SR = 16000
STEP_MS = 10
CONF_THR = 0.7          # tighter than vocals — bass f0 is very confident when present
MIN_NOTE_MS = 120       # bass notes are typically longer

bass_path = next(STEMS.glob("*bass*.mp3"))
print(f"loading {bass_path.name}")
y, _sr = librosa.load(str(bass_path), sr=SR, mono=True)

print("running CREPE on bass (large model, viterbi)...")
time, frequency, confidence, _ = crepe.predict(
    y, SR,
    step_size=STEP_MS,
    model_capacity="full",
    viterbi=True,
    verbose=1,
)

# Confidence gate
freq = np.where(confidence > CONF_THR, frequency, 0.0)

# Volume gate: drop frames where the stem is essentially silent
rms = librosa.feature.rms(y=y, frame_length=2048,
                          hop_length=int(SR*STEP_MS/1000))[0]
rms_thr = np.percentile(rms, 40)
if len(rms) < len(freq):
    rms = np.pad(rms, (0, len(freq)-len(rms)))
freq = np.where(rms[:len(freq)] > rms_thr, freq, 0.0)

# Median-smooth f0 to suppress octave jumps
def med(x, k=5):
    pad = k // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    return np.array([np.median(xp[i:i+k]) for i in range(len(x))])

freq = med(freq, k=5)

# Convert to MIDI pitch (rounded int) and segment into note runs
midi = np.zeros_like(freq)
nz = freq > 0
midi[nz] = librosa.hz_to_midi(freq[nz])
midi_int = np.where(midi > 0, np.round(midi).astype(int), 0)

notes = []
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

# Length filter + range filter (E1=28 .. C4=60 covers typical bass)
notes = [(s, e, p) for (s, e, p) in notes
         if (e - s) * 1000 >= MIN_NOTE_MS and 28 <= p <= 60]
print(f"{len(notes)} bass notes after filtering")

pm = pretty_midi.PrettyMIDI(initial_tempo=95.7)
inst = pretty_midi.Instrument(program=33, name="Bass")  # Electric Bass (finger)
for (s, e, p) in notes:
    inst.notes.append(pretty_midi.Note(velocity=95, pitch=p,
                                       start=float(s), end=float(e)))
pm.instruments.append(inst)
pm.write("midi/bass_crepe.mid")
print("wrote midi/bass_crepe.mid")
if notes:
    print(f"pitch range: MIDI {min(n[2] for n in notes)}..{max(n[2] for n in notes)}")

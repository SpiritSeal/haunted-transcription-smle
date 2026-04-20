"""Analyze the full mix: tempo, key, duration."""
import librosa
import numpy as np
import json
import sys

path = "smle - Haunted (ft. Seann Bowe).mp3"
print(f"Loading {path}...", file=sys.stderr)
y, sr = librosa.load(path, sr=22050, mono=True)
duration = len(y) / sr

# Tempo + beats
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
tempo = float(tempo) if np.isscalar(tempo) else float(tempo[0])
beat_times = librosa.frames_to_time(beats, sr=sr)

# Key estimation via chroma
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
chroma_mean = chroma.mean(axis=1)
keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Schmuckler key profiles
maj_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
min_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
best = (-1, None, None)
for i in range(12):
    maj_corr = np.corrcoef(np.roll(maj_profile, i), chroma_mean)[0, 1]
    min_corr = np.corrcoef(np.roll(min_profile, i), chroma_mean)[0, 1]
    if maj_corr > best[0]:
        best = (maj_corr, keys[i], "major")
    if min_corr > best[0]:
        best = (min_corr, keys[i], "minor")

result = {
    "duration_sec": round(duration, 2),
    "tempo_bpm": round(tempo, 2),
    "n_beats": len(beat_times),
    "first_beat": round(float(beat_times[0]), 3) if len(beat_times) else None,
    "beat_interval_mean": round(float(np.mean(np.diff(beat_times))), 4) if len(beat_times) > 1 else None,
    "key": best[1],
    "mode": best[2],
    "key_confidence": round(float(best[0]), 3),
    "sr": sr,
}
print(json.dumps(result, indent=2))
np.save("beat_times.npy", beat_times)

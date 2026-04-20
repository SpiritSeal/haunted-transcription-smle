"""Build a beat-accurate timing grid from the mix.

We use librosa's beat tracker on the drum stem (more reliable than the full mix
for percussion-locked songs), then fall back to onset-enhanced tracking on the
mix if that looks unstable. Output: JSON with beat times, downbeats, median
tempo, and phase offset.
"""
from pathlib import Path
import json
import numpy as np
import librosa

STEMS = Path("stems")
MIX   = Path("smle - Haunted (ft. Seann Bowe).mp3")
SR    = 22050

def load(p, sr=SR):
    y, _ = librosa.load(str(p), sr=sr, mono=True)
    return y

# Beat track the drum stem — more reliable when kick/snare are isolated
drum_path = next(STEMS.glob("*drums*.mp3"))
y_drum = load(drum_path)
y_mix  = load(MIX)

def track(y, sr=SR, start_bpm=96):
    # Use a tighter tightness for pop (locks the tracker harder onto tempo)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, start_bpm=start_bpm, tightness=120, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    return tempo, np.asarray(beats, dtype=float)

tempo_d, beats_d = track(y_drum)
tempo_m, beats_m = track(y_mix)

def interval_stats(beats):
    if len(beats) < 2:
        return None, None, None
    di = np.diff(beats)
    return float(np.median(di)), float(np.mean(di)), float(np.std(di))

med_d, mean_d, std_d = interval_stats(beats_d)
med_m, mean_m, std_m = interval_stats(beats_m)

# Pick whichever has tighter beat intervals (lower std relative to mean)
choice = "drum" if (std_d/mean_d) <= (std_m/mean_m) else "mix"
beats  = beats_d if choice == "drum" else beats_m
median_interval = med_d if choice == "drum" else med_m
median_tempo    = 60.0 / median_interval

# Estimate downbeats: pick the beat phase (0..3) whose positions carry the most
# kick-band energy on average. This fixes the common "first beat is beat 3" case.
S = np.abs(librosa.stft(y_drum, n_fft=2048, hop_length=512))
freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
kick_env = S[(freqs >= 30) & (freqs <= 120), :].sum(axis=0)
kick_env = kick_env / (kick_env.max() + 1e-9)
hop_time = 512 / SR

def env_at(t):
    idx = int(round(t / hop_time))
    idx = max(0, min(idx, len(kick_env) - 1))
    return kick_env[idx]

phase_scores = []
for phase in range(4):
    pts = beats[phase::4]
    phase_scores.append(float(np.mean([env_at(t) for t in pts])) if len(pts) else 0.0)
downbeat_phase = int(np.argmax(phase_scores))

# Build canonical beat grid starting from the first actual downbeat
first_downbeat_idx = downbeat_phase
first_downbeat     = float(beats[first_downbeat_idx])

# Extrapolate a regular grid backward and forward from first_downbeat at the
# median interval; but prefer the *measured* beat times for quantization where
# we have them (they track tempo drift).
# We'll still expose the measured beats for quantization and the downbeat index.
beat_times = beats.tolist()

result = {
    "choice": choice,
    "median_interval_sec": median_interval,
    "median_tempo_bpm": round(median_tempo, 3),
    "n_beats": len(beats),
    "first_beat": float(beats[0]),
    "first_downbeat": first_downbeat,
    "downbeat_phase": downbeat_phase,
    "phase_scores": phase_scores,
    "tempo_stability_cv_drum": (std_d / mean_d) if mean_d else None,
    "tempo_stability_cv_mix":  (std_m / mean_m) if mean_m else None,
}
print(json.dumps(result, indent=2))

np.savez("grid.npz",
         beat_times=np.asarray(beat_times),
         first_downbeat=first_downbeat,
         downbeat_phase=downbeat_phase,
         median_interval=median_interval,
         median_tempo=median_tempo)
print("saved grid.npz")

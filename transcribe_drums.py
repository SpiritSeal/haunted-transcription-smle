"""Detect kick/snare/hi-hat onsets from the drum stem and write a MIDI drum track."""
import os
import librosa
import numpy as np
import pretty_midi
from pathlib import Path

STEMS_DIR = Path(os.environ.get("STEMS_DIR", "stems"))
MIDI_DIR = Path(os.environ.get("MIDI_DIR", "midi"))
DRUM_PATH = next(STEMS_DIR.glob("*drums*.mp3"))
SR = 22050
y, sr = librosa.load(str(DRUM_PATH), sr=SR, mono=True)

# Band-limited onsets for kick (low), snare (mid), hi-hat (high).
def band_onsets(y, sr, fmin, fmax, delta=0.3, pre_max=3, post_max=3, wait=3):
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    mask = (freqs >= fmin) & (freqs <= fmax)
    env = S[mask, :].sum(axis=0)
    env = env / (env.max() + 1e-9)
    onsets = librosa.onset.onset_detect(
        onset_envelope=env, sr=sr, hop_length=512,
        delta=delta, pre_max=pre_max, post_max=post_max, wait=wait,
        units="time",
    )
    return onsets, env

kick_times, _  = band_onsets(y, sr, 30, 120,  delta=0.25)
snare_times, _ = band_onsets(y, sr, 150, 450, delta=0.35)
hat_times, _   = band_onsets(y, sr, 6000, 11025, delta=0.35)

print(f"kicks={len(kick_times)} snares={len(snare_times)} hats={len(hat_times)}")

# Build a GM drum MIDI (channel 10, program 0 — pretty_midi sets is_drum=True).
pm = pretty_midi.PrettyMIDI()
drum = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
# GM drum map
KICK, SNARE, HAT = 36, 38, 42

def add_hits(times, pitch, dur=0.08, vel=100):
    for t in times:
        drum.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch,
                                           start=float(t), end=float(t)+dur))

add_hits(kick_times, KICK, vel=110)
add_hits(snare_times, SNARE, vel=105)
add_hits(hat_times, HAT, dur=0.05, vel=85)

pm.instruments.append(drum)
out = MIDI_DIR / "drums.mid"
out.parent.mkdir(parents=True, exist_ok=True)
pm.write(str(out))
print(f"wrote {out}")

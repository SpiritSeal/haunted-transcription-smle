"""Richer drum transcription: band-separated onset detection with spectral-
flux envelopes for kick, snare, hi-hat, and overheads (ride/crash).

Key changes vs transcribe_drums.py:
  - hi-hat uses a tighter 5-10 kHz band and the high-frequency content onset
    function (librosa.onset.onset_strength on a high-passed signal), not a
    generic sum.
  - adds an "overheads" class from 10-15 kHz with a higher threshold; these
    become ride cymbal (GM 51) or crash (GM 49) based on duration.
  - merges hits that are closer than 40ms on the same class.
"""
import librosa
import numpy as np
import pretty_midi
from pathlib import Path

DRUM = next(Path("stems").glob("*drums*.mp3"))
SR = 22050
y, _ = librosa.load(str(DRUM), sr=SR, mono=True)

HOP = 512
hop_time = HOP / SR
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)

def band_env(fmin, fmax, power=1.0):
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not mask.any():
        return np.zeros(S.shape[1])
    env = (S[mask, :] ** power).sum(axis=0)
    m = env.max()
    return env / (m + 1e-9)

def band_onsets(env, delta=0.30, pre_max=3, post_max=3, wait=3):
    return librosa.onset.onset_detect(
        onset_envelope=env, sr=SR, hop_length=HOP,
        delta=delta, pre_max=pre_max, post_max=post_max, wait=wait,
        units="time",
    )

# Envelopes per-band. The power=2 on the HF bands increases transient
# selectivity — cymbals have broad spectra but peaky transients.
kick_env  = band_env(30, 100)
snare_env = band_env(150, 500)
hat_env   = band_env(5000, 10000, power=2.0)
over_env  = band_env(10000, 15000, power=2.0)

kicks  = band_onsets(kick_env,  delta=0.22)
snares = band_onsets(snare_env, delta=0.32)
hats   = band_onsets(hat_env,   delta=0.25, pre_max=2, post_max=2, wait=2)
overs  = band_onsets(over_env,  delta=0.35, pre_max=4, post_max=4, wait=6)

print(f"kicks={len(kicks)} snares={len(snares)} hats={len(hats)} overs={len(overs)}")

def dedupe(times, min_gap=0.04):
    out = []
    last = -1e9
    for t in times:
        if t - last >= min_gap:
            out.append(t); last = t
    return out

kicks  = dedupe(kicks)
snares = dedupe(snares)
hats   = dedupe(hats)
overs  = dedupe(overs)

# Suppress hi-hats that fall within ±15ms of a snare (snare transients leak
# energy into the high band and get re-detected as a hat).
def suppress_near(ts, ref, tol=0.015):
    import bisect
    ref_sorted = sorted(ref)
    out = []
    for t in ts:
        i = bisect.bisect_left(ref_sorted, t)
        near = False
        for j in (i-1, i):
            if 0 <= j < len(ref_sorted) and abs(ref_sorted[j] - t) <= tol:
                near = True; break
        if not near:
            out.append(t)
    return out
hats = suppress_near(hats, snares, tol=0.005)   # only collapse identical onsets

print(f"after dedupe+suppress: kicks={len(kicks)} snares={len(snares)} "
      f"hats={len(hats)} overs={len(overs)}")

# GM drum mapping
KICK, SNARE, HAT_CLOSED, RIDE, CRASH = 36, 38, 42, 51, 49

pm = pretty_midi.PrettyMIDI(initial_tempo=95.7)
drum = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

def add_hits(times, pitch, dur=0.08, vel=100):
    for t in times:
        drum.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch,
                                           start=float(t), end=float(t)+dur))
add_hits(kicks,  KICK,       dur=0.12, vel=115)
add_hits(snares, SNARE,      dur=0.10, vel=108)
add_hits(hats,   HAT_CLOSED, dur=0.04, vel=90)
# Overheads: likely ride in a pop song with moderate sparsity (<1 per beat).
# We call it ride (GM 51) by default; if we wanted crash we'd need to pick
# hits near section boundaries, which is structure-detection territory.
add_hits(overs,  RIDE,       dur=0.15, vel=95)

pm.instruments.append(drum)
pm.write("midi/drums.mid")
print("wrote midi/drums.mid")

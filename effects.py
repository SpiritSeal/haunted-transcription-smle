"""Audio effects used by the evaluation harness.

Problem: the reference audio (stems/mix) is a professionally mixed recording
with compression, EQ, stereo imaging, and reverb baked in. My synthesized
audio (MuseScore MS Basic SoundFont through fluidsynth) is bone dry. Comparing
them directly with a mel-spectrogram metric penalizes the transcription for
production artifacts that have nothing to do with note correctness.

Two strategies this module supports:
  (1) Forward: apply production-like effects to the synth to move it toward
      the reference's acoustic domain. Chain: loudness match → spectral-
      envelope EQ match → plate reverb.
  (2) Reverse: a light dereverberation on the reference via spectral
      subtraction, pulling the reference toward a drier domain that better
      matches the synth and reduces reverb-tail-induced onset/note errors
      at transcription time.

Both are lossy; the goal is "close enough that mel_L1 is about notes, not
about the room". Chroma-CENS and onset detection are already effect-
invariant, so they run on raw signals.
"""
from __future__ import annotations

import numpy as np
import librosa
from scipy.signal import butter, lfilter, fftconvolve


# ---- loudness / RMS matching ------------------------------------------

def rms(y: np.ndarray) -> float:
    return float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))


def loudness_match(y: np.ndarray, ref: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Scale y so its RMS equals ref's RMS."""
    r_y, r_r = rms(y), rms(ref)
    if r_y < eps:
        return y
    return y * (r_r / r_y)


# ---- time-invariant EQ matching ---------------------------------------

def spectrum_match(y: np.ndarray, ref: np.ndarray, sr: int,
                   n_fft: int = 4096, hop: int = 1024,
                   cap: float = 10.0) -> np.ndarray:
    """Apply a time-invariant EQ to y so its long-term average magnitude
    spectrum approaches ref's. cap limits the per-bin gain to prevent
    amplifying silence noise."""
    if len(ref) == 0 or len(y) == 0:
        return y
    S_y = np.abs(librosa.stft(y,   n_fft=n_fft, hop_length=hop))
    S_r = np.abs(librosa.stft(ref, n_fft=n_fft, hop_length=hop))
    mean_y = S_y.mean(axis=1) + 1e-7
    mean_r = S_r.mean(axis=1) + 1e-7
    gain = np.clip(mean_r / mean_y, 1.0 / cap, cap)
    # Smooth the gain curve across frequency bins so we apply an EQ rather
    # than reshaping every peak. A 5-bin boxcar is mild enough to preserve
    # broad tilt but suppresses ringing.
    k = 9
    gain_smooth = np.convolve(gain, np.ones(k) / k, mode="same")
    Y = librosa.stft(y, n_fft=n_fft, hop_length=hop)
    Y = Y * gain_smooth[:, np.newaxis]
    return librosa.istft(Y, hop_length=hop, length=len(y))


# ---- plate-ish convolution reverb -------------------------------------

_IR_CACHE: dict[tuple, np.ndarray] = {}


def _build_ir(sr: int, rt60: float = 1.4, seed: int = 42) -> np.ndarray:
    """Filtered-noise decaying impulse response. Cached by (sr, rt60, seed).
    rt60 is the -60dB decay time (~1.0-1.5s for a pop plate)."""
    key = (sr, round(rt60, 3), seed)
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    n = int(rt60 * sr * 1.2)
    t = np.arange(n) / sr
    decay = np.exp(-t * (6.908 / rt60))      # 6.908 = ln(1000), -60dB
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    # Light low-pass for plate-like smoothness
    b, a = butter(2, 0.55)
    noise = lfilter(b, a, noise)
    ir = (noise * decay).astype(np.float32)
    # Predelay ~20ms of near-silence, small early reflections
    pre = int(0.02 * sr)
    ir[:pre] *= 0.1
    ir /= np.max(np.abs(ir)) + 1e-9
    _IR_CACHE[key] = ir
    return ir


def add_reverb(y: np.ndarray, sr: int, rt60: float = 1.4,
               wet: float = 0.28) -> np.ndarray:
    """Mix y with (wet) × (y convolved with a plate-style IR). Synth becomes
    more "mixed" sounding, closer to the stem's reverb tail character."""
    if wet <= 0 or len(y) == 0:
        return y
    ir = _build_ir(sr, rt60)
    wet_sig = fftconvolve(y, ir, mode="full")[: len(y)]
    # normalize wet to have the same RMS as dry before blending
    r_y, r_w = rms(y), rms(wet_sig)
    if r_w > 1e-9:
        wet_sig *= r_y / r_w
    return (1.0 - wet) * y + wet * wet_sig


# ---- simple dereverberation for the reference ------------------------

def dereverb(y: np.ndarray, sr: int, n_fft: int = 2048, hop: int = 512,
             alpha: float = 1.5, floor: float = 0.08) -> np.ndarray:
    """Dereverberation by spectral subtraction of a slowly-evolving estimate
    of the long-term noise/tail spectrum. Crude but keeps onsets intact.

    For each frame, subtract alpha × the minimum-magnitude envelope over a
    surrounding window (the 'stationary tail'), flooring at `floor` of the
    original to avoid over-suppression artifacts."""
    Y = librosa.stft(y, n_fft=n_fft, hop_length=hop)
    mag = np.abs(Y)
    phase = np.angle(Y)
    # Rolling minimum over a 1s window ≈ estimate of the sustained tail.
    w = int(sr / hop)                       # 1 second in frames
    mins = np.zeros_like(mag)
    for i in range(mag.shape[1]):
        lo, hi = max(0, i - w // 2), min(mag.shape[1], i + w // 2 + 1)
        mins[:, i] = np.min(mag[:, lo:hi], axis=1)
    mag2 = np.maximum(mag - alpha * mins, floor * mag)
    Y2 = mag2 * np.exp(1j * phase)
    return librosa.istft(Y2, hop_length=hop, length=len(y))


# ---- top-level pipeline -----------------------------------------------

def apply_production_effects(synth: np.ndarray, reference: np.ndarray,
                             sr: int,
                             do_spectrum: bool = True,
                             do_reverb: bool = True,
                             do_loudness: bool = True) -> np.ndarray:
    """Transform dry synth to better match the reference's acoustic domain.
    Applied in order: spectrum match → reverb → loudness match.

    Order matters: spectrum match first (raw frequency response), then reverb
    (which adds its own tail spectrum, but small amount), then loudness
    (normalizes end level)."""
    out = synth
    if do_spectrum:
        out = spectrum_match(out, reference, sr)
    if do_reverb:
        out = add_reverb(out, sr)
    if do_loudness:
        out = loudness_match(out, reference)
    return out

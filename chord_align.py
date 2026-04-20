"""DTW-align the published chord chart (one chord per bar) to the audio mix.

Approach:
  1. Parse published_chart.txt into a flat list of chords (one per bar).
  2. Build a symbolic chroma sequence: for each bar, emit the chord's
     triad chroma template (3 nonzero pitch-classes).
  3. Compute CENS chroma on the mix, aggregated per bar (using grid.npz).
  4. DTW-align symbolic vs audio chroma sequences.
  5. Emit chords.json with one run per bar, timestamps derived from the grid.

This gives chord *labels* from the chart but *timing* from the audio, so the
transcription picks up actual harmonic rhythm even if the chart's section
order is slightly off.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import librosa

SR = 22050
HOP = 2048
MIX = Path("smle - Haunted (ft. Seann Bowe).mp3")

# --- chart parsing -------------------------------------------------------

def parse_chart(path: str = "published_chart.txt") -> list[str]:
    chords: list[str] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        # Each token is one chord (one bar).
        for tok in line.split():
            chords.append(tok)
    return chords

# --- chroma templates ----------------------------------------------------

PITCH = {'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,
         'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11}

def triad(root: str, minor: bool) -> np.ndarray:
    v = np.zeros(12)
    iv = (0, 3, 7) if minor else (0, 4, 7)
    for i in iv:
        v[(PITCH[root] + i) % 12] = 1.0
    return v / np.linalg.norm(v)

def chord_to_chroma(label: str) -> np.ndarray:
    label = label.strip()
    m = re.match(r'^([A-G][#b]?)(m?)', label)
    root = m.group(1)
    is_min = m.group(2) == 'm'
    return triad(root, is_min)

# --- audio chroma per bar ------------------------------------------------

def per_bar_chroma(y: np.ndarray, bar_times: np.ndarray) -> np.ndarray:
    """Return (n_bars, 12) CENS chroma averaged over each bar."""
    chroma = librosa.feature.chroma_cens(y=y, sr=SR, hop_length=HOP)
    hop_t = HOP / SR
    out = np.zeros((len(bar_times) - 1, 12))
    for i in range(len(bar_times) - 1):
        f0 = int(bar_times[i]   / hop_t)
        f1 = int(bar_times[i+1] / hop_t)
        f0 = max(0, f0); f1 = min(chroma.shape[1], f1)
        if f1 > f0:
            col = chroma[:, f0:f1].mean(axis=1)
            n = np.linalg.norm(col)
            out[i] = col / n if n > 1e-6 else col
    return out

# --- dtw -----------------------------------------------------------------

def dtw_align(sym_chroma: np.ndarray, aud_chroma: np.ndarray) -> np.ndarray:
    """Anchored DTW: force audio-bar 0 to map to chart-bar 0 (song starts at
    the beginning of the chart). Allow skipping chart bars only, never audio.

    The published chart has MORE bars than the actual recording (chart
    specifies all theoretical sections; recording plays a subset). So we
    want a path that goes audio-start → chart-start, audio-end → somewhere
    in the chart, visits every audio bar exactly once, and can skip chart
    bars when the audio doesn't play them.
    """
    A = aud_chroma / (np.linalg.norm(aud_chroma, axis=1, keepdims=True) + 1e-9)
    S = sym_chroma / (np.linalg.norm(sym_chroma, axis=1, keepdims=True) + 1e-9)
    n_aud, n_sym = A.shape[0], S.shape[0]
    cost = 1.0 - (A @ S.T)             # (n_aud, n_sym), ∈ [0, 2]

    # dp[i][j] = min cost of aligning audio[0..i] ending at chart-bar j.
    # Allowed moves: diagonal (advance both) or horizontal (skip chart bar).
    # No vertical — every audio bar must emit a chart label.
    INF = 1e9
    dp = np.full((n_aud, n_sym), INF)
    bp = np.full((n_aud, n_sym), -1, dtype=int)
    # Anchor start: audio[0] must map to chart[0].
    dp[0, 0] = cost[0, 0]
    # Allow audio[0] to map to early chart positions with small penalty
    # (lets first bar start a few bars into intro if mismatch).
    for j in range(1, min(8, n_sym)):
        dp[0, j] = cost[0, j] + 0.3 * j

    for i in range(1, n_aud):
        for j in range(0, n_sym):
            # diagonal from (i-1, j-1): the song advances one chart bar
            best = INF; best_k = -1
            if j > 0:
                v = dp[i-1, j-1]
                if v < best: best, best_k = v, j-1
            # diagonal + skip: audio advances one bar while chart skips k bars
            # (cap skip distance so we don't teleport across the chart)
            for k in range(1, 5):
                if j - 1 - k >= 0:
                    v = dp[i-1, j-1-k] + 0.15 * k   # penalize skips
                    if v < best:
                        best, best_k = v, j-1-k
            if best == INF:
                continue
            dp[i, j] = cost[i, j] + best
            bp[i, j] = best_k

    # Best endpoint = min of last row
    j_end = int(np.argmin(dp[-1]))
    path: list[int] = [j_end]
    j = j_end
    for i in range(n_aud - 1, 0, -1):
        j = int(bp[i, j])
        path.append(j)
    path.reverse()
    return np.array(path, dtype=int)

# --- main ----------------------------------------------------------------

def main():
    chart = parse_chart()
    print(f"chart has {len(chart)} bars")
    sym_chroma = np.stack([chord_to_chroma(c) for c in chart])

    # grid
    grid = np.load("grid.npz", allow_pickle=True)
    ANCHOR     = float(grid["first_downbeat"])
    MEDIAN_INT = float(grid["median_interval"])
    PRE_MEASURES = int(np.floor(ANCHOR / (MEDIAN_INT * 4)))
    origin = ANCHOR - PRE_MEASURES * 4 * MEDIAN_INT

    y, _ = librosa.load(str(MIX), sr=SR, mono=True)
    duration = len(y) / SR
    n_bars = int(np.floor((duration - origin) / (MEDIAN_INT * 4)))
    bar_times = origin + MEDIAN_INT * 4 * np.arange(n_bars + 1)

    aud_chroma = per_bar_chroma(y, bar_times)
    print(f"audio: {n_bars} bars starting at {origin:.2f}s")

    mapping = dtw_align(sym_chroma, aud_chroma)
    print(f"first 10 audio-bar → chart-bar: {list(mapping[:10])}")

    # Emit per-beat labels (4 per bar) in the same shape chord_detect.py wrote.
    n_beats = n_bars * 4
    per_beat_labels = []
    for bar_i in range(n_bars):
        sym_i = int(mapping[bar_i]) if mapping[bar_i] >= 0 else 0
        label = chart[sym_i]
        per_beat_labels.extend([label] * 4)

    # Collapse to runs
    runs = []
    i = 0
    while i < n_beats:
        j = i
        while j < n_beats and per_beat_labels[j] == per_beat_labels[i]:
            j += 1
        runs.append({"start_beat": i, "end_beat": j, "chord": per_beat_labels[i]})
        i = j

    payload = {
        "origin_sec": origin,
        "beat_interval_sec": MEDIAN_INT,
        "runs": runs,
        "per_beat_labels": per_beat_labels,
        "source": "dtw-aligned published chart",
    }
    Path("chords.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote chords.json ({len(runs)} runs)")
    # Quick sanity: show first 15 run labels
    print("first 15 runs:", [(r['start_beat'], r['chord']) for r in runs[:15]])


if __name__ == "__main__":
    main()

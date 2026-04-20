"""Chord recognition on the full mix, constrained to the 6-chord set from the
published chord chart: Bm, A, G, D, Em, F#m. We also include N (no chord).

Approach: chroma-CENS features at ~10 Hz, then at each beat (we have the beat
grid in grid.npz), sum chroma over the beat window and template-match against
the 6 major/minor triad templates. Returns chord per beat, written to a JSON
side-car for the assembler.
"""
from pathlib import Path
import numpy as np
import librosa
import json

MIX = Path("smle - Haunted (ft. Seann Bowe).mp3")
SR = 22050
grid = np.load("grid.npz", allow_pickle=True)
ANCHOR = float(grid["first_downbeat"])
MEDIAN_INT = float(grid["median_interval"])
SIXTEENTH = MEDIAN_INT / 4

y, _ = librosa.load(str(MIX), sr=SR, mono=True)

# CENS chroma — robust to timbre; hop ~200ms
chroma = librosa.feature.chroma_cens(y=y, sr=SR, hop_length=2205)   # 10 Hz
hop_time = 2205 / SR
n_frames = chroma.shape[1]

PITCH = {'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,
         'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11}

def triad_template(root, mode):
    # simple 3-note triad template normalized
    v = np.zeros(12)
    intervals = (0, 4, 7) if mode == 'maj' else (0, 3, 7)
    for i in intervals:
        v[(PITCH[root] + i) % 12] = 1.0
    return v / np.linalg.norm(v)

CHORDS = {
    'Bm':  triad_template('B',  'min'),
    'A':   triad_template('A',  'maj'),
    'G':   triad_template('G',  'maj'),
    'D':   triad_template('D',  'maj'),
    'Em':  triad_template('E',  'min'),
    'F#m': triad_template('F#', 'min'),
}
chord_names = list(CHORDS.keys())
templates = np.stack(list(CHORDS.values()), axis=0)   # (n_chords, 12)

# Per-bar chord scoring — one chord per 4-beat measure. This matches the
# published chart's harmonic rhythm and removes within-bar chord flicker.
duration = len(y) / SR
PRE_MEASURES = int(np.floor(ANCHOR / (MEDIAN_INT * 4)))
origin = ANCHOR - PRE_MEASURES * 4 * MEDIAN_INT
n_beats  = int(np.ceil((duration - origin) / MEDIAN_INT))
n_bars   = (n_beats + 3) // 4
print(f"labeling {n_bars} bars (4-beat windows), origin={origin:.3f}s")

# Per-bar emission scores
bar_emit = np.zeros((n_bars, len(chord_names)))
for bar in range(n_bars):
    t0 = origin + bar * 4 * MEDIAN_INT
    t1 = origin + (bar + 1) * 4 * MEDIAN_INT
    f0 = max(0, int(t0 / hop_time))
    f1 = min(n_frames, int(t1 / hop_time))
    if f1 <= f0:
        continue
    profile = chroma[:, f0:f1].sum(axis=1)
    nrm = np.linalg.norm(profile)
    if nrm < 1e-6:
        continue
    bar_emit[bar] = templates @ (profile / nrm)

# Viterbi on bars with a mild self-bonus (holds a chord for 2 bars if the
# emissions are close, but allows change every bar if the audio supports it).
self_bonus = 0.0    # pure emission — each bar's chord is the best template match
n_c = len(chord_names)
dp = np.full((n_bars, n_c), -np.inf)
bp = np.zeros((n_bars, n_c), dtype=int)
dp[0] = bar_emit[0]
for t in range(1, n_bars):
    for j in range(n_c):
        trans = dp[t-1] + np.where(np.arange(n_c) == j, self_bonus, 0.0)
        bp[t, j] = int(np.argmax(trans))
        dp[t, j] = float(trans[bp[t, j]]) + bar_emit[t, j]

path_bar = np.zeros(n_bars, dtype=int)
path_bar[-1] = int(np.argmax(dp[-1]))
for t in range(n_bars - 2, -1, -1):
    path_bar[t] = bp[t+1, path_bar[t+1]]

# Expand bar labels to per-beat labels (4 copies each)
labels_s = []
for i in range(n_beats):
    labels_s.append(chord_names[path_bar[i // 4]])

# Collapse runs into (start_beat, end_beat, chord)
runs = []
i = 0
while i < len(labels_s):
    j = i
    while j < len(labels_s) and labels_s[j] == labels_s[i]:
        j += 1
    runs.append({"start_beat": i, "end_beat": j, "chord": labels_s[i]})
    i = j

# Drop micro-runs (< 2 beats) — absorb into neighbours
cleaned = []
for r in runs:
    length = r['end_beat'] - r['start_beat']
    if length < 2 and cleaned:
        # extend the previous
        cleaned[-1]['end_beat'] = r['end_beat']
    else:
        cleaned.append(r)

print("first 20 chord runs:")
for r in cleaned[:20]:
    t0 = origin + r['start_beat'] * MEDIAN_INT
    t1 = origin + r['end_beat'] * MEDIAN_INT
    print(f"  beat {r['start_beat']:4d}-{r['end_beat']:4d}  t={t0:6.2f}-{t1:6.2f}s  {r['chord']}")

with open("chords.json", "w") as f:
    json.dump({
        "origin_sec": origin,
        "beat_interval_sec": MEDIAN_INT,
        "runs": cleaned,
        "per_beat_labels": labels_s,
    }, f, indent=1)
print(f"saved chords.json ({len(cleaned)} runs)")

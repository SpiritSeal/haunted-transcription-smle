"""Run basic-pitch on each pitched stem to generate per-track MIDI."""
import os, sys, time
from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import build_icassp_2022_model_path, FilenameSuffix
ICASSP_2022_MODEL_PATH = build_icassp_2022_model_path(FilenameSuffix.onnx)

STEMS_DIR = Path(os.environ.get("STEMS_DIR", "stems"))
OUT_DIR = Path(os.environ.get("MIDI_DIR", "midi"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Stem-specific parameters tuned for each instrument
# onset_threshold: lower = more notes detected (sensitive to quiet notes)
# frame_threshold: lower = notes are extended longer
# minimum_note_length: in ms
# minimum_frequency / maximum_frequency: constrain pitch range (Hz)
STEM_CONFIG = {
    "vocals":  {"onset_threshold": 0.5,  "frame_threshold": 0.3,  "minimum_note_length": 100, "minimum_frequency": 80,  "maximum_frequency": 1500, "multiple_pitch_bends": False, "melodia_trick": True},
    "piano":   {"onset_threshold": 0.6,  "frame_threshold": 0.3,  "minimum_note_length": 60,  "minimum_frequency": 55,  "maximum_frequency": 3000, "multiple_pitch_bends": False, "melodia_trick": True},
    "guitar":  {"onset_threshold": 0.6,  "frame_threshold": 0.3,  "minimum_note_length": 60,  "minimum_frequency": 75,  "maximum_frequency": 2000, "multiple_pitch_bends": False, "melodia_trick": True},
    "bass":    {"onset_threshold": 0.5,  "frame_threshold": 0.3,  "minimum_note_length": 100, "minimum_frequency": 30,  "maximum_frequency": 400,  "multiple_pitch_bends": False, "melodia_trick": True},
}

targets = []
for name, cfg in STEM_CONFIG.items():
    candidates = list(STEMS_DIR.glob(f"*{name}*.mp3"))
    if not candidates:
        print(f"WARN: no stem file found for {name}", file=sys.stderr)
        continue
    targets.append((name, candidates[0], cfg))

for name, path, cfg in targets:
    t0 = time.time()
    print(f"→ transcribing {name} from {path.name}", file=sys.stderr)
    predict_and_save(
        [str(path)],
        str(OUT_DIR),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        **cfg,
    )
    # rename output to include stem label
    produced = list(OUT_DIR.glob(f"{path.stem}_basic_pitch.mid"))
    if produced:
        target = OUT_DIR / f"{name}.mid"
        produced[0].rename(target)
        print(f"  saved {target}  ({time.time()-t0:.1f}s)", file=sys.stderr)
    else:
        print(f"  WARN: no midi produced for {name}", file=sys.stderr)

print("done", file=sys.stderr)

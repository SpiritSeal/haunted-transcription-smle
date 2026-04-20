"""Re-run basic-pitch on the vocal stem with polyphony-friendly params.

The original run used melodia_trick=True which biases toward a single melody
line. For harmony extraction we want the opposite: keep all plausible
simultaneous pitches.
"""
from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import build_icassp_2022_model_path, FilenameSuffix
ICASSP_2022_MODEL_PATH = build_icassp_2022_model_path(FilenameSuffix.onnx)

path = next(Path("stems").glob("*vocals*.mp3"))
out = Path("midi")
predict_and_save(
    [str(path)],
    str(out),
    save_midi=True,
    sonify_midi=False,
    save_model_outputs=False,
    save_notes=False,
    model_or_model_path=ICASSP_2022_MODEL_PATH,
    onset_threshold=0.4,        # lower → more notes detected
    frame_threshold=0.25,        # lower → notes extend longer
    minimum_note_length=70,      # ms
    minimum_frequency=100,
    maximum_frequency=1500,
    multiple_pitch_bends=False,
    melodia_trick=False,         # KEY: disable melody bias so harmonies survive
)
# rename produced file
produced = list(out.glob(f"{path.stem}_basic_pitch.mid"))
if produced:
    dest = out / "vocals_poly.mid"
    produced[0].rename(dest)
    print(f"wrote {dest}")

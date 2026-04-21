"""Voice-convert our synthesized vocal line to a target voice using
an RVC model fine-tuned on target-voice audio.

Usage:
    python synth_vocals_rvc.py \
        --input rvc_training/source/vocals_synth.wav \
        --output runs/<id>/audio/vocals_rvc.wav \
        --model seann_bowe \
        [--f0up 0]
"""
import argparse
import os
import shutil
import sys
from pathlib import Path


def _parse_our_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--model",  default="seann_bowe")
    ap.add_argument("--f0up", type=int, default=0)
    ap.add_argument("--f0method", default="rmvpe",
                    choices=["rmvpe", "harvest", "pm", "crepe"])
    ap.add_argument("--index_rate", type=float, default=0.66)
    return ap.parse_args()


# Parse our CLI BEFORE importing RVC modules (which shadow sys.argv).
_args = _parse_our_args()
sys.argv = sys.argv[:1]

ROOT = Path(__file__).parent.resolve()
RVC = ROOT / "rvc_repo"


def find_trained_checkpoint(exp_dir: Path) -> Path | None:
    # RVC saves to logs/<exp>/G_<step>.pth; often a sentinel G_2333333.pth
    cands = sorted(exp_dir.glob("G_*.pth"),
                   key=lambda p: int(p.stem.split("_")[1]))
    return cands[-1] if cands else None


def main():
    exp_dir = RVC / "logs" / _args.model
    ckpt = find_trained_checkpoint(exp_dir)
    if ckpt is None:
        raise FileNotFoundError(f"no G_*.pth in {exp_dir}. Train first.")
    print(f"using checkpoint: {ckpt}")

    weights_dir = RVC / "assets" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    model_pth = weights_dir / f"{_args.model}.pth"

    # Training checkpoints have keys like {'model', 'iteration', 'optimizer'};
    # inference expects an "extracted" small model with 'weight', 'config',
    # etc. Call extract_small_model to package.
    old_cwd_pre = os.getcwd()
    os.chdir(str(RVC))
    sys.path.insert(0, str(RVC))
    from infer.lib.train.process_ckpt import extract_small_model
    res = extract_small_model(
        str(ckpt), _args.model, "48k", 1, f"fine-tune of {_args.model}", "v2"
    )
    os.chdir(old_cwd_pre)
    if res != "Success.":
        raise RuntimeError(f"extract_small_model failed:\n{res}")
    print(f"packaged inference model: {model_pth}")

    index_path = ""
    index_candidates = list(exp_dir.glob("added_*.index"))
    if index_candidates:
        index_path = str(index_candidates[0])

    os.chdir(str(RVC))
    sys.path.insert(0, str(RVC))

    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

    # RVC's .env defines these paths; set them explicitly so we don't depend
    # on dotenv loading at the right moment.
    os.environ["weight_root"]     = "assets/weights"
    os.environ["rmvpe_root"]      = "assets/rmvpe"
    os.environ["index_root"]      = "logs"
    os.environ["weight_uvr5_root"] = "assets/uvr5_weights"

    from configs.config import Config
    from infer.modules.vc.modules import VC
    from scipy.io import wavfile

    config = Config()
    vc = VC(config)
    vc.get_vc(f"{_args.model}.pth")

    abs_in = _args.input if _args.input.is_absolute() else (ROOT / _args.input).resolve()
    _args.output.parent.mkdir(parents=True, exist_ok=True)
    abs_out = _args.output if _args.output.is_absolute() else (ROOT / _args.output).resolve()

    _, wav_opt = vc.vc_single(
        0,                     # sid
        str(abs_in),           # input_path
        _args.f0up,            # f0up_key
        None,                  # f0_file
        _args.f0method,        # f0_method
        index_path,            # file_index
        None,                  # file_index2
        _args.index_rate,      # index_rate
        3,                     # filter_radius
        0,                     # resample_sr
        1,                     # rms_mix_rate
        0.33,                  # protect
    )
    sr, wav = wav_opt
    wavfile.write(str(abs_out), sr, wav)
    print(f"wrote {abs_out} ({sr} Hz, {len(wav)/sr:.1f}s)")


if __name__ == "__main__":
    main()

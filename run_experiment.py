"""Orchestrate one transcription experiment run.

Does:
  1. Run `assemble_v4.py` to produce Haunted.{musicxml,pdf} + midi/
  2. Render PDF via LilyPond (musicxml2ly + lilypond)
  3. Copy artifacts + git-diff snapshot into runs/YYYY-MM-DD_NNN_<slug>/
  4. Invoke eval.py on the produced musicxml
  5. Seed notes.md with the human-feedback template
  6. Append a row to runs/INDEX.md (creates the file if absent)
  7. If --compare <prev_run_id>, print a metric delta table

Usage:
  run_experiment.py --slug baseline --hypothesis "v4 pipeline unchanged"
  run_experiment.py --slug tie-merge --hypothesis "..." --compare 2026-04-20_001_baseline
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
RUNS_DIR = ROOT / "runs"

PYTHON = str(ROOT / ".venv" / "bin" / "python")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command and stream output; raise on failure."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(ROOT), check=True,
                          stdout=sys.stdout, stderr=sys.stderr, **kw)


def run_assemble():
    """Run assemble_v4.py; produces Haunted.musicxml + midi/combined.mid."""
    run([PYTHON, "assemble_v4.py"])


def run_lilypond_pdf():
    """Convert the musicxml to PDF via musicxml2ly + lilypond; apply the
    chord-quality fix for musicxml2ly's ':5' / ':m5' bug."""
    # clean previous lily output
    for f in ("Haunted.ly", "Haunted.pdf"):
        Path(f).unlink(missing_ok=True)
    subprocess.run(["musicxml2ly", "Haunted.musicxml", "-o", "Haunted.ly"],
                   cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    ly = Path("Haunted.ly").read_text()
    ly = re.sub(r":m5\b", ":m", ly)
    ly = re.sub(r":5\b",  "",   ly)
    Path("Haunted.ly").write_text(ly)
    subprocess.run(["lilypond", "--pdf", "-o", "Haunted", "Haunted.ly"],
                   cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)


def next_run_id(slug: str, today: str) -> str:
    existing = [p.name for p in RUNS_DIR.glob(f"{today}_*")]
    nums = []
    for name in existing:
        m = re.match(rf"{today}_(\d+)_", name)
        if m: nums.append(int(m.group(1)))
    n = (max(nums) if nums else 0) + 1
    return f"{today}_{n:03d}_{slug}"


def gather_git_diff() -> str:
    try:
        out = subprocess.run(["git", "diff", "HEAD", "--"],
                             cwd=str(ROOT), check=True, capture_output=True, text=True)
        return out.stdout
    except subprocess.CalledProcessError:
        return ""


def script_shas() -> dict[str, str]:
    """SHA-1 of each pipeline script, for reproducibility fingerprints."""
    import hashlib
    scripts = ["assemble_v4.py", "transcribe_stems.py", "transcribe_drums.py",
               "transcribe_vocals_poly.py", "vocal_melody.py", "vocal_harmony.py",
               "analyze_grid.py", "chord_detect.py", "midi_utils.py"]
    out = {}
    for s in scripts:
        p = ROOT / s
        if p.exists():
            out[s] = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
    return out


NOTES_TEMPLATE = """# Run {run_id} — {hypothesis}

## Metrics summary

{metrics_md}

## What I heard (listening A/B vs stems)
- Vocals:
- Piano:
- Guitar:
- Bass:
- Drums:

## Regressions vs previous run
-

## Try next
-

## Keep / revert
"""


def append_index(run_id: str, hypothesis: str, metrics: dict):
    idx = RUNS_DIR / "INDEX.md"
    if not idx.exists():
        header = ("# Transcription runs\n\n"
                  "Newest first. `★` = worth listening to (human-rated). "
                  "See each run's `notes.md` for details.\n\n"
                  "| run_id | hypothesis | chroma | onset_F1 | note_F1 | overall | ★ | link |\n"
                  "|---|---|---:|---:|---:|---:|:-:|---|\n")
        idx.write_text(header)

    # Compute mix-level averages to surface in the table
    per = metrics["per_stem"]
    def avg(k):
        vals = [m[k] for s, m in per.items() if s != "_mix" and not _nan(m[k])]
        return sum(vals)/len(vals) if vals else float("nan")
    chroma = avg("chroma_cosine"); onset = avg("onset_f1"); note = avg("note_f1")
    overall = metrics["overall"]
    row = (f"| {run_id} | {hypothesis} | {chroma:.3f} | {onset:.3f} | "
           f"{note:.3f} | **{overall:.3f}** |  | [dir](./{run_id}/) |\n")
    # Insert row right after the runs-table separator line. The file may
    # contain other tables (methodology table etc.) with "|---" separators,
    # so anchor specifically under the "## Runs" heading.
    lines = idx.read_text().splitlines(keepends=True)
    runs_hdr = next((i for i, l in enumerate(lines) if l.strip() == "## Runs"), None)
    if runs_hdr is not None:
        sep_idx = next((i for i, l in enumerate(lines[runs_hdr:], start=runs_hdr)
                        if l.startswith("|---")), None)
    else:
        sep_idx = next((i for i, l in enumerate(lines) if l.startswith("|---")), None)
    if sep_idx is not None:
        lines.insert(sep_idx + 1, row)
    else:
        lines.append(row)
    idx.write_text("".join(lines))


def _nan(x):
    return isinstance(x, float) and x != x


def compare_runs(current_id: str, prev_id: str):
    cur = json.loads((RUNS_DIR / current_id / "metrics.json").read_text())
    prev = json.loads((RUNS_DIR / prev_id / "metrics.json").read_text())
    keys = sorted(set(cur["per_stem"]) | set(prev["per_stem"]))
    print(f"\n=== Delta vs {prev_id} ===")
    print(f"{'stem':<10} {'chroma Δ':>10} {'onset_F1 Δ':>12} {'note_F1 Δ':>11} {'composite Δ':>13}")
    for k in keys:
        a = cur["per_stem"].get(k, {})
        b = prev["per_stem"].get(k, {})
        def d(m):
            av = a.get(m); bv = b.get(m)
            if av is None or bv is None or _nan(av) or _nan(bv): return "    —    "
            return f"{av - bv:+.3f}"
        print(f"{k:<10} {d('chroma_cosine'):>10} {d('onset_f1'):>12} "
              f"{d('note_f1'):>11} {d('composite'):>13}")
    print(f"Overall Δ: {cur['overall'] - prev['overall']:+.3f}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="short kebab slug, e.g. 'baseline'")
    ap.add_argument("--hypothesis", required=True, help="1-line description")
    ap.add_argument("--compare", help="previous run_id to diff metrics against")
    ap.add_argument("--skip-assemble", action="store_true",
                    help="reuse current Haunted.musicxml without rerunning pipeline")
    ap.add_argument("--vocals-wav", type=Path, default=None,
                    help="pass-through: RVC or other pre-rendered vocal WAV")
    args = ap.parse_args()

    today = date.today().isoformat()
    run_id = next_run_id(args.slug, today)
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== Experiment run {run_id} ===")

    # 1-2. Build the score + PDF
    if not args.skip_assemble:
        print("[1/5] running assemble_v4.py")
        run_assemble()
        print("[2/5] rendering PDF via LilyPond")
        run_lilypond_pdf()

    # 3. Snapshot artifacts + git diff + script SHAs
    print("[3/5] snapshotting artifacts")
    for f in ("Haunted.musicxml", "Haunted.pdf"):
        if Path(f).exists():
            shutil.copy(f, run_dir / f)
    midi_copy = run_dir / "midi"
    midi_copy.mkdir(exist_ok=True)
    for f in Path("midi").glob("*.mid"):
        shutil.copy(f, midi_copy / f.name)

    (run_dir / "diff.patch").write_text(gather_git_diff())
    import yaml
    (run_dir / "config.yaml").write_text(yaml.safe_dump({
        "run_id": run_id,
        "hypothesis": args.hypothesis,
        "date": today,
        "script_shas": script_shas(),
    }))

    # 4. Evaluate
    print("[4/5] running eval.py")
    eval_cmd = [PYTHON, "eval.py", str(run_dir / "Haunted.musicxml"), str(run_dir)]
    if args.vocals_wav is not None:
        eval_cmd += ["--vocals-wav", str(args.vocals_wav)]
    run(eval_cmd)
    metrics = json.loads((run_dir / "metrics.json").read_text())

    # 5. Seed notes.md, append to INDEX.md
    print("[5/5] writing notes.md, updating INDEX.md")
    metrics_md = (run_dir / "metrics.md").read_text()
    (run_dir / "notes.md").write_text(NOTES_TEMPLATE.format(
        run_id=run_id, hypothesis=args.hypothesis, metrics_md=metrics_md))
    append_index(run_id, args.hypothesis, metrics)

    if args.compare:
        compare_runs(run_id, args.compare)

    print(f"\nDone. Run dir: {run_dir}")
    print(f"Open: runs/INDEX.md  |  {run_dir}/notes.md  |  {run_dir}/Haunted.pdf")


if __name__ == "__main__":
    main()

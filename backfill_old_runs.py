"""One-shot utility to retroactively create runs/ entries for pre-harness
commits (before `ce9b8e1` added the eval harness).

For each commit: extract Haunted.{musicxml,pdf} + midi/*.mid into
runs/<date>_0X_<slug>/, run eval.py, seed notes.md.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
PYTHON = str(ROOT / ".venv" / "bin" / "python")
RUNS_DIR = ROOT / "runs"

# (sha, short_slug, date, hypothesis)
COMMITS = [
    ("8dbcc0b", "0a_draft1",  "2026-04-20",
     "First auto-transcription (basic-pitch on Demucs-v3 stems, float-quantize "
     "via pretty_midi → music21). No chord symbols, no effect matching."),
    ("8fbd2ac", "0b_clean",   "2026-04-20",
     "First cleanup pass: chord detection added, basic post-quantize cleanup."),
    ("1262f93", "0c_max",     "2026-04-20",
     "Piano RH/LH split, CREPE vocal melody, chord filter first introduced."),
    ("80245f0", "0d_xml-fix", "2026-04-20",
     "MusicXML structural fixes + vocal polyphony merge."),
]


def run(cmd, check=True, capture=False, cwd=None):
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd or ROOT), check=check,
                          capture_output=capture, text=True)


def git_show_blob(sha: str, path: str) -> bytes:
    r = subprocess.run(["git", "show", f"{sha}:{path}"],
                       cwd=str(ROOT), check=True, capture_output=True)
    return r.stdout


def git_list_tree(sha: str, prefix: str) -> list[str]:
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha],
                       cwd=str(ROOT), check=True, capture_output=True, text=True)
    return [p for p in r.stdout.splitlines() if p.startswith(prefix)]


NOTES_TEMPLATE = """# Run {run_id} — {hypothesis}

Retroactive eval of git commit `{sha}` ({date}). Artifacts extracted from git
tree; metrics computed with current `eval.py` (post-hoc, so scoring pipeline
did not exist at the time of this commit).

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


def main():
    for sha, slug, date, hypothesis in COMMITS:
        run_id = f"{date}_{slug}"
        rd = RUNS_DIR / run_id
        if (rd / "metrics.json").exists():
            print(f"skip {run_id}: already has metrics.json")
            continue
        print(f"\n=== {run_id}  ({sha}) ===")
        rd.mkdir(parents=True, exist_ok=True)

        # 1. extract artifacts
        for p in ("Haunted.musicxml", "Haunted.pdf"):
            try:
                blob = git_show_blob(sha, p)
                (rd / p).write_bytes(blob)
            except subprocess.CalledProcessError:
                print(f"  {p} not in {sha}, skipping")
        midi_dir = rd / "midi"
        midi_dir.mkdir(exist_ok=True)
        for p in git_list_tree(sha, "midi/"):
            if not p.endswith(".mid"):
                continue
            blob = git_show_blob(sha, p)
            (midi_dir / Path(p).name).write_bytes(blob)

        # 2. seed config.yaml
        import yaml
        (rd / "config.yaml").write_text(yaml.safe_dump({
            "run_id": run_id,
            "hypothesis": hypothesis,
            "date": date,
            "source_commit": sha,
            "retroactive": True,
        }))

        # 3. run eval on the extracted musicxml
        xml = rd / "Haunted.musicxml"
        if not xml.exists():
            print(f"  no musicxml for {sha}, skipping eval")
            continue
        run([PYTHON, "eval.py", str(xml), str(rd)])

        # 4. seed notes.md
        metrics_md = (rd / "metrics.md").read_text()
        (rd / "notes.md").write_text(NOTES_TEMPLATE.format(
            run_id=run_id, hypothesis=hypothesis, sha=sha, date=date,
            metrics_md=metrics_md))

    print("\nall done.")


if __name__ == "__main__":
    main()

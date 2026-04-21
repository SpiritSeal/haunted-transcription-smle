"""Shared utilities for the transcription pipeline.

Functions:
  stem_paths()                      — resolve the stem mp3s from stems/
  merge_tied_notes(notes, gap_ms)   — collapse same-pitch fragments
  render_per_track(pm, out_dir,...) — MIDI → per-instrument WAVs via fluidsynth
  validate_musicxml(path)           — assert durations sum correctly per measure
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import subprocess
import shutil

import numpy as np
import pretty_midi
import soundfile as sf


# ---- stem discovery -----------------------------------------------------

def stem_paths(stems_dir: str | Path = "stems") -> dict[str, Path]:
    """Map canonical stem names to their mp3 paths on disk."""
    d = Path(stems_dir)
    names = ["vocals", "piano", "guitar", "bass", "drums", "other"]
    out = {}
    for n in names:
        hits = list(d.glob(f"*{n}*.mp3"))
        if hits:
            out[n] = hits[0]
    return out


def mix_path() -> Path | None:
    """Return the original mix mp3 at project root, or None."""
    hits = list(Path(".").glob("*.mp3"))
    # Exclude the stems (those live in stems/)
    hits = [p for p in hits if p.parent.name != "stems"]
    return hits[0] if hits else None


# ---- note-merging utility ----------------------------------------------

def merge_tied_notes(notes, gap_ms: float = 80.0):
    """Collapse consecutive same-pitch pretty_midi.Note objects whose gap is
    below `gap_ms`. Useful for stitching basic-pitch's fragmented sustains.

    Accepts either a list of pretty_midi.Note objects OR a list of
    [start, end, pitch, velocity] quadruples (in seconds). Returns the same
    shape you passed in."""
    if not notes:
        return notes
    is_pm = hasattr(notes[0], "pitch")
    gap_s = gap_ms / 1000.0

    if is_pm:
        by_pitch: dict[int, list[pretty_midi.Note]] = {}
        for n in sorted(notes, key=lambda x: (x.pitch, x.start)):
            lst = by_pitch.setdefault(n.pitch, [])
            if lst and n.start - lst[-1].end <= gap_s:
                lst[-1].end = max(lst[-1].end, n.end)
                lst[-1].velocity = max(lst[-1].velocity, n.velocity)
            else:
                lst.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch,
                                            start=n.start, end=n.end))
        out = [n for lst in by_pitch.values() for n in lst]
        return sorted(out, key=lambda x: (x.start, x.pitch))
    else:
        by_pitch: dict[int, list[list]] = {}
        for s, e, p, v in sorted(notes, key=lambda x: (x[2], x[0])):
            lst = by_pitch.setdefault(p, [])
            if lst and s - lst[-1][1] <= gap_s:
                lst[-1][1] = max(lst[-1][1], e)
                lst[-1][3] = max(lst[-1][3], v)
            else:
                lst.append([s, e, p, v])
        return sorted([x for xs in by_pitch.values() for x in xs],
                      key=lambda x: (x[0], x[2]))


# ---- rendering via fluidsynth ------------------------------------------

DEFAULT_SF2 = Path("assets/FluidR3.sf3")

# For each score-part name, pick a GM percussion channel? No — we only have
# pitched parts in the score; drums are in the playback midi only.
# Mapping from track name → the stem it should be compared against.
TRACK_TO_STEM = {
    "Vocals":   "vocals",
    "Piano RH": "piano",
    "Piano LH": "piano",
    "Guitar":   "guitar",
    "Bass":     "bass",
    "Drums":    "drums",
}


def _fluidsynth_render(mid_path: Path, wav_path: Path, sf2: Path, sr: int = 44100):
    """Render a MIDI file to WAV with the fluidsynth CLI. This is more robust
    than pretty_midi's built-in fluidsynth call, which requires pyfluidsynth."""
    cmd = [
        "fluidsynth", "-ni", "-F", str(wav_path), "-r", str(sr),
        "-q",   # quiet
        str(sf2), str(mid_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)


def render_per_track(pm: pretty_midi.PrettyMIDI, out_dir: Path,
                     sf2: Path = DEFAULT_SF2, sr: int = 44100,
                     also_mix: bool = True) -> dict[str, Path]:
    """Render each instrument in `pm` to its own WAV file in `out_dir`.
    Returns {track_name: wav_path}. If `also_mix` is True, also writes mix.wav."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    # Per-track renders
    for inst in pm.instruments:
        solo = pretty_midi.PrettyMIDI(initial_tempo=pm.get_tempo_changes()[1][0] if len(pm.get_tempo_changes()[1]) else 120)
        new_inst = pretty_midi.Instrument(program=inst.program, is_drum=inst.is_drum,
                                          name=inst.name)
        new_inst.notes = list(inst.notes)
        solo.instruments.append(new_inst)
        name = inst.name or f"track{len(results)}"
        safe = name.replace(" ", "_").replace("/", "_").lower()
        mid_tmp = out_dir / f"_{safe}.mid"
        wav_out = out_dir / f"{safe}.wav"
        solo.write(str(mid_tmp))
        _fluidsynth_render(mid_tmp, wav_out, sf2, sr)
        mid_tmp.unlink()
        results[name] = wav_out

    # Combined mix
    if also_mix:
        mid_tmp = out_dir / "_mix.mid"
        pm.write(str(mid_tmp))
        _fluidsynth_render(mid_tmp, out_dir / "mix.wav", sf2, sr)
        mid_tmp.unlink()
        results["_mix"] = out_dir / "mix.wav"

    return results


# ---- musicxml validation ------------------------------------------------

def validate_musicxml(path: str | Path) -> tuple[bool, list[str]]:
    """Return (ok, issues). Fast structural checks: XML well-formedness, all
    parts have same measure count, every measure's note durations sum to
    divisions*4 (for 4/4)."""
    import xml.etree.ElementTree as ET
    issues: list[str] = []
    try:
        tree = ET.parse(str(path))
    except ET.ParseError as e:
        return False, [f"XML parse error: {e}"]

    root = tree.getroot()
    parts = root.findall("part")
    if not parts:
        return False, ["no <part> elements found"]

    measure_counts = []
    for part in parts:
        divs_elem = part.find(".//divisions")
        divs = int(divs_elem.text) if divs_elem is not None else 480
        expected = divs * 4
        measures = part.findall("measure")
        measure_counts.append(len(measures))
        for m in measures:
            voice_durs: dict[str, int] = {}
            for n in m.findall("note"):
                if n.find("chord") is not None:
                    continue
                v = n.find("voice")
                voice = v.text if v is not None else "1"
                d = n.find("duration")
                dur = int(d.text) if d is not None else 0
                voice_durs[voice] = voice_durs.get(voice, 0) + dur
            for voice, dur in voice_durs.items():
                if dur != expected:
                    issues.append(
                        f"part {part.get('id','?')[:8]} m{m.get('number')} "
                        f"voice {voice}: {dur} ≠ {expected}"
                    )

    if len(set(measure_counts)) > 1:
        issues.append(f"part measure counts differ: {measure_counts}")
    return len(issues) == 0, issues

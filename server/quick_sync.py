"""Conservative preliminary subtitle alignment from a short local media sample."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import time
from datetime import timedelta
from pathlib import Path

import srt

from cueflow.engine import SyncError, SyncRequest, ffmpeg_directory, read_subtitles, synchronize

MAX_OFFSET = 15
EDGE_MARGIN = MAX_OFFSET + 0.5
MIN_CUES = 6
MAX_SPREAD = 0.5


def sample_duration(media: Path) -> float:
    suffix = ".exe" if os.name == "nt" else ""
    try:
        probe = subprocess.run(
            [str(ffmpeg_directory() / ("ffprobe" + suffix)), "-v", "error",
             "-show_entries", "format=duration", "-of", "json", str(media)],
            capture_output=True, text=True, timeout=15, check=True,
        )
        duration = float(json.loads(probe.stdout)["format"]["duration"])
    except (subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise SyncError("quick_sample_invalid") from exc
    if not math.isfinite(duration) or not 45 <= duration <= 180:
        raise SyncError("quick_sample_duration")
    return duration


def select_cues(entries: list[srt.Subtitle], start: float, duration: float) -> list[srt.Subtitle]:
    """Leave enough space for every candidate shift without clipping evidence."""
    selected = [
        srt.Subtitle(cue.index, cue.start - timedelta(seconds=start),
                     cue.end - timedelta(seconds=start), cue.content, cue.proprietary)
        for cue in entries
        if cue.start.total_seconds() >= start + EDGE_MARGIN
        and cue.end.total_seconds() <= start + duration - EDGE_MARGIN
    ]
    if len(selected) < MIN_CUES:
        raise SyncError("quick_insufficient_cues")
    halves = (selected[:len(selected) // 2], selected[len(selected) // 2:])
    if any((part[-1].end - part[0].start).total_seconds() < 12 for part in halves):
        raise SyncError("quick_insufficient_span")
    return selected


def speech_evidence(media: Path, cues: list[srt.Subtitle], offset: float) -> dict:
    """Check speech presence and contrast, independent of the aligner's best score."""
    import numpy as np
    from ffsubsync.speech_transformers import VideoSpeechTransformer

    speech = VideoSpeechTransformer(
        vad="webrtc", sample_rate=100, frame_rate=48000, non_speech_label=0,
        ffmpeg_path=str(ffmpeg_directory()), ref_stream="0:a:0",
    ).fit_transform(str(media))
    speech = np.asarray(speech) > 0.5
    if len(speech) == 0 or speech.sum() < 300:
        raise SyncError("quick_insufficient_speech")
    mask = np.zeros(len(speech), dtype=bool)
    for cue in cues:
        begin = max(0, round((cue.start.total_seconds() + offset) * 100))
        end = min(len(speech), round((cue.end.total_seconds() + offset) * 100))
        mask[begin:end] = True
    begin = max(0, round((cues[0].start.total_seconds() - MAX_OFFSET) * 100))
    end = min(len(speech), round((cues[-1].end.total_seconds() + MAX_OFFSET) * 100))
    region = np.zeros(len(speech), dtype=bool)
    region[begin:end] = True
    outside = region & ~mask
    if mask.sum() < 300 or outside.sum() < 300:
        raise SyncError("quick_insufficient_contrast")
    on_cues, off_cues = float(speech[mask].mean()), float(speech[outside].mean())
    if on_cues < 0.3 or on_cues - off_cues < 0.1:
        raise SyncError("quick_insufficient_contrast")
    return {"speech_seconds": round(float(speech.sum()) / 100, 2),
            "speech_on_cues": round(on_cues, 3), "speech_off_cues": round(off_cues, 3)}


def crop_region(media: Path, cues: list[srt.Subtitle], duration: float,
                output: Path) -> tuple[Path, list[srt.Subtitle]]:
    """Exclude the other region's speech when checking independent cue groups."""
    begin = max(0.0, cues[0].start.total_seconds() - EDGE_MARGIN)
    end = min(duration, cues[-1].end.total_seconds() + EDGE_MARGIN)
    suffix = ".exe" if os.name == "nt" else ""
    try:
        subprocess.run(
            [str(ffmpeg_directory() / ("ffmpeg" + suffix)), "-v", "error", "-nostdin",
             "-i", str(media), "-ss", str(begin), "-t", str(end - begin),
             "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(output)],
            capture_output=True, timeout=30, check=True,
        )
    except subprocess.SubprocessError as exc:
        raise SyncError("quick_sample_invalid") from exc
    return output, [srt.Subtitle(cue.index, cue.start - timedelta(seconds=begin),
                                cue.end - timedelta(seconds=begin), cue.content,
                                cue.proprietary) for cue in cues]


def shifted_subtitles(entries: list[srt.Subtitle], offset: float, duration: float) -> str:
    """Preserve every cue and its order; refuse cues entirely outside the video."""
    shifted = []
    for cue in entries:
        begin = max(0.0, cue.start.total_seconds() + offset)
        end = min(duration, cue.end.total_seconds() + offset)
        begin_ms = round(begin * 1000)
        end_ms = min(math.floor(duration * 1000), round(end * 1000))
        if begin_ms >= end_ms:
            raise SyncError("quick_cue_bounds")
        shifted.append(srt.Subtitle(
            cue.index, timedelta(milliseconds=begin_ms),
            timedelta(milliseconds=end_ms), cue.content, cue.proprietary))
    return srt.compose(shifted, reindex=False)


def quick_synchronize(media: str, subtitle: str, sample_start: float,
                      full_duration: float, output: str) -> dict:
    started = time.monotonic()
    media_path, source, destination = map(lambda value: Path(value).resolve(),
                                          (media, subtitle, output))
    if not media_path.is_file() or not source.is_file():
        raise SyncError("input_missing")
    if destination in (media_path, source) or not destination.parent.is_dir():
        raise SyncError("quick_output_invalid")
    if (not math.isfinite(sample_start) or not math.isfinite(full_duration)
            or sample_start < 0 or full_duration <= sample_start):
        raise SyncError("quick_timeline_invalid")
    duration = sample_duration(media_path)
    if sample_start + duration > full_duration + 0.5:
        raise SyncError("quick_timeline_invalid")
    _, entries, _, _ = read_subtitles(source, "auto", False)
    selected = select_cues(entries, sample_start, duration)
    groups = (selected, selected[:len(selected) // 2], selected[len(selected) // 2:])
    offsets = []
    with tempfile.TemporaryDirectory(prefix="cueflow-quick-") as work:
        for index, cues in enumerate(groups):
            reference = media_path
            if index:
                reference, cues = crop_region(media_path, cues, duration,
                                               Path(work) / f"region-{index}.wav")
            subset = Path(work) / f"sample-{index}.srt"
            subset.write_text(srt.compose(cues, reindex=False), encoding="utf-8")
            result = synchronize(SyncRequest(
                str(reference), str(subset), work, repair_encoding=False,
                max_offset=MAX_OFFSET, fix_framerate=False,
            ))
            offset, scale = float(result["offset"]), float(result["scale"])
            if (not math.isfinite(offset) or not math.isfinite(scale)
                    or abs(scale - 1) > 0.000001 or abs(offset) >= MAX_OFFSET - 0.5):
                raise SyncError("quick_uncertain_offset")
            offsets.append(offset)
    spread = max(offsets) - min(offsets)
    if spread > MAX_SPREAD:
        raise SyncError("quick_unstable_offset")
    offset = offsets[0]
    evidence = speech_evidence(media_path, selected, offset)
    text = shifted_subtitles(entries, offset, full_duration)
    # Replace only after all checks succeed; a failed sample leaves output intact.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=destination.parent, prefix=".quick-",
                                         suffix=".srt", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "status": "preliminary", "sync_status": "sampled", "preliminary": True,
        "output": str(destination), "offset": offset, "scale": 1,
        "cues": len(entries), "sample_cues": len(selected),
        "sample_start": sample_start, "sample_duration": duration,
        "elapsed": round(time.monotonic() - started, 2),
        "evidence": {"offsets": offsets, "spread": round(spread, 3), **evidence},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media")
    parser.add_argument("subtitle")
    parser.add_argument("sample_start", type=float)
    parser.add_argument("full_duration", type=float)
    parser.add_argument("output")
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        result = quick_synchronize(args.media, args.subtitle, args.sample_start,
                                   args.full_duration, args.output)
    except SyncError as exc:
        result = {"status": "waiting_full", "preliminary": True, "error": exc.code,
                  "elapsed": round(time.monotonic() - started, 2)}
    except Exception:
        result = {"status": "waiting_full", "preliminary": True, "error": "quick_failed",
                  "elapsed": round(time.monotonic() - started, 2)}
    print("CUEFLOW_QUICK_RESULT " + json.dumps(result, ensure_ascii=True), flush=True)
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())

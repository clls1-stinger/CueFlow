"""File-safe adapter around ffsubsync. This module has no GUI dependency."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import chardet
import ftfy
import srt


class SyncError(Exception):
    """An error the interface can translate without parsing exception text."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclasses.dataclass
class SyncRequest:
    video: str
    subtitle: str
    output_dir: str
    encoding: str = "auto"
    repair_encoding: bool = True
    max_offset: int = 300
    fix_framerate: bool = True


def ffmpeg_directory() -> Path:
    """Prefer the release's replaceable binaries; source installs may use PATH."""
    suffix = ".exe" if os.name == "nt" else ""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    candidates = [root / "vendor" / "ffmpeg"]
    if override := os.environ.get("CUEFLOW_FFMPEG_DIR"):
        candidates.insert(0, Path(override))
    for folder in candidates:
        if all((folder / (name + suffix)).is_file() for name in ("ffmpeg", "ffprobe")):
            return folder
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg and ffprobe and Path(ffmpeg).parent == Path(ffprobe).parent:
        return Path(ffmpeg).parent
    raise SyncError("ffmpeg_missing")


def read_subtitles(path: Path, encoding: str, repair: bool) -> tuple[str, list, str, bool]:
    raw = path.read_bytes()
    if not raw or len(raw) > 20_000_000:
        raise SyncError("subtitle_invalid")
    if encoding == "auto":
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        else:
            try:
                raw.decode("utf-8-sig")
                encoding = "utf-8-sig"
            except UnicodeDecodeError:
                encoding = chardet.detect(raw).get("encoding") or "cp1252"
    try:
        text = raw.decode(encoding)
    except (UnicodeError, LookupError) as exc:
        raise SyncError("encoding", str(exc)) from exc
    original = text
    if repair:
        # Encoding repair only: do not rewrite, translate, unescape HTML, or remove styling.
        text = ftfy.fix_encoding(text)
    text = text.lstrip("\ufeff")
    try:
        entries = list(srt.parse(text))
    except srt.SRTParseError as exc:
        raise SyncError("subtitle_invalid", str(exc)) from exc
    if not entries or any(x.start >= x.end or x.start.total_seconds() < 0 for x in entries):
        raise SyncError("subtitle_invalid")
    if any(a.start > b.start for a, b in zip(entries, entries[1:])):
        raise SyncError("subtitle_order")
    return text, entries, encoding, text != original


def save_unique(folder: Path, stem: str, text: str) -> Path:
    """Exclusive creation: even another running instance cannot overwrite a file."""
    for i in range(10_000):
        suffix = "" if i == 0 else f".{i}"
        path = folder / f"{stem}.synced{suffix}.srt"
        try:
            handle = path.open("x", encoding="utf-8", newline="\n")
        except FileExistsError:
            continue
        try:
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path
    raise SyncError("output_full")


def synchronize(request: SyncRequest, notify=lambda event: None) -> dict:
    import numpy as np
    from ffsubsync.ffsubsync import make_parser, run
    from ffsubsync.speech_transformers import VideoSpeechTransformer

    started = time.monotonic()
    video, subtitle, output_dir = (
        Path(request.video).resolve(),
        Path(request.subtitle).resolve(),
        Path(request.output_dir).resolve(),
    )
    if not video.is_file() or not subtitle.is_file() or video == subtitle:
        raise SyncError("input_missing")
    if not request.output_dir or not output_dir.is_dir():
        raise SyncError("output_missing")
    if not 1 <= request.max_offset <= 3600:
        raise SyncError("offset_invalid")
    ffmpeg_dir = ffmpeg_directory()
    text, entries, encoding, repaired = read_subtitles(
        subtitle, request.encoding, request.repair_encoding
    )
    notify({"phase": "analyzing"})
    with tempfile.TemporaryDirectory(prefix="cueflow-") as workspace:
        source = Path(workspace) / "source.srt"
        aligned = Path(workspace) / "aligned.srt"
        # Preserve CRLF input without Windows expanding it to CRCRLF.
        source.write_text(text, encoding="utf-8", newline="\n")
        arguments = [
            str(video),
            "-i",
            str(source),
            "-o",
            str(aligned),
            "--encoding",
            "utf-8",
            "--output-encoding",
            "utf-8",
            "--vad",
            "webrtc",
            "--reference-stream",
            "0:a:0",
            "--ffmpeg-path",
            str(ffmpeg_dir),
            "--max-offset-seconds",
            str(request.max_offset),
            "--strict",
            "--log-dir-path",
            workspace,
        ]
        if not request.fix_framerate:
            arguments.append("--no-fix-framerate")

        def progress(info):
            # ffsubsync's progress dataclass may extend its fields in future versions.
            data = info._asdict() if hasattr(info, "_asdict") else {}
            notify({"phase": "analyzing", "progress": data})

        speech = VideoSpeechTransformer(
            vad="webrtc",
            sample_rate=100,
            frame_rate=48000,
            non_speech_label=0,
            ffmpeg_path=str(ffmpeg_dir),
            ref_stream="0:a:0",
            progress_handler=progress,
        ).fit_transform(str(video))
        if len(speech) < 100 or np.count_nonzero(speech) < 50:
            raise SyncError("no_speech")
        reference = Path(workspace) / "speech.npz"
        np.savez_compressed(reference, speech=speech)
        arguments[0] = str(reference)
        notify({"phase": "aligning"})
        result = run(make_parser().parse_args(arguments))
        if result.get("retval") or not result.get("sync_was_successful") or not aligned.exists():
            raise SyncError("alignment_failed")
        notify({"phase": "saving"})
        synced = aligned.read_text(encoding="utf-8")
        output_entries = list(srt.parse(synced))
        if len(output_entries) != len(entries):
            raise SyncError("cue_loss")
        if any(a.content != b.content for a, b in zip(entries, output_entries)):
            raise SyncError("cue_loss")
        if any(
            s.start.total_seconds() < 0
            or s.start >= s.end
            or s.end.total_seconds() > len(speech) / 100 + 0.5
            for s in output_entries
        ):
            raise SyncError("alignment_failed")
        path = save_unique(output_dir, video.stem, synced)
    return {
        "output": str(path),
        "cues": len(entries),
        "encoding": encoding,
        "encoding_repaired": repaired,
        "offset": result["offset_seconds"],
        "scale": result["framerate_scale_factor"],
        "elapsed": round(time.monotonic() - started, 2),
    }


def worker(request_file: str) -> int:
    def emit(data):
        print("CUEFLOW_EVENT " + json.dumps(data, ensure_ascii=True), flush=True)

    try:
        request = SyncRequest(**json.loads(Path(request_file).read_text(encoding="utf-8")))
        emit({"result": synchronize(request, emit)})
        return 0
    except SyncError as exc:
        emit({"error": exc.code, "detail": exc.detail})
    except Exception as exc:
        emit({"error": "unexpected", "detail": str(exc)})
    return 1


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="CueFlow local subtitle synchronization")
    parser.add_argument("video")
    parser.add_argument("subtitle")
    parser.add_argument("--output-dir")
    parser.add_argument("--encoding", default="auto")
    args = parser.parse_args(argv)
    result = synchronize(
        SyncRequest(
            args.video,
            args.subtitle,
            args.output_dir or str(Path(args.video).resolve().parent),
            encoding=args.encoding,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

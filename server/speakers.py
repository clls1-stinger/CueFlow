"""Speaker diarization with sherpa-onnx, and assignment of speakers to subtitle cues.

The worker runs in a child process (``python -m server.speakers movie.mp4 subtitles.srt turns.json``) so
expiry can kill it, and so the ONNX runtime memory is returned when it finishes.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import srt

MODELS = Path(os.getenv("CUEFLOW_MODELS", "/app/models"))
SEGMENTATION = MODELS / "pyannote-segmentation-3-0.int8.onnx"
EMBEDDING = MODELS / "campplus-voxceleb-16k.onnx"
DASH = re.compile(r"^\s*[-–—]\s*")
PALETTE_SIZE = 6


def available() -> bool:
    return os.getenv("CUEFLOW_DIARIZATION", "1") != "0" and SEGMENTATION.is_file() and EMBEDDING.is_file()


def regions(text: str, pad=0.3, gap=1.0) -> list[tuple[float, float]]:
    """Merged subtitle spans: only audio with dialogue is analysed."""
    spans = sorted((max(0, c.start.total_seconds() - pad), c.end.total_seconds() + pad) for c in srt.parse(text))
    merged = []
    for a, b in spans:
        if merged and a - merged[-1][1] <= gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def diarize(media: str, subtitles: str, threshold: float, chunk_seconds=300) -> list[tuple[float, float, int]]:
    """Diarize dialogue in bounded chunks, then link chunk-local speakers by voice embedding.

    Whole-film diarization keeps every embedding and frame in memory (a 93 min film passed 3 GB),
    so memory here depends on the chunk size, not on the film length."""
    import numpy as np
    import sherpa_onnx as so

    threads = int(os.getenv("CUEFLOW_DIARIZATION_THREADS", "2"))
    embedding_config = so.SpeakerEmbeddingExtractorConfig(model=str(EMBEDDING), num_threads=threads)
    config = so.OfflineSpeakerDiarizationConfig(
        segmentation=so.OfflineSpeakerSegmentationModelConfig(
            pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(SEGMENTATION)), num_threads=threads),
        embedding=embedding_config,
        clustering=so.FastClusteringConfig(num_clusters=-1, threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    if not config.validate():
        raise RuntimeError("invalid diarization config")
    engine = so.OfflineSpeakerDiarization(config)
    extractor = so.SpeakerEmbeddingExtractor(embedding_config)
    rate = engine.sample_rate
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file", "-i", media,
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    audio = np.frombuffer(raw, dtype=np.int16)  # int16 view; chunks are converted on demand

    def samples(a, b):
        return audio[int(a * rate):int(b * rate)].astype(np.float32) / 32768

    # Group dialogue spans into chunks of about chunk_seconds of audio.
    chunks, current, size = [], [], 0.0
    for a, b in regions(Path(subtitles).read_text(encoding="utf-8")):
        while b - a > chunk_seconds:
            chunks.append([(a, a + chunk_seconds)])
            a += chunk_seconds
        if current and size + b - a > chunk_seconds:
            chunks.append(current)
            current, size = [], 0.0
        current.append((a, b))
        size += b - a
    if current:
        chunks.append(current)

    centroids, counts, turns = [], [], []
    for spans in chunks:
        pieces = [samples(a, b) for a, b in spans]
        joined = np.concatenate(pieces) if pieces else np.zeros(0, np.float32)
        if len(joined) < rate:
            continue
        offsets, position = [], 0.0  # (position in joined audio, real start, length)
        for (a, _), piece in zip(spans, pieces):
            offsets.append((position, a, len(piece) / rate))
            position += len(piece) / rate
        local = {}
        for seg in engine.process(joined).sort_by_start_time():
            for at, real, length in offsets:  # map back, splitting at span boundaries
                a, b = max(seg.start, at), min(seg.end, at + length)
                if b - a >= 0.2:
                    local.setdefault(seg.speaker, []).append((real + a - at, real + b - at))
        for speaker, spans_ in local.items():
            longest = sorted(spans_, key=lambda s: s[0] - s[1])
            voice, total = [], 0.0
            for a, b in longest:
                if total >= 30:
                    break
                voice.append(samples(a, b))
                total += b - a
            stream = extractor.create_stream()
            stream.accept_waveform(sample_rate=rate, waveform=np.concatenate(voice))
            stream.input_finished()
            vector = np.array(extractor.compute(stream), dtype=np.float32)
            vector /= np.linalg.norm(vector) or 1
            scores = [float(vector @ (c / np.linalg.norm(c))) for c in centroids]
            best = int(np.argmax(scores)) if scores else -1
            if best >= 0 and scores[best] >= 1 - threshold:
                centroids[best] = centroids[best] + vector * total
                counts[best] += total
                label = best
            else:
                centroids.append(vector * total)
                counts.append(total)
                label = len(centroids) - 1
            turns.extend((round(a, 3), round(b, 3), label) for a, b in spans_)
    return sorted(turns)


def _overlaps(turns, start, end):
    totals = {}
    for a, b, speaker in turns:
        if b <= start:
            continue
        if a >= end:
            break
        totals[speaker] = totals.get(speaker, 0) + min(b, end) - max(a, start)
    return totals


def _speaker(turns, start, end, minimum=0.3):
    totals = _overlaps(turns, start, end)
    if not totals:
        return None
    speaker, seconds = max(totals.items(), key=lambda item: item[1])
    return speaker if seconds >= minimum * (end - start) else None


def _split_point(turns, start, end, first, second):
    """Where the first part's speaker hands over, or a proportional guess by text length."""
    changes = [a for i, (a, b, _) in enumerate(turns)
               if start < a < end and i and turns[i - 1][2] != turns[i][2]]
    if changes:
        return min(changes, key=lambda a: abs(a - (start + (end - start) * first / (first + second))))
    return start + (end - start) * first / (first + second)


def assign(text: str, turns: list[tuple[float, float, int]]) -> list[tuple[srt.Subtitle, int | None]]:
    """Split two-person dialogue cues and label every cue with its dominant speaker."""
    turns = sorted(turns)
    output = []
    for cue in srt.parse(text):
        start, end = cue.start.total_seconds(), cue.end.total_seconds()
        lines = [line for line in cue.content.splitlines() if line.strip()]
        dashed = [i for i, line in enumerate(lines) if DASH.match(line)]
        if len(dashed) >= 2 and dashed[0] == 0 and end - start >= 1:
            # "- Who?\n- Me." — one cue, two speakers. Group continuation lines with their dash.
            groups = [lines[a:b] for a, b in zip(dashed, dashed[1:] + [len(lines)])]
            first = "\n".join(DASH.sub("", line) for line in groups[0])
            rest = "\n".join(DASH.sub("", line) if i == 0 else line
                             for g in groups[1:] for i, line in enumerate(g))
            middle = _split_point(turns, start, end, len(first), len(rest))
            for a, b, content in ((start, middle, first), (middle, end, rest)):
                part = srt.Subtitle(0, timedelta(seconds=a), timedelta(seconds=b), content)
                output.append((part, _speaker(turns, a, b)))
        else:
            output.append((cue, _speaker(turns, start, end)))
    return output


def speaker_vtt(cues: list[tuple[srt.Subtitle, int | None]]) -> str:
    """WebVTT with voice spans. Speakers are numbered by first appearance; colors cycle by class."""
    order = {}
    parts = ["WEBVTT\n"]
    for cue, speaker in cues:
        a = srt.timedelta_to_srt_timestamp(cue.start).replace(",", ".")
        b = srt.timedelta_to_srt_timestamp(cue.end).replace(",", ".")
        content = html.escape(re.sub(r"<[^>]*>", "", cue.content))
        if speaker is not None:
            number = order.setdefault(speaker, len(order) + 1)
            content = f"<v.s{(number - 1) % PALETTE_SIZE + 1} {number}>{content}</v>"
        parts.append(f"{a} --> {b}\n{content}\n")
    return "\n".join(parts)


if __name__ == "__main__":
    result = diarize(sys.argv[1], sys.argv[2], float(os.getenv("CUEFLOW_DIARIZATION_THRESHOLD", "0.5")))
    Path(sys.argv[3]).write_text(json.dumps(result), encoding="utf-8")
    print("CUEFLOW_SPEAKERS " + str(len({s for *_, s in result})), flush=True)

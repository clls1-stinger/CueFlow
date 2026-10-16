"""Deterministic, original fixtures for release smoke tests and the demo recording."""

import hashlib
import math
import struct
import subprocess
import tempfile
import time
import wave
from datetime import timedelta
from pathlib import Path

import srt

from cueflow.engine import ffmpeg_directory


def fixture(folder: Path):
    """Speech-like harmonic bursts; no external or copyrighted media is needed."""
    audio = folder / "Evening walk.wav"
    subtitle = folder / "Evening walk.srt"
    segments = [
        (2, 3.2),
        (4.7, 6.8),
        (8.1, 9.6),
        (12, 15.3),
        (17, 18.1),
        (20.6, 23.7),
        (26, 27.8),
        (29.1, 32.4),
        (35, 36.2),
        (39.4, 42.8),
    ]
    samples = bytearray()
    rate = 16000
    for i in range(46 * rate):
        t = i / rate
        active = next(((a, b) for a, b in segments if a <= t < b), None)
        value = 0
        if active:
            envelope = min(1, (t - active[0]) * 20, (active[1] - t) * 20)
            frequency = 125 + 25 * math.sin(t * 3)
            value = int(
                5500
                * envelope
                * sum(math.sin(2 * math.pi * frequency * k * t) / k for k in range(1, 9))
            )
        samples.extend(struct.pack("<h", value))
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples)
    lines = [
        "The street is quiet.",
        "Let's take the long way home.",
        "Look at the evening sky.",
        "We still have a little time.",
        "I hear the river.",
        "The lights are coming on.",
        "We can stop here.",
        "Tomorrow is another day.",
        "See you in the morning.",
        "Good night.",
    ]
    entries = [
        srt.Subtitle(i + 1, timedelta(seconds=a + 2), timedelta(seconds=b + 2), lines[i])
        for i, (a, b) in enumerate(segments)
    ]
    subtitle.write_text(srt.compose(entries), encoding="utf-8")
    return audio, subtitle


def self_test():
    import os

    from PySide6.QtWidgets import QApplication

    from cueflow.app import Window

    app = QApplication.instance() or QApplication([])
    window = Window()
    window.show()
    app.processEvents()
    assert window.title.text()
    suffix = ".exe" if os.name == "nt" else ""
    for tool in ("ffmpeg", "ffprobe"):
        subprocess.run(
            [str(ffmpeg_directory() / (tool + suffix)), "-version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        video, subtitle = fixture(folder)
        before = hashlib.sha256(subtitle.read_bytes()).hexdigest()
        window.set_file("video", str(video))
        window.set_file("subtitle", str(subtitle))
        window.framerate.setChecked(False)
        window.start()
        deadline = time.monotonic() + 90
        while window.busy() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        if window.busy():
            window.cancel()
            window.process.waitForFinished(3000)
            raise RuntimeError("Frozen GUI worker timed out")
        assert window.result is not None, window.details.toPlainText()
        result = window.result
        assert result["cues"] == 10
        assert abs(result["offset"] + 2) < 0.5, result
        assert before == hashlib.sha256(subtitle.read_bytes()).hexdigest()
        assert Path(result["output"]).is_file()
        print(
            "CueFlow smoke test passed: Qt, FFmpeg, ffprobe, VAD, alignment and safe output.",
            flush=True,
        )
    window.close()
    return 0

"""Capture actual Qt states and a real sync job into a small bilingual demo GIF."""

import io
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication

from cueflow.app import Window
from cueflow.smoke import multitrack_fixture

app = QApplication(sys.argv)
window = Window()
window.resize(840, 1100)
window.show()
frames, durations = [], []


def capture(duration=1200):
    app.processEvents()
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    window.grab().save(buffer, "PNG")
    frame = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGB")
    frames.append(frame)
    durations.append(duration)


assets = Path("docs/assets")
assets.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="cueflow-demo-") as workspace:
    video, subtitle = multitrack_fixture(Path(workspace))
    for lang in ("en", "es"):
        window.language.setCurrentIndex(0 if lang == "en" else 1)
        window.result, window.error_code, window.phase = None, None, "ready"
        window.open_button.hide()
        for _, field, _ in window.fields.values():
            field.clear()
        window.audio_tracks = []
        window.refresh_audio_tracks()
        window.refresh_status()
        capture(1400)
        window.grab().save(str(assets / f"screenshot-{lang}.png"))
        window.set_file("video", str(video))
        deadline = time.monotonic() + 25
        while window.probe and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)
        if window.probe or window.audio.count() != 2:
            raise RuntimeError("Could not read demo audio tracks")
        window.audio.setCurrentIndex(1)
        capture(1000)
        window.set_file("subtitle", str(subtitle))
        capture(1000)
        window.start()
        deadline = time.monotonic() + 60
        while window.busy() and time.monotonic() < deadline:
            app.processEvents()
            capture(180)
            time.sleep(0.18)
        app.processEvents()
        if not window.result:
            raise RuntimeError(window.details.toPlainText())
        capture(2800)
        window.grab().save(str(assets / f"result-{lang}.png"))
        window.summary.clear()
        window.progress.setValue(0)
frames[0].save(
    assets / "demo.gif",
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True,
)
window.close()
print(f"Recorded {len(frames)} frames from the real application.")

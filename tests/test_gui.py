from PySide6.QtCore import Qt

from cueflow.app import Window
from cueflow.smoke import fixture, multitrack_fixture


def test_language_switch_and_missing_files(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window.language.setCurrentIndex(1)
    assert window.sync_button.text() == "Ajustar los tiempos"
    window.start()
    assert window.error_code == "input_missing"
    window.language.setCurrentIndex(0)
    assert "existing" in window.status.text()


def test_full_gui_worker_flow(qtbot, tmp_path):
    video, subtitle = multitrack_fixture(tmp_path)
    window = Window()
    qtbot.addWidget(window)
    window.show()
    window.set_file("video", str(video))
    window.set_file("subtitle", str(subtitle))
    qtbot.waitUntil(lambda: window.probe is None, timeout=25000)
    assert window.audio.count() == 2
    window.audio.setCurrentIndex(1)
    window.language.setCurrentIndex(1)
    assert window.audio.currentData() == 1
    window.framerate.setChecked(False)
    qtbot.mouseClick(window.sync_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: window.result is not None or window.error_code is not None, timeout=60000
    )
    qtbot.waitUntil(lambda: not window.busy(), timeout=10000)
    assert window.error_code is None, window.details.toPlainText()
    assert window.result["cues"] == 10
    assert window.result["audio_track"] == 2
    assert window.open_button.isVisible()


def test_cancellation_cleans_worker_files(qtbot, tmp_path):
    from pathlib import Path

    from PySide6.QtCore import QProcess

    video, subtitle = fixture(tmp_path)
    window = Window()
    qtbot.addWidget(window)
    window.set_file("video", str(video))
    window.set_file("subtitle", str(subtitle))
    qtbot.waitUntil(lambda: window.probe is None, timeout=25000)
    window.start()
    workspace = Path(window.workspace.name)
    qtbot.waitUntil(lambda: window.process.state() == QProcess.Running, timeout=10000)
    window.cancel()
    qtbot.waitUntil(lambda: not window.busy() and window.workspace is None, timeout=10000)
    assert window.phase == "cancelled"
    assert not workspace.exists()
    assert not list(tmp_path.glob("*.synced*.srt"))


def test_audio_probe_recovers_after_invalid_media(qtbot, tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not media")
    window = Window()
    qtbot.addWidget(window)
    window.set_file("video", str(bad))
    qtbot.waitUntil(lambda: window.probe is None, timeout=25000)
    assert window.error_code == "audio_probe_failed"
    video, _ = fixture(tmp_path)
    window.set_file("video", str(bad))
    window.set_file("video", str(video))
    qtbot.waitUntil(lambda: window.probe is None, timeout=25000)
    assert window.error_code is None
    assert window.audio.currentData() == 0
    assert not window.sync_button.isEnabled()


def test_home_and_progressive_sync_controls(qtbot, tmp_path):
    window = Window()
    qtbot.addWidget(window)
    window.show()
    assert window.pages.currentIndex() == 0
    assert not window.sync_button.isVisible()
    qtbot.mouseClick(window.choices[0], Qt.LeftButton)
    assert window.pages.currentIndex() == 1
    assert not window.sync_button.isEnabled()
    assert not window.file_rows["output"].isVisible()
    assert not window.audio.isVisible()
    video, subtitle = fixture(tmp_path)
    window.set_file("video", str(video))
    qtbot.waitUntil(lambda: window.probe is None, timeout=25000)
    assert not window.sync_button.isEnabled()
    assert window.fields["video"][1].text() == video.name
    window.set_file("subtitle", str(subtitle))
    assert window.sync_button.isEnabled()
    window.advanced.setChecked(True)
    assert window.file_rows["output"].isVisible()
    assert window.paths["output"] == str(tmp_path)
    qtbot.mouseClick(window.back_button, Qt.LeftButton)
    assert window.pages.currentIndex() == 0
    qtbot.mouseClick(window.choices[0], Qt.LeftButton)
    assert window.sync_button.isEnabled()

from PySide6.QtCore import Qt

from cueflow.app import Window
from cueflow.smoke import fixture


def test_language_switch_and_missing_files(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window.language.setCurrentIndex(1)
    assert window.sync_button.text() == "Sincronizar subtítulos"
    window.start()
    assert window.error_code == "input_missing"
    window.language.setCurrentIndex(0)
    assert "existing" in window.status.text()


def test_full_gui_worker_flow(qtbot, tmp_path):
    video, subtitle = fixture(tmp_path)
    window = Window()
    qtbot.addWidget(window)
    window.show()
    window.set_file("video", str(video))
    window.set_file("subtitle", str(subtitle))
    window.framerate.setChecked(False)
    qtbot.mouseClick(window.sync_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: window.result is not None or window.error_code is not None, timeout=60000
    )
    qtbot.waitUntil(lambda: not window.busy(), timeout=10000)
    assert window.error_code is None, window.details.toPlainText()
    assert window.result["cues"] == 10
    assert window.open_button.isVisible()


def test_cancellation_cleans_worker_files(qtbot, tmp_path):
    from pathlib import Path

    from PySide6.QtCore import QProcess

    video, subtitle = fixture(tmp_path)
    window = Window()
    qtbot.addWidget(window)
    window.set_file("video", str(video))
    window.set_file("subtitle", str(subtitle))
    window.start()
    workspace = Path(window.workspace.name)
    qtbot.waitUntil(lambda: window.process.state() == QProcess.Running, timeout=10000)
    window.cancel()
    qtbot.waitUntil(lambda: not window.busy() and window.workspace is None, timeout=10000)
    assert window.phase == "cancelled"
    assert not workspace.exists()
    assert not list(tmp_path.glob("*.synced*.srt"))

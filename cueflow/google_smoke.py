"""Verify the bundled Chromium process and JS bridge without internet."""
from PySide6.QtCore import QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication


def run():
    app = QApplication.instance() or QApplication([])
    view = QWebEngineView()
    result = {'ok': False}

    def loaded(ok):
        if not ok:
            app.exit(1)
            return
        view.page().runJavaScript('document.getElementById("cue").textContent', checked)

    def checked(value):
        result['ok'] = value == 'Hello 世界'
        app.exit(0 if result['ok'] else 1)

    view.loadFinished.connect(loaded)
    view.setHtml('<!doctype html><meta charset="UTF-8"><p id="cue">Hello 世界</p>')
    view.show()
    QTimer.singleShot(20000, lambda: app.exit(1))
    app.exec()
    print('Google widget browser runtime:', 'PASS' if result['ok'] else 'FAIL', flush=True)
    # Chromium teardown can defer process shutdown in a frozen executable.
    view.close()
    return 0 if result['ok'] else 1

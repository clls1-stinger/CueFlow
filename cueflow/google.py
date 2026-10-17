"""Google Website Translator inside a visible Chromium view, with explicit user consent."""
from __future__ import annotations

import json
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal


class GoogleTranslation(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, texts, source, target, language, parent=None):
        super().__init__(parent)
        from PySide6.QtWebEngineCore import QWebEngineProfile
        from PySide6.QtWebEngineWidgets import QWebEngineView

        # A separate, non-persistent profile prevents translation cookies carrying
        # across batches, and does not share the user's normal browser session.
        self.profile = QWebEngineProfile(self)
        self.view = QWebEngineView()
        from PySide6.QtWebEngineCore import QWebEnginePage

        self.view.setPage(QWebEnginePage(self.profile, self.view))
        self.view.setWindowTitle('CueFlow · Google Translate')
        self.view.resize(720, 360)
        self.data = {'texts': texts, 'source': source, 'target': target, 'ui': language}
        self.active = True
        self.started = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.poll)
        self.view.loadFinished.connect(self.loaded)

    def start(self):
        self.view.show()
        self.view.load(QUrl('https://cueflow.enriquepl.com/google-translate.html'))
        self.timer.start()

    def loaded(self, ok):
        if not self.active:
            return
        if not ok:
            self.finish(None, 'googleUnavailable')
            return
        self.view.page().runJavaScript('window.cueflowStart && window.cueflowStart(' + json.dumps(self.data, ensure_ascii=True) + ')')

    def poll(self):
        if not self.active:
            return
        if time.monotonic() - self.started > 100:
            self.finish(None, 'googleTimeout')
            return
        if not self.view.isVisible():
            self.finish(None, 'cancelled')
            return
        self.view.page().runJavaScript('JSON.stringify(window.cueflowResult || null)', self.result)

    def result(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                return
        if not self.active or not isinstance(data, dict):
            return
        if data.get('error'):
            self.finish(None, data['error'])
            return
        values = data.get('translations')
        if not isinstance(values, list) or len(values) != len(self.data['texts']) or any(not isinstance(t, str) or not t.strip() for t in values):
            self.finish(None, 'translationInvalid')
            return
        self.finish(values)

    def finish(self, values=None, error=None):
        if not self.active:
            return
        self.active = False
        self.timer.stop()
        self.view.stop()
        self.view.close()
        self.view.destroyed.connect(self.deleteLater)
        self.view.deleteLater()
        if error:
            self.failed.emit(error)
        else:
            self.finished.emit(values)

    def cancel(self):
        self.finish(None, 'cancelled')

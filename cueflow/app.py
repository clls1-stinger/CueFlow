from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import psutil
from PySide6.QtCore import QLocale, QProcess, QProcessEnvironment, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from cueflow import __version__
from cueflow.engine import SyncError, SyncRequest, audio_probe_command, parse_audio_tracks
from cueflow.i18n import TEXT

STYLE = """
QWidget { background: #08090a; color: #f7f8f8; font-size: 14px; }
QLabel { background: transparent; }
QLabel[role="muted"] { color: #a6abb4; }
QLabel[role="eyebrow"] { color: #a6abb4; font-size: 11px; letter-spacing: 2px; }
QLabel[role="title"] { font-size: 32px; font-weight: 500; }
QLabel[role="brand"] { font-size: 20px; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
 background: #141516; border: 1px solid #34343a; border-radius: 8px;
 padding: 10px; selection-background-color: #555863;
}
QPushButton { background: #1c1c1f; border: 1px solid #34343a;
 border-radius: 18px; padding: 10px 18px; }
QPushButton:hover { background: #2d2e31; border-color: #8a8f98; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
 border: 2px solid #d0d6e0;
}
QPushButton#primary { background: #ff4700; color: #08090a; border: none;
 font-weight: 600; border-radius: 8px; padding: 15px 24px; }
QPushButton#primary:hover { background: #ff6a30; }
QPushButton#primary:focus { border: 2px solid #ffffff; }
QPushButton:disabled { background: #1c1c1f; color: #8a8f98; border-color: #23252a; }
QPushButton#primary:disabled { background: #29211e; color: #a6abb4; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #8a8f98; border-radius: 4px; }
QCheckBox::indicator:checked { background: #d0d6e0; border: 4px solid #34343a; }
QProgressBar { background: #23252a; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #d0d6e0; border-radius: 3px; }
QToolTip { background: #23252a; color: #f7f8f8; border: 1px solid #34343a; }
"""


def label(text="", role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setProperty("role", role)
    return widget


class Timeline(QWidget):
    """An explicitly schematic pair of cue tracks, never a fake measured waveform."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(54)
        self.setAccessibleName("CueFlow subtitle alignment diagram")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#34343a"), 1))
        for y in (17, 39):
            painter.drawLine(0, y, self.width(), y)
        for y, shift, color in [(11, 28, "#52565f"), (33, 0, "#d0d6e0")]:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            for start, width in [
                (0.05, 0.13),
                (0.23, 0.09),
                (0.39, 0.19),
                (0.65, 0.12),
                (0.84, 0.08),
            ]:
                painter.drawRoundedRect(
                    int(start * self.width()) + shift, y, int(width * self.width()), 12, 3, 3
                )


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("CueFlow", "CueFlow")
        default = "es" if QLocale.system().language() == QLocale.Spanish else "en"
        self.lang = self.settings.value("language", default)
        if self.lang not in TEXT:
            self.lang = "en"
        self.process = None
        self.probe = None
        self.audio_tracks = []
        self.audio_error = None
        self.probe_timer = QTimer(self)
        self.probe_timer.setSingleShot(True)
        self.probe_timer.timeout.connect(self.probe_timeout)
        self.workspace = None
        self.result = None
        self.buffer = ""
        self.error_code = None
        self.phase = "ready"
        self.cancelled = False
        self.setWindowTitle("CueFlow")
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.setWindowIcon(QIcon(str(root / "docs/assets/cueflow.png")))
        self.setMinimumSize(660, 580)
        self.resize(820, 820)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        body = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        top = QHBoxLayout()
        top.addWidget(label("◫  CueFlow", "brand"))
        top.addStretch()
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("Español", "es")
        self.language.setCurrentIndex(1 if self.lang == "es" else 0)
        self.language.setAccessibleName("Interface language / Idioma de la interfaz")
        self.language.currentIndexChanged.connect(self.change_language)
        top.addWidget(self.language)
        layout.addLayout(top)
        self.local = label(role="eyebrow")
        layout.addWidget(self.local)
        self.title = label(role="title")
        layout.addWidget(self.title)
        self.intro = label(role="muted")
        layout.addWidget(self.intro)
        self.editor_button = QPushButton()
        self.editor_button.clicked.connect(self.open_editor)
        layout.addWidget(self.editor_button, alignment=Qt.AlignLeft)
        layout.addWidget(Timeline())
        self.fields = {}
        for key in ("video", "subtitle", "output"):
            caption = label()
            layout.addWidget(caption)
            row = QHBoxLayout()
            field = QLineEdit()
            field.setReadOnly(True)
            field.setMinimumHeight(24)
            button = QPushButton()
            button.clicked.connect(lambda checked=False, name=key: self.browse(name))
            row.addWidget(field, 1)
            row.addWidget(button)
            layout.addLayout(row)
            caption.setBuddy(field)
            self.fields[key] = (caption, field, button)
            if key == "video":
                self.audio_label = label()
                self.audio = QComboBox()
                self.audio_label.setBuddy(self.audio)
                layout.addWidget(self.audio_label)
                layout.addWidget(self.audio)
        self.advanced = QCheckBox()
        layout.addWidget(self.advanced)
        self.advanced_panel = QWidget()
        form = QFormLayout(self.advanced_panel)
        form.setContentsMargins(0, 0, 0, 0)
        self.encoding_label = label()
        self.encoding = QComboBox()
        for name, value in [
            ("Automatic", "auto"),
            ("UTF-8", "utf-8-sig"),
            ("Windows-1252", "cp1252"),
            ("Latin-1", "latin1"),
            ("UTF-16", "utf-16"),
            ("UTF-32", "utf-32"),
            ("Cyrillic / Windows-1251", "cp1251"),
            ("Cyrillic / KOI8-R", "koi8-r"),
            ("Arabic / Windows-1256", "cp1256"),
            ("Hebrew / Windows-1255", "cp1255"),
            ("Greek / Windows-1253", "cp1253"),
            ("Turkish / Windows-1254", "cp1254"),
            ("Vietnamese / Windows-1258", "cp1258"),
            ("Thai / Windows-874", "cp874"),
            ("Japanese / CP932 (Shift JIS)", "cp932"),
            ("Japanese / EUC-JP", "euc-jp"),
            ("Chinese / GB18030", "gb18030"),
            ("Chinese / Big5", "big5"),
            ("Korean / CP949", "cp949"),
        ]:
            self.encoding.addItem(name, value)
        form.addRow(self.encoding_label, self.encoding)
        self.max_offset = QSpinBox()
        self.max_offset.setRange(1, 3600)
        self.max_offset.setValue(300)
        self.offset_label = label()
        form.addRow(self.offset_label, self.max_offset)
        self.repair = QCheckBox()
        self.repair.setChecked(True)
        self.framerate = QCheckBox()
        self.framerate.setChecked(True)
        form.addRow(self.repair)
        form.addRow(self.framerate)
        self.advanced_panel.hide()
        self.advanced.toggled.connect(self.advanced_panel.setVisible)
        layout.addWidget(self.advanced_panel)
        actions = QHBoxLayout()
        self.sync_button = QPushButton()
        self.sync_button.setObjectName("primary")
        self.sync_button.clicked.connect(self.start)
        actions.addWidget(self.sync_button, 1)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.safe = label(role="muted")
        layout.addWidget(self.safe)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = label()
        layout.addWidget(self.status)
        self.summary = label(role="muted")
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.summary)
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self.open_output)
        self.open_button.hide()
        layout.addWidget(self.open_button, alignment=Qt.AlignLeft)
        self.details_toggle = QCheckBox()
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(140)
        self.details.document().setMaximumBlockCount(400)
        self.details.hide()
        self.details_toggle.toggled.connect(self.details.setVisible)
        layout.addWidget(self.details_toggle)
        layout.addWidget(self.details)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.retranslate()

    def t(self, key):
        return TEXT[self.lang].get(key, TEXT[self.lang]["unexpected"])

    def open_editor(self):
        from cueflow.editor import SubtitleEditor

        dialog = SubtitleEditor(self.lang, self)
        dialog.exec()

    def change_language(self):
        self.lang = self.language.currentData()
        self.settings.setValue("language", self.lang)
        self.retranslate()

    def retranslate(self):
        self.editor_button.setText("Traducir y editar subtítulos" if self.lang == "es" else "Translate & edit subtitles")
        for widget, key in [
            (self.title, "tagline"),
            (self.intro, "intro"),
            (self.local, "local"),
            (self.safe, "safe"),
            (self.sync_button, "sync"),
            (self.cancel_button, "cancel"),
            (self.open_button, "open"),
            (self.advanced, "advanced"),
            (self.encoding_label, "encoding"),
            (self.audio_label, "audio_track"),
            (self.offset_label, "offset"),
            (self.repair, "repair"),
            (self.framerate, "framerate"),
            (self.details_toggle, "details"),
        ]:
            widget.setText(self.t(key))
        self.encoding.setItemText(0, self.t("auto"))
        self.language.setToolTip(self.t("interface_language"))
        self.audio.setAccessibleName(self.t("audio_track"))
        self.audio.setToolTip(self.t("audio_help"))
        self.refresh_audio_tracks()
        for key, (caption, field, button) in self.fields.items():
            caption.setText(self.t(key))
            field.setAccessibleName(self.t(key))
            button.setText(self.t("browse"))
            button.setAccessibleName(self.t(key) + " · " + self.t("browse"))
            field.setPlaceholderText(self.t(key + "_hint") if key != "output" else self.t("output"))
        self.refresh_status()

    def browse(self, key):
        if key == "output":
            path = QFileDialog.getExistingDirectory(self, self.t(key), self.fields[key][1].text())
        else:
            filters = (
                "SubRip (*.srt);;All files (*)"
                if key == "subtitle"
                else "Media (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.wav *.mp3 *.flac *.m4a *.mka *.ogg *.aac *.ac3 *.aiff);;All files (*)"
            )
            path, _ = QFileDialog.getOpenFileName(self, self.t(key), "", filters)
        if path:
            self.set_file(key, path)

    def set_file(self, key, path):
        path = str(Path(path).resolve())
        self.fields[key][1].setText(path)
        self.fields[key][1].setToolTip(path)
        if key == "video":
            self.fields["output"][1].setText(str(Path(path).parent))
            self.load_audio_tracks(path)

    def refresh_audio_tracks(self):
        selected = self.audio.currentData()
        self.audio.clear()
        for track in self.audio_tracks:
            code = track["language"]
            language = QLocale.codeToLanguage(code)
            name = (
                QLocale(language).nativeLanguageName()
                if language not in (QLocale.AnyLanguage, QLocale.C)
                else code
                if code not in ("und", "")
                else self.t("unknown_language")
            )
            parts = [self.t("track_number").format(number=track["index"] + 1), name]
            if track["title"]:
                parts.append(track["title"])
            if track["codec"]:
                parts.append(track["codec"])
            self.audio.addItem(" · ".join(parts), track["index"])
        if not self.audio_tracks:
            self.audio.addItem(self.t("probing" if self.probe else "choose_media"), None)
        index = self.audio.findData(selected)
        if index >= 0:
            self.audio.setCurrentIndex(index)
        self.audio.setEnabled(bool(self.audio_tracks) and not self.busy())

    def stop_probe(self):
        self.probe_timer.stop()
        process, self.probe = self.probe, None
        if process:
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()

    def load_audio_tracks(self, path):
        self.stop_probe()
        self.audio_tracks, self.audio_error = [], None
        self.audio.clear()
        self.error_code = None
        try:
            command = audio_probe_command(Path(path))
        except SyncError as exc:
            self.audio_error = self.error_code = exc.code
            self.sync_button.setEnabled(True)
            self.refresh_audio_tracks()
            self.refresh_status()
            return
        process = self.probe = QProcess(self)
        process.finished.connect(lambda code, status, p=process: self.probe_finished(p, code))
        process.errorOccurred.connect(lambda error, p=process: self.probe_failed(p, error))
        self.sync_button.setEnabled(False)
        self.refresh_audio_tracks()
        process.start(command[0], command[1:])
        self.probe_timer.start(20000)

    def probe_failed(self, process, error):
        if error == QProcess.FailedToStart:
            self.probe_finished(process, 1)

    def probe_timeout(self):
        if self.probe:
            self.probe.kill()

    def probe_finished(self, process, code):
        if process is not self.probe:
            return
        self.probe_timer.stop()
        self.probe = None
        try:
            if code:
                raise SyncError("audio_probe_failed")
            self.audio_tracks = parse_audio_tracks(
                bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            )
        except SyncError as exc:
            self.audio_error = self.error_code = exc.code
        self.sync_button.setEnabled(True)
        self.refresh_audio_tracks()
        self.refresh_status()
        process.deleteLater()

    def dragEnterEvent(self, event):
        if (
            not self.busy()
            and event.mimeData().hasUrls()
            and all(u.isLocalFile() for u in event.mimeData().urls())
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.busy():
            return
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file():
                self.set_file("subtitle" if path.suffix.lower() == ".srt" else "video", str(path))
        event.acceptProposedAction()

    def busy(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def start(self):
        if self.busy() or self.probe:
            return
        self.result, self.error_code, self.cancelled = None, None, False
        self.buffer = ""
        self.open_button.hide()
        self.details.clear()
        self.summary.clear()
        if not all(Path(self.fields[k][1].text()).is_file() for k in ("video", "subtitle")):
            self.error_code = "input_missing"
            self.refresh_status()
            return
        if self.audio_error or self.audio.currentData() is None:
            self.error_code = self.audio_error or "audio_missing"
            self.refresh_status()
            return
        request = SyncRequest(
            self.fields["video"][1].text(),
            self.fields["subtitle"][1].text(),
            self.fields["output"][1].text(),
            self.encoding.currentData(),
            self.repair.isChecked(),
            self.max_offset.value(),
            self.framerate.isChecked(),
            self.audio.currentData(),
        )
        self.workspace = tempfile.TemporaryDirectory(prefix="cueflow-ui-")
        request_path = Path(self.workspace.name) / "request.json"
        request_path.write_text(json.dumps(dataclasses.asdict(request)), encoding="utf-8")
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        for key in ("TMPDIR", "TMP", "TEMP"):
            environment.insert(key, self.workspace.name)
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_events)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)
        args = ["--worker", str(request_path)]
        if not getattr(sys, "frozen", False):
            args = ["-m", "cueflow", *args]
        self.phase = "analyzing"
        self.started = time.monotonic()
        self.set_busy(True)
        self.progress.setRange(0, 0)
        self.timer.start(1000)
        self.process.start(sys.executable, args)
        self.refresh_status()

    def set_busy(self, busy):
        self.sync_button.setEnabled(not busy)
        self.advanced.setEnabled(not busy)
        self.advanced_panel.setEnabled(not busy)
        self.audio.setEnabled(not busy and bool(self.audio_tracks))
        for _, field, button in self.fields.values():
            field.setEnabled(not busy)
            button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)

    def read_events(self):
        self.buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if "CUEFLOW_EVENT " in line:
                try:
                    data = json.loads(line.split("CUEFLOW_EVENT ", 1)[1])
                except ValueError:
                    continue
                if "result" in data:
                    self.result = data["result"]
                elif "error" in data:
                    self.error_code = (
                        "encoding_error" if data["error"] == "encoding" else data["error"]
                    )
                    self.details.appendPlainText(data.get("detail", ""))
                elif "phase" in data:
                    self.phase = data["phase"]
                    info = data.get("progress", {})
                    # Use measured audio time only; do not invent percentage estimates.
                    total = info.get("total_seconds")
                    processed = info.get("processed_seconds")
                    if total and processed is not None:
                        self.progress.setRange(0, 100)
                        self.progress.setValue(min(99, int(100 * processed / total)))
                self.refresh_status()
            elif line.strip():
                if "computing alignments" in line:
                    self.phase = "aligning"
                self.details.appendPlainText(line.strip())

    def process_error(self, error):
        if error == QProcess.FailedToStart:
            self.error_code = "unexpected"
            self.details.appendPlainText(self.process.errorString())
            self.finished(1)

    def finished(self, code, status=None):
        self.read_events()
        self.timer.stop()
        self.set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if self.result else 0)
        if self.result:
            self.phase = "done"
            self.error_code = None
            self.open_button.show()
        elif self.cancelled:
            self.phase = "cancelled"
        elif not self.error_code:
            self.error_code = "alignment_failed"
        if self.workspace:
            self.workspace.cleanup()
            self.workspace = None
        self.refresh_status()

    def refresh_status(self):
        self.status.setText(self.t(self.error_code or self.phase))
        if self.result:
            self.summary.setMinimumHeight(76)
            self.summary.setText(
                self.t("result").format(**self.result)
                + "\n"
                + Path(self.result["output"]).name
                + "\n"
                + self.t("review")
            )
        elif self.busy():
            self.summary.setMinimumHeight(22)
            self.summary.setText(
                self.t("elapsed").format(seconds=int(time.monotonic() - self.started))
            )
        else:
            self.summary.setMinimumHeight(22)
            self.summary.setText(self.t("drop") if self.phase == "ready" else "")

    def cancel(self):
        if not self.busy():
            return
        self.cancelled = True
        # Include FFmpeg children; stopping only the Python worker leaves decoding running.
        try:
            process = psutil.Process(self.process.processId())
            children = process.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
        except psutil.Error:
            pass
        self.process.kill()

    def open_output(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.result["output"]).parent)))

    def closeEvent(self, event):
        if self.busy():
            if (
                QMessageBox.question(self, self.t("closing"), self.t("closing_text"))
                != QMessageBox.Yes
            ):
                event.ignore()
                return
            self.cancel()
            self.process.waitForFinished(3000)
        self.stop_probe()
        event.accept()


def launch():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("CueFlow")
    app.setApplicationVersion(__version__)
    app.setFont(
        QFont(
            "Segoe UI"
            if os.name == "nt"
            else "Helvetica"
            if sys.platform == "darwin"
            else "DejaVu Sans",
            10,
        )
    )
    window = Window()
    window.show()
    return app.exec()

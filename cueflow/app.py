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
from PySide6.QtGui import QDesktopServices, QFont, QIcon
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
    QStackedWidget,
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
QLabel[role="step"] { font-size: 18px; font-weight: 600; }
QPushButton[role="choice"] { text-align: left; padding: 20px; border-radius: 10px; font-size: 17px; }
QTableWidget { background: #141516; alternate-background-color: #1c1c1f; gridline-color: #34343a; border: 1px solid #34343a; }
QHeaderView::section { background: #23252a; color: #f7f8f8; padding: 10px; border: none; }
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


class TaskButton(QPushButton):
    """A keyboard-operable task choice with a short, readable explanation."""

    def __init__(self):
        super().__init__()
        self.setProperty("role", "choice")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)
        self.heading = label(role="step")
        self.description = label(role="muted")
        for child in (self.heading, self.description):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(child)

    def setCopy(self, text):
        heading, description = text.split("\n", 1)
        self.heading.setText(heading)
        self.description.setText(description)
        self.setAccessibleName(heading + ". " + description)


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
        self.resize(800, 720)
        self.paths = {}
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
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        home = QWidget()
        home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(0, 24, 0, 0)
        home_layout.setSpacing(18)
        self.home_title = label(role="title")
        self.home_intro = label(role="muted")
        home_layout.addWidget(self.home_title)
        home_layout.addWidget(self.home_intro)
        self.choices = []
        for callback in (self.show_sync, lambda: self.open_editor("translate"), lambda: self.open_editor("edit")):
            button = TaskButton()
            button.setMinimumHeight(90)
            button.clicked.connect(callback)
            home_layout.addWidget(button)
            self.choices.append(button)
        self.search_button = QPushButton()
        self.search_button.clicked.connect(self.open_search)
        home_layout.addWidget(self.search_button, alignment=Qt.AlignLeft)
        self.home_note = label(role="muted")
        home_layout.addWidget(self.home_note)
        home_layout.addStretch()
        self.pages.addWidget(home)
        sync_page = QWidget()
        self.pages.addWidget(sync_page)
        layout = QVBoxLayout(sync_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.back_button = QPushButton()
        self.back_button.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        layout.addWidget(self.back_button, alignment=Qt.AlignLeft)
        self.local = label(role="eyebrow")
        layout.addWidget(self.local)
        self.title = label(role="title")
        layout.addWidget(self.title)
        self.intro = label(role="muted")
        layout.addWidget(self.intro)
        self.editor_button = QPushButton()
        self.editor_button.clicked.connect(self.open_editor)
        self.editor_button.hide()
        self.fields = {}
        self.file_rows = {}
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
            row_widget = QWidget()
            row.setContentsMargins(0, 0, 0, 0)
            row_widget.setLayout(row)
            layout.addWidget(row_widget)
            self.file_rows[key] = row_widget
            caption.setBuddy(field)
            self.fields[key] = (caption, field, button)
            if key == "video":
                self.audio_label = label()
                self.audio = QComboBox()
                self.audio_label.setBuddy(self.audio)
                layout.addWidget(self.audio_label)
                layout.addWidget(self.audio)
        self.search_sync = QPushButton()
        self.search_sync.clicked.connect(self.open_search)
        layout.addWidget(self.search_sync, alignment=Qt.AlignLeft)
        self.advanced = QCheckBox()
        layout.addWidget(self.advanced)
        self.advanced_panel = QWidget()
        form = QFormLayout(self.advanced_panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.fields["output"][0], self.file_rows["output"])
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

    def open_search(self):
        from cueflow.search import SubtitleSearch

        dialog = SubtitleSearch(self.lang, self.paths.get("video", ""), lambda: self.browse("subtitle"), self)
        dialog.exec()

    def show_sync(self):
        self.pages.setCurrentIndex(1)
        self.refresh_status()

    def open_editor(self, mode="translate"):
        from cueflow.editor import SubtitleEditor

        dialog = SubtitleEditor(self.lang, self, mode=mode)
        dialog.exec()

    def change_language(self):
        self.lang = self.language.currentData()
        self.settings.setValue("language", self.lang)
        self.retranslate()

    def retranslate(self):
        for button in (self.search_button, self.search_sync):
            button.setText(self.t("find_subtitles"))
        for widget, key in [(self.home_title, "home_title"), (self.home_intro, "home_intro"),
                            (self.home_note, "home_note"), (self.back_button, "back_home")]:
            widget.setText(self.t(key))
        for button, key in zip(self.choices, ("choose_sync", "choose_translate", "choose_edit")):
            button.setCopy(self.t(key))
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
            button.setText(self.t("choose_" + key))
            button.setAccessibleName(self.t(key) + " · " + self.t("browse"))
            field.setPlaceholderText(self.t(key + "_hint") if key != "output" else self.t("output"))
        self.refresh_status()

    def browse(self, key):
        if key == "output":
            path = QFileDialog.getExistingDirectory(self, self.t(key), self.paths.get(key, ""))
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
        if self.busy():
            return
        self.show_sync()
        self.paths[key] = path
        self.result, self.error_code, self.phase = None, None, "ready"
        self.open_button.hide()
        self.fields[key][1].setText(path if key == "output" else Path(path).name)
        self.fields[key][1].setToolTip(path)
        if key == "video":
            self.paths["output"] = str(Path(path).parent)
            self.fields["output"][1].setText(self.paths["output"])
            self.load_audio_tracks(path)
        self.refresh_status()

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
            self.audio.addItem(" · ".join(parts), track["index"])
        if not self.audio_tracks:
            self.audio.addItem(self.t("probing" if self.probe else "choose_media"), None)
        index = self.audio.findData(selected)
        if index >= 0:
            self.audio.setCurrentIndex(index)
        self.audio.setEnabled(bool(self.audio_tracks) and not self.busy())
        self.audio_label.setVisible(len(self.audio_tracks) > 1)
        self.audio.setVisible(len(self.audio_tracks) > 1)

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
        if not all(Path(self.paths.get(k, "")).is_file() for k in ("video", "subtitle")):
            self.error_code = "input_missing"
            self.refresh_status()
            return
        if self.audio_error or self.audio.currentData() is None:
            self.error_code = self.audio_error or "audio_missing"
            self.refresh_status()
            return
        request = SyncRequest(
            self.paths.get("video", ""),
            self.paths.get("subtitle", ""),
            self.paths.get("output", ""),
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
        self.back_button.setEnabled(not busy)
        self.search_sync.setEnabled(not busy)
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
            self.details.appendPlainText(self.t("result").format(**self.result))
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
        busy = self.busy()
        ready = all(Path(self.paths.get(k, "")).is_file() for k in ("video", "subtitle"))
        self.sync_button.setEnabled(ready and not busy and not self.probe and not self.audio_error and self.audio.currentData() is not None)
        self.progress.setVisible(busy)
        self.details_toggle.setVisible(bool(self.result or self.error_code or busy or self.details.toPlainText()))
        self.safe.setText(self.t("safe"))
        if self.paths.get("output") and self.paths.get("video") and self.paths["output"] != str(Path(self.paths["video"]).parent):
            self.safe.setText(self.t("copy_folder") + self.paths["output"])
        self.status.setText(self.t(self.error_code or self.phase))
        if self.phase == "ready" and not self.error_code:
            key = "pick_video_next" if not self.paths.get("video") else "pick_subtitle_next" if not self.paths.get("subtitle") else "probing" if self.probe else "ready_to_sync"
            self.status.setText(self.t(key))
        if self.result:
            self.summary.setMinimumHeight(76)
            self.summary.setText(
                Path(self.result["output"]).name
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
            self.summary.setText("")

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

"""Native subtitle editor, converter and opt-in online translation."""
from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from cueflow.formats import FORMATS, batches, parse, seconds, stamp
from cueflow.google import GoogleTranslation
from cueflow.languages import languages


class SubtitleEditor(QDialog):
    def __init__(self, lang='es', parent=None):
        super().__init__(parent)
        self.lang = lang
        self.files = []
        self.page = 0
        self.busy = False
        self.reply = None
        self.queue = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.next_batch)
        self.setWindowTitle(self.tr('Traducir y editar — CueFlow', 'Translate & edit — CueFlow'))
        self.resize(980, 760)
        layout = QVBoxLayout(self)
        intro = QLabel(self.tr('Traduce subtítulos conservando sus tiempos. Editar y convertir funciona sin conexión.', 'Translate subtitles while keeping their timing. Editing and conversion work offline.'))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.add = QPushButton(self.tr('Añadir subtítulos', 'Add subtitles'))
        self.add.clicked.connect(self.add_files)
        self.file_select = QComboBox()
        self.file_select.currentIndexChanged.connect(self.select_file)
        self.remove = QPushButton(self.tr('Quitar', 'Remove'))
        self.remove.clicked.connect(self.remove_file)
        row.addWidget(self.add)
        row.addWidget(self.file_select, 1)
        row.addWidget(self.remove)
        layout.addLayout(row)
        hint = QLabel(self.tr('Hasta 20 archivos / 1 MB · SRT, VTT, ASS, SBV, SubViewer SUB y Spruce STL (texto).', 'Up to 20 files / 1 MB · SRT, VTT, ASS, SBV, SubViewer SUB and Spruce STL (text).'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        self.encoding = QComboBox()
        self.encoding.addItems(['Unicode', 'cp1252', 'cp1251', 'cp1250', 'cp1253', 'cp1254', 'cp1255', 'cp1256', 'shift_jis', 'gb18030', 'big5', 'euc_kr', 'cp874'])
        self.fps = QComboBox()
        self.fps.addItems(['25', '24', '30'])
        self.source, self.target = QComboBox(), QComboBox()
        self.source.addItem(self.tr('Detectar automáticamente', 'Detect automatically'), 'auto')
        names = []
        for entry in languages():
            code = entry["code"]
            locale = QLocale(code)
            name = locale.nativeLanguageName() if locale.language() != QLocale.C else entry["name"]
            names.append((name, code))
        for name, code in sorted(names):
            self.source.addItem(f'{name} ({code})', code)
            self.target.addItem(f'{name} ({code})', code)
        self.target.setCurrentIndex(self.target.findData(lang))
        self.format = QComboBox()
        self.format.addItem(self.tr('Conservar formato', 'Keep original format'), 'same')
        for f in FORMATS:
            self.format.addItem(f.upper(), f)
        for i, (caption, widget) in enumerate([
            (self.tr('Origen', 'Source'), self.source),
            (self.tr('Destino', 'Target'), self.target),
            (self.tr('Codificación de entrada', 'Input encoding'), self.encoding),
            ('STL FPS', self.fps),
        ]):
            label = QLabel(caption)
            label.setBuddy(widget)
            grid.addWidget(label, (i // 2) * 2, i % 2)
            grid.addWidget(widget, (i // 2) * 2 + 1, i % 2)
        layout.addLayout(grid)
        self.consent = QCheckBox(self.tr('Acepto enviar el texto a Google Translate para traducirlo (requiere internet).', 'I agree to send subtitle text to Google Translate for translation (internet required).'))
        self.consent.stateChanged.connect(self.update_controls)
        layout.addWidget(self.consent)
        privacy = QLabel(self.tr('No se envían video, audio ni tiempos. La calidad varía por idioma; revisa el resultado. La sesión se pierde al cerrar.', 'Video, audio and timestamps are not sent. Quality varies by language; review the result. Closing discards this session.'))
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        actions = QHBoxLayout()
        self.translate = QPushButton(self.tr('Google Translate / continuar', 'Google Translate / resume'))
        self.translate.setObjectName('primary')
        self.translate.clicked.connect(self.begin)
        self.cancel = QPushButton(self.tr('Cancelar', 'Cancel'))
        self.cancel.clicked.connect(self.stop)
        actions.addWidget(self.translate)
        actions.addWidget(self.cancel)
        layout.addLayout(actions)
        self.status = QLabel('')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([self.tr('Inicio', 'Start'), self.tr('Fin', 'End'), self.tr('Original', 'Original'), self.tr('Texto de salida', 'Output text')])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 125)
        self.table.setColumnWidth(1, 125)
        self.table.itemChanged.connect(self.save_edit)
        layout.addWidget(self.table, 1)
        pager = QHBoxLayout()
        self.previous = QPushButton(self.tr('Anterior', 'Previous'))
        self.next = QPushButton(self.tr('Siguiente', 'Next'))
        self.previous.clicked.connect(lambda: self.move_page(-1))
        self.next.clicked.connect(lambda: self.move_page(1))
        self.page_label = QLabel('')
        pager.addWidget(self.previous)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next)
        layout.addLayout(pager)
        downloads = QHBoxLayout()
        downloads.addWidget(self.format)
        self.save = QPushButton(self.tr('Guardar archivo', 'Save file'))
        self.save.clicked.connect(self.save_file)
        self.save_all = QPushButton(self.tr('Guardar lote ZIP', 'Save batch ZIP'))
        self.save_all.clicked.connect(self.save_zip)
        downloads.addWidget(self.save)
        downloads.addWidget(self.save_all)
        layout.addLayout(downloads)
        note = QLabel(self.tr('Convertir simplifica estilos y posiciones. ASS/SUB usan centésimas; STL usa los FPS elegidos al abrir.', 'Conversion simplifies styles and positioning. ASS/SUB use hundredths; STL uses the frame rate selected on import.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.update_controls()

    def tr(self, es, en):
        return es if self.lang == 'es' else en

    def message(self, text):
        self.status.setText(text)

    def current(self):
        index = self.file_select.currentIndex()
        return self.files[index] if 0 <= index < len(self.files) else None

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, self.tr('Abrir subtítulos', 'Open subtitles'), '', 'Subtitles (*.srt *.vtt *.ass *.sbv *.sub *.stl)')
        try:
            if len(self.files) + len(paths) > 20 or sum(f['size'] for f in self.files) + sum(Path(p).stat().st_size for p in paths) > 1000000:
                raise ValueError(self.tr('Máximo 20 archivos y 1 MB.', 'Maximum 20 files and 1 MB.'))
            added = []
            for path in paths:
                p = Path(path)
                raw = p.read_bytes()
                enc = self.encoding.currentText()
                if enc == 'Unicode':
                    enc = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
                doc = parse(raw.decode(enc), p.suffix[1:].lower(), int(self.fps.currentText()))
                added.append({'name': p.name, 'size': len(raw), 'doc': doc, 'original': copy.deepcopy(doc.cues), 'done': set(), 'pair': None})
            for f in added:
                self.files.append(f)
                self.file_select.addItem(f['name'])
            self.update_controls()
        except (ValueError, UnicodeError, OSError) as error:
            self.message(self.tr('No se pudo abrir: ', 'Could not open: ') + str(error))

    def select_file(self):
        self.page = 0
        self.render()

    def remove_file(self):
        index = self.file_select.currentIndex()
        if index >= 0:
            self.files.pop(index)
            self.file_select.removeItem(index)
        self.render()

    def move_page(self, delta):
        self.page += delta
        self.render()

    def render(self):
        file = self.current()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if file:
            for row, cue in enumerate(file['doc'].cues[self.page * 20:self.page * 20 + 20]):
                self.table.insertRow(row)
                values = [stamp(cue.start, ','), stamp(cue.end, ','), file['original'][self.page * 20 + row].text, cue.text]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 2:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, col, item)
                self.table.setRowHeight(row, 60)
            self.page_label.setText(f'{self.page + 1} / {(len(file["doc"].cues) + 19) // 20}')
        self.table.blockSignals(False)
        self.update_controls()

    def update_controls(self, *_args):
        have = bool(self.files)
        for widget in [self.add, self.file_select, self.remove, self.encoding, self.fps, self.source, self.target, self.consent, self.table, self.format]:
            widget.setEnabled(not self.busy)
        self.translate.setEnabled(have and self.consent.isChecked() and not self.busy)
        self.cancel.setEnabled(self.busy)
        self.save.setEnabled(have and not self.busy)
        self.save_all.setEnabled(have and not self.busy)
        self.previous.setEnabled(have and self.page > 0 and not self.busy)
        f = self.current()
        self.next.setEnabled(bool(f and (self.page + 1) * 20 < len(f['doc'].cues) and not self.busy))

    def save_edit(self, item):
        f = self.current()
        if not f:
            return
        cue = f['doc'].cues[self.page * 20 + item.row()]
        old = copy.deepcopy(cue)
        try:
            cue.start = seconds(self.table.item(item.row(), 0).text())
            cue.end = seconds(self.table.item(item.row(), 1).text())
            cue.text = self.table.item(item.row(), 3).text()
            f['doc'].validate()
            self.message(self.tr('Cambios guardados en esta sesión.', 'Changes saved for this session.'))
        except ValueError:
            cue.start, cue.end, cue.text = old.start, old.end, old.text
            self.message(self.tr('Cambio rechazado: tiempos no válidos o texto vacío.', 'Change rejected: invalid times or empty text.'))
            self.render()

    def begin(self):
        if self.busy or not self.consent.isChecked():
            return
        pair = (self.source.currentData(), self.target.currentData())
        if pair[0] == pair[1]:
            self.message(self.tr('Elige un idioma diferente.', 'Choose a different language.'))
            return
        self.queue = []
        try:
            for f in self.files:
                if f['pair'] != pair:
                    f['done'].clear()
                    f['pair'] = pair
                for indices in batches(f['original']):
                    if not all(i in f['done'] for i in indices):
                        self.queue.append((f, indices))
        except ValueError as error:
            self.message(str(error))
            return
        self.busy = True
        self.update_controls()
        self.next_batch()

    def next_batch(self):
        if not self.busy:
            return
        if not self.queue:
            self.busy = False
            self.message(self.tr('Traducción completa. Revisa y guarda el resultado.', 'Translation complete. Review and save the result.'))
            self.render()
            return
        file, indices = self.queue[0]
        self.message(f'{file["name"]} · {len(file["done"])}/{len(file["doc"].cues)}')
        job = GoogleTranslation([file['original'][i].text for i in indices], file['pair'][0], file['pair'][1], self.lang, self)
        self.reply = job
        job.finished.connect(lambda values: self.received(job, file, indices, values))
        job.failed.connect(lambda error: self.translation_error(job, error))
        job.start()

    def received(self, job, file, indices, values):
        if self.reply != job or not self.busy:
            return
        self.reply = None
        for index, text in zip(indices, values):
            file['doc'].cues[index].text = text
            file['done'].add(index)
        self.queue.pop(0)
        self.render()
        self.timer.start(300)

    def translation_error(self, job, error):
        if self.reply != job or not self.busy:
            return
        self.reply = None
        self.busy = False
        self.message(self.tr('Google no completó este bloque. Comprueba internet y los bloqueadores de contenido. Pulsa Google Translate / continuar para reintentar. El progreso se conserva.', 'Google did not complete this batch. Check internet and content blockers. Press Google Translate / resume to retry. Progress is preserved.'))
        self.render()

    def stop(self):
        self.busy = False
        self.timer.stop()
        reply, self.reply = self.reply, None
        if reply:
            reply.cancel()
        self.message(self.tr('Detenido. Puedes continuar o guardar el resultado parcial.', 'Stopped. Resume or save the partial result.'))
        self.render()

    def output(self, f, index):
        format = self.format.currentData()
        if format == 'same':
            format = f['doc'].format
        suffix = '.edited'
        if f['done']:
            suffix = '.' + f['pair'][1] + ('.partial' if len(f['done']) < len(f['doc'].cues) else '')
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', Path(f['name']).stem)
        return f'{index + 1}-{name}{suffix}.{format}', f['doc'].serialize(format)

    def save_file(self):
        try:
            name, text = self.output(self.current(), self.file_select.currentIndex())
            path, _ = QFileDialog.getSaveFileName(self, self.tr('Guardar copia', 'Save copy'), name)
            if path:
                Path(path).write_text(text, encoding='utf-8', newline='\n')
                self.message(self.tr('Copia guardada.', 'Copy saved.'))
        except (ValueError, OSError) as error:
            self.message(str(error))

    def save_zip(self):
        try:
            outputs = [self.output(f, i) for i, f in enumerate(self.files)]
            path, _ = QFileDialog.getSaveFileName(self, self.tr('Guardar lote', 'Save batch'), 'CueFlow-subtitles.zip', 'ZIP (*.zip)')
            if path:
                with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for name, text in outputs:
                        archive.writestr(name, text.encode('utf-8'))
                self.message(self.tr('ZIP guardado.', 'ZIP saved.'))
        except (ValueError, OSError) as error:
            self.message(str(error))

    def closeEvent(self, event):
        if self.files:
            answer = QMessageBox.question(self, 'CueFlow', self.tr('¿Cerrar el editor? Descarga primero los cambios que quieras conservar.', 'Close the editor? Download any changes you want to keep first.'), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.stop()
        event.accept()

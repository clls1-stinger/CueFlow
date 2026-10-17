"""Native subtitle editor, converter and opt-in online translation."""
from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cueflow.formats import FORMATS, batches, parse, seconds, stamp
from cueflow.google import GoogleTranslation
from cueflow.languages import languages


class SubtitleEditor(QDialog):
    def __init__(self, lang='es', parent=None, mode='translate'):
        super().__init__(parent)
        from cueflow.app import STYLE, label

        self.lang, self.mode = lang, mode
        self.files, self.queue = [], []
        self.page, self.busy, self.reply = 0, False, None
        self.saved_path = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.next_batch)
        self.setStyleSheet(STYLE)
        self.setWindowTitle(self.tr('Subtítulos · CueFlow', 'Subtitles · CueFlow'))
        self.resize(940, 740)
        self.setMinimumSize(720, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        header = QHBoxLayout()
        self.back = QPushButton(self.tr('← Inicio', '← Home'))
        self.back.clicked.connect(self.go_back)
        header.addWidget(self.back)
        header.addStretch()
        header.addWidget(label('CueFlow', 'brand'))
        layout.addLayout(header)
        layout.addWidget(label(self.tr('Traducir subtítulos', 'Translate subtitles') if mode == 'translate' else self.tr('Editar subtítulos', 'Edit subtitles'), 'title'))
        self.steps = label(role='muted')
        layout.addWidget(self.steps)
        self.file_bar = QWidget()
        file_row = QHBoxLayout(self.file_bar)
        file_row.setContentsMargins(0, 0, 0, 0)
        self.file_select = QComboBox()
        self.file_select.setAccessibleName(self.tr('Archivo que estás revisando', 'File you are reviewing'))
        self.file_select.currentIndexChanged.connect(self.select_file)
        self.remove = QPushButton(self.tr('Quitar archivo', 'Remove file'))
        self.remove.clicked.connect(self.remove_file)
        self.manage = QPushButton(self.tr('Añadir archivos', 'Add files'))
        self.manage.clicked.connect(lambda: self.show_step(0))
        file_row.addWidget(self.file_select, 1)
        file_row.addWidget(self.manage)
        file_row.addWidget(self.remove)
        layout.addWidget(self.file_bar)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        opening = QWidget()
        first = QVBoxLayout(opening)
        first.setContentsMargins(0, 16, 0, 0)
        first.setSpacing(18)
        first.addWidget(label(self.tr('Abre el archivo de subtítulos', 'Open your subtitle file'), 'step'))
        first.addWidget(label(self.tr('No necesitas el video para traducir o editar. Busca un archivo como pelicula.srt.', 'You do not need the video to translate or edit. Look for a file such as movie.srt.'), 'muted'))
        self.add = QPushButton(self.tr('Elegir subtítulos', 'Choose subtitles'))
        self.add.setObjectName('primary')
        self.add.clicked.connect(self.add_files)
        first.addWidget(self.add)
        first.addWidget(label(self.tr('Puedes elegir hasta 20 archivos (1 MB en total).\nFormatos: SRT, VTT, ASS, SBV, SUB y STL de texto.', 'Choose up to 20 files (1 MB total).\nFormats: SRT, VTT, ASS, SBV, SUB and text STL.'), 'muted'))
        self.find_subtitles = QPushButton(self.tr('¿No tienes el archivo? Buscar en OpenSubtitles ↗', 'Need the file? Search OpenSubtitles ↗'))
        self.find_subtitles.clicked.connect(self.open_search)
        first.addWidget(self.find_subtitles)
        self.import_options = QCheckBox(self.tr('Opciones para archivos antiguos o con letras extrañas', 'Options for older files or unreadable characters'))
        first.addWidget(self.import_options)
        import_panel = QWidget()
        import_layout = QVBoxLayout(import_panel)
        self.encoding = QComboBox()
        self.encoding.addItems(['Unicode', 'cp1252', 'cp1251', 'cp1250', 'cp1253', 'cp1254', 'cp1255', 'cp1256', 'shift_jis', 'gb18030', 'big5', 'euc_kr', 'cp874'])
        self.fps = QComboBox()
        self.fps.addItems(['25', '24', '30'])
        for caption, widget in [(self.tr('Cómo leer los caracteres (codificación)', 'How to read characters (encoding)'), self.encoding), (self.tr('Fotogramas por segundo, solo para STL', 'Frames per second, only for STL'), self.fps)]:
            caption_label = label(caption)
            caption_label.setBuddy(widget)
            import_layout.addWidget(caption_label)
            import_layout.addWidget(widget)
        import_panel.hide()
        self.import_options.toggled.connect(import_panel.setVisible)
        first.addWidget(import_panel)
        self.continue_button = QPushButton(self.tr('Continuar con los archivos abiertos', 'Continue with the open files'))
        self.continue_button.clicked.connect(lambda: self.show_step(1 if self.mode == 'translate' else 2))
        first.addWidget(self.continue_button)
        first.addStretch()
        self.pages.addWidget(opening)

        translating = QWidget()
        second = QVBoxLayout(translating)
        second.setContentsMargins(0, 12, 0, 0)
        second.setSpacing(16)
        target_label = label(self.tr('¿En qué idioma los quieres?', 'Which language would you like?'), 'step')
        second.addWidget(target_label)
        self.source, self.target = QComboBox(), QComboBox()
        self.source.addItem(self.tr('Detectar automáticamente', 'Detect automatically'), 'auto')
        names = []
        for entry in languages():
            code = entry['code']
            locale = QLocale(code)
            name = entry['name'] if lang == 'es' or locale.language() == QLocale.C else QLocale.languageToString(locale.language())
            names.append((name, code))
        for name, code in sorted(names):
            # Codes distinguish regional variants with the same display name.
            self.source.addItem(f'{name} ({code})', code)
            self.target.addItem(f'{name} ({code})', code)
        self.target.setCurrentIndex(self.target.findData(lang))
        self.target.setEditable(True)
        self.target.setInsertPolicy(QComboBox.NoInsert)
        self.target.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.target.completer().setFilterMode(Qt.MatchContains)
        self.target.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.target.lineEdit().setPlaceholderText(self.tr('Escribe para buscar un idioma', 'Type to find a language'))
        self.target.setToolTip(self.tr('Puedes escribir el nombre del idioma para buscarlo.', 'Type a language name to find it.'))
        target_label.setBuddy(self.target)
        second.addWidget(self.target)
        self.source_toggle = QCheckBox(self.tr('Elegir el idioma original manualmente', 'Choose the original language manually'))
        second.addWidget(self.source_toggle)
        self.source.hide()
        self.source.setAccessibleName(self.tr('Idioma original', 'Original language'))
        self.source_toggle.toggled.connect(self.source.setVisible)
        self.source_toggle.toggled.connect(lambda checked: None if checked else self.source.setCurrentIndex(0))
        second.addWidget(self.source)
        second.addWidget(label(self.tr('Google traducirá el archivo original. Después podrás corregir el resultado.', 'Google will translate the original file. You can edit the result afterwards.'), 'muted'))
        self.consent = QCheckBox(self.tr('Permitir que Google traduzca el texto (requiere internet)', 'Allow Google to translate the text (internet required)'))
        second.addWidget(self.consent)
        second.addWidget(label(self.tr('Solo se envían los diálogos. El video y el audio se quedan en tu equipo.', 'Only the dialogue is sent. Your video and audio stay on your device.'), 'muted'))
        self.translate = QPushButton()
        self.translate.setObjectName('primary')
        self.translate.clicked.connect(self.begin)
        self.cancel = QPushButton(self.tr('Detener traducción', 'Stop translation'))
        self.cancel.clicked.connect(self.stop)
        second.addWidget(self.translate)
        second.addWidget(self.cancel)
        self.progress = QProgressBar()
        second.addWidget(self.progress)
        self.review_button = QPushButton(self.tr('Revisar o editar sin traducir', 'Review or edit without translating'))
        self.review_button.clicked.connect(lambda: self.show_step(2))
        second.addWidget(self.review_button)
        second.addStretch()
        self.pages.addWidget(translating)

        reviewing = QWidget()
        third = QVBoxLayout(reviewing)
        third.setContentsMargins(0, 0, 0, 0)
        third.setSpacing(12)
        third.addWidget(label(self.tr('Revisa el texto y guarda una copia', 'Review the text and save a copy'), 'step'))
        third.addWidget(label(self.tr('Haz doble clic en «Tu versión» para corregir una frase. El archivo original se conserva.', 'Double-click “Your version” to edit a line. Your original file is kept.'), 'muted'))
        self.times_toggle = QCheckBox(self.tr('También quiero editar los tiempos', 'I also want to edit the timing'))
        third.addWidget(self.times_toggle)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([self.tr('Inicio', 'Start'), self.tr('Fin', 'End'), self.tr('Original', 'Original'), self.tr('Tu versión', 'Your version')])
        self.table.setAccessibleName(self.tr('Original y texto que guardarás', 'Original and text you will save'))
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 125)
        self.table.setColumnWidth(1, 125)
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(1, True)
        self.times_toggle.toggled.connect(lambda checked: [self.table.setColumnHidden(i, not checked) for i in (0, 1)])
        self.table.itemChanged.connect(self.save_edit)
        third.addWidget(self.table, 1)
        pager = QHBoxLayout()
        self.previous = QPushButton(self.tr('← Anteriores', '← Previous'))
        self.next = QPushButton(self.tr('Siguientes →', 'Next →'))
        self.previous.clicked.connect(lambda: self.move_page(-1))
        self.next.clicked.connect(lambda: self.move_page(1))
        self.page_label = label()
        pager.addWidget(self.previous)
        pager.addWidget(self.page_label, 1, Qt.AlignCenter)
        pager.addWidget(self.next)
        third.addLayout(pager)
        self.format_toggle = QCheckBox(self.tr('Guardar en otro formato', 'Save in another format'))
        third.addWidget(self.format_toggle)
        self.format = QComboBox()
        self.format.addItem(self.tr('Conservar formato original', 'Keep the original format'), 'same')
        for f in FORMATS:
            self.format.addItem(f.upper(), f)
        self.format.hide()
        self.format_toggle.toggled.connect(self.format.setVisible)
        self.format_toggle.toggled.connect(lambda checked: None if checked else self.format.setCurrentIndex(0))
        third.addWidget(self.format)
        self.format_note = label(self.tr('Al convertir pueden cambiar los estilos, las posiciones y la precisión de los tiempos.', 'Converting can change styling, positioning and timing precision.'), 'muted')
        third.addWidget(self.format_note)
        downloads = QHBoxLayout()
        self.save = QPushButton(self.tr('Guardar una copia…', 'Save a copy…'))
        self.save.setObjectName('primary')
        self.save.clicked.connect(self.save_file)
        self.save_all = QPushButton(self.tr('Guardar todos en un ZIP…', 'Save all in a ZIP…'))
        self.save_all.clicked.connect(self.save_zip)
        downloads.addWidget(self.save, 1)
        downloads.addWidget(self.save_all)
        third.addLayout(downloads)
        self.open_saved = QPushButton(self.tr('Abrir carpeta del archivo guardado', 'Open the saved file’s folder'))
        self.open_saved.clicked.connect(self.open_saved_folder)
        third.addWidget(self.open_saved)
        self.pages.addWidget(reviewing)
        self.status = label()
        layout.addWidget(self.status)
        for signal in (self.consent.stateChanged, self.target.currentIndexChanged, self.target.editTextChanged, self.source.currentIndexChanged, self.format.currentIndexChanged):
            signal.connect(self.update_controls)
        self.show_step(0)

    def open_search(self):
        from cueflow.search import SubtitleSearch

        dialog = SubtitleSearch(self.lang, load_file=self.add_files, parent=self)
        dialog.exec()

    def show_step(self, step):
        if self.busy:
            return
        self.pages.setCurrentIndex(step if self.files or step == 0 else 0)
        self.update_controls()

    def go_back(self):
        step = self.pages.currentIndex()
        if step == 0:
            self.reject()
        else:
            self.show_step(1 if step == 2 and self.mode == 'translate' else 0)

    def open_saved_folder(self):
        if self.saved_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.saved_path).parent)))

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
                added.append({'name': p.name, 'size': len(raw), 'doc': doc, 'original': copy.deepcopy(doc.cues), 'done': set(), 'pair': None, 'dirty': False})
            for f in added:
                self.files.append(f)
                self.file_select.addItem(f['name'])
            if added:
                self.message('')
                self.show_step(1 if self.mode == 'translate' else 2)
            self.update_controls()
        except (ValueError, UnicodeError, OSError) as error:
            self.message(self.tr('No se pudo abrir: ', 'Could not open: ') + str(error))

    def select_file(self):
        self.page = 0
        f = self.current()
        self.saved_path = f.get("saved_path") if f else None
        self.render()

    def remove_file(self):
        index = self.file_select.currentIndex()
        if index >= 0:
            if self.files[index].get('dirty') and QMessageBox.question(self, 'CueFlow', self.tr('Este archivo tiene cambios sin guardar. ¿Quitarlo?', 'This file has unsaved changes. Remove it?'), QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            self.files.pop(index)
            self.file_select.removeItem(index)
        if not self.files:
            self.show_step(0)
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
        for widget in [self.add, self.file_select, self.remove, self.encoding, self.fps, self.source, self.target, self.consent, self.table, self.format, self.back, self.manage, self.review_button, self.continue_button]:
            widget.setEnabled(not self.busy)
        step = self.pages.currentIndex()
        self.file_bar.setVisible(have and step != 1)
        self.continue_button.setVisible(have)
        self.translate.setEnabled(have and self.consent.isChecked() and not self.busy and self.target.findText(self.target.currentText()) >= 0)
        done = sum(len(f['done']) for f in self.files)
        total = sum(len(f['doc'].cues) for f in self.files)
        self.translate.setText(self.tr('Continuar traducción', 'Resume translation') if 0 < done < total else self.tr('Traducir con Google', 'Translate with Google'))
        self.cancel.setVisible(self.busy)
        self.progress.setVisible(self.busy)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.save.setEnabled(have and not self.busy)
        self.save_all.setEnabled(have and not self.busy)
        self.save_all.setVisible(len(self.files) > 1)
        self.open_saved.setVisible(bool(self.saved_path))
        self.format_note.setVisible(self.format.currentData() != 'same')
        self.previous.setEnabled(have and self.page > 0 and not self.busy)
        f = self.current()
        self.next.setEnabled(bool(f and (self.page + 1) * 20 < len(f['doc'].cues) and not self.busy))
        self.previous.setVisible(bool(f and len(f['doc'].cues) > 20))
        self.next.setVisible(bool(f and len(f['doc'].cues) > 20))
        self.page_label.setVisible(bool(f and len(f['doc'].cues) > 20))
        titles = [self.tr('1. Abrir archivo', '1. Open file'), self.tr('2. Elegir idioma y traducir', '2. Choose language and translate'), self.tr('3. Revisar y guardar', '3. Review and save')]
        if self.mode == 'edit':
            titles[2] = self.tr('2. Editar y guardar', '2. Edit and save')
        self.steps.setText(titles[step] + (f' · {len(self.files)} ' + self.tr('archivo' if len(self.files) == 1 else 'archivos', 'file' if len(self.files) == 1 else 'files') if have else ''))
        self.back.setText(self.tr('← Inicio', '← Home') if step == 0 else self.tr('← Volver', '← Back'))

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
            f['dirty'] = True
            f['saved_path'] = self.saved_path = None
            self.update_controls()
            self.message(self.tr('Cambios pendientes. Pulsa Guardar una copia para conservarlos.', 'Unsaved changes. Click Save a copy to keep them.'))
        except ValueError:
            cue.start, cue.end, cue.text = old.start, old.end, old.text
            self.message(self.tr('Cambio rechazado: tiempos no válidos o texto vacío.', 'Change rejected: invalid times or empty text.'))
            self.render()

    def begin(self):
        if self.busy or not self.consent.isChecked():
            return
        target_index = self.target.findText(self.target.currentText())
        if target_index < 0:
            self.message(self.tr('Elige un idioma de la lista.', 'Choose a language from the list.'))
            return
        self.target.setCurrentIndex(target_index)
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
            self.message(self.tr('Traducción terminada. Aún falta guardar tu copia.', 'Translation finished. Save your copy to keep it.'))
            self.show_step(2)
            self.render()
            return
        file, indices = self.queue[0]
        self.message(self.tr('Traduciendo ', 'Translating ') + f'{file["name"]} · {len(file["done"])}/{len(file["doc"].cues)} ' + self.tr('frases completadas', 'lines completed'))
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
            file['dirty'] = True
            file['saved_path'] = self.saved_path = None
        self.queue.pop(0)
        self.render()
        self.timer.start(300)

    def translation_error(self, job, error):
        if self.reply != job or not self.busy:
            return
        self.reply = None
        self.busy = False
        self.message(self.tr('Google no completó este bloque. Comprueba internet y los bloqueadores de contenido. Vuelve a pulsar el botón de traducción para reintentar. El progreso se conserva.', 'Google did not complete this batch. Check internet and content blockers. Click the translation button to retry. Progress is preserved.'))
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
                self.current()['dirty'] = False
                self.current()['saved_path'] = path
                self.saved_path = path
                self.message(self.tr('Copia guardada: ', 'Copy saved: ') + path)
                self.update_controls()
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
                for f in self.files:
                    f['dirty'] = False
                    f['saved_path'] = path
                self.saved_path = path
                self.message(self.tr('ZIP guardado: ', 'ZIP saved: ') + path)
                self.update_controls()
        except (ValueError, OSError) as error:
            self.message(str(error))

    def reject(self):
        if self.busy or any(f.get('dirty') for f in self.files):
            answer = QMessageBox.question(self, 'CueFlow', self.tr('Tienes trabajo sin guardar. ¿Cerrar y descartarlo?', 'You have unsaved work. Close and discard it?'), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        self.stop()
        super().reject()

    def closeEvent(self, event):
        event.ignore()
        self.reject()

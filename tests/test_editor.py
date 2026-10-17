import copy

from PySide6.QtWidgets import QFileDialog, QMessageBox

from cueflow.editor import SubtitleEditor
from cueflow.formats import parse
from cueflow.languages import languages

SOURCE = '1\n00:00:01,000 --> 00:00:03,000\nHello.\n'


def test_native_editor_import_edit_export_and_consent(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args, **kwargs: QMessageBox.Yes)
    source = tmp_path / 'original.srt'
    source.write_text(SOURCE)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(source)], ''))
    editor = SubtitleEditor('es')
    qtbot.addWidget(editor)
    editor.add_files()
    assert editor.table.rowCount() == 1
    assert not editor.translate.isEnabled()
    editor.consent.setChecked(True)
    assert editor.translate.isEnabled()
    editor.table.item(0, 3).setText('Hola.')
    editor.format.setCurrentIndex(editor.format.findData('vtt'))
    _, output = editor.output(editor.files[0], 0)
    assert output.startswith('WEBVTT')
    assert 'Hola.' in output
    assert '00:00:01.000 --> 00:00:03.000' in output
    assert source.read_text() == SOURCE
    editor.table.item(0, 1).setText('00:00:00,000')
    assert editor.files[0]['doc'].cues[0].end == 3
    assert len(languages()) >= 200


def test_native_google_batches_resume_without_retranslating_finished(qtbot, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    monkeypatch.setattr(QMessageBox, 'question', lambda *args, **kwargs: QMessageBox.Yes)
    calls = []

    class GoogleFixture(QObject):
        finished = Signal(object)
        failed = Signal(str)

        def __init__(self, texts, source, target, language, parent):
            super().__init__(parent)
            self.texts = texts

        def start(self):
            calls.append(self.texts)
            self.finished.emit(['Hola.' for text in self.texts])

        def cancel(self):
            self.failed.emit('cancelled')

    monkeypatch.setattr('cueflow.editor.GoogleTranslation', GoogleFixture)
    editor = SubtitleEditor('es')
    qtbot.addWidget(editor)
    doc = parse(SOURCE, 'srt')
    editor.files.append({'name':'demo.srt','size':len(SOURCE),'doc':doc,'original':copy.deepcopy(doc.cues),'done':set(),'pair':None})
    editor.file_select.addItem('demo.srt')
    editor.consent.setChecked(True)
    editor.begin()
    qtbot.waitUntil(lambda: not editor.busy)
    assert editor.files[0]['doc'].cues[0].text == 'Hola.'
    editor.begin()
    assert len(calls) == 1


def test_guided_editor_and_saved_state(qtbot, tmp_path, monkeypatch):
    source = tmp_path / 'original.srt'
    source.write_text(SOURCE)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(source)], ''))
    editor = SubtitleEditor('es')
    qtbot.addWidget(editor)
    editor.show()
    assert editor.pages.currentIndex() == 0
    assert not editor.table.isVisible()
    assert not editor.encoding.isVisible()
    editor.add_files()
    assert editor.pages.currentIndex() == 1
    assert not editor.translate.isEnabled()
    assert not editor.source.isVisible()
    editor.show_step(2)
    assert editor.table.isColumnHidden(0)
    assert not editor.save_all.isVisible()
    editor.table.item(0, 3).setText('Hola.')
    assert editor.files[0]['dirty']
    monkeypatch.setattr(QMessageBox, 'question', lambda *args, **kwargs: QMessageBox.No)
    editor.reject()
    assert editor.isVisible()
    output = tmp_path / 'translated.srt'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output), ''))
    editor.save_file()
    assert not editor.files[0]['dirty']
    assert 'Hola.' in output.read_text()
    assert source.read_text() == SOURCE
    assert editor.open_saved.isVisible()
    editor.reject()
    assert not editor.isVisible()


def test_edit_mode_skips_online_translation(qtbot, tmp_path, monkeypatch):
    source = tmp_path / 'original.srt'
    source.write_text(SOURCE)
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args: ([str(source)], ''))
    editor = SubtitleEditor('en', mode='edit')
    qtbot.addWidget(editor)
    editor.show()
    editor.add_files()
    assert editor.pages.currentIndex() == 2
    assert not editor.consent.isVisible()
    assert editor.save.isEnabled()
    editor.go_back()
    assert editor.pages.currentIndex() == 0

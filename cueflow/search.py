"""User-initiated OpenSubtitles search in the user's normal browser."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout


def suggested_title(filename: str) -> str:
    """An editable suggestion, never an inferred identification of the movie."""
    title = Path(filename).stem.replace('.', ' ').replace('_', ' ')
    title = re.split(r'\b(?:2160p|1080p|720p|480p|bluray|blu ray|webrip|web[ -]?dl|dvdrip|x26[45]|h26[45])\b', title, maxsplit=1, flags=re.I)[0]
    return ' '.join(title.replace('[', ' ').replace(']', ' ').split()).strip(' -')[:160]


def search_url(query: str, language: str = 'es') -> str:
    language = 'es' if language == 'es' else 'en'
    query = query.strip()
    if not query:
        return f'https://www.opensubtitles.com/{language}/home'
    return f'https://www.opensubtitles.com/{language}/all/search-all/q-{quote(query, safe="")}/hearing_impaired-include/machine_translated-/trusted_sources-'


class SubtitleSearch(QDialog):
    def __init__(self, language='es', filename='', load_file=None, parent=None):
        super().__init__(parent)
        from cueflow.app import STYLE, label

        self.language, self.load_file = language, load_file
        self.setStyleSheet(STYLE)
        self.setWindowTitle('OpenSubtitles · CueFlow')
        self.resize(620, 410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label(self.tr('Busca los subtítulos que te faltan', 'Find the subtitles you need'), 'step'))
        caption = label(self.tr('Nombre de la película o serie', 'Movie or TV show title'))
        layout.addWidget(caption)
        self.query = QLineEdit(suggested_title(filename) if filename else '')
        self.query.setMaxLength(160)
        self.query.setPlaceholderText(self.tr('Por ejemplo: The Congress', 'For example: The Congress'))
        caption.setBuddy(self.query)
        layout.addWidget(self.query)
        layout.addWidget(label(self.tr('Se abrirá OpenSubtitles en tu navegador. Allí puedes elegir el idioma y descargar el archivo. El sitio puede pedirte iniciar sesión.', 'OpenSubtitles opens in your browser. Choose the language and download the file there. The site may ask you to sign in.'), 'muted'))
        self.search = QPushButton(self.tr('Buscar en OpenSubtitles ↗', 'Search OpenSubtitles ↗'))
        self.search.setObjectName('primary')
        self.search.clicked.connect(self.open_search)
        self.query.returnPressed.connect(self.open_search)
        self.query.textChanged.connect(lambda text: self.search.setEnabled(bool(text.strip())))
        self.search.setEnabled(bool(self.query.text().strip()))
        layout.addWidget(self.search)
        self.home = QPushButton(self.tr('Abrir la página principal ↗', 'Open the home page ↗'))
        self.home.clicked.connect(lambda: self.open_url(search_url('', self.language)))
        layout.addWidget(self.home)
        self.downloaded = QPushButton(self.tr('Ya lo descargué: abrir subtítulos…', 'Downloaded it: open subtitles…'))
        self.downloaded.clicked.connect(self.load_download)
        self.downloaded.setVisible(load_file is not None)
        layout.addWidget(self.downloaded)
        self.status = label()
        self.status.setOpenExternalLinks(False)
        layout.addWidget(self.status)
        self.query.setFocus()

    def tr(self, es, en):
        return es if self.language == 'es' else en

    def open_url(self, url):
        if QDesktopServices.openUrl(QUrl(url)):
            self.status.setText(self.tr('Continúa en el navegador. Después vuelve aquí para abrir el archivo descargado. Si recibes un ZIP, extráelo primero.', 'Continue in your browser, then return here to open the downloaded file. Extract it first if you receive a ZIP.'))
        else:
            self.status.setText(self.tr('No se pudo abrir el navegador: ', 'Could not open the browser: ') + url)

    def open_search(self):
        if self.query.text().strip():
            self.open_url(search_url(self.query.text(), self.language))

    def load_download(self):
        if self.load_file:
            self.accept()
            self.load_file()

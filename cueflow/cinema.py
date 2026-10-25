"""The same temporary cinema workspace inside the desktop application."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QVBoxLayout


class CinemaDialog(QDialog):
    def __init__(self, lang="es", parent=None):
        super().__init__(parent)
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.setWindowTitle("CueFlow · Películas" if lang == "es" else "CueFlow · Movies")
        self.resize(1050, 800)
        layout = QVBoxLayout(self)
        note = QLabel("Los archivos de Oracle caducan; las descargas guardadas en tu equipo se conservan."
            if lang == "es" else "Oracle files expire; downloads saved on your computer are kept.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.profile = QWebEngineProfile(self)
        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(self.profile, self.view))
        self.profile.downloadRequested.connect(self.download)
        layout.addWidget(self.view)
        self.view.load(QUrl("https://cueflow.enriquepl.com/#movies"))

    def download(self, item):
        name = Path(item.downloadFileName()).name
        destination, _ = QFileDialog.getSaveFileName(self, "CueFlow", str(Path.home() / "Downloads" / name))
        if not destination:
            item.cancel()
            return
        path = Path(destination)
        item.setDownloadDirectory(str(path.parent))
        item.setDownloadFileName(path.name)
        item.accept()

    def closeEvent(self, event):
        self.view.setUrl(QUrl("about:blank"))
        super().closeEvent(event)

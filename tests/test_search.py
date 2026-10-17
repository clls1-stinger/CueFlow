from urllib.parse import unquote, urlsplit

from PySide6.QtGui import QDesktopServices

from cueflow.search import SubtitleSearch, search_url, suggested_title


def test_search_title_and_url_stay_on_official_site():
    assert suggested_title('/movies/The.Congress.2013.1080p.BluRay.x264.mp4') == 'The Congress 2013'
    query = 'Amélie / 千と千尋 ? #test'
    parsed = urlsplit(search_url(query))
    assert parsed.netloc == 'www.opensubtitles.com'
    assert not parsed.query and not parsed.fragment
    assert query in unquote(parsed.path)
    assert search_url('', 'unknown') == 'https://www.opensubtitles.com/en/home'


def test_search_handoff_and_return(qtbot, monkeypatch):
    opened, loaded = [], []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: opened.append(url.toString()) or True)
    dialog = SubtitleSearch('es', '/movies/Evening.Walk.1080p.mp4', lambda: loaded.append(True))
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.query.text() == 'Evening Walk'
    dialog.open_search()
    assert len(opened) == 1 and 'search-all' in opened[0]
    assert 'navegador' in dialog.status.text()
    dialog.query.clear()
    assert not dialog.search.isEnabled()
    dialog.open_search()
    assert len(opened) == 1
    dialog.load_download()
    assert loaded == [True]
    assert not dialog.isVisible()

from pathlib import Path

import pytest

from cueflow.engine import SyncError, SyncRequest, read_subtitles, save_unique, synchronize
from cueflow.smoke import fixture


def test_preserves_original_and_recovers_offset(tmp_path):
    video, subtitle = fixture(tmp_path)
    original = subtitle.read_bytes()
    result = synchronize(SyncRequest(str(video), str(subtitle), str(tmp_path), fix_framerate=False))
    assert result["cues"] == 10
    assert result["offset"] == pytest.approx(-2, abs=0.5)
    assert subtitle.read_bytes() == original
    assert Path(result["output"]).exists()


def test_no_overwrite_even_with_existing_result(tmp_path):
    first = save_unique(tmp_path, "movie", "first")
    second = save_unique(tmp_path, "movie", "second")
    assert first != second
    assert first.read_text() == "first"
    assert second.read_text() == "second"


@pytest.mark.parametrize("encoding", ["utf-8-sig", "cp1252", "utf-16", "latin1"])
def test_legacy_and_unicode_subtitles(tmp_path, encoding):
    path = tmp_path / "sub.srt"
    text = "1\n00:00:01,000 --> 00:00:03,000\n¿Mañana? Sí, aquí.\n"
    path.write_bytes(text.encode(encoding))
    _, entries, _, _ = read_subtitles(path, encoding, True)
    assert entries[0].content == "¿Mañana? Sí, aquí."


def test_preserves_styling_and_non_latin_text(tmp_path):
    path = tmp_path / "sub.srt"
    text = "1\n00:00:01,000 --> 00:00:03,000\n<i>こんにちは &amp; مرحبًا</i>\n"
    path.write_text(text, encoding="utf-8")
    cleaned, _, _, _ = read_subtitles(path, "auto", True)
    assert cleaned == text


@pytest.mark.parametrize("text", ["not a subtitle", "1\n00:00:03,000 --> 00:00:01,000\nNo\n"])
def test_rejects_invalid_srt(tmp_path, text):
    path = tmp_path / "bad.srt"
    path.write_text(text)
    with pytest.raises(SyncError, match="subtitle_invalid"):
        read_subtitles(path, "auto", True)


def test_refuses_output_for_missing_input(tmp_path):
    with pytest.raises(SyncError, match="input_missing"):
        synchronize(SyncRequest("missing", "missing", str(tmp_path)))
    assert not list(tmp_path.iterdir())

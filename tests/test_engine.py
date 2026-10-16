from pathlib import Path

import pytest

from cueflow.engine import (
    SyncError,
    SyncRequest,
    probe_audio_tracks,
    read_subtitles,
    save_unique,
    synchronize,
)
from cueflow.smoke import MULTILINGUAL_LINES, fixture, multitrack_fixture


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_preserves_original_and_recovers_offset(tmp_path, line_ending):
    video, subtitle = fixture(tmp_path)
    subtitle.write_bytes(subtitle.read_text(encoding="utf-8").replace("\n", line_ending).encode())
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
    path.write_bytes(text.encode("utf-8"))
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


@pytest.mark.parametrize(
    "encoding,content",
    [
        ("cp932", "明日また会いましょう。"),
        ("gb18030", "明天再见。"),
        ("cp949", "내일 만나요."),
        ("cp1251", "Привет, мир."),
        ("cp1256", "مرحبا بالعالم"),
        ("cp1255", "שלום עולם"),
        ("cp874", "พรุ่งนี้พบกันใหม่"),
        ("utf-32", "कल फिर मिलेंगे।"),
    ],
)
def test_multilingual_legacy_encodings(tmp_path, encoding, content):
    path = tmp_path / "sub.srt"
    path.write_bytes(f"1\n00:00:01,000 --> 00:00:03,000\n{content}\n".encode(encoding))
    choice = "auto" if encoding == "utf-32" else encoding
    _, entries, _, _ = read_subtitles(path, choice, True)
    assert entries[0].content == content


def test_selected_audio_and_multilingual_output(tmp_path):
    import srt

    media, subtitle = multitrack_fixture(tmp_path)
    original = subtitle.read_bytes()
    tracks = probe_audio_tracks(media)
    assert [t["language"] for t in tracks] == ["eng", "jpn"]
    with pytest.raises(SyncError, match="no_speech"):
        synchronize(SyncRequest(str(media), str(subtitle), str(tmp_path), audio_track=0))
    with pytest.raises(SyncError, match="audio_track_invalid"):
        synchronize(SyncRequest(str(media), str(subtitle), str(tmp_path), audio_track=2))
    assert not list(tmp_path.glob("*.synced*.srt"))
    result = synchronize(
        SyncRequest(
            str(media),
            str(subtitle),
            str(tmp_path),
            audio_track=1,
            fix_framerate=False,
        )
    )
    assert result["offset"] == pytest.approx(-2, abs=0.5)
    assert result["audio_track"] == 2
    assert subtitle.read_bytes() == original
    output = Path(result["output"]).read_text(encoding="utf-8")
    assert [entry.content for entry in srt.parse(output)] == MULTILINGUAL_LINES

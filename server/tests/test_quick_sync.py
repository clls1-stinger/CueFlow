import shutil
import subprocess
import wave
from datetime import timedelta
from pathlib import Path

import pytest
import srt

from cueflow.engine import SyncError, ffmpeg_directory
from cueflow.smoke import MULTILINGUAL_LINES, fixture
from server import quick_sync


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    folder = tmp_path_factory.mktemp("quick-original-fixture")
    audio, subtitle = fixture(folder)
    padded = folder / "sample.wav"
    with wave.open(str(audio), "rb") as source, wave.open(str(padded), "wb") as target:
        target.setparams(source.getparams())
        second = source.getframerate() * source.getsampwidth()
        target.writeframes(b"\x00" * second * 20)
        target.writeframes(source.readframes(source.getnframes()))
        target.writeframes(b"\x00" * second * 54)
    entries = list(srt.parse(subtitle.read_text()))
    for cue, content in zip(entries, MULTILINGUAL_LINES):
        cue.start += timedelta(seconds=120)
        cue.end += timedelta(seconds=120)
        cue.content = content
    entries.insert(0, srt.Subtitle(0, timedelta(seconds=0.5), timedelta(seconds=3), "Opening."))
    entries.append(srt.Subtitle(99, timedelta(seconds=250), timedelta(seconds=252), "Closing."))
    subtitle.write_text(srt.compose(entries, reindex=False), encoding="utf-8")
    return padded, subtitle


def test_real_engine_recovers_offset_from_sample_and_preserves_full_srt(sample, tmp_path):
    media, subtitle = sample
    original = subtitle.read_bytes()
    result = quick_sync.quick_synchronize(str(media), str(subtitle), 100, 300,
                                          str(tmp_path / "preliminary.srt"))
    assert result["status"] == "preliminary" and result["preliminary"] is True
    assert result["sync_status"] == "sampled" and result["scale"] == 1
    assert result["offset"] == pytest.approx(-2, abs=0.3)
    assert result["sample_cues"] == 10 and result["cues"] == 12
    assert result["evidence"]["spread"] <= 0.5
    assert result["evidence"]["speech_seconds"] > 3
    before = list(srt.parse(original.decode("utf-8")))
    after = list(srt.parse(Path(result["output"]).read_text(encoding="utf-8")))
    assert [(x.index, x.content) for x in after] == [(x.index, x.content) for x in before]
    assert after[0].start.total_seconds() == 0
    assert all(0 <= x.start.total_seconds() < x.end.total_seconds() <= 300 for x in after)
    assert subtitle.read_bytes() == original


def test_disagreeing_regions_leave_existing_output_untouched(sample, tmp_path, monkeypatch):
    media, subtitle = sample
    offsets = iter([-2, -2, 3])
    monkeypatch.setattr(quick_sync, "synchronize", lambda request: {"offset": next(offsets), "scale": 1})
    output = tmp_path / "previous.srt"
    output.write_text("previous valid result")
    with pytest.raises(SyncError, match="quick_unstable_offset"):
        quick_sync.quick_synchronize(str(media), str(subtitle), 100, 300, str(output))
    assert output.read_text() == "previous valid result"


def test_real_local_hls_sample_is_supported(sample, tmp_path, monkeypatch):
    # Desktop vendor binaries deliberately omit HLS; the server uses system FFmpeg.
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not (Path(ffmpeg).parent / "ffprobe").is_file():
        pytest.skip("System FFmpeg and ffprobe required for the server HLS integration")
    monkeypatch.setenv("CUEFLOW_FFMPEG_DIR", str(Path(ffmpeg).parent))
    media, subtitle = sample
    manifest = tmp_path / "sample.m3u8"
    subprocess.run(
        [str(ffmpeg_directory() / "ffmpeg"), "-v", "error", "-nostdin", "-i", str(media),
         "-map", "0:a:0", "-c:a", "aac", "-f", "hls", "-hls_time", "6",
         "-hls_list_size", "0", str(manifest)], check=True, timeout=20,
    )
    result = quick_sync.quick_synchronize(str(manifest), str(subtitle), 100, 300,
                                          str(tmp_path / "hls-output.srt"))
    assert result["status"] == "preliminary"
    assert result["offset"] == pytest.approx(-2, abs=0.3)
    assert result["cues"] == 12


def test_real_silent_sample_never_produces_alignment(sample, tmp_path):
    _, subtitle = sample
    silence = tmp_path / "silence.wav"
    with wave.open(str(silence), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00" * 16000 * 2 * 120)
    output = tmp_path / "output.srt"
    with pytest.raises(SyncError, match="no_speech"):
        quick_sync.quick_synchronize(str(silence), str(subtitle), 100, 300, str(output))
    assert not output.exists()


def test_edge_cues_cannot_bias_alignment(sample):
    _, subtitle = sample
    entries = list(srt.parse(subtitle.read_text(encoding="utf-8")))
    selected = quick_sync.select_cues(entries, 100, 120)
    assert len(selected) == 10
    assert all(x.start.total_seconds() >= quick_sync.EDGE_MARGIN for x in selected)
    assert all(x.end.total_seconds() <= 120 - quick_sync.EDGE_MARGIN for x in selected)
    with pytest.raises(SyncError, match="quick_insufficient_cues"):
        quick_sync.select_cues(entries[:4], 100, 120)


@pytest.mark.parametrize("offset, expected", [(-1, (0, 2)), (8, (8.5, 10))])
def test_clips_only_partial_cues_to_video_bounds(offset, expected):
    cue = srt.Subtitle(12, timedelta(seconds=0.5), timedelta(seconds=3), "<i>你好</i>", "X1:2")
    result = list(srt.parse(quick_sync.shifted_subtitles([cue], offset, 10)))[0]
    assert (result.start.total_seconds(), result.end.total_seconds()) == expected
    assert (result.index, result.content, result.proprietary) == (12, "<i>你好</i>", "X1:2")


def test_does_not_invent_duration_for_cue_shifted_entirely_outside_video():
    cue = srt.Subtitle(1, timedelta(seconds=0.5), timedelta(seconds=1), "Opening")
    with pytest.raises(SyncError, match="quick_cue_bounds"):
        quick_sync.shifted_subtitles([cue], -2, 10)


def test_rounding_does_not_extend_a_cue_beyond_fractional_video_duration():
    cue = srt.Subtitle(1, timedelta(seconds=9), timedelta(seconds=12), "Closing")
    result = list(srt.parse(quick_sync.shifted_subtitles([cue], 0, 10.0006)))[0]
    assert result.end.total_seconds() == 10


def test_continuous_voice_without_temporal_contrast_is_rejected(sample, monkeypatch):
    import numpy as np
    from ffsubsync.speech_transformers import VideoSpeechTransformer

    media, subtitle = sample
    entries = list(srt.parse(subtitle.read_text(encoding="utf-8")))
    monkeypatch.setattr(VideoSpeechTransformer, "fit_transform", lambda self, media: np.ones(12000))
    with pytest.raises(SyncError, match="quick_insufficient_contrast"):
        quick_sync.speech_evidence(media, quick_sync.select_cues(entries, 100, 120), -2)


def test_cli_failure_exposes_full_analysis_fallback_without_creating_output(tmp_path, capsys):
    output = tmp_path / "output.srt"
    assert quick_sync.main(["missing", "missing", "0", "120", str(output)]) == 1
    assert 'CUEFLOW_QUICK_RESULT {"status": "waiting_full"' in capsys.readouterr().out
    assert not output.exists()

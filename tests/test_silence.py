import wave

import pytest

from cueflow.engine import SyncError, SyncRequest, synchronize


def test_silent_audio_never_creates_misleading_result(tmp_path):
    audio = tmp_path / "silent.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 16000 * 8)
    subtitle = tmp_path / "silent.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello\n")
    with pytest.raises(SyncError, match="no_speech"):
        synchronize(SyncRequest(str(audio), str(subtitle), str(tmp_path)))
    assert not list(tmp_path.glob("*.synced*.srt"))

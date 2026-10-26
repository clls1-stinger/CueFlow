import pytest

from server import speakers

TEXT = """1
00:00:01,000 --> 00:00:03,000
Where were you?

2
00:00:04,000 --> 00:00:08,000
- On set, all day.
- Filming what?

3
00:00:09,000 --> 00:00:10,000
<i>Music</i>
"""


def test_assign_splits_dialogue_at_speaker_change():
    turns = [(0.8, 3.2, 7), (4.0, 6.5, 3), (6.5, 8.0, 7)]
    cues = speakers.assign(TEXT, turns)
    assert [(c.content, s) for c, s in cues] == [
        ("Where were you?", 7), ("On set, all day.", 3), ("Filming what?", 7), ("<i>Music</i>", None)]
    assert cues[1][0].end.total_seconds() == 6.5 == cues[2][0].start.total_seconds()


def test_assign_without_turns_splits_proportionally():
    cues = speakers.assign(TEXT, [])
    assert all(s is None for _, s in cues)
    assert 4 < cues[1][0].end.total_seconds() < 8


def test_vtt_numbers_speakers_by_first_appearance_and_escapes():
    vtt = speakers.speaker_vtt(speakers.assign(TEXT, [(0.8, 3.2, 7), (4.0, 6.5, 3), (6.5, 8.0, 7)]))
    assert "<v.s1 1>Where were you?</v>" in vtt
    assert "<v.s2 2>On set, all day.</v>" in vtt
    assert "<v.s1 1>Filming what?</v>" in vtt
    assert "&lt;" not in vtt and "<i>" not in vtt


def test_regions_merge_close_cues_and_skip_silence():
    assert speakers.regions(TEXT) == pytest.approx([(0.7, 10.3)])
    assert speakers.regions(TEXT, gap=0.1) == pytest.approx([(0.7, 3.3), (3.7, 8.3), (8.7, 10.3)])

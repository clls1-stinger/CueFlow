import pytest

from cueflow.formats import FORMATS, batches, parse

SOURCE = '1\n00:00:01,200 --> 00:00:03,400\n<i>Hello 世界!</i>\nSecond line.\n\n2\n00:00:05,000 --> 00:00:06,800\nGoodbye.\n'


@pytest.mark.parametrize('format', FORMATS)
def test_formats_roundtrip(format):
    doc = parse(SOURCE, 'srt')
    result = parse(doc.serialize(format), format)
    assert len(result.cues) == 2
    assert result.cues[0].start == 1.2
    assert result.cues[1].end == 6.8
    assert '世界' in result.cues[0].text
    assert '\nSecond line.' in result.cues[0].text


def test_vtt_ass_metadata():
    vtt = 'WEBVTT\n\nNOTE Private comment\n\ncue-name\n00:01.200 --> 00:03.400 line:90%\n<b>Hello</b>\n'
    doc = parse(vtt, 'vtt')
    doc.cues[0].text = '<b>Hola</b>'
    output = doc.serialize()
    assert 'NOTE Private comment' in output
    assert 'cue-name\n00:00:01.200 --> 00:00:03.400 line:90%' in output
    assert '<b>Hola</b>' in output
    ass = '[Script Info]\nTitle: Demo\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.20,0:00:03.40,Custom,{\\i1}Hello, friend!\\NWorld\n'
    doc = parse(ass, 'ass')
    doc.cues[0].text = doc.cues[0].text.replace('Hello', 'Hola')
    assert doc.serialize() == ass.replace('Hello', 'Hola')


def test_batches_and_invalid():
    doc = parse(SOURCE, 'srt')
    assert batches(doc.cues) == [[0, 1]]
    doc.cues[0].text = 'x' * 3001
    with pytest.raises(ValueError):
        batches(doc.cues)
    with pytest.raises(ValueError):
        parse('{25}{100}Hi', 'sub')
    with pytest.raises(ValueError):
        parse('binary\0', 'stl')


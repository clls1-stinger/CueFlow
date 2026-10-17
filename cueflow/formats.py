"""Subtitle documents for the local editor. Never render subtitle text as HTML."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FORMATS = ('srt', 'vtt', 'ass', 'sbv', 'sub', 'stl')


def seconds(value, fps=25):
    match = re.fullmatch(r'(?:(\d{1,3}):)?(\d{2}):(\d{2})(?:[.,](\d{1,4})|:(\d{2}))', value.strip())
    if not match:
        raise ValueError('Invalid timestamp')
    h, m, s, fraction, frame = match.groups()
    if int(m) > 59 or int(s) > 59 or (frame and int(frame) >= fps):
        raise ValueError('Invalid timestamp')
    sub = int(frame) / fps if frame else int(fraction) / (1000 if len(fraction) == 4 else 10 ** len(fraction))
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + sub


def stamp(value, separator='.', precision=3):
    units = 10 ** precision
    n = round(value * units)
    total, fraction = divmod(n, units)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f'{h:02}:{m:02}:{s:02}{separator}{fraction:0{precision}}'


def plain(text):
    return re.sub(r'<[^>]*>|\{[^}]*\}', '', text).replace(r'\N', '\n').replace(r'\n', '\n').replace(r'\h', ' ')


@dataclass
class Cue:
    start: float
    end: float
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class Document:
    format: str
    cues: list[Cue]
    lines: list[str]
    blocks: list[str]
    fps: int = 25

    def validate(self):
        if not 1 <= len(self.cues) <= 20000:
            raise ValueError('Invalid cue count')
        for cue in self.cues:
            if not 0 <= cue.start < cue.end <= 86400 or not cue.text.strip() or re.search(r'\n\s*\n', cue.text):
                raise ValueError('Invalid timing or empty text')

    def serialize(self, format=None):
        self.validate()
        format = format or self.format
        if format not in FORMATS:
            raise ValueError('Unsupported format')
        same = format == self.format

        def render(c, i):
            text = c.text if same else plain(c.text)
            if format == 'srt':
                return f'{i+1}\n{stamp(c.start, ",")} --> {stamp(c.end, ",")}{c.meta.get("settings", "") if same else ""}\n{text}'
            if format == 'vtt':
                identifier = c.meta.get('identifier', '') if same else ''
                return (identifier + '\n' if identifier else '') + f'{stamp(c.start)} --> {stamp(c.end)}{c.meta.get("settings", "") if same else ""}\n{text}'
            if format == 'ass':
                start, end = stamp(c.start, precision=2).lstrip('0'), stamp(c.end, precision=2).lstrip('0')
                start, end = ('0' + start if start.startswith(':') else start), ('0' + end if end.startswith(':') else end)
                text = text.replace('\n', r'\N')
                if same:
                    values, fields = c.meta['values'][:], c.meta['fields']
                    values[fields.index('start')], values[fields.index('end')], values[-1] = start, end, text
                    return 'Dialogue: ' + ','.join(values)
                return f'Dialogue: 0,{start},{end},Default,,0,0,0,,{text}'
            if format == 'stl':
                def frame_stamp(t):
                    whole, frame = divmod(round(t * self.fps), self.fps)
                    return stamp(whole)[:8] + f':{frame:02}'
                return f'{frame_stamp(c.start)},{frame_stamp(c.end)},{text.replace(chr(10), " | ")}'
            if format == 'sub':
                return f'{stamp(c.start, precision=2)},{stamp(c.end, precision=2)}\n{text.replace(chr(10), "[br]")}'
            return f'{stamp(c.start)},{stamp(c.end)}\n{text}'

        if same and format in ('ass', 'stl'):
            lines = self.lines[:]
            for i, c in enumerate(self.cues):
                lines[c.meta['line']] = render(c, i)
            return '\n'.join(lines)
        if same and format == 'vtt':
            blocks = self.blocks[:]
            for i, c in enumerate(self.cues):
                blocks[c.meta['block']] = render(c, i)
            return '\n\n'.join(blocks) + '\n'
        header = 'WEBVTT\n\n' if format == 'vtt' else ''
        if format == 'ass':
            header = '[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
        separator = '\n' if format in ('ass', 'stl') else '\n\n'
        return header + separator.join(render(c, i) for i, c in enumerate(self.cues)) + '\n'


def parse(text, format, fps=25):
    if format not in FORMATS or fps not in (24, 25, 30) or '\0' in text:
        raise ValueError('Unsupported format')
    text = text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    blocks = re.split(r'\n[ \t]*\n', text.strip())
    doc = Document(format, [], lines, blocks, fps)
    if format == 'ass':
        fields, events = [], False
        for number, line in enumerate(lines):
            if line.startswith('['):
                events = line.strip().lower() == '[events]'
            if not events:
                continue
            if line.lower().startswith('format:'):
                fields = [f.strip().lower() for f in line.split(':', 1)[1].split(',')]
            if line.lower().startswith('dialogue:'):
                if 'start' not in fields or 'end' not in fields or fields[-1] != 'text':
                    raise ValueError('Invalid ASS fields')
                values = line.split(':', 1)[1].lstrip().split(',', len(fields) - 1)
                if len(values) != len(fields):
                    raise ValueError('Invalid ASS event')
                doc.cues.append(Cue(seconds(values[fields.index('start')]), seconds(values[fields.index('end')]), values[-1].replace(r'\N', '\n'), {'line': number, 'fields': fields[:], 'values': values}))
    elif format == 'stl':
        for number, line in enumerate(lines):
            if not line.strip() or line.startswith(('$', '//')):
                continue
            m = re.fullmatch(r'(\d{2}:\d{2}:\d{2}:\d{2})\s*,\s*(\d{2}:\d{2}:\d{2}:\d{2})\s*,\s?(.*)', line)
            if not m:
                raise ValueError('STL must be Spruce text, not binary EBU')
            doc.cues.append(Cue(seconds(m[1], fps), seconds(m[2], fps), m[3].replace(' | ', '\n'), {'line': number}))
    else:
        if format == 'vtt' and not re.match(r'WEBVTT(?:\s|$)', text):
            raise ValueError('Missing WEBVTT header')
        for number, block in enumerate(blocks):
            part = block.split('\n')
            if format == 'vtt' and re.match(r'^(WEBVTT|NOTE|STYLE|REGION)(?:\s|$)', part[0]):
                continue
            timing = next((i for i, line in enumerate(part) if ('-->' in line if format in ('srt', 'vtt') else re.match(r'^\d.*?,\d', line))), -1)
            if timing < 0:
                if format == 'sub' and part[0].startswith('['):
                    continue
                raise ValueError('Invalid subtitle block')
            if format == 'srt' and (timing != 1 or not part[0].isdigit()):
                raise ValueError('Invalid SRT index')
            pattern = r'(\S+)\s+-->\s+(\S+)(.*)' if format in ('srt', 'vtt') else r'(\d[\d:.]+),(\d[\d:.]+)'
            m = re.fullmatch(pattern, part[timing])
            if not m or len(part) <= timing + 1:
                raise ValueError('Missing cue text')
            body = '\n'.join(part[timing + 1:])
            if format == 'sub':
                body = body.replace('[br]', '\n')
            doc.cues.append(Cue(seconds(m[1]), seconds(m[2]), body, {'block': number, 'identifier': '\n'.join(part[:timing]), 'settings': m[3] if len(m.groups()) == 3 else ''}))
    doc.validate()
    return doc


def batches(cues):
    result, batch, size = [], [], 0
    for i, cue in enumerate(cues):
        if len(cue.text) > 3000:
            raise ValueError('A cue exceeds 3,000 characters')
        if len(batch) == 20 or size + len(cue.text) > 6000:
            result.append(batch)
            batch, size = [], 0
        batch.append(i)
        size += len(cue.text)
    if batch:
        result.append(batch)
    return result

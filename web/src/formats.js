import { parseSrt, timestamp } from './subtitles.js';
export const FORMATS = ['srt', 'vtt', 'ass', 'sbv', 'sub', 'stl'];
export function timeValue(value, fps = 25) {
  const match = /^(?:(\d{1,3}):)?(\d{2}):(\d{2})(?:[.,](\d{1,4})|:(\d{2}))$/.exec(value.trim());
  if (!match || +match[2] > 59 || +match[3] > 59 || (match[5] && +match[5] >= fps)) throw new Error('formatInvalid');
  return +(match[1] || 0) * 3600 + +match[2] * 60 + +match[3] + (match[5] ? +match[5] / fps : +match[4] / (match[4].length === 4 ? 1000 : 10 ** match[4].length));
}
export function validCues(cues) {
  if (!cues.length || cues.length > 20000 || cues.some(c => !Number.isFinite(c.start) || !Number.isFinite(c.end) || c.start < 0 || c.end <= c.start || c.end > 86400 || typeof c.text !== 'string' || !c.text.trim() || /\n\s*\n/.test(c.text))) throw new Error('formatInvalid');
  return cues;
}
export function parseDocument(text, format, fps = 25) {
  if (!FORMATS.includes(format) || ![24,25,30].includes(+fps) || text.includes('\0')) throw new Error('formatInvalid');
  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
  const doc = { format, fps: +fps, cues: [], lines: normalized.split('\n') };
  if (format === 'srt') doc.cues = parseSrt(normalized);
  else if (format === 'ass') {
    let fields = [], events = false;
    doc.lines.forEach((line, lineIndex) => {
      if (/^\[/.test(line)) events = /^\[Events\]$/i.test(line.trim());
      if (!events) return;
      if (/^Format:/i.test(line)) fields = line.slice(7).split(',').map(v => v.trim().toLowerCase());
      if (!/^Dialogue:/i.test(line)) return;
      if (!fields.includes('start') || !fields.includes('end') || fields.at(-1) !== 'text') throw new Error('formatInvalid');
      const parts = line.slice(line.indexOf(':') + 1).trimStart().split(',');
      const values = [...parts.slice(0, fields.length - 1), parts.slice(fields.length - 1).join(',')];
      if (values.length !== fields.length) throw new Error('formatInvalid');
      doc.cues.push({ start: timeValue(values[fields.indexOf('start')]), end: timeValue(values[fields.indexOf('end')]), text: values.at(-1).replace(/\\N/g, '\n'), lineIndex, fields: [...fields], values });
    });
  } else if (format === 'stl') {
    doc.lines.forEach((line, lineIndex) => {
      if (!line.trim() || line.startsWith('$') || line.startsWith('//')) return;
      const m = /^(\d{2}:\d{2}:\d{2}:\d{2})\s*,\s*(\d{2}:\d{2}:\d{2}:\d{2})\s*,\s?(.*)$/.exec(line);
      if (!m) throw new Error('formatInvalid');
      doc.cues.push({ start: timeValue(m[1], fps), end: timeValue(m[2], fps), text: m[3].replace(/ \| /g, '\n'), lineIndex });
    });
  } else {
    if (format === 'vtt' && !/^WEBVTT(?:\s|$)/.test(normalized)) throw new Error('formatInvalid');
    // A template preserves VTT headers, identifiers, cue settings, STYLE/REGION and notes.
    const blocks = normalized.trim().split(/\n[ \t]*\n/);
    doc.blocks = blocks;
    for (let blockIndex = 0; blockIndex < blocks.length; blockIndex++) {
      const lines = blocks[blockIndex].split('\n');
      if (format === 'vtt' && /^(WEBVTT|NOTE|STYLE|REGION)(?:\s|$)/.test(lines[0])) continue;
      let ti = lines.findIndex(l => format === 'vtt' ? l.includes('-->') : /^\d.*?,\d/.test(l));
      if (ti < 0) { if (format === 'sub' && /^\[/.test(lines[0])) continue; throw new Error('formatInvalid'); }
      const match = format === 'vtt' ? /^(\S+)\s+-->\s+(\S+)(.*)$/.exec(lines[ti]) : /^(\d[\d:.]+),(\d[\d:.]+)$/.exec(lines[ti]);
      if (!match || !lines[ti + 1]) throw new Error('formatInvalid');
      doc.cues.push({ start: timeValue(match[1]), end: timeValue(match[2]), text: lines.slice(ti + 1).join('\n').replace(format === 'sub' ? /\[br\]/g : /$^/g, '\n'), settings: match[3] || '', identifier: lines.slice(0, ti).join('\n'), blockIndex, prefix: lines.slice(0, ti) });
    }
  }
  validCues(doc.cues);
  return doc;
}
const stamp = s => timestamp(s).replace(',', '.');
const assStamp = s => stamp(Math.round(s * 100) / 100).replace(/^0/, '').slice(0, -1);
function frameStamp(s, fps) {
  const frame = Math.round(s * fps), whole = Math.floor(frame / fps);
  return `${stamp(whole).slice(0,8)}:${String(frame % fps).padStart(2,'0')}`;
}
export function serializeDocument(doc, format = doc.format) {
  validCues(doc.cues);
  if (!FORMATS.includes(format)) throw new Error('formatInvalid');
  const same = format === doc.format;
  if (format === 'ass') {
    if (same) {
      const lines = [...doc.lines];
      for (const c of doc.cues) {
        const values = [...c.values]; values[c.fields.indexOf('start')] = assStamp(c.start); values[c.fields.indexOf('end')] = assStamp(c.end); values[values.length - 1] = c.text.replace(/\n/g,'\\N');
        lines[c.lineIndex] = 'Dialogue: ' + values.join(',');
      }
      return lines.join('\n');
    }
    return '[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n' + doc.cues.map(c => `Dialogue: 0,${assStamp(c.start)},${assStamp(c.end)},Default,,0,0,0,,${plain(c.text).replace(/\n/g,'\\N')}`).join('\n') + '\n';
  }
  const render = (c, i) => {
    const text = same ? c.text : plain(c.text);
    if (format === 'srt') return `${i+1}\n${timestamp(c.start)} --> ${timestamp(c.end)}${same ? c.settings || '' : ''}\n${text}`;
    if (format === 'vtt') return `${same && c.identifier ? c.identifier+'\n' : ''}${stamp(c.start)} --> ${stamp(c.end)}${same ? c.settings || '' : ''}\n${text}`;
    if (format === 'stl') return `${frameStamp(c.start,doc.fps)},${frameStamp(c.end,doc.fps)},${text.replace(/\n/g,' | ')}`;
    return `${format === 'sub' ? assStamp(c.start).padStart(11,'0') : stamp(c.start)},${format === 'sub' ? assStamp(c.end).padStart(11,'0') : stamp(c.end)}\n${format === 'sub' ? text.replace(/\n/g,'[br]') : text}`;
  };
  if (same && format === 'vtt') {
    const blocks = [...doc.blocks]; doc.cues.forEach((c,i) => { blocks[c.blockIndex] = render(c,i); }); return blocks.join('\n\n') + '\n';
  }
  if (same && format === 'stl') {
    const lines = [...doc.lines]; doc.cues.forEach((c,i) => { lines[c.lineIndex] = render(c,i); }); return lines.join('\n');
  }
  return (format === 'vtt' ? 'WEBVTT\n\n' : '') + doc.cues.map(render).join(format === 'stl' ? '\n' : '\n\n') + '\n';
}
export function plain(text) { return text.replace(/\{[^}]*\}/g,'').replace(/<[^>]*>/g,'').replace(/\\[Nn]/g,'\n').replace(/\\h/g,' '); }
export function batches(cues) {
  const output = []; let batch = [], size = 0;
  for (let i=0;i<cues.length;i++) {
    const text = cues[i].text;
    if (text.length > 3000) throw new Error('cueLarge');
    if (batch.length === 20 || size + text.length > 6000) { output.push(batch); batch=[];size=0; }
    batch.push(i);size+=text.length;
  }
  if (batch.length) output.push(batch);
  return output;
}
export { default as GOOGLE_LANGUAGES } from '../../cueflow/google_languages.json' with { type: 'json' };

export const MAX_DURATION = 4 * 3600;
export function decodeSrt(buffer, encoding = 'auto') {
  const bytes = new Uint8Array(buffer);
  let selected = encoding;
  if (encoding === 'auto') {
    if (bytes[0] === 255 && bytes[1] === 254) selected = 'utf-16le';
    else if (bytes[0] === 254 && bytes[1] === 255) selected = 'utf-16be';
    else selected = 'utf-8';
  }
  try { return new TextDecoder(selected, { fatal: true }).decode(bytes); }
  catch { throw new Error('encoding'); }
}
function seconds(h, m, s, ms) {
  if (+m > 59 || +s > 59) throw new Error('invalidSrt');
  return +h * 3600 + +m * 60 + +s + +ms / 1000;
}
export function parseSrt(text) {
  const blocks = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').trim().split(/\n[ \t]*\n/);
  if (blocks.length > 20000) throw new Error('tooManyCues');
  let previous = -1;
  const cues = blocks.map(block => {
    const lines = block.split('\n');
    if (!/^\d+$/.test(lines[0].trim())) throw new Error('invalidSrt');
    const match = /^(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3,4})\s*-->\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3,4})([^\n]*)$/.exec(lines[1] || '');
    if (!match || lines.length < 3) throw new Error('invalidSrt');
    const start = seconds(...match.slice(1, 5)), end = seconds(...match.slice(5, 9));
    if (start < previous || end <= start || end > MAX_DURATION + 600) throw new Error('invalidSrt');
    previous = start;
    return { start, end, text: lines.slice(2).join('\n'), settings: match[9] };
  });
  if (!cues.length) throw new Error('invalidSrt');
  return cues;
}
export function timestamp(seconds) {
  const ms = Math.round(Math.max(0, seconds) * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
}
export function applyTiming(cues, offset, scale, duration) {
  if (!Number.isFinite(offset) || !Number.isFinite(scale) || scale <= 0) throw new Error('invalidTiming');
  const adjusted = cues.map(cue => ({ ...cue, start: cue.start * scale + offset, end: cue.end * scale + offset }));
  if (adjusted.some(c => c.end <= 0 || c.start < -0.5 || c.end > duration + 5)) throw new Error('outsideAudio');
  return adjusted.map((c, i) => `${i + 1}\n${timestamp(c.start)} --> ${timestamp(c.end)}${c.settings}\n${c.text}\n`).join('\n');
}

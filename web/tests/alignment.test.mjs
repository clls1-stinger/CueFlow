import test from 'node:test';
import assert from 'node:assert/strict';
import { align } from '../src/alignment.js';
import { parseSrt, decodeSrt, applyTiming } from '../src/subtitles.js';
const cues = [3, 9, 16, 26, 37, 50, 63, 77, 90, 105, 117].map((start, i) => ({ start, end: start + 1.3 + i % 3 * .4, text: ['日本語', 'العربية', 'Español <i>sí</i>'][i % 3], settings: '' }));
function speechFor(offset, scale) {
  const speech = new Float32Array(140 * 50);
  for (const cue of cues) speech.fill(1, Math.round((cue.start * scale + offset) * 50), Math.round((cue.end * scale + offset) * 50));
  return speech;
}
test('recovers positive and negative offsets without depending on subtitle language', () => {
  for (const offset of [-2, 3.24]) {
    const result = align(speechFor(offset, 1), cues, { maxOffset: 10, fixFramerate: false });
    assert.ok(Math.abs(result.offset - offset) < .03); assert.ok(result.score > .95);
  }
});
test('recovers PAL / NTSC speed and offset', () => {
  const result = align(speechFor(1.2, 25 / 24), cues, { maxOffset: 10 });
  assert.ok(Math.abs(result.scale - 25 / 24) < .0006); assert.ok(Math.abs(result.offset - 1.2) < .05);
});
test('rejects silence, constant activity and too few cues', () => {
  assert.throws(() => align(new Float32Array(10000), cues), /noSpeech/);
  assert.throws(() => align(new Float32Array(10000).fill(1), cues), /noSpeech/);
  assert.throws(() => align(speechFor(0, 1), cues.slice(0, 2)), /fewCues/);
});
test('preserves multilingual text, tags and timing settings through serialization', () => {
  const source = '1\r\n00:00:04,000 --> 00:00:06,000 X1:10\r\nالعربية <i>日本語</i>\r\n\r\n2\r\n00:00:08,000 --> 00:00:09,000\r\nHola\r\n';
  const parsed = parseSrt(source), result = parseSrt(applyTiming(parsed, -1, 1, 20));
  assert.deepEqual(result.map(c => c.text), parsed.map(c => c.text)); assert.equal(result[0].start, 3); assert.equal(result[0].settings, ' X1:10');
});
test('rejects malformed times and out of range transformations', () => {
  assert.throws(() => parseSrt('1\n00:70:00,000 --> 00:71:00,000\nHi'), /invalidSrt/);
  assert.throws(() => applyTiming(cues, -10, 1, 140), /outsideAudio/);
  assert.throws(() => applyTiming(cues, 0, 2, 140), /outsideAudio/);
});
test('detects Unicode BOMs and requires explicit selection for legacy encodings', () => {
  const b = new Uint8Array([255, 254, 72, 0, 105, 0]); assert.equal(decodeSrt(b.buffer), 'Hi');
  const legacy = new Uint8Array([99, 97, 102, 233]); assert.throws(() => decodeSrt(legacy.buffer), /encoding/); assert.equal(decodeSrt(legacy.buffer, 'windows-1252'), 'café');
});
test('normalizes overflowing millisecond fields used by existing subtitle files', () => {
  const cue = parseSrt('1\n00:00:04,1000 --> 00:00:06,000\nHello')[0];
  assert.equal(cue.start,5);
  assert.match(applyTiming([cue],0,1,10),/00:00:05,000/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { FORMATS, parseDocument, serializeDocument, batches, timeValue } from '../src/formats.js';
import { zipFiles } from '../src/translator.js';
const source='1\n00:00:01,200 --> 00:00:03,400\n<i>Hello 世界!</i>\nSecond line.\n\n2\n00:00:05,000 --> 00:00:06,800\nGoodbye.\n';
test('all six text formats round-trip timing and Unicode with format precision',()=>{
 const doc=parseDocument(source,'srt');
 for(const format of FORMATS){const exported=serializeDocument(doc,format);const parsed=parseDocument(exported,format);assert.equal(parsed.cues.length,2,format);assert.equal(parsed.cues[0].start,1.2,format);assert.equal(parsed.cues[1].end,6.8,format);assert.match(parsed.cues[0].text,/世界/);assert.match(parsed.cues[0].text,/Second line/);}
});
test('VTT preserves header, comments, identifiers, settings and tags',()=>{
 const text='WEBVTT\n\nNOTE private comment\nkept\n\nintro\n00:00:01.200 --> 00:00:03.400 line:90%\n<b>Hello</b>\n';
 const doc=parseDocument(text,'vtt');doc.cues[0].text='<b>Hola</b>';
 assert.equal(serializeDocument(doc),text.replace('Hello','Hola'));
});
test('ASS keeps styles and non-dialogue data and commas',()=>{
 const text='[Script Info]\nTitle: Demo\n\n[V4+ Styles]\nStyle: Custom,Arial,24\n\n[Events]\nFormat: Layer, Start, End, Style, Text\nComment: 0,0:00:00.00,0:00:01.00,Custom,Keep\nDialogue: 0,0:00:01.20,0:00:03.40,Custom,{\\i1}Hello, friend!\\NWorld\n';
 const doc=parseDocument(text,'ass');doc.cues[0].text=doc.cues[0].text.replace('Hello','Hola');assert.equal(serializeDocument(doc),text.replace('Hello','Hola'));
});
test('invalid/binary files and invalid edits cannot export',()=>{
 for(const [text,format] of [['binary\0','stl'],['{25}{100}Hi','sub'],['WEBVTT\n\n00:00:02.000 --> 00:00:01.000\nHi','vtt']])assert.throws(()=>parseDocument(text,format));
 const doc=parseDocument(source,'srt');doc.cues[0].end=0;assert.throws(()=>serializeDocument(doc));assert.throws(()=>timeValue('00:99:00.000'));
});
test('translation batches cover every cue once without crossing API limits',()=>{
 const cues=Array.from({length:97},(_,i)=>({text:'x'.repeat(100+i*3)}));
 const groups=batches(cues);assert.deepEqual(groups.flat(),cues.map((_,i)=>i));for(const ids of groups){assert.ok(ids.length<=20);assert.ok(ids.reduce((n,i)=>n+cues[i].text.length,0)<=6000);}
 assert.throws(()=>batches([{text:'x'.repeat(3001)}]));
});
test('download ZIP uses valid store records, UTF-8 names and CRC',async()=>{
 const bytes=new Uint8Array(await zipFiles([{name:'日本語.srt',text:'Hello!'}]).arrayBuffer());const view=new DataView(bytes.buffer);
 assert.equal(view.getUint32(0,true),0x04034b50);assert.equal(view.getUint16(6,true),0x800);assert.equal(view.getUint32(bytes.length-22,true),0x06054b50);assert.equal(view.getUint16(bytes.length-14,true),1);assert.equal(view.getUint32(14,true),0x9d2acc56);
});

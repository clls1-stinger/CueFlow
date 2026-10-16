import { mkdir, writeFile } from 'node:fs/promises';
const dir = new URL('../tests/fixtures/', import.meta.url); await mkdir(dir, { recursive: true });
const rate = 8000, duration = 46, segments = [[2,3.2],[4.7,6.8],[8.1,9.6],[12,15.3],[17,18.1],[20.6,23.7],[26,27.8],[29.1,32.4],[35,36.2],[39.4,42.8]];
const buffer = Buffer.alloc(44 + duration * rate * 2);
buffer.write('RIFF');buffer.writeUInt32LE(buffer.length - 8, 4);buffer.write('WAVEfmt ',8);buffer.writeUInt32LE(16,16);buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(1,22);buffer.writeUInt32LE(rate,24);buffer.writeUInt32LE(rate*2,28);buffer.writeUInt16LE(2,32);buffer.writeUInt16LE(16,34);buffer.write('data',36);buffer.writeUInt32LE(buffer.length-44,40);
await writeFile(new URL('silence.wav',dir),buffer);
for(let i=0;i<rate*duration;i++) {
  const t=i/rate, segment=segments.find(([a,b])=>t>=a&&t<b); if(!segment)continue;
  const envelope=Math.min(1,(t-segment[0])*20,(segment[1]-t)*20), frequency=125+25*Math.sin(t*3);
  let value=0;for(let k=1;k<9;k++)value+=Math.sin(2*Math.PI*frequency*k*t)/k;
  buffer.writeInt16LE(Math.round(5500*envelope*value),44+i*2);
}
await writeFile(new URL('Evening walk.wav',dir),buffer);
const text=['¿Mañana? Sí, aquí.','明日また会いましょう。','明天再见。','내일 만나요.','Привет, мир.','مرحبًا بالعالم','שלום עולם','कल फिर मिलेंगे।','พรุ่งนี้พบกันใหม่','<i>Até amanhã. Görüşürüz. À bientôt.</i>'];
const stamp=t=>`00:00:${String(Math.floor(t)).padStart(2,'0')},${String(Math.round(t%1*1000)).padStart(3,'0')}`;
await writeFile(new URL('Evening walk.srt',dir),segments.map(([a,b],i)=>`${i+1}\n${stamp(a+2)} --> ${stamp(b+2)}\n${text[i]}\n`).join('\n'));

import { mkdir, readFile, writeFile, cp } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const root = new URL('../', import.meta.url);
const file = p => new URL(p, root);
await mkdir(file('public/engine/ffmpeg'), { recursive: true });
await cp(file('node_modules/@ffmpeg/ffmpeg/dist/esm'), file('public/engine/ffmpeg'), { recursive: true });
await cp(file('node_modules/@ffmpeg/core/dist/esm/ffmpeg-core.js'), file('public/engine/ffmpeg-core.js'));
const wasm = await readFile(file('node_modules/@ffmpeg/core/dist/esm/ffmpeg-core.wasm'));
const chunks = [];
for (let offset = 0; offset < wasm.length; offset += 8 * 1024 * 1024) {
  const data = wasm.subarray(offset, offset + 8 * 1024 * 1024);
  const name = `core-${chunks.length}.bin`;
  await writeFile(file(`public/engine/${name}`), data);
  chunks.push({ name, bytes: data.length, sha256: createHash('sha256').update(data).digest('hex') });
}
await writeFile(file('public/engine/manifest.json'), JSON.stringify({ version: '0.12.10', bytes: wasm.length, chunks }));
await cp(file('node_modules/@ozymandiasthegreat/vad/lib'), file('public/engine/vad'), { recursive: true });
await cp(file('node_modules/@ozymandiasthegreat/vad/dist/libfvad.wasm'), file('public/engine/vad/libfvad.wasm'));
await mkdir(file('public/licenses'), { recursive: true });
for (const [pkg, name] of [['@ozymandiasthegreat/vad', 'libfvad']]) {
  await cp(file(`node_modules/${pkg}/LICENSE`), file(`public/licenses/${name}.txt`));
}
await cp(new URL('../../LICENSE', import.meta.url), file('public/licenses/cueflow.txt'));
console.log(`Prepared local engine: ${(wasm.length / 1048576).toFixed(1)} MiB in ${chunks.length} chunks.`);

await cp(file('licenses'), file('public/licenses'), { recursive: true });
await writeFile(file('public/licenses/fft.txt'), (await readFile(file('node_modules/fft.js/README.md'), 'utf8')).split('#### LICENSE')[1] || await readFile(file('node_modules/fft.js/README.md'), 'utf8'));

for (const name of ['AUTHORS', 'PATENTS']) await cp(file('node_modules/@ozymandiasthegreat/vad/' + name), file('public/licenses/libfvad-' + name + '.txt'));

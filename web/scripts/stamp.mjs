import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const sha = process.env.GITHUB_SHA || execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('Missing source commit');
const worker = new URL('../dist/_worker.js', import.meta.url);
await writeFile(worker, (await readFile(worker, 'utf8')).replace('__CUEFLOW_COMMIT__', sha));

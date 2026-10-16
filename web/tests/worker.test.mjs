import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../public/_worker.js';
test('edge worker is read-only and publishes no upload endpoint', async () => {
  const health = await worker.fetch(new Request('https://example.com/api/health'), {});
  assert.equal((await health.json()).uploads, false);
  assert.equal((await worker.fetch(new Request('https://example.com/api/health',{method:'POST',body:'private bytes'}),{})).status,405);
  assert.equal((await worker.fetch(new Request('https://example.com/api/upload'),{})).status,404);
});
test('download redirect points at the actual public repository', async () => {
  const result = await worker.fetch(new Request('https://example.com/download'),{});
  assert.equal(result.status,302);assert.equal(result.headers.get('Location'),'https://github.com/clls1-stinger/CueFlow/releases/latest');
});

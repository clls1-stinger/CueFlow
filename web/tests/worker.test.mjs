import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../public/_worker.js';
test('local synchronization publishes no media upload endpoint', async () => {
  const health = await worker.fetch(new Request('https://example.com/api/health'), {});
  assert.equal((await health.json()).uploads, false);
  assert.equal((await worker.fetch(new Request('https://example.com/api/health',{method:'POST',body:'private bytes'}),{})).status,405);
  assert.equal((await worker.fetch(new Request('https://example.com/api/upload'),{})).status,404);
});

test('cinema proxy preserves ranges and strips unrelated credentials', async t => {
  let received;
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    received={url:String(url),options};
    return new Response('part',{status:206,headers:{'Content-Range':'bytes 2-5/10'}});
  });
  const response=await worker.fetch(new Request('https://cueflow.enriquepl.com/api/cinema/jobs/token/files/movie.mp4',{
    headers:{Range:'bytes=2-5',Cookie:'private=value',Authorization:'secret'}
  }),{});
  assert.equal(received.url,'https://cueflow-api.enriquepl.com/api/cinema/jobs/token/files/movie.mp4');
  assert.equal(received.options.headers.get('range'),'bytes=2-5');
  assert.equal(received.options.headers.get('cookie'),null);
  assert.equal(received.options.headers.get('authorization'),null);
  assert.equal(response.status,206);assert.match(response.headers.get('cache-control'),/no-store/);
});
test('download redirect points at the actual public repository', async () => {
  const result = await worker.fetch(new Request('https://example.com/download'),{});
  assert.equal(result.status,302);assert.equal(result.headers.get('Location'),'https://github.com/clls1-stinger/CueFlow/releases/latest');
});

test('Google document has its own CSP on both Pages canonical paths', async () => {
  for (const path of ['/google-translate.html','/google-translate']) {
    const response=await worker.fetch(new Request('https://example.com'+path),{ASSETS:{fetch:()=>new Response('widget',{headers:{'Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'"}})}});
    assert.match(response.headers.get('Content-Security-Policy'),/https:\/\/\*\.google\.com/);
    assert.doesNotMatch(response.headers.get('Content-Security-Policy'),/frame-ancestors 'none'/);
  }
});

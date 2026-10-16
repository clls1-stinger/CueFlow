import { readFile, writeFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const dist = new URL('../dist/', import.meta.url);
async function files(dir, prefix = '') {
  const items = await readdir(dir, { withFileTypes: true }), result = [];
  for (const item of items) {
    if (item.isDirectory()) result.push(...await files(new URL(item.name + '/', dir), prefix + item.name + '/'));
    else result.push('/' + prefix + item.name);
  }
  return result;
}
const all = await files(dist);
const shell = ['/', ...all.filter(p => p.startsWith('/assets/') || p.startsWith('/icons/') || ['/index.html', '/favicon.svg', '/manifest.webmanifest', '/licenses.html'].includes(p))];
const engine = all.filter(p => p.startsWith('/engine/') && !p.endsWith('.d.ts'));
const hash = createHash('sha256');
for (const path of [...shell.filter(p => p !== '/'), ...engine]) hash.update(path).update(await readFile(new URL(path.slice(1), dist)));
const version = hash.digest('hex').slice(0, 16);
const source = `const CACHE = 'cueflow-${version}';
const SHELL = ${JSON.stringify(shell)}, ENGINE = ${JSON.stringify(engine)};
const ALLOWED = new Set([...SHELL, ...ENGINE]);
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const name of await caches.keys()) if (name.startsWith('cueflow-') && name !== CACHE) await caches.delete(name);
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !ALLOWED.has(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(url.pathname);
    if (hit) return hit;
    // Engine files are saved only through the explicit offline preparation action.
    return fetch(event.request);
  })());
});
let preparation;
async function saveEngine(port) {
  const cache = await caches.open(CACHE);
  for (let i = 0; i < ENGINE.length; i++) {
    const path = ENGINE[i];
    if (!await cache.match(path)) {
      const response = await fetch(path);
      if (!response.ok) throw new Error('download');
      await cache.put(path, response);
    }
    port.postMessage({ progress: (i + 1) / ENGINE.length });
  }
  port.postMessage({ done: true });
}
self.addEventListener('message', event => {
  const port = event.ports[0]; if (!port) return;
  if (event.data?.type === 'CHECK_OFFLINE') event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const matches = await Promise.all([...SHELL, ...ENGINE].map(path => cache.match(path)));
    port.postMessage({ ready: matches.every(Boolean) });
  })());
  if (event.data?.type === 'PREPARE_OFFLINE') event.waitUntil((async () => {
    try {
      // Keep concurrent tabs from interleaving partial preparations.
      if (preparation) await preparation;
      preparation = saveEngine(port); await preparation;
    } catch { port.postMessage({ error: 'offlineError' }); }
    finally { preparation = null; }
  })());
});
`;
await writeFile(new URL('sw.js', dist), source);

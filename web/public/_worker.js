const REPO = 'https://github.com/clls1-stinger/CueFlow';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    if (url.pathname === '/download') return Response.redirect(`${REPO}/releases/latest`, 302);
    if (url.pathname === '/api/health') return Response.json({ service: 'CueFlow Web', version: '1.0.0', commit: '__CUEFLOW_COMMIT__', processing: 'browser', uploads: false, repository: REPO }, { headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
    if (url.pathname.startsWith('/api/')) return new Response('Not found', { status: 404 });
    return env.ASSETS.fetch(request);
  }
};

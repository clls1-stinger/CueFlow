const REPO = 'https://github.com/clls1-stinger/CueFlow';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    if (url.pathname === '/google-translate.html') {
      const response = await env.ASSETS.fetch(request);
      const headers = new Headers(response.headers);
      headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' https://*.google.com https://*.googleapis.com https://*.gstatic.com; style-src 'self' 'unsafe-inline' https://*.googleapis.com https://*.gstatic.com; connect-src https://*.google.com https://*.googleapis.com https://*.googleusercontent.com; img-src 'self' data: https://*.google.com https://*.gstatic.com https://*.googleapis.com; font-src https://*.gstatic.com; frame-src 'self' https://*.google.com; object-src 'none'; base-uri 'none'; form-action 'none'");
      headers.set('Cache-Control','no-store');
      return new Response(response.body,{status:response.status,headers});
    }
    if (url.pathname === '/download') return Response.redirect(`${REPO}/releases/latest`, 302);
    if (url.pathname === '/api/health') return Response.json({ service: 'CueFlow Web', version: '1.2.0', commit: '__CUEFLOW_COMMIT__', processing: 'browser', uploads: false, translation: 'google-widget-in-browser', repository: REPO }, { headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
    if (url.pathname.startsWith('/api/')) return new Response('Not found', { status: 404 });
    return env.ASSETS.fetch(request);
  }
};

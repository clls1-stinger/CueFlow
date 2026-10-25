const REPO = 'https://github.com/clls1-stinger/CueFlow';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/cinema/')) {
      if (!['GET','HEAD','POST','DELETE'].includes(request.method)) return new Response('Method not allowed', {status:405});
      const target = new URL(url.pathname + url.search, 'https://cueflow-api.enriquepl.com');
      const headers = new Headers(request.headers);
      headers.delete('cookie');headers.delete('authorization');headers.delete('host');
      const response = await fetch(target, {method:request.method,headers,body:['GET','HEAD'].includes(request.method)?undefined:request.body,redirect:'manual'});
      const output = new Headers(response.headers);output.set('Cache-Control','private, no-store');output.set('Referrer-Policy','no-referrer');
      return new Response(response.body,{status:response.status,headers:output});
    }
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    if (['/google-translate.html', '/google-translate'].includes(url.pathname)) {
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

export function setupPwa(t) {
  const status = document.getElementById('pwa-status');
  const prepare = document.getElementById('prepare-offline');
  const install = document.getElementById('install-app');
  let prompt, state = '', percent = '', registration;
  const render = () => { status.textContent = state ? t(state) + percent : ''; };
  document.getElementById('language').addEventListener('click', render);
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); prompt = event; });
  window.addEventListener('appinstalled', () => { prompt = null; state = 'installed'; render(); });
  install.onclick = async () => {
    if (matchMedia('(display-mode: standalone)').matches) state = 'installed';
    else if (prompt) { await prompt.prompt(); await prompt.userChoice; prompt = null; return; }
    else state = 'installHint';
    percent = ''; render();
  };
  if (!('serviceWorker' in navigator)) { prepare.disabled = true; state = 'offlineUnavailable'; render(); return; }
  const ready = navigator.serviceWorker.register('/sw.js').then(async reg => {
    registration = reg; return navigator.serviceWorker.ready;
  }).catch(() => { state = 'offlineUnavailable'; render(); return null; });
  prepare.onclick = async () => {
    prepare.disabled = true; state = 'offlinePreparing'; percent = ''; render();
    let timer, port;
    try {
      const reg = await Promise.race([ready, new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 30000))]);
      if (!reg?.active) throw new Error('unavailable');
      await new Promise((resolve, reject) => {
        const channel = new MessageChannel(); port = channel.port1;
        timer = setTimeout(() => reject(new Error('timeout')), 180000);
        channel.port1.onmessage = ({ data }) => {
          if (data.error) reject(new Error(data.error));
          else if (data.done) resolve();
          else { percent = ` · ${Math.round(data.progress * 100)}%`; render(); }
        };
        reg.active.postMessage({ type: 'PREPARE_OFFLINE' }, [channel.port2]);
      });
      // Persistence is best effort; a browser may still evict storage.
      try { await navigator.storage?.persist?.(); } catch { /* No permission is required to sync. */ }
      state = 'offlineReady'; percent = ''; render();
    } catch { state = 'offlineError'; percent = ''; render(); }
    finally { clearTimeout(timer); port?.close(); prepare.disabled = false; }
  };
  ready.then(reg => {
    if (!reg?.active) return;
    const channel = new MessageChannel();
    channel.port1.onmessage = ({ data }) => { if (data.ready && !state) { state = 'offlineReady'; render(); } channel.port1.close(); };
    registration.active?.postMessage({ type: 'CHECK_OFFLINE' }, [channel.port2]);
  });
}

import './style.css';
import { setupTranslator } from './translator.js';
import { setupPwa } from './pwa.js';
import { setupCinema } from './cinema.js';
import { messages } from './i18n.js';
import { decodeSrt, parseSrt, applyTiming } from './subtitles.js';
import { MediaSession } from './media.js';
const $ = id => document.getElementById(id);
let lang = 'es';
try { lang = localStorage.getItem('cueflow-language') || (navigator.language.startsWith('es') ? 'es' : 'en'); } catch { /* Storage is optional. */ }
if (!messages[lang]) lang = 'es';
let video, subtitle, session, analyzer, outputURL, generation = 0, busy = false, syncing = false, phase = '', fraction = 0, started = 0, errorKey = '', watchdog, rejectAnalysis;
const t = key => messages[lang][key];
const translator = setupTranslator(() => lang);
function changeMode(mode, navigate=true) {
  for (const key of ['sync','translate','movies']) { const tab=$('mode-'+key);tab.setAttribute('aria-selected',String(key===mode));tab.tabIndex=key===mode?0:-1; }
  $('sync-workspace').hidden=mode!=='sync';$('translate-panel').hidden=mode!=='translate';
  $('cinema-panel').hidden=mode!=='movies';
  document.querySelectorAll('.privacy,.practical').forEach(el=>{el.hidden=mode==='movies';});
  if(navigate)history.replaceState(null,'',mode==='sync'?location.pathname:'#'+mode);
}
const modes=['sync','translate','movies'];
for(const key of modes) { $('mode-'+key).onclick=()=>changeMode(key);$('mode-'+key).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const index=e.key==='Home'?0:e.key==='End'?2:(modes.indexOf(key)+(e.key==='ArrowRight'?1:2))%3;const next=modes[index];changeMode(next);$('mode-'+next).focus();}};}
if(location.hash==='#translate')changeMode('translate');
const cinema = setupCinema(()=>lang, changeMode);
function translate() {
  document.documentElement.lang = lang;
  document.title = lang === 'es' ? 'CueFlow — Sincroniza, traduce y edita subtítulos' : 'CueFlow — Subtitle sync, Google translation & editor';
  translator?.retranslate();
  cinema.retranslate();
  $('mode-sync').textContent = lang === 'es' ? 'Sincronizar' : 'Synchronize';
  $('mode-translate').textContent = lang === 'es' ? 'Traducir y editar' : 'Translate & edit';
  $('mode-movies').textContent = lang === 'es' ? 'Películas' : 'Movies';
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  $('language').textContent = lang === 'es' ? 'EN' : 'ES';
  $('language').setAttribute('aria-label', lang === 'es' ? 'Switch to English' : 'Cambiar a español');
  $('video-file').setAttribute('aria-label', t('video')); $('subtitle-file').setAttribute('aria-label', t('subtitle'));
  showFile('video', video); showFile('subtitle', subtitle); renderStatus();
  if (errorKey) $('error-message').textContent = messages[lang].errors[errorKey] || messages[lang].errors.generic;
}
function showFile(kind, file) {
  $(kind + '-card').classList.toggle('has-file', !!file);
  $(kind + '-name').textContent = file?.name || t('choose');
  $(kind + '-name').title = file?.name || '';
  $(kind + '-meta').textContent = file ? `${(file.size / 1048576).toLocaleString(lang, { maximumFractionDigits: 1 })} MB · ${t('replace')}` : t(kind === 'video' ? 'videoHint' : 'subtitleHint');
}
function update() {
  $('sync').disabled = busy || !video || !subtitle;
  $('inputs').disabled = syncing;
  $('sync').hidden = busy;
  $('cancel').hidden = !busy;
  $('status').hidden = !busy;
  document.body.classList.toggle('busy', syncing);
}
function renderStatus() {
  $('phase').textContent = t(phase) || '';
  $('percent').textContent = phase === 'probing' ? '' : `${Math.round(fraction * 100)}%`;
  $('progress').value = fraction * 100;
  if (started) $('elapsed').textContent = `${Math.floor((Date.now() - started) / 60000)}:${String(Math.floor((Date.now() - started) / 1000) % 60).padStart(2, '0')}`;
}
function report(p, f) { phase = p; fraction = Math.max(0, Math.min(1, f)); renderStatus(); }
function clearError() { errorKey = ''; $('error').hidden = true; $('notice').hidden = true; }
function showError(error) {
  errorKey = error?.message || String(error);
  $('error-message').textContent = messages[lang].errors[errorKey] || messages[lang].errors.generic;
  $('error').hidden = false;
}
function stop() {
  ++generation; rejectAnalysis?.(new Error('cancelled')); rejectAnalysis = null; clearTimeout(watchdog); session?.stop(); session = null; analyzer?.terminate(); analyzer = null;
  busy = false; syncing = false; update();
}
function deadline(ms, id) {
  clearTimeout(watchdog);
  watchdog = setTimeout(() => { if (generation === id) { stop(); showError(new Error('generic')); } }, ms);
}
async function openMedia(id) {
  session = new MediaSession((p, f) => { if (id === generation) report(p, f); });
  const tracks = await session.open(video);
  if (id !== generation) return;
  $('audio-track').replaceChildren();
  tracks.forEach((track, i) => {
    const option = document.createElement('option'); option.value = String(i);
    const tag = track.tags?.language || '';
    let label = tag;
    try { label = tag && tag !== 'und' ? new Intl.DisplayNames([lang], { type: 'language' }).of(tag) : ''; } catch { /* Keep container language tag. */ }
    option.textContent = [`${i + 1}`, label, track.tags?.title?.slice(0, 100), track.codec_name, track.channels ? `${track.channels} ch` : ''].filter(Boolean).join(' · ');
    $('audio-track').append(option);
  });
  $('track-area').hidden = tracks.length < 2;
}
async function choose(kind, file) {
  if (!file || syncing) return;
  if (kind === 'subtitle') {
    if (file.size > 10 * 1024 ** 2) { showError(new Error('subtitleLarge')); return; }
    subtitle = file; showFile(kind, file); clearError(); update(); return;
  }
  stop(); clearError();
  video = file; showFile(kind, file); $('track-area').hidden = true;
  if (file.size > 2 * 1024 ** 3) { video = null; showFile(kind); showError(new Error('tooLarge')); update(); return; }
  const id = generation;
  busy = true; started = Date.now(); update(); deadline(120000, id);
  try { await openMedia(id); }
  catch (error) { if (id === generation) { session?.stop(); session = null; showError(error); } }
  finally { if (id === generation) { clearTimeout(watchdog); busy = false; update(); } }
}
for (const kind of ['video', 'subtitle']) {
  $(kind + '-file').addEventListener('change', e => choose(kind, e.target.files[0]));
  const card = $(kind + '-card');
  card.addEventListener('dragover', e => { e.preventDefault(); if (!syncing) card.classList.add('dragging'); });
  card.addEventListener('dragleave', () => card.classList.remove('dragging'));
  card.addEventListener('drop', e => { e.preventDefault(); card.classList.remove('dragging'); choose(kind, e.dataTransfer.files[0]); });
}
$('sync-form').addEventListener('submit', async e => {
  e.preventDefault(); if (busy || !video || !subtitle) return;
  clearError();
  const maxOffset = Number($('max-offset').value);
  if (!Number.isFinite(maxOffset) || maxOffset < 1 || maxOffset > 600) { showError(new Error('invalidOffset')); return; }
  const id = ++generation; busy = true; syncing = true; started = Date.now(); update(); deadline(15 * 60000, id);
  try {
    const bytes = await subtitle.arrayBuffer();
    if (id !== generation) return;
    const cues = parseSrt(decodeSrt(bytes, $('encoding').value.toLowerCase()));
    if (cues.length < 3) throw new Error('fewCues');
    const selectedTrack = $('audio-track').value;
    if (!session?.ff) await openMedia(id);
    if (id !== generation) return;
    if (selectedTrack && Number(selectedTrack) < session.tracks.length) $('audio-track').value = selectedTrack;
    // Refresh the callback after probing so progress belongs to this run.
    session.report = (p, f) => { if (id === generation) report(p, f); };
    const pcm = await session.extract(Number($('audio-track').value || 0));
    if (id !== generation) return;
    analyzer = new Worker(new URL('./analyze.worker.js', import.meta.url), { type: 'module' });
    const { result, duration } = await new Promise((resolve, reject) => {
      rejectAnalysis = reject;
      analyzer.onmessage = ({ data }) => {
        if (id !== generation) return;
        if (data.type === 'progress') report(data.phase, data.value);
        if (data.type === 'done') resolve(data);
        if (data.type === 'error') reject(new Error(data.error));
      };
      analyzer.onerror = () => reject(new Error('generic'));
      analyzer.postMessage({ pcm: pcm.buffer, cues, options: { maxOffset, fixFramerate: $('framerate').checked } }, [pcm.buffer]);
    });
    if (id !== generation) return;
    rejectAnalysis = null;
    const output = applyTiming(cues, result.offset, result.scale, duration);
    if (outputURL) URL.revokeObjectURL(outputURL);
    outputURL = URL.createObjectURL(new Blob([output], { type: 'application/x-subrip;charset=utf-8' }));
    const name = video.name.replace(/\.[^.]+$/, '') + '.synced.srt';
    $('download').href = outputURL; $('download').download = name; $('output-name').textContent = name;
    $('offset-result').textContent = `${result.offset >= 0 ? '+' : ''}${result.offset.toFixed(2)} s`;
    $('scale-result').textContent = `${result.scale.toFixed(5)}×`; $('cues-result').textContent = String(cues.length);
    $('sync-form').hidden = true; $('result').hidden = false; $('result').focus();
  } catch (error) { if (id === generation) showError(error); }
  finally { if (id === generation) { clearTimeout(watchdog); rejectAnalysis = null; session?.stop(); session = null; analyzer?.terminate(); analyzer = null; busy = false; syncing = false; update(); } }
});
$('cancel').onclick = () => { stop(); clearError(); $('notice').textContent = t('cancelled'); $('notice').hidden = false; };
$('language').onclick = () => { lang = lang === 'es' ? 'en' : 'es'; try { localStorage.setItem('cueflow-language', lang); } catch { /* Optional. */ } translate(); };
$('reset').onclick = () => {
  stop(); clearError(); if (outputURL) URL.revokeObjectURL(outputURL); outputURL = null;
  video = subtitle = null; $('sync-form').reset(); $('track-area').hidden = true;
  $('result').hidden = true; $('sync-form').hidden = false; translate(); update(); $('video-file').focus();
};
window.addEventListener('beforeunload', e => { if (busy) { e.preventDefault(); e.returnValue = ''; } });
setInterval(() => { if (busy) renderStatus(); }, 1000);
translate(); update();
setupPwa(t);
if (!globalThis.WebAssembly || !globalThis.Worker || !crypto.subtle) { showError(new Error('unsupported')); $('inputs').disabled = true; }

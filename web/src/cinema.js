import { googleTranslate } from './google.js';
import { GOOGLE_LANGUAGES, parseDocument, serializeDocument, batches } from './formats.js';

const API = '/api/cinema';
const words = {
  es: {
    title:'Películas',search:'Buscar en StreamIMDB',query:'Nombre de la película',find:'Buscar',empty:'No se encontraron películas.',
    found:'Resultados',choose:'Versión de subtítulos',language:'Idioma de salida',quality:'Calidad',small:'Hasta 480p · descarga más ligera',large:'Hasta 720p',
    prepare:'Preparar película y sincronizar',loading:'Buscando…',loadingMovie:'Consultando video y subtítulos…',
    note:'La película se prepara temporalmente en Oracle. Los archivos se borran tras una hora sin actividad y, como máximo, a las seis horas de crearlos.',
    consent:'Acepto enviar el texto de los subtítulos a Google para traducirlo al idioma elegido.',
    fallback:'No hay una versión en ese idioma. Puedes traducir una de las versiones encontradas después de sincronizarla.',
    noSubs:'No encontramos subtítulos para esta película. Puedes volver a consultar más tarde.',
    downloading:'Descargando la película',remuxing:'Preparando el video',synchronizing:'Sincronizando con el audio',packaging:'Añadiendo subtítulos al MP4',translating:'Añadiendo la traducción al MP4',ready:'Lista para ver',
    download:'Descargar MP4 con subtítulos',srt:'Descargar SRT sincronizado',translate:'Traducir subtítulos',translation:'Traduciendo diálogos',translationDone:'Traducción completa. Preparando el MP4.',
    cancel:'Cancelar y borrar archivos',erase:'Borrar esta sesión',expiry:'Se borrará si dejas de usarla a las',max:'El enlace es temporal. Al caducar puedes preparar la película otra vez.',
    edit:'¿Necesitas otro idioma?',busy:'La preparación puede tardar varios minutos. Puedes dejar esta pestaña abierta.',expired:'Esta sesión caducó. Vuelve a preparar la película.',
    errors:{query_invalid:'Escribe al menos dos caracteres.',queue_full:'Oracle está ocupado. Inténtalo de nuevo en unos minutos.',storage_full:'El espacio temporal está ocupado. Borra una sesión o vuelve más tarde.',rate_limit:'Se alcanzó el límite temporal. Espera unos minutos.',movie_too_large:'Esta calidad supera el límite de 2 GB. Prueba hasta 480p.',source_unavailable:'La fuente no respondió. Vuelve a intentarlo.',movie_unavailable:'La fuente no ofrece un video disponible para esta película.',subtitle_missing:'Elige una versión de subtítulos.',alignment_failed:'No se pudo verificar la sincronización con esta versión. Prueba otra.',processing_failed:'No se pudo completar la película con esta versión. Prueba otra.',interrupted:'La preparación se interrumpió. Vuelve a iniciarla.',job_expired:'Esta sesión caducó. Vuelve a preparar la película.',googleTimeout:'Google tardó demasiado. Puedes reintentar la traducción.',googleUnavailable:'Google Translate no respondió. El video y los subtítulos originales siguen disponibles.',translation_timing_changed:'La traducción cambió los tiempos y no se guardó.',network:'No se pudo completar la operación. Comprueba la conexión o vuelve a intentarlo.'},
  },
  en: {
    title:'Movies',search:'Search StreamIMDB',query:'Movie title',find:'Search',empty:'No movies found.',found:'Results',choose:'Subtitle release',language:'Output language',quality:'Quality',small:'Up to 480p · smaller download',large:'Up to 720p',prepare:'Prepare movie and sync subtitles',loading:'Searching…',loadingMovie:'Checking video and subtitles…',
    note:'The movie is prepared temporarily on Oracle. Files are deleted after one hour of inactivity, and at most six hours after creation.',consent:'I agree to send the subtitle text to Google for translation into the selected language.',fallback:'There is no release in this language. You can translate an available release after synchronization.',noSubs:'No subtitles were found for this movie. Try checking again later.',downloading:'Downloading movie',remuxing:'Preparing video',synchronizing:'Synchronizing with audio',packaging:'Adding subtitles to MP4',translating:'Adding translation to MP4',ready:'Ready to watch',download:'Download MP4 with subtitles',srt:'Download synchronized SRT',translate:'Translate subtitles',translation:'Translating dialogue',translationDone:'Translation complete. Preparing MP4.',cancel:'Cancel and delete files',erase:'Delete this session',expiry:'If unused, files will be deleted at',max:'This link is temporary. Prepare the movie again after it expires.',edit:'Need another language?',busy:'Preparation may take several minutes. You can leave this tab open.',expired:'This session expired. Prepare the movie again.',
    errors:{query_invalid:'Enter at least two characters.',queue_full:'Oracle is busy. Try again in a few minutes.',storage_full:'Temporary storage is full. Delete a session or try later.',rate_limit:'Temporary request limit reached. Wait a few minutes.',movie_too_large:'This quality exceeds 2 GB. Try up to 480p.',source_unavailable:'The source did not respond. Try again.',movie_unavailable:'No available video was found for this movie.',subtitle_missing:'Choose a subtitle release.',alignment_failed:'Synchronization could not be verified for this release. Try another.',processing_failed:'This release could not be processed. Try another.',interrupted:'Preparation was interrupted. Start it again.',job_expired:'This session expired. Prepare the movie again.',googleTimeout:'Google took too long. Retry the translation.',googleUnavailable:'Google Translate did not respond. Video and original subtitles remain available.',translation_timing_changed:'The translation changed timing and was not saved.',network:'The operation could not be completed. Check your connection or retry.'},
  },
};

export function setupCinema(getLanguage, activate) {
  const panel = document.getElementById('cinema-panel');
  const $ = id => document.getElementById('cinema-' + id);
  const t = key => words[getLanguage()][key];
  let movie, job, poll, request, selectedRun = 0, translation, translating = false, autoTranslate = false, wantedLanguage;
  panel.innerHTML = `
    <form id="cinema-search"><label for="cinema-query" data-cinema="search"></label><div class="cinema-search-row"><input id="cinema-query" type="search" required minlength="2" maxlength="120" autocomplete="off"><button class="secondary" type="submit" data-cinema="find"></button></div></form>
    <p id="cinema-message" role="status" aria-live="polite"></p><p id="cinema-error" role="alert" hidden></p>
    <div id="cinema-results" class="cinema-results"></div>
    <section id="cinema-detail" hidden><h2 id="cinema-title"></h2><p class="help" data-cinema="note"></p>
      <div class="cinema-options"><label><span data-cinema="language"></span><select id="cinema-language"></select></label><label><span data-cinema="quality"></span><select id="cinema-quality"><option value="480" data-cinema="small"></option><option value="720" data-cinema="large"></option></select></label></div>
      <label><span data-cinema="choose"></span><select id="cinema-subtitle"></select></label><p id="cinema-fallback" class="help" data-cinema="fallback" hidden></p>
      <label id="cinema-consent-label" class="checkbox" hidden><input id="cinema-consent" type="checkbox"><span data-cinema="consent"></span></label>
      <button id="cinema-prepare" class="primary" type="button" data-cinema="prepare"></button>
    </section>
    <section id="cinema-session" hidden><h2 id="cinema-session-title"></h2><p id="cinema-state" role="status" aria-live="polite"></p><progress id="cinema-progress" max="100" value="0"></progress><p id="cinema-busy" class="help" data-cinema="busy"></p>
      <video id="cinema-video" controls playsinline preload="metadata" hidden></video>
      <p id="cinema-metrics" class="help"></p>
      <div id="cinema-downloads" class="cinema-actions" hidden><a id="cinema-download" class="primary" data-cinema="download" download></a><a id="cinema-srt" class="secondary" data-cinema="srt" download></a></div>
      <details id="cinema-translation" hidden><summary data-cinema="edit"></summary><label><span data-cinema="language"></span><select id="cinema-target"></select></label><label class="checkbox"><input id="cinema-translate-consent" type="checkbox"><span data-cinema="consent"></span></label><button id="cinema-translate" class="secondary" type="button" data-cinema="translate"></button></details>
      <p id="cinema-translation-status" role="status"></p><div id="cinema-google-frame"></div>
      <p id="cinema-expiry" class="help"></p><p class="help" data-cinema="max"></p><button id="cinema-delete" class="text-button" type="button"></button>
    </section>`;

  async function api(path, options = {}) {
    const response = await fetch(API + path, {...options, headers:{'Content-Type':'application/json',...options.headers}});
    if (response.status === 204) return null;
    let data; try { data = await response.json(); } catch { throw new Error('network'); }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'network');
    return data;
  }
  function error(e) { $('error').textContent = t('errors')[e.message] || t('errors').network; $('error').hidden = false; }
  function clearError() { $('error').hidden = true; }
  function languageName(code) { try { return new Intl.DisplayNames([getLanguage()],{type:'language'}).of(code==='pb'?'pt-BR':code); } catch { return code; } }
  function file(name, download=false) { return `${API}/jobs/${encodeURIComponent(job.token)}/files/${name}${download?'?download=true':''}`; }
  function languageMenus() {
    const options = GOOGLE_LANGUAGES.map(({code})=>[code,languageName(code)]).sort((a,b)=>a[1].localeCompare(b[1]));
    for (const key of ['language','target']) {
      const old=$(key).value || getLanguage();
      $(key).replaceChildren(...options.map(([code,name])=>new Option(name,code)));
      $(key).value=old;
    }
  }
  function sourceLanguage() { const code=movie?.subtitles.find(s=>s.id===$('subtitle').value)?.language;return code==='pb'?'pt':code; }
  function updateSelection(selectBest=false) {
    if (!movie) return;
    const target=$('language').value;
    if (selectBest) {
      const preferred=movie.subtitles.find(s=>s.language===target || (s.language==='pb'&&target==='pt')) || movie.subtitles.find(s=>s.language==='en') || movie.subtitles[0];
      if(preferred)$('subtitle').value=preferred.id;
    }
    const missing=sourceLanguage()!==target;
    $('fallback').hidden=!missing;$('consent-label').hidden=!missing;
    $('prepare').disabled=!movie.subtitles.length || !!job && !['ready','error'].includes(job.state);
  }
  async function selectMovie(slug, navigate=true) {
    request?.abort();request=new AbortController();const run=++selectedRun;
    clearError();$('message').textContent=t('loadingMovie');$('detail').hidden=true;
    try {
      const data=await api('/movies/'+encodeURIComponent(slug),{signal:request.signal});
      if(run!==selectedRun)return;
      movie=data;$('title').textContent=data.title;$('detail').hidden=false;
      $('subtitle').replaceChildren(...data.subtitles.map(s=>new Option(`${languageName(s.language)} · ${s.name}`,s.id)));
      $('message').textContent=data.subtitles.length?'':t('noSubs');updateSelection(true);
      if(navigate)history.replaceState(null,'',`#movie/${slug}`);
    } catch(e) {if(run===selectedRun&&e.name!=='AbortError'){error(e);$('message').textContent='';}}
  }
  $('search').onsubmit=async e=>{
    e.preventDefault();request?.abort();request=new AbortController();const run=++selectedRun;
    clearError();$('message').textContent=t('loading');$('results').replaceChildren();
    try {
      const data=await api('/search?q='+encodeURIComponent($('query').value.trim()),{signal:request.signal});
      if(run!==selectedRun)return;
      $('message').textContent=data.results.length?t('found'):t('empty');
      for(const result of data.results){
        const button=document.createElement('button');button.type='button';button.className='cinema-result';
        const title=document.createElement('strong'),meta=document.createElement('span');title.textContent=result.title;meta.textContent=result.meta;
        button.append(title,meta);button.onclick=()=>selectMovie(result.slug);$('results').append(button);
      }
    }catch(e){if(run===selectedRun&&e.name!=='AbortError'){error(e);$('message').textContent='';}}
  };
  function resetVideo() {
    $('video').pause();$('video').removeAttribute('src');$('video').replaceChildren();$('video').load();$('video').hidden=true;
  }
  function remember() {try{localStorage.setItem('cueflow-movie-session',JSON.stringify({token:job.token,slug:job.slug}));}catch{/* Optional. */}}
  function renderJob() {
    if(!job)return;
    $('session').hidden=false;$('session-title').textContent=job.title;
    $('state').textContent=job.state==='error'?(t('errors')[job.error]||t('errors').processing_failed):(t(job.state)||job.state);
    $('progress').value=job.progress;$('progress').hidden=['ready','error'].includes(job.state);$('busy').hidden=['ready','error'].includes(job.state);
    $('delete').textContent=t(['ready','error'].includes(job.state)?'erase':'cancel');
    $('expiry').textContent=`${t('expiry')} ${new Date(job.expires_at*1000).toLocaleTimeString(getLanguage())}.`;
    const ready=job.files.includes('movie.mp4');
    $('downloads').hidden=!ready;$('translation').hidden=!ready;
    if(ready){
      const translated=job.translated_language && job.files.includes('translated.mp4');
      $('download').href=file(translated?'translated.mp4':'movie.mp4',true);
      $('srt').href=file(translated?'translated.srt':'subtitles.srt',true);
      $('video').hidden=false;
      if(!$('video').getAttribute('src')){$('video').src=file('movie.mp4');}
      const trackName=translated?'translated.vtt':'subtitles.vtt';
      const trackVersion=trackName+':'+(job.translated_language||job.language);
      if($('video').dataset.track!==trackVersion){
        $('video').replaceChildren();const track=document.createElement('track');track.kind='subtitles';track.src=file(trackName);track.srclang=job.translated_language||job.language;track.label=languageName(track.srclang);track.default=true;$('video').append(track);$('video').dataset.track=trackVersion;
        track.addEventListener('load',()=>{track.track.mode='showing';});
      }
      const result=job.result;
      $('metrics').textContent=result?`${result.cues} · ${Number(result.offset).toFixed(2)} s · ${Number(result.scale).toFixed(5)}×`:'';
    }
    $('translate').disabled=translating||job.state!=='ready'||!$('translate-consent').checked;
    updateSelection();
  }
  async function watch(token, slug) {
    clearTimeout(poll);resetVideo();delete $('video').dataset.track;
    try {job=await api('/jobs/'+encodeURIComponent(token));remember();renderJob();}
    catch(e){job=null;if(slug)await selectMovie(slug);error(e);return;}
    history.replaceState(null,'',`#watch/${token}/${slug||job.slug}`);
    schedulePoll();
  }
  function schedulePoll() {
    clearTimeout(poll);if(!job)return;
    const token=job.token;
    poll=setTimeout(async()=>{
      try {
        const data=await api('/jobs/'+encodeURIComponent(token));
        if(job?.token!==token)return;
        job=data;renderJob();
        if(job.state==='ready'&&autoTranslate){autoTranslate=false;$('target').value=wantedLanguage;$('translate-consent').checked=true;await translate();}
      }catch(e){if(job?.token===token){error(e);if(e.message==='job_expired'){resetVideo();$('downloads').hidden=true;job=null;}}}
      schedulePoll();
    },job.state==='ready'?15000:2500);
  }
  $('prepare').onclick=async()=>{
    if(!movie)return;clearError();$('prepare').disabled=true;
    try {
      const source=sourceLanguage();wantedLanguage=$('language').value;autoTranslate=wantedLanguage!==source&&$('consent').checked;
      const data=await api('/jobs',{method:'POST',body:JSON.stringify({slug:movie.slug,subtitle_id:$('subtitle').value,height:Number($('quality').value)})});
      await watch(data.token,movie.slug);$('session').scrollIntoView({behavior:'smooth',block:'start'});
    }catch(e){error(e);}finally{updateSelection();}
  };
  async function translate() {
    if(!job||job.state!=='ready'||translating||!$('translate-consent').checked)return;
    const token=job.token,target=$('target').value;
    translating=true;translation=new AbortController();clearError();renderJob();
    try {
      const response=await fetch(file('subtitles.srt'),{signal:translation.signal});if(!response.ok)throw new Error('job_expired');
      const doc=parseDocument(await response.text(),'srt');const original=structuredClone(doc.cues);
      let done=0;
      for(const indices of batches(original)){
        if(job?.token!==token)return;
        $('translation-status').textContent=`${t('translation')} · ${done}/${doc.cues.length}`;
        const result=await googleTranslate(indices.map(i=>original[i].text),job.language==='pb'?'pt':job.language,target,getLanguage(),$('google-frame'),translation.signal);
        if(job?.token!==token)return;
        indices.forEach((i,j)=>{doc.cues[i].text=result[j];});done+=indices.length;
      }
      job=await api('/jobs/'+encodeURIComponent(token)+'/subtitles',{method:'POST',body:JSON.stringify({text:serializeDocument(doc,'srt'),language:target})});
      $('translation-status').textContent=t('translationDone');renderJob();
    }catch(e){if(job?.token===token)error(e);}finally{translating=false;renderJob();}
  }
  $('translate').onclick=translate;$('translate-consent').onchange=renderJob;
  $('language').onchange=()=>updateSelection(true);$('subtitle').onchange=()=>updateSelection();
  $('delete').onclick=async()=>{
    if(!job)return;const token=job.token;clearError();translation?.abort();autoTranslate=false;
    try {await api('/jobs/'+encodeURIComponent(token),{method:'DELETE'});}catch(e){if(e.message!=='job_expired'){error(e);return;}}
    clearTimeout(poll);job=null;resetVideo();$('session').hidden=true;$('translation-status').textContent='';
    try{localStorage.removeItem('cueflow-movie-session');}catch{/* Optional. */}
    history.replaceState(null,'',movie?`#movie/${movie.slug}`:'#movies');updateSelection();
  };
  // Heartbeat only while this workspace is visible or its video is playing.
  setInterval(async()=>{
    if(!job || (panel.hidden && $('video').paused) || document.hidden && $('video').paused)return;
    try {const data=await api('/jobs/'+encodeURIComponent(job.token)+'/heartbeat',{method:'POST'});if(job?.token===data.token){job=data;renderJob();}}catch{/* Poll reports expiry. */}
  },60000);
  function route() {
    const parts=location.hash.slice(1).split('/');
    if(parts[0]==='movie'&&/^[a-z0-9-]{2,121}$/.test(parts[1]||'')){activate('movies',false);selectMovie(parts[1],false);}
    else if(parts[0]==='watch'&&/^[A-Za-z0-9_-]{43}$/.test(parts[1]||'')){activate('movies',false);watch(parts[1],parts[2]);}
    else if(parts[0]==='movies'){activate('movies',false);}
  }
  const retranslate=()=>{panel.querySelectorAll('[data-cinema]').forEach(el=>{el.textContent=t(el.dataset.cinema);});$('query').setAttribute('aria-label',t('query'));languageMenus();updateSelection();renderJob();};
  retranslate();route();window.addEventListener('hashchange',route);
  return {retranslate};
}

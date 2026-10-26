import { googleTranslate } from './google.js';
import { GOOGLE_LANGUAGES, parseDocument, serializeDocument, batches, plain } from './formats.js';

const API = '/api/cinema';
const words = {
  es: {
    popular:'Populares de hoy',popularSource:'En StreamIMDB',browse:'Ver populares',title:'Películas',search:'Buscar en StreamIMDB',query:'Nombre de la película',find:'Buscar',empty:'No se encontraron películas.',
    found:'Resultados',choose:'Versión de subtítulos',language:'Idioma de salida',quality:'Calidad',small:'Hasta 480p · descarga más ligera',large:'Hasta 720p',
    prepare:'Ver película y sincronizar',loading:'Buscando…',loadingMovie:'Consultando video y subtítulos…',
    note:'La película se prepara temporalmente en Oracle. Los archivos se borran tras una hora sin actividad y, como máximo, a las seis horas de crearlos.',
    consent:'Acepto enviar el texto de los subtítulos a Google para traducirlo al idioma elegido. Mantendré esta pestaña visible durante la traducción.',
    fallback:'No hay una versión en ese idioma. Puedes traducir una de las versiones encontradas mientras se prepara el video.',
    noSubs:'No encontramos subtítulos para esta película. Puedes volver a consultar más tarde.',
    downloading:'Descargando la película',remuxing:'Preparando el video',synchronizing:'Sincronizando con el audio',packaging:'Añadiendo subtítulos al MP4',translating:'Añadiendo la traducción al MP4',ready:'Lista para ver',
    download:'Descargar MP4 con subtítulos',srt:'Descargar SRT sincronizado',translate:'Traducir subtítulos',translation:'Traduciendo diálogos',translationDone:'Traducción completa. Preparando el MP4.',
    cancel:'Cancelar y borrar archivos',erase:'Borrar esta sesión',expiry:'Se borrará si dejas de usarla a las',max:'El enlace es temporal. Al caducar puedes preparar la película otra vez.',
    edit:'¿Necesitas otro idioma?',style:'Estilo de subtítulos',styleColor:'Color',styleFont:'Fuente',styleSize:'Tamaño',styleBackground:'Opacidad del fondo',styleReset:'Restablecer',styleSpeakers:'Un color por personaje',speakersRunning:'Separando diálogos por personaje en segundo plano…',speakersReady:'Diálogos separados por personaje',yellow:'Amarillo',white:'Blanco',cyan:'Cian',green:'Verde',fontScript:'Guion (Courier Prime)',fontSans:'Sans serif',fontSerif:'Serif',busy:'Puedes reproducir mientras se prepara el archivo completo. La sincronización se verifica en segundo plano.',pendingSync:'Subtítulos originales · sincronización pendiente',preliminarySync:'Ajuste preliminar · verificando el audio completo',verifiedSync:'Sincronización verificada',streaming:'Ya puedes reproducir',translationWaiting:'Traducción lista para ver. El MP4 se prepara al terminar la sincronización.',expired:'Esta sesión caducó. Vuelve a preparar la película.',
    errors:{query_invalid:'Escribe al menos dos caracteres.',queue_full:'Oracle está ocupado. Inténtalo de nuevo en unos minutos.',storage_full:'El espacio temporal está ocupado. Borra una sesión o vuelve más tarde.',rate_limit:'Se alcanzó el límite temporal. Espera unos minutos.',movie_too_large:'Esta calidad supera el límite de 2 GB. Prueba hasta 480p.',source_unavailable:'La fuente no respondió. Vuelve a intentarlo.',movie_unavailable:'La fuente no ofrece un video disponible para esta película.',subtitle_missing:'Elige una versión de subtítulos.',alignment_failed:'No se pudo verificar la sincronización con esta versión. Prueba otra.',processing_failed:'No se pudo completar la película con esta versión. Prueba otra.',interrupted:'La preparación se interrumpió. Vuelve a iniciarla.',job_expired:'Esta sesión caducó. Vuelve a preparar la película.',googleTimeout:'Google tardó demasiado. Puedes reintentar la traducción.',googleUnavailable:'Google Translate no respondió. El video y los subtítulos originales siguen disponibles.',translation_timing_changed:'La traducción cambió los tiempos y no se guardó.',network:'No se pudo completar la operación. Comprueba la conexión o vuelve a intentarlo.'},
  },
  en: {
    popular:'Popular today',popularSource:'On StreamIMDB',browse:'Browse popular movies',title:'Movies',search:'Search StreamIMDB',query:'Movie title',find:'Search',empty:'No movies found.',found:'Results',choose:'Subtitle release',language:'Output language',quality:'Quality',small:'Up to 480p · smaller download',large:'Up to 720p',prepare:'Watch movie and sync subtitles',loading:'Searching…',loadingMovie:'Checking video and subtitles…',
    note:'The movie is prepared temporarily on Oracle. Files are deleted after one hour of inactivity, and at most six hours after creation.',consent:'I agree to send the subtitle text to Google for translation into the selected language. I will keep this tab visible during translation.',fallback:'There is no release in this language. You can translate an available release while the video is being prepared.',noSubs:'No subtitles were found for this movie. Try checking again later.',downloading:'Downloading movie',remuxing:'Preparing video',synchronizing:'Synchronizing with audio',packaging:'Adding subtitles to MP4',translating:'Adding translation to MP4',ready:'Ready to watch',download:'Download MP4 with subtitles',srt:'Download synchronized SRT',translate:'Translate subtitles',translation:'Translating dialogue',translationDone:'Translation complete. Preparing MP4.',cancel:'Cancel and delete files',erase:'Delete this session',expiry:'If unused, files will be deleted at',max:'This link is temporary. Prepare the movie again after it expires.',edit:'Need another language?',style:'Subtitle style',styleColor:'Color',styleFont:'Font',styleSize:'Size',styleBackground:'Background opacity',styleReset:'Reset',styleSpeakers:'One color per character',speakersRunning:'Separating dialogue by character in the background…',speakersReady:'Dialogue separated by character',yellow:'Yellow',white:'White',cyan:'Cyan',green:'Green',fontScript:'Screenplay (Courier Prime)',fontSans:'Sans serif',fontSerif:'Serif',busy:'You can watch while the complete file is prepared. Synchronization is verified in the background.',pendingSync:'Original subtitles · synchronization pending',preliminarySync:'Preliminary adjustment · checking the full audio',verifiedSync:'Synchronization verified',streaming:'Playback is available',translationWaiting:'Translation ready to watch. MP4 export follows full synchronization.',expired:'This session expired. Prepare the movie again.',
    errors:{query_invalid:'Enter at least two characters.',queue_full:'Oracle is busy. Try again in a few minutes.',storage_full:'Temporary storage is full. Delete a session or try later.',rate_limit:'Temporary request limit reached. Wait a few minutes.',movie_too_large:'This quality exceeds 2 GB. Try up to 480p.',source_unavailable:'The source did not respond. Try again.',movie_unavailable:'No available video was found for this movie.',subtitle_missing:'Choose a subtitle release.',alignment_failed:'Synchronization could not be verified for this release. Try another.',processing_failed:'This release could not be processed. Try another.',interrupted:'Preparation was interrupted. Start it again.',job_expired:'This session expired. Prepare the movie again.',googleTimeout:'Google took too long. Retry the translation.',googleUnavailable:'Google Translate did not respond. Video and original subtitles remain available.',translation_timing_changed:'The translation changed timing and was not saved.',network:'The operation could not be completed. Check your connection or retry.'},
  },
};

export function setupCinema(getLanguage, activate) {
  const panel = document.getElementById('cinema-panel');
  const $ = id => document.getElementById('cinema-' + id);
  const t = key => words[getLanguage()][key];
  let movie, job, poll, request, selectedRun = 0, translation, translating = false, autoTranslate = false, wantedLanguage, hls, sourceToken, captionsURL, captionRun=0, draft, timingCache, submitting=false;
  let browsing=true, popularLoading=false, popularUntil=0;
  panel.innerHTML = `
    <form id="cinema-search"><label for="cinema-query" data-cinema="search"></label><div class="cinema-search-row"><input id="cinema-query" type="search" required minlength="2" maxlength="120" autocomplete="off"><button class="secondary" type="submit" data-cinema="find"></button></div></form>
    <p id="cinema-message" role="status" aria-live="polite"></p><p id="cinema-error" role="alert" hidden></p>
    <button id="cinema-browse" class="text-button" type="button" data-cinema="browse" hidden></button>
    <section id="cinema-popular" aria-labelledby="cinema-popular-title" hidden><div class="cinema-popular-heading"><h2 id="cinema-popular-title" data-cinema="popular"></h2><span data-cinema="popularSource"></span></div><div id="cinema-posters" class="cinema-posters"></div></section>
    <div id="cinema-results" class="cinema-results"></div>
    <section id="cinema-detail" hidden><h2 id="cinema-title" tabindex="-1"></h2><p class="help" data-cinema="note"></p>
      <div class="cinema-options"><label><span data-cinema="language"></span><select id="cinema-language"></select></label><label><span data-cinema="quality"></span><select id="cinema-quality"><option value="480" data-cinema="small"></option><option value="720" data-cinema="large"></option></select></label></div>
      <label><span data-cinema="choose"></span><select id="cinema-subtitle"></select></label><p id="cinema-fallback" class="help" data-cinema="fallback" hidden></p>
      <label id="cinema-consent-label" class="checkbox" hidden><input id="cinema-consent" type="checkbox"><span data-cinema="consent"></span></label>
      <button id="cinema-prepare" class="primary" type="button" data-cinema="prepare"></button>
    </section>
    <section id="cinema-session" hidden><h2 id="cinema-session-title"></h2><p id="cinema-state" role="status" aria-live="polite"></p><progress id="cinema-progress" max="100" value="0"></progress><p id="cinema-busy" class="help" data-cinema="busy"></p>
      <video id="cinema-video" controls playsinline preload="metadata" hidden></video>
      <details id="cinema-style" class="cinema-style" hidden><summary data-cinema="style"></summary><div class="cinema-style-grid">
        <label><span data-cinema="styleColor"></span><select id="cinema-style-color"><option value="#ffe14d" data-cinema="yellow"></option><option value="#ffffff" data-cinema="white"></option><option value="#7fe7ff" data-cinema="cyan"></option><option value="#9dff8a" data-cinema="green"></option></select></label>
        <label><span data-cinema="styleFont"></span><select id="cinema-style-font"><option value="script" data-cinema="fontScript"></option><option value="sans" data-cinema="fontSans"></option><option value="serif" data-cinema="fontSerif"></option></select></label>
        <label><span data-cinema="styleSize"></span><input id="cinema-style-size" type="range" min="60" max="200" step="10"></label>
        <label><span data-cinema="styleBackground"></span><input id="cinema-style-background" type="range" min="0" max="100" step="5"></label>
        <label class="checkbox"><input id="cinema-style-speakers" type="checkbox"><span data-cinema="styleSpeakers"></span></label>
      </div><p id="cinema-speakers" class="help" role="status"></p><button id="cinema-style-reset" class="text-button" type="button" data-cinema="styleReset"></button></details>
      <p id="cinema-metrics" class="help"></p>
      <div id="cinema-downloads" class="cinema-actions" hidden><a id="cinema-download" class="primary" data-cinema="download" download></a><a id="cinema-srt" class="secondary" data-cinema="srt" download></a></div>
      <details id="cinema-translation" hidden><summary data-cinema="edit"></summary><label><span data-cinema="language"></span><select id="cinema-target"></select></label><label class="checkbox"><input id="cinema-translate-consent" type="checkbox"><span data-cinema="consent"></span></label><button id="cinema-translate" class="secondary" type="button" data-cinema="translate"></button></details>
      <p id="cinema-translation-status" role="status"></p><div id="cinema-google-frame"></div>
      <p id="cinema-expiry" class="help"></p><p class="help" data-cinema="max"></p><button id="cinema-delete" class="text-button" type="button"></button>
    </section>`;

  const STYLE_DEFAULT={color:'#ffe14d',font:'script',size:100,background:75,speakers:true};
  const SPEAKER_COLORS=['#7fe7ff','#9dff8a','#ffb3d9','#ffb26b','#c9a6ff'];
  const FONTS={script:'"Courier Prime","Courier New",Courier,monospace',sans:'Inter,Arial,sans-serif',serif:'Georgia,"Times New Roman",serif'};
  let subtitleStyle={...STYLE_DEFAULT};
  try{subtitleStyle={...STYLE_DEFAULT,...JSON.parse(localStorage.getItem('cueflow-subtitle-style')||'{}')};}catch{/* Optional. */}
  function applyStyle(save=true) {
    const v=$('video').style;
    if(!FONTS[subtitleStyle.font])subtitleStyle.font=STYLE_DEFAULT.font;
    v.setProperty('--cue-color',subtitleStyle.color);v.setProperty('--cue-font',FONTS[subtitleStyle.font]);
    v.setProperty('--cue-size',subtitleStyle.size+'%');
    SPEAKER_COLORS.forEach((c,i)=>v.setProperty(`--cue-s${i+2}`,subtitleStyle.speakers?c:subtitleStyle.color));$('style-speakers').checked=subtitleStyle.speakers;v.setProperty('--cue-bg',`rgba(0,0,0,${subtitleStyle.background/100})`);
    $('style-color').value=subtitleStyle.color;$('style-font').value=subtitleStyle.font;
    $('style-size').value=subtitleStyle.size;$('style-background').value=subtitleStyle.background;
    if(save)try{localStorage.setItem('cueflow-subtitle-style',JSON.stringify(subtitleStyle));}catch{/* Optional. */}
  }
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
  function browseView(show) {
    browsing=show;$('popular').hidden=!show||!$('posters').children.length;
    $('browse').hidden=show||!!job;
  }
  async function showPopular() {
    if(!browsing||popularLoading)return;
    browseView(true);
    if(Date.now()<popularUntil)return;
    popularLoading=true;
    try{
      const data=await api('/popular');
      const cards=[];
      for(const item of (Array.isArray(data.results)?data.results:[]).slice(0,4)){
        if(!/^[a-z0-9][a-z0-9-]{1,120}$/.test(item.slug)||typeof item.title!=='string'||!/^https:\/\/image\.tmdb\.org\/t\/p\/w342\/[A-Za-z0-9]+\.(jpg|png|webp)$/.test(item.poster))continue;
        const link=document.createElement('a');link.className='cinema-poster';link.href='#movie/'+item.slug;
        const cover=document.createElement('span');cover.className='cinema-poster-image';
        const img=document.createElement('img');img.src=item.poster;img.alt='';img.width=228;img.height=342;
        img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';img.onerror=()=>img.remove();
        const title=document.createElement('span');title.className='cinema-poster-title';title.textContent=item.title;
        cover.append(img);link.append(cover,title);cards.push(link);
      }
      $('posters').replaceChildren(...cards);popularUntil=Date.now()+900000;
      browseView(browsing);
    }catch{/* Discovery is optional; search remains available. */}
    finally{popularLoading=false;}
  }
  $('browse').onclick=()=>{
    request?.abort();selectedRun++;movie=null;$('detail').hidden=true;$('results').replaceChildren();
    $('query').value='';$('message').textContent='';clearError();browseView(true);
    history.replaceState(null,'','#movies');showPopular();$('query').focus();
  };
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
    browseView(false);clearError();$('message').textContent=t('loadingMovie');$('detail').hidden=true;
    try {
      const data=await api('/movies/'+encodeURIComponent(slug),{signal:request.signal});
      if(run!==selectedRun)return;
      movie=data;$('title').textContent=data.title;$('detail').hidden=false;
      $('subtitle').replaceChildren(...data.subtitles.map(s=>new Option(`${languageName(s.language)} · ${s.name}`,s.id)));
      $('message').textContent=data.subtitles.length?'':t('noSubs');updateSelection(true);
      if(navigate)history.replaceState(null,'',`#movie/${slug}`);
      $('title').focus({preventScroll:true});
    } catch(e) {if(run===selectedRun&&e.name!=='AbortError'){error(e);$('message').textContent='';}}
  }
  $('search').onsubmit=async e=>{
    e.preventDefault();request?.abort();request=new AbortController();const run=++selectedRun;
    browseView(false);clearError();$('message').textContent=t('loading');$('results').replaceChildren();
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
    hls?.destroy();hls=null;sourceToken=null;captionRun++;timingCache=null;
    if(captionsURL)URL.revokeObjectURL(captionsURL);captionsURL=null;
    delete $('video').dataset.track;
    $('video').pause();$('video').removeAttribute('src');$('video').replaceChildren();$('video').load();$('video').hidden=true;$('style').hidden=true;
  }
  function remember() {try{localStorage.setItem('cueflow-movie-session',JSON.stringify({token:job.token,slug:job.slug}));}catch{/* Optional. */}}
  function setTrack(source, language, version) {
    if($('video').dataset.track===version)return;
    $('video').replaceChildren();
    const track=document.createElement('track');track.kind='subtitles';track.src=source;
    track.srclang=language;track.label=languageName(language);track.default=true;
    $('video').append(track);$('video').dataset.track=version;
    track.addEventListener('load',()=>{track.track.mode='showing';});
  }
  async function attachVideo() {
    if(sourceToken===job.token)return;
    const token=job.token;sourceToken=token;$('video').hidden=false;$('style').hidden=false;
    if(!job.stream_ready){$('video').src=file('movie.mp4');return;}
    const url=`${API}/jobs/${encodeURIComponent(token)}/stream.m3u8`;
    if($('video').canPlayType('application/vnd.apple.mpegurl')){$('video').src=url;return;}
    try {
      const {default:Hls}=await import('hls.js');
      if(job?.token!==token||sourceToken!==token)return;
      if(!Hls.isSupported())throw new Error('network');
      hls=new Hls({enableWorker:false,maxBufferLength:20,maxMaxBufferLength:40,backBufferLength:30});
      hls.on(Hls.Events.ERROR,(_,data)=>{if(data.fatal&&job?.token===token)error(new Error('source_unavailable'));});
      hls.loadSource(url);hls.attachMedia($('video'));
    }catch(e){if(job?.token===token)error(e);}
  }
  function captionSource() {
    if(job.files.includes('subtitles.srt'))return 'subtitles';
    if(job.files.includes('preliminary.srt'))return 'preliminary';
    return 'original';
  }
  async function timedDocument() {
    const name=captionSource(), key=job.token+':'+name;
    if(timingCache?.key!==key){
      const response=await fetch(file(name+'.srt'));
      if(!response.ok)throw new Error('job_expired');
      const doc=parseDocument(await response.text(),'srt');timingCache={key,doc};
    }
    return structuredClone(timingCache.doc);
  }
  async function renderCaptions() {
    if(!job)return;
    const translated=job.translated_language&&job.files.includes('translated.vtt');
    if(draft?.token!==job.token||!draft.done||translated&&draft.target===job.translated_language){
      const source=translated?'translated':captionSource(), name=source==='subtitles'&&job.files.includes('speakers.vtt')?'speakers':source;
      if(job.files.includes(name+'.vtt'))setTrack(file(name+'.vtt'),translated?job.translated_language:job.language,name+':'+(job.translated_language||job.language));
      return;
    }
    const version=job.token+':'+captionSource()+':'+draft.target+':'+draft.done;
    if($('video').dataset.track===version)return;
    const run=++captionRun, currentDraft=draft;
    try {
      const doc=await timedDocument();
      if(run!==captionRun||draft!==currentDraft||job?.token!==currentDraft.token)return;
      doc.cues.forEach((cue,i)=>{cue.text=plain(currentDraft.texts[i]??cue.text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');});
      const old=captionsURL;captionsURL=URL.createObjectURL(new Blob([serializeDocument(doc,'vtt')],{type:'text/vtt'}));
      setTrack(captionsURL,draft.target,version);if(old)URL.revokeObjectURL(old);
    }catch(e){if(run===captionRun)error(e);}
  }
  function renderJob() {
    if(!job)return;
    $('session').hidden=false;$('session-title').textContent=job.title;
    $('speakers').textContent=['pending','running'].includes(job.speakers)?t('speakersRunning'):job.speakers==='ready'&&job.files.includes('speakers.vtt')?t('speakersReady'):'';
    $('state').textContent=job.state==='error'?(t('errors')[job.error]||t('errors').processing_failed):(job.stream_ready&&job.state!=='ready'?t('streaming')+' · ':'')+(t(job.state)||job.state);
    $('progress').value=job.progress;$('progress').hidden=['ready','error'].includes(job.state);$('busy').hidden=['ready','error'].includes(job.state);
    $('delete').textContent=t(['ready','error'].includes(job.state)?'erase':'cancel');
    $('expiry').textContent=`${t('expiry')} ${new Date(job.expires_at*1000).toLocaleTimeString(getLanguage())}.`;
    const ready=job.files.includes('movie.mp4');
    $('downloads').hidden=!ready;$('translation').hidden=!ready&&!job.files.includes('original.srt');
    if(ready){
      const translated=job.translated_language && job.files.includes('translated.mp4');
      $('download').href=file(translated?'translated.mp4':'movie.mp4',true);
      $('srt').href=file(translated?'translated.srt':'subtitles.srt',true);
    }
    if(ready||job.stream_ready){
      attachVideo();renderCaptions();
      const result=job.result||job.preliminary_result;
      $('metrics').textContent=t(job.result?'verifiedSync':job.sync_status==='preliminary'?'preliminarySync':'pendingSync')+(result?` · ${Number(result.offset).toFixed(2)} s`:'');
    }
    $('translate').disabled=translating||submitting||job.state==='error'||job.state==='translating'||!$('translate-consent').checked;
    updateSelection();
  }
  async function watch(token, slug) {
    browseView(false);$('browse').hidden=true;clearTimeout(poll);translation?.abort();draft=null;resetVideo();
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
        if((job.files.includes('original.srt')||job.state==='ready')&&autoTranslate){autoTranslate=false;$('target').value=wantedLanguage;$('translate-consent').checked=true;void translate();}
        if(job.state==='ready'&&draft?.complete&&!draft.submitted)void submitTranslation();
      }catch(e){if(job?.token===token){error(e);if(e.message==='job_expired'){resetVideo();$('downloads').hidden=true;job=null;}}}
      schedulePoll();
    },job.state==='ready'?15000:1500);
  }
  $('prepare').onclick=async()=>{
    if(!movie)return;clearError();$('prepare').disabled=true;
    try {
      const source=sourceLanguage();wantedLanguage=$('language').value;autoTranslate=wantedLanguage!==source&&$('consent').checked;
      const data=await api('/jobs',{method:'POST',body:JSON.stringify({slug:movie.slug,subtitle_id:$('subtitle').value,height:Number($('quality').value)})});
      await watch(data.token,movie.slug);$('session').scrollIntoView({behavior:'smooth',block:'start'});
    }catch(e){error(e);}finally{updateSelection();}
  };
  async function submitTranslation() {
    if(!job||job.state!=='ready'||!draft?.complete||draft.submitted||submitting)return;
    const current=draft,token=job.token;submitting=true;
    try {
      const doc=await timedDocument();
      if(job?.token!==token||draft!==current)return;
      if(doc.cues.length!==current.texts.length)throw new Error('translation_timing_changed');
      doc.cues.forEach((cue,i)=>{cue.text=current.texts[i];});
      const data=await api('/jobs/'+encodeURIComponent(token)+'/subtitles',{method:'POST',body:JSON.stringify({text:serializeDocument(doc,'srt'),language:current.target})});
      if(job?.token!==token)return;
      current.submitted=true;job=data;$('translation-status').textContent=t('translationDone');renderJob();
    }catch(e){if(job?.token===token)error(e);}finally{submitting=false;}
  }
  async function translate() {
    if(!job||job.state==='error'||translating||!$('translate-consent').checked)return;
    const token=job.token,target=$('target').value;
    translating=true;translation=new AbortController();clearError();renderJob();
    try {
      const doc=await timedDocument();
      if(job?.token!==token)return;
      if(draft?.token!==token||draft.target!==target)draft={token,target,texts:new Array(doc.cues.length),done:0};
      for(const indices of batches(doc.cues)){
        if(job?.token!==token)return;
        if(indices.every(i=>draft.texts[i]!==undefined))continue;
        $('translation-status').textContent=`${t('translation')} · ${draft.done}/${doc.cues.length}`;
        let result;
        const signal=translation.signal;
        for(let attempt=0;attempt<3;attempt++){
          if(signal.aborted||job?.token!==token)throw new Error('cancelled');
          try{
            result=await googleTranslate(indices.map(i=>doc.cues[i].text),job.language==='pb'?'pt':job.language,target,getLanguage(),$('google-frame'),signal);
            break;
          }catch(e){
            if(attempt===2||!['googleUnavailable','googleTimeout'].includes(e.message))throw e;
            await new Promise((resolve,reject)=>{
              const abort=()=>{clearTimeout(timer);reject(new Error('cancelled'));};
              const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve();},attempt===0?2000:5000);
              signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
            });
          }
        }
        if(job?.token!==token)return;
        indices.forEach((i,j)=>{draft.texts[i]=result[j];});draft.done= draft.texts.filter(text=>text!==undefined).length;
        $('translation-status').textContent=`${t('translation')} · ${draft.done}/${doc.cues.length}`;
        await renderCaptions();
      }
      draft.complete=true;$('translation-status').textContent=t('translationWaiting');
      await submitTranslation();
    }catch(e){if(job?.token===token&&e.message!=='cancelled')error(e);}finally{translating=false;renderJob();}
  }
  $('translate').onclick=translate;$('translate-consent').onchange=renderJob;
  $('style-color').onchange=e=>{subtitleStyle.color=e.target.value;applyStyle();};
  $('style-font').onchange=e=>{subtitleStyle.font=e.target.value;applyStyle();};
  $('style-size').oninput=e=>{subtitleStyle.size=Number(e.target.value);applyStyle();};
  $('style-background').oninput=e=>{subtitleStyle.background=Number(e.target.value);applyStyle();};
  $('style-speakers').onchange=e=>{subtitleStyle.speakers=e.target.checked;applyStyle();};
  $('style-reset').onclick=()=>{subtitleStyle={...STYLE_DEFAULT};applyStyle();};
  applyStyle(false);
  $('language').onchange=()=>updateSelection(true);$('subtitle').onchange=()=>updateSelection();
  $('delete').onclick=async()=>{
    if(!job)return;const token=job.token;clearError();translation?.abort();autoTranslate=false;
    try {await api('/jobs/'+encodeURIComponent(token),{method:'DELETE'});}catch(e){if(e.message!=='job_expired'){error(e);return;}}
    clearTimeout(poll);job=null;draft=null;resetVideo();$('session').hidden=true;$('translation-status').textContent='';
    try{localStorage.removeItem('cueflow-movie-session');}catch{/* Optional. */}
    history.replaceState(null,'',movie?`#movie/${movie.slug}`:'#movies');browseView(!movie);if(!movie)showPopular();updateSelection();
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
    else if(parts[0]==='movies'){activate('movies',false);if(!job){request?.abort();selectedRun++;movie=null;$('detail').hidden=true;$('results').replaceChildren();$('message').textContent='';clearError();browseView(true);showPopular();}}
  }
  const retranslate=()=>{panel.querySelectorAll('[data-cinema]').forEach(el=>{el.textContent=t(el.dataset.cinema);});$('query').setAttribute('aria-label',t('query'));languageMenus();updateSelection();renderJob();};
  retranslate();route();window.addEventListener('hashchange',route);
  return {retranslate,show:showPopular,routeHash:()=>job?`#watch/${job.token}/${job.slug}`:movie?`#movie/${movie.slug}`:'#movies'};
}

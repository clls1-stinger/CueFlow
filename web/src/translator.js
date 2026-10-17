import { googleTranslate } from './google.js';
import { decodeSrt } from './subtitles.js';
import { FORMATS, GOOGLE_LANGUAGES, parseDocument, serializeDocument, timeValue, batches } from './formats.js';
import { timestamp } from './subtitles.js';
const $ = id => document.getElementById(id);
const copy = {
  es: {
    tab:'Traducir y editar',syncTab:'Sincronizar',title:'Tus subtítulos. En otro idioma.',intro:'Traduce el texto, revisa cada diálogo y conserva sus tiempos. También puedes editar y convertir sin conexión.',
    files:'Elegir subtítulos',hint:'Hasta 20 archivos · 1 MB en total · SRT, VTT, ASS, SBV, SubViewer SUB y Spruce STL de texto.',source:'Idioma original',target:'Traducir a',auto:'Detectar automáticamente',encoding:'Codificación',fps:'Fotogramas por segundo (STL)',options:'Opciones de lectura',
    consent:'Acepto enviar el texto a Google Translate. No se envían el video, el audio ni los tiempos.',privacy:'Traducción online · Sincronización, edición y conversión locales. La disponibilidad y calidad varían por idioma. No todos los idiomas están garantizados.',translate:'Traducir con Google',cancel:'Cancelar',retry:'Continuar traducción',ready:'Listo para editar o traducir.',done:'Traducción completa. Revisa el resultado antes de descargar.',cancelled:'Traducción detenida. Puedes continuar o descargar el trabajo parcial.',
    editor:'Revisar y editar',original:'Original',result:'Texto de salida',start:'Inicio',end:'Fin',previous:'Anterior',next:'Siguiente',format:'Formato de descarga',same:'Conservar formato',download:'Descargar archivo',downloadAll:'Descargar lote ZIP',remove:'Quitar',empty:'Elige uno o varios archivos para comenzar.',partial:'Parcial',complete:'Traducido',untranslated:'Sin traducir',progress:'Traduciendo',cue:'Diálogo',conversion:'Al convertir a otro formato se conservan texto y tiempos, pero se simplifican estilos y posiciones. STL usa la tasa de fotogramas elegida; ASS y SUB redondean a centésimas.',saved:'Cambios guardados en esta sesión. Descarga antes de cerrar.',
    errors:{googleUnavailable:'Google Translate no está disponible o fue bloqueado. Comprueba la conexión y los bloqueadores de contenido.',googleTimeout:'Google no terminó a tiempo. Reintenta este bloque; tu progreso se conserva.',googleLanguage:'Google no ofrece ese idioma en esta sesión. Prueba otro.',formatInvalid:'El formato o los tiempos no son válidos. SUB debe ser SubViewer; STL debe ser texto Spruce, no EBU binario.',invalidSrt:'El SRT no es válido o tiene tiempos desordenados.',encoding:'No pudimos leer el texto. Cambia la codificación en Opciones y vuelve a elegir el archivo.',batchLimit:'Elige hasta 20 archivos, con un máximo de 1 MB en total.',cueLarge:'Un diálogo supera los 3.000 caracteres. Divídelo antes de traducir.',input:'Los datos no son válidos.',rateLimit:'Se alcanzó el límite temporal de traducción. Espera un minuto; si persiste, vuelve mañana. Tu progreso se conserva en esta sesión.',translationUnavailable:'Google Translate no está disponible. Puedes seguir editando o volver a intentar más tarde.',translationInvalid:'La traducción llegó incompleta o cambió el formato. No reemplazamos ese bloque. Puedes volver a intentar.',network:'No se pudo conectar. Comprueba internet y vuelve a intentar.',sameLanguage:'Elige un idioma de destino diferente.',editInvalid:'Revisa los tiempos: fin debe ser posterior a inicio. El texto no puede quedar vacío ni contener líneas en blanco.'}
  },
  en: {
    tab:'Translate & edit',syncTab:'Synchronize',title:'Your subtitles. Another language.',intro:'Translate the text, review each line and keep its timing. You can also edit and convert offline.',
    files:'Choose subtitles',hint:'Up to 20 files · 1 MB total · SRT, VTT, ASS, SBV, SubViewer SUB and text Spruce STL.',source:'Original language',target:'Translate into',auto:'Detect automatically',encoding:'Encoding',fps:'Frames per second (STL)',options:'Import options',
    consent:'I agree to send the text to Google Translate. Video, audio and timestamps are not sent.',privacy:'Online translation · Local synchronization, editing and conversion. Availability and quality vary by language. Not every language is guaranteed.',translate:'Translate with Google',cancel:'Cancel',retry:'Continue translation',ready:'Ready to edit or translate.',done:'Translation complete. Review the result before downloading.',cancelled:'Translation stopped. Continue or download your partial work.',
    editor:'Review & edit',original:'Original',result:'Output text',start:'Start',end:'End',previous:'Previous',next:'Next',format:'Download format',same:'Keep original format',download:'Download file',downloadAll:'Download batch ZIP',remove:'Remove',empty:'Choose one or more files to begin.',partial:'Partial',complete:'Translated',untranslated:'Not translated',progress:'Translating',cue:'Cue',conversion:'Conversion preserves text and timing but simplifies styles and positioning. STL uses the selected frame rate; ASS and SUB round to hundredths.',saved:'Changes saved for this session. Download before closing.',
    errors:{googleUnavailable:'Google Translate is unavailable or blocked. Check your connection and content blockers.',googleTimeout:'Google did not finish in time. Retry this batch; your progress is preserved.',googleLanguage:'Google does not offer that language in this session. Try another.',formatInvalid:'Invalid format or timestamps. SUB must be SubViewer; STL must be Spruce text, not binary EBU.',invalidSrt:'The SRT is invalid or has out-of-order timestamps.',encoding:'Could not decode the text. Change the encoding under Options and choose the file again.',batchLimit:'Choose up to 20 files with a total size of 1 MB or less.',cueLarge:'One cue exceeds 3,000 characters. Split it before translating.',input:'The data is invalid.',rateLimit:'Translation limit reached. Wait a minute; if it persists, try tomorrow. Progress is kept in this session.',translationUnavailable:'Google Translate is unavailable. Keep editing or try again later.',translationInvalid:'The response was incomplete or changed formatting. That batch was not replaced. Try again.',network:'Could not connect. Check your internet connection and retry.',sameLanguage:'Choose a different target language.',editInvalid:'Check the times: end must follow start. Text cannot be empty or contain blank lines.'}
  }
};
// Small ZIP store writer: UTF-8 filenames, CRC-32, no dependency or compression of private text.
export function zipFiles(files) {
  const enc = new TextEncoder(), parts = [], central = []; let offset = 0;
  const header = (size, values) => { const b = new Uint8Array(size), v = new DataView(b.buffer); for (const [at,n,width] of values) width === 2 ? v.setUint16(at,n,true) : v.setUint32(at,n,true); return b; };
  for (const file of files) {
    const name = enc.encode(file.name), data = enc.encode(file.text); let crc = -1;
    for (const byte of data) { crc ^= byte; for(let i=0;i<8;i++) crc = (crc>>>1) ^ ((crc&1) ? 0xedb88320 : 0); } crc = (crc ^ -1)>>>0;
    const local = header(30,[[0,0x04034b50,4],[4,20,2],[6,0x800,2],[10,0,2],[12,33,2],[14,crc,4],[18,data.length,4],[22,data.length,4],[26,name.length,2]]);
    parts.push(local,name,data);
    central.push(header(46,[[0,0x02014b50,4],[4,20,2],[6,20,2],[8,0x800,2],[14,33,2],[16,crc,4],[20,data.length,4],[24,data.length,4],[28,name.length,2],[42,offset,4]]),name);
    offset += local.length+name.length+data.length;
  }
  const size = central.reduce((n,b)=>n+b.length,0);
  return new Blob([...parts,...central,header(22,[[0,0x06054b50,4],[8,files.length,2],[10,files.length,2],[12,size,4],[16,offset,4]])],{type:'application/zip'});
}

export function setupTranslator(getLanguage) {
  let files=[], selected=0, page=0, busy=false, controller, run=0, status='';
  const t = key => copy[getLanguage()][key];
  const panel = $('translate-panel');
  panel.innerHTML = `<h2 data-tr="title"></h2><p class="lead" data-tr="intro"></p>
    <label class="translate-upload"><strong data-tr="files"></strong><input id="translate-files" type="file" multiple accept=".srt,.vtt,.ass,.sbv,.sub,.stl"><span class="help" data-tr="hint"></span></label>
    <details><summary data-tr="options"></summary><div class="settings-grid"><label><span data-tr="encoding"></span><select id="translate-encoding"></select></label><label><span data-tr="fps"></span><select id="translate-fps"><option>25</option><option>24</option><option>30</option></select></label></div></details>
    <ul id="translation-files" class="translation-files"></ul>
    <div class="settings-grid"><label><span data-tr="source"></span><select id="source-language"></select></label><label><span data-tr="target"></span><select id="target-language"></select></label></div>
    <p class="help" data-tr="privacy"></p><label class="checkbox translation-consent"><input id="translation-consent" type="checkbox"><span data-tr="consent"></span></label>
    <button id="translate-run" class="primary" type="button" data-tr="translate" disabled></button><button id="translate-cancel" type="button" class="secondary" data-tr="cancel" hidden></button>
    <div id="google-translation-frame"></div><p class="help google-credit">Translation by <a href="https://translate.google.com/" target="_blank" rel="noopener noreferrer">Google Translate</a></p><p id="translation-status" role="status" aria-live="polite"></p><p id="translation-error" role="alert" hidden></p>
    <section id="subtitle-editor" hidden><h3 data-tr="editor"></h3><div id="editor-cues"></div><div class="editor-pager"><button id="editor-prev" class="secondary" type="button" data-tr="previous"></button><span id="editor-page"></span><button id="editor-next" class="secondary" type="button" data-tr="next"></button></div>
    <label><span data-tr="format"></span><select id="export-format"><option value="same" data-tr="same"></option>${FORMATS.map(f=>`<option value="${f}">${f.toUpperCase()}</option>`).join('')}</select></label><p class="help" data-tr="conversion"></p><div class="android-actions"><button id="translate-download" class="secondary" type="button" data-tr="download"></button><button id="translate-download-all" class="secondary" type="button" data-tr="downloadAll"></button></div></section>`;
  $('translate-encoding').replaceChildren(...[...$('encoding').options].map(o=>o.cloneNode(true)));
  const err = e => { $('translation-error').textContent=copy[getLanguage()].errors[e.message] || copy[getLanguage()].errors.network; $('translation-error').hidden=false; };
  const clearError = () => { $('translation-error').hidden=true; };
  function renderLanguages() {
    const names = new Intl.DisplayNames([getLanguage()],{type:'language'});
    for(const id of ['source-language','target-language']) {
      const old=$(id).value; $(id).replaceChildren();
      if(id==='source-language') $(id).add(new Option(t('auto'),'auto'));
      GOOGLE_LANGUAGES.map(({code,name})=>{let label=name;try{label=names.of(code)||name;}catch{}return [code,label];}).sort((a,b)=>a[1].localeCompare(b[1],getLanguage())).forEach(([code,name])=>$(id).add(new Option(name,code)));
      $(id).value=old || (id==='source-language'?'auto':getLanguage());
    }
  }
  function update() {
    panel.querySelectorAll('[data-tr]').forEach(el=>{el.textContent=t(el.dataset.tr);});
    $('translate-files').disabled=busy; $('translate-encoding').disabled=busy; $('translate-fps').disabled=busy;
    $('source-language').disabled=busy; $('target-language').disabled=busy; $('translation-consent').disabled=busy;
    $('translate-run').disabled=busy || !files.length || !$('translation-consent').checked;
    $('translate-run').textContent=t(files.some(f=>f.done.size>0 && f.done.size<f.doc.cues.length)?'retry':'translate');
    $('translate-cancel').hidden=!busy;
    $('subtitle-editor').hidden=!files.length;
    $('translation-status').textContent=status || t(files.length?'ready':'empty');
    $('translation-files').replaceChildren();
    files.forEach((f,i)=>{
      const li=document.createElement('li'), choose=document.createElement('button'), remove=document.createElement('button');
      choose.type=remove.type='button'; choose.className='file-choice'; choose.setAttribute('aria-pressed',String(i===selected));
      choose.textContent=`${f.name} · ${f.doc.cues.length} · ${t(f.done.size===f.doc.cues.length?'complete':f.done.size?'partial':'untranslated')}`;
      choose.disabled=busy;choose.onclick=()=>{selected=i;page=0;update();};
      remove.textContent='×';remove.setAttribute('aria-label',`${t('remove')} ${f.name}`);remove.disabled=busy;remove.onclick=()=>{files.splice(i,1);selected=Math.min(selected,files.length-1);page=0;status='';update();};li.append(choose,remove);$('translation-files').append(li);
    });
    renderEditor();
  }
  function renderEditor() {
    $('editor-cues').replaceChildren(); const file=files[selected];if(!file)return;
    const start=page*8;
    file.doc.cues.slice(start,start+8).forEach((cue,local)=>{
      const index=start+local,row=document.createElement('div');row.className='cue-editor';
      const heading=document.createElement('strong');heading.textContent=`${t('cue')} ${index+1}`;
      const times=document.createElement('div');times.className='cue-times';
      const controls={};
      for(const key of ['start','end']) {
        const label=document.createElement('label'),span=document.createElement('span'),input=document.createElement('input');
        span.textContent=t(key);input.value=timestamp(cue[key]);input.disabled=busy;input.setAttribute('aria-label',`${t(key)} ${index+1}`);input.inputMode='decimal';controls[key]=input;label.append(span,input);times.append(label);
      }
      const columns=document.createElement('div');columns.className='cue-columns';
      const source=document.createElement('p');source.className='cue-original';source.dir='auto';source.textContent=file.original[index].text;source.setAttribute('aria-label',t('original'));
      const label=document.createElement('label'),span=document.createElement('span'),input=document.createElement('textarea');span.textContent=t('result');input.value=cue.text;input.dir='auto';input.rows=3;input.disabled=busy;input.setAttribute('aria-label',`${t('result')} ${index+1}`);label.append(span,input);columns.append(source,label);
      const save=()=>{try{
        const a=timeValue(controls.start.value),b=timeValue(controls.end.value);
        if(a<0 || b<=a || b>86400 || !input.value.trim() || /\n\s*\n/.test(input.value))throw new Error('editInvalid');
        cue.start=a;cue.end=b;cue.text=input.value;row.classList.remove('invalid');input.setCustomValidity('');clearError();status=t('saved');$('translation-status').textContent=status;
      }catch{row.classList.add('invalid');input.setCustomValidity(t('errors').editInvalid);err(new Error('editInvalid'));}};
      for(const item of [...Object.values(controls),input])item.addEventListener('input',save);
      row.append(heading,times,columns);$('editor-cues').append(row);
    });
    $('editor-page').textContent=`${page+1} / ${Math.ceil(file.doc.cues.length/8)}`;
    $('editor-prev').disabled=busy||page===0;$('editor-next').disabled=busy||(page+1)*8>=file.doc.cues.length;
    $('translate-download').disabled=$('translate-download-all').disabled=busy;
  }
  $('translate-files').onchange=async e=>{
    if(busy)return;clearError();status='';const chosen=[...e.target.files];
    try {
      if(files.length+chosen.length>20 || files.reduce((s,f)=>s+f.size,0)+chosen.reduce((s,f)=>s+f.size,0)>1000000)throw new Error('batchLimit');
      const added=[];
      for(const file of chosen) {
        const format=file.name.split('.').at(-1).toLowerCase();
        const doc=parseDocument(decodeSrt(await file.arrayBuffer(),$('translate-encoding').value),format,Number($('translate-fps').value));
        added.push({name:file.name,size:file.size,doc,original:structuredClone(doc.cues),done:new Set(),target:null});
      }
      files.push(...added);selected=files.length-chosen.length;page=0;update();
    }catch(error){err(error);} finally { e.target.value=''; }
  };
  $('translation-consent').onchange=()=>{ $('translate-run').disabled=!files.length || !$('translation-consent').checked; };
  $('editor-prev').onclick=()=>{if(panel.querySelector('.invalid'))return err(new Error('editInvalid'));page--;renderEditor();};
  $('editor-next').onclick=()=>{if(panel.querySelector('.invalid'))return err(new Error('editInvalid'));page++;renderEditor();};
  $('translate-cancel').onclick=()=>{++run;controller?.abort();busy=false;status=t('cancelled');update();};
  $('translate-run').onclick=async()=>{
    if(busy||!files.length||!$('translation-consent').checked)return;
    if(panel.querySelector('.invalid'))return err(new Error('editInvalid'));
    clearError();const target=$('target-language').value,source=$('source-language').value;
    if(target===source)return err(new Error('sameLanguage'));
    const id=++run;busy=true;controller=new AbortController();
    // A new language pair starts again from the original dialogue; retries keep completed batches.
    for(const f of files)if(f.target!==target || f.source!==source){f.done.clear();f.target=target;f.source=source;}
    update();
    try {
      for(const file of files) {
        const all=batches(file.original);
        for(const indices of all) {
          if(indices.every(i=>file.done.has(i)))continue;
          if(id!==run)return;
          status=`${t('progress')} · ${file.name} · ${file.done.size}/${file.doc.cues.length}`; $('translation-status').textContent=status;
          const translated=await googleTranslate(indices.map(i=>file.original[i].text),source,target,getLanguage(),$('google-translation-frame'),controller.signal);
          if(id!==run)return;
          indices.forEach((index,j)=>{file.doc.cues[index].text=translated[j];file.done.add(index);});
          update();

        }
      }
      status=t('done');
    }catch(error){if(id===run){status=t('cancelled');err(error);}}
    finally {if(id===run){busy=false;update();}}
  };
  function output(file,index) {
    if(panel.querySelector('.invalid'))throw new Error('editInvalid');
    const format=$('export-format').value==='same'?file.doc.format:$('export-format').value;
    const suffix=file.done.size ? `.${file.target}${file.done.size<file.doc.cues.length?'.partial':''}` : '.edited';
    const name=`${index+1}-${file.name.replace(/\.[^.]+$/,'').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_')}${suffix}.${format}`;
    return {name,text:serializeDocument(file.doc,format)};
  }
  function download(blob,name) {const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  $('translate-download').onclick=()=>{try{const out=output(files[selected],selected);download(new Blob([out.text],{type:'text/plain;charset=utf-8'}),out.name);}catch(error){err(error);}};
  $('translate-download-all').onclick=()=>{try{download(zipFiles(files.map(output)),'CueFlow-subtitles.zip');}catch(error){err(error);}};
  const retranslate=()=>{renderLanguages();status='';update();}; retranslate();
  return {retranslate,isBusy:()=>busy};
}

export function googleTranslate(texts, source, target, ui, container, signal) {
  return new Promise((resolve,reject)=>{
    const production=['cueflow.enriquepl.com','cueflow-dhh.pages.dev'].includes(location.hostname);
    const origin=production?(location.hostname==='cueflow-dhh.pages.dev'?'https://cueflow.enriquepl.com':'https://cueflow-dhh.pages.dev'):location.origin;
    const frame=document.createElement('iframe');frame.title='Google Translate';frame.className='google-frame';
    frame.setAttribute('sandbox','allow-scripts allow-same-origin');
    const finish=(error,result)=>{clearTimeout(timer);window.removeEventListener('message',receive);signal?.removeEventListener('abort',abort);frame.remove();error?reject(new Error(error)):resolve(result);};
    const abort=()=>finish('cancelled');
    const receive=event=>{
      if(event.source!==frame.contentWindow||event.origin!==origin)return;
      if(event.data?.type==='cueflow-google-ready')frame.contentWindow.postMessage({type:'cueflow-google-start',texts,source,target,ui},origin);
      if(event.data?.type==='cueflow-google-result'){
        const result=event.data.translations;
        if(event.data.error)return finish(event.data.error);
        if(!Array.isArray(result)||result.length!==texts.length||result.some(t=>typeof t!=='string'||!t.trim()))return finish('translationInvalid');
        finish(null,result);
      }
    };
    const timer=setTimeout(()=>finish('googleTimeout'),100000);
    window.addEventListener('message',receive);signal?.addEventListener('abort',abort,{once:true});
    if(signal?.aborted)return abort();
    frame.src=origin+'/google-translate.html';container.replaceChildren(frame);
  });
}

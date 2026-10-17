/* Independent integration of Google's public Website Translator widget.
 * The widget performs translation; CueFlow preserves document structure locally. */
(() => {
  let started=false, timer, observer, lastMutation=0, pending=0, translatedRequests=0, requestFailed=false;
  const root=document.getElementById('dialogue');
  window.cueflowResult=null;
  function finish(result) {
    if(window.cueflowResult)return;
    clearInterval(timer);observer?.disconnect();window.cueflowResult=result;
    if(parent!==window)parent.postMessage({type:'cueflow-google-result',...result},'*');
  }
  // Observe completion, without calling or recreating Google's internal endpoints.
  const open=XMLHttpRequest.prototype.open,send=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(method,url,...args){this.cueflowTranslation=/translate.*google|google.*translate/.test(String(url));return open.call(this,method,url,...args);};
  XMLHttpRequest.prototype.send=function(...args){
    if(this.cueflowTranslation){pending++;this.addEventListener('loadend',()=>{pending--;translatedRequests++;if(this.status===0||this.status>=400)requestFailed=true;},{once:true});}
    return send.apply(this,args);
  };
  window.cueflowStart = data => {
    if(started)return;started=true;
    if(!Array.isArray(data.texts)||!data.texts.length||data.texts.length>20||data.texts.some(t=>typeof t!=='string'||t.length>3000)||data.texts.reduce((n,t)=>n+t.length,0)>6000)return finish({error:'input'});
    if(!/^(auto|[a-z]{2,3}(?:-[A-Za-z0-9]+)*)$/.test(data.source)||!/^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$/.test(data.target))return finish({error:'input'});
    const records=data.texts.map(text=>{
      const row=document.createElement('p');row.className='cue';row.dir='auto';
      const fragments=text.split(/(<[^>\n]+>|\{[^}\n]*\}|\\[Nnh]|\[br\]|\n)/g).filter(Boolean);
      const parts=fragments.map(part=>{
        const node=document.createElement('span');node.textContent=part;
        const protectedPart=/^(<[^>\n]+>|\{[^}\n]*\}|\\[Nnh]|\[br\]|\n)$/.test(part);
        if(protectedPart){node.className='notranslate';node.translate=false;}else node.className='cf-text';
        row.append(node);return {node,original:part,protected:protectedPart};
      });root.append(row);return {row,parts};
    });
    lastMutation=Date.now();observer=new MutationObserver(()=>{lastMutation=Date.now();});observer.observe(root,{childList:true,characterData:true,subtree:true});
    let selected=false;const start=Date.now();
    window.googleTranslateElementInit=()=>{new google.translate.TranslateElement({pageLanguage:data.source,autoDisplay:false},'google_translate_element');};
    const script=document.createElement('script');script.src='https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit&hl='+ (data.ui==='es'?'es':'en');script.onerror=()=>finish({error:'googleUnavailable'});document.head.append(script);
    timer=setInterval(()=>{
      if(Date.now()-start>90000)return finish({error:'googleTimeout'});
      const select=document.querySelector('.goog-te-combo');
      if(select&&!selected){
        if(![...select.options].some(o=>o.value===data.target)){if(Date.now()-start>20000&&select.options.length>1)finish({error:'googleLanguage'});return;}
        selected=true;select.value=data.target;select.dispatchEvent(new Event('change',{bubbles:true}));
      }
      if(!selected||pending||Date.now()-lastMutation<1800||document.querySelector('.goog-te-spinner-pos-show'))return;
      const translated=records.every(r=>r.parts.every(p=>p.protected||!/[\p{L}\p{N}]/u.test(p.original)||p.node.querySelector('font')));
      if(!translated){if(requestFailed&&translatedRequests)return finish({error:'googleUnavailable'});return;}
      const outputs=records.map(r=>r.parts.map(p=>p.node.textContent).join(''));
      if(records.some(r=>r.parts.some(p=>p.protected&&p.node.textContent!==p.original))||outputs.some((t,i)=>!t.trim()||t.length>Math.max(1000,data.texts[i].length*6)))return finish({error:'translationInvalid'});
      finish({translations:outputs});
    },250);
  };
  addEventListener('message',event=>{if(event.source===parent&&parent!==window&&event.data?.type==='cueflow-google-start')window.cueflowStart(event.data);});
  if(parent!==window)parent.postMessage({type:'cueflow-google-ready'},'*');
})();

import { test, expect } from '@playwright/test';
const subtitle='1\n00:00:01,200 --> 00:00:03,400\n<i>Hello, friend!</i>\n\n2\n00:00:05,000 --> 00:00:06,800\nGoodbye.\n';
async function open(page) {await page.goto('/#translate');await page.locator('#translate-files').setInputFiles({name:'Example.srt',mimeType:'text/plain',buffer:Buffer.from(subtitle)});}
test('translate with consent, preserve timestamps, edit and download',async({page})=>{
 let posted;
 await page.exposeFunction('captureTranslation', data=>{posted=data;});
 await page.route('**/google-translate.html',route=>route.fulfill({contentType:'text/html',body:`<script>addEventListener('message',async e=>{await parent.captureTranslation(e.data);parent.postMessage({type:'cueflow-google-result',translations:['<i>Hola, amigo.</i>','Adiós.']},'*')});parent.postMessage({type:'cueflow-google-ready'},'*');</script>`}));
 await open(page);
 await expect(page.locator('#translate-run')).toBeDisabled();
 await page.locator('#translation-consent').check();await page.locator('#translate-run').click();
 await expect(page.locator('#translation-status')).toContainText('Traducción completa');
 expect(posted).toMatchObject({source:'auto',target:'es',texts:['<i>Hello, friend!</i>','Goodbye.']});
 await expect(page.getByLabel('Texto de salida 1',{exact:true})).toHaveValue('<i>Hola, amigo.</i>');
 await page.getByLabel('Texto de salida 2',{exact:true}).fill('Hasta luego.');
 const promise=page.waitForEvent('download');await page.locator('#translate-download').click();const download=await promise;
 const stream=await download.createReadStream();const chunks=[];for await(const c of stream)chunks.push(c);const output=Buffer.concat(chunks).toString();
 expect(output).toContain('00:00:01,200 --> 00:00:03,400');expect(output).toContain('Hasta luego.');expect(download.suggestedFilename()).toContain('.es.srt');
});
test('local conversion, batch ZIP, malicious text stays inert, invalid edit blocked',async({page})=>{
 let requests=0;page.on('request',r=>{if(r.method()==='POST')requests++;});await open(page);
 await page.getByLabel('Texto de salida 1',{exact:true}).fill('<script>window.evil=1</script>');expect(await page.evaluate(()=>window.evil)).toBeUndefined();
 await page.locator('#export-format').selectOption('vtt');const promise=page.waitForEvent('download');await page.locator('#translate-download-all').click();expect((await promise).suggestedFilename()).toBe('CueFlow-subtitles.zip');
 await page.getByLabel('Fin 1',{exact:true}).fill('00:00:00,000');await page.locator('#translate-download').click();await expect(page.locator('#translation-error')).toBeVisible();expect(requests).toBe(0);
});
test('Google error preserves originals and permits retry',async({page})=>{
 let calls=0;await page.route('**/google-translate.html',route=>{calls++;return route.fulfill({contentType:'text/html',body:`<script>addEventListener('message',()=>parent.postMessage(${JSON.stringify(calls===1?{type:'cueflow-google-result',error:'googleUnavailable'}:{type:'cueflow-google-result',translations:['Hola.','Adiós.']})},'*'));parent.postMessage({type:'cueflow-google-ready'},'*');</script>`});});
 await open(page);await page.locator('#translation-consent').check();await page.locator('#translate-run').click();await expect(page.locator('#translation-error')).toContainText('Google Translate');await expect(page.getByLabel('Texto de salida 1',{exact:true})).toHaveValue('<i>Hello, friend!</i>');await page.locator('#translate-run').click();await expect(page.locator('#translation-status')).toContainText('Traducción completa');
});
test('mobile translation mode fits and switches interface languages',async({page})=>{
 await page.setViewportSize({width:390,height:844});await open(page);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.locator('#language').click();await expect(page.locator('#translate-run')).toHaveText('Translate with Google');await expect(page.locator('#translate-panel h2')).toHaveText('Your subtitles. Another language.');
});

import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const token='s'.repeat(43);
const state={token,slug:'original-fixture',title:'Original fixture',state:'downloading',progress:5,language:'en',translated_language:null,expires_at:Date.now()/1000+3600,sync_status:'pending',stream_ready:true,files:['original.srt','original.vtt']};
let fixture;
test.beforeAll(async()=>{
  fixture=await mkdtemp(join(tmpdir(),'cueflow-hls-browser-'));
  execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','10','-c:v','libx264','-preset','ultrafast','-g','24','-c:a','aac','-hls_time','1','-hls_list_size','0',join(fixture,'stream.m3u8')]);
});
test.afterAll(async()=>{await rm(fixture,{recursive:true,force:true});});

test('plays and seeks HLS before MP4 is ready, then keeps playback during export completion',async({page})=>{
  let exported=false,segmentRequests=0;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/cinema/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('.m3u8'))return route.fulfill({body:await readFile(join(fixture,'stream.m3u8')),contentType:'application/vnd.apple.mpegurl'});
    if(path.endsWith('.ts')){segmentRequests++;return route.fulfill({body:await readFile(join(fixture,path.split('/').at(-1))),contentType:'video/mp2t'});}
    if(path.endsWith('.vtt'))return route.fulfill({body:'WEBVTT\n\n00:00:00.000 --> 00:00:09.000\nOriginal fixture\n',contentType:'text/vtt'});
    return route.fulfill({json:exported?{...state,state:'ready',progress:100,result:{offset:0,scale:1,cues:3},files:[...state.files,'movie.mp4','subtitles.srt','subtitles.vtt']}:state});
  });
  await page.goto('/#watch/'+token+'/original-fixture');
  const video=page.locator('#cinema-video');
  await expect(video).toBeVisible();await expect(page.locator('#cinema-downloads')).toBeHidden();
  await expect.poll(()=>video.evaluate(v=>v.readyState)).toBeGreaterThanOrEqual(3);
  await video.evaluate(v=>v.play());
  await expect.poll(()=>video.evaluate(v=>v.currentTime)).toBeGreaterThan(.5);
  const source=await video.getAttribute('src');
  await video.evaluate(v=>{v.currentTime=7;});
  await expect.poll(()=>video.evaluate(v=>v.currentTime)).toBeGreaterThan(7.2);
  exported=true;await expect(page.locator('#cinema-downloads')).toBeVisible();
  await expect(video).toHaveAttribute('src',source);
  expect(segmentRequests).toBeGreaterThan(1);expect(errors).toEqual([]);
});

test('shows translated batches early and submits them using final verified timing',async({page})=>{
  let exported=false,submitted,widgetRequests=0;
  const srt=shift=>Array.from({length:23},(_,i)=>`${i+1}\n00:00:${String(i*2+1+shift).padStart(2,'0')},000 --> 00:00:${String(i*2+2+shift).padStart(2,'0')},000\nHello ${i+1}.\n`).join('\n');
  await page.route('**/api/cinema/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/subtitles')){submitted=route.request().postDataJSON();return route.fulfill({status:202,json:{...state,state:'translating',stream_ready:false,files:['movie.mp4','subtitles.srt','subtitles.vtt']}});}
    if(path.endsWith('.srt'))return route.fulfill({body:srt(path.endsWith('/subtitles.srt')?1:0),contentType:'application/x-subrip'});
    if(path.endsWith('.vtt'))return route.fulfill({body:'WEBVTT\n',contentType:'text/vtt'});
    if(path.endsWith('.mp4'))return route.fulfill({status:404});
    return route.fulfill({json:{...state,stream_ready:false,...(exported?{state:'ready',result:{offset:1,scale:1,cues:23},files:['original.srt','original.vtt','movie.mp4','subtitles.srt','subtitles.vtt']}:{})}});
  });
  await page.route('**/google-translate.html',route=>{widgetRequests++;return route.fulfill({contentType:'text/html',body:`<script>
    parent.postMessage({type:'cueflow-google-ready'},location.origin);
    onmessage=e=>{if(e.data.type==='cueflow-google-start')setTimeout(()=>parent.postMessage(${widgetRequests===2?"{type:'cueflow-google-result',error:'googleUnavailable'}":"{type:'cueflow-google-result',translations:e.data.texts.map(t=>'Hola '+t.match(/\\d+/)[0]+'.')}"},location.origin),e.data.texts.length===20?50:3500);};
  </script>`});});
  await page.goto('/#watch/'+token+'/original-fixture');
  await page.locator('#cinema-translation summary').click();
  await page.locator('#cinema-target').selectOption('es');await page.locator('#cinema-translate-consent').check();await page.locator('#cinema-translate').click();
  await expect(page.locator('#cinema-translation-status')).toContainText('20/23');
  await expect(page.locator('#cinema-video track')).toHaveAttribute('src',/^blob:/);
  const preview=await page.locator('#cinema-video track').getAttribute('src');
  const caption=await page.evaluate(url=>fetch(url).then(r=>r.text()),preview);
  expect(caption).toContain('Hola 1.');expect(submitted).toBeUndefined();
  exported=true;
  await expect.poll(()=>submitted,{timeout:15000}).toBeTruthy();
  expect(submitted.language).toBe('es');expect(submitted.text).toContain('00:00:02,000 --> 00:00:03,000\nHola 1.');
  expect((submitted.text.match(/Hola /g)||[]).length).toBe(23);
  expect(widgetRequests).toBe(3);
  await expect(page.locator('#cinema-error')).toBeHidden();
});

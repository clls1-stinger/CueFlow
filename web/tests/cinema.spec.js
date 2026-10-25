import {test,expect} from '@playwright/test';

const token='a'.repeat(43);
const movie={slug:'test-film',title:'Película de prueba',subtitles:[{id:'os-1',language:'en',name:'Original.srt'},{id:'os-2',language:'es',name:'Español.srt'}]};
const ready={token,slug:movie.slug,title:movie.title,state:'ready',progress:100,language:'es',translated_language:null,expires_at:Date.now()/1000+3600,result:{cues:10,offset:-2,scale:1},files:['movie.mp4','subtitles.srt','subtitles.vtt']};

test('search, select language, start, restore, download and delete a movie session',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let posted,deleted=false;
  await page.route('**/api/cinema/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname,method=route.request().method();
    if(path.endsWith('/search'))return route.fulfill({json:{results:[{slug:movie.slug,title:movie.title,meta:'2026'}]}});
    if(path.includes('/movies/'))return route.fulfill({json:movie});
    if(path.endsWith('/jobs')&&method==='POST'){posted=route.request().postDataJSON();return route.fulfill({status:202,json:ready});}
    if(method==='DELETE'){deleted=true;return route.fulfill({status:204});}
    if(path.includes('/files/'))return route.fulfill({status:200,body:'WEBVTT\n',contentType:'text/vtt'});
    return route.fulfill({json:ready});
  });
  await page.goto('/#movies');await expect(page.locator('#cinema-panel')).toBeVisible();
  await page.locator('#cinema-query').fill('Película');await page.locator('#cinema-search button').click();
  await page.getByRole('button',{name:'Película de prueba 2026'}).click();
  await expect(page.locator('#cinema-subtitle')).toHaveValue('os-2');
  await page.locator('#cinema-prepare').click();
  await expect(page.locator('#cinema-downloads')).toBeVisible();
  expect(posted).toEqual({slug:'test-film',subtitle_id:'os-2',height:480});
  await expect(page.locator('#cinema-download')).toHaveAttribute('href',/movie\.mp4\?download=true/);
  await page.reload();await expect(page.locator('#cinema-downloads')).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'test-results/cinema-mobile.png',fullPage:true});
  await page.locator('#cinema-delete').click();await expect(page.locator('#cinema-session')).toBeHidden();
  expect(deleted).toBeTruthy();expect(errors).toEqual([]);
});

test('unavailable language offers translation and expired link offers the movie again',async({page})=>{
  await page.route('**/api/cinema/**',async route=>{
    if(route.request().url().includes('/movies/'))return route.fulfill({json:{...movie,subtitles:movie.subtitles.slice(0,1)}});
    return route.fulfill({status:410,json:{detail:'job_expired'}});
  });
  await page.goto('/#movie/test-film');
  await expect(page.locator('#cinema-fallback')).toBeVisible();
  await expect(page.locator('#cinema-consent')).not.toBeChecked();
  await page.goto('/#watch/'+token+'/test-film');
  await expect(page.locator('#cinema-detail')).toBeVisible();
  await expect(page.locator('#cinema-prepare')).toBeEnabled();
});

import {test,expect} from '@playwright/test';

const movies=Array.from({length:6},(_,i)=>({slug:`popular-${i}`,title:`Película ${i+1}`,poster:`https://image.tmdb.org/t/p/w342/Poster${i}.jpg`}));
const poster='<svg xmlns="http://www.w3.org/2000/svg" width="228" height="342"><rect width="228" height="342" fill="#34343a"/></svg>';

test('loads a restrained poster selection on demand, opens a movie with keyboard and returns to browsing',async({page})=>{
  let popularRequests=0;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://image.tmdb.org/**',route=>route.fulfill({body:poster,contentType:'image/svg+xml'}));
  await page.route('**/api/cinema/**',route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/popular')){popularRequests++;return route.fulfill({json:{results:movies}});}
    if(path.endsWith('/search'))return route.fulfill({json:{results:[{slug:'result-movie',title:'Resultado',meta:'2026'}]}});
    return route.fulfill({json:{slug:'popular-0',title:'Película 1',subtitles:[]}});
  });
  await page.goto('/');expect(popularRequests).toBe(0);
  await page.locator('#mode-movies').click();
  await expect(page.locator('#cinema-posters a')).toHaveCount(4);
  await expect(page.locator('#cinema-popular-title')).toHaveText('Populares de hoy');
  const first=page.locator('#cinema-posters a').first();
  await first.focus();await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#movie\/popular-0$/);
  await expect(page.locator('#cinema-title')).toBeFocused();
  await expect(page.locator('#cinema-popular')).toBeHidden();
  await page.locator('#cinema-browse').click();
  await expect(page.locator('#cinema-popular')).toBeVisible();expect(popularRequests).toBe(1);
  await page.setViewportSize({width:390,height:844});
  const layout=await page.locator('#cinema-posters').evaluate(el=>({columns:getComputedStyle(el).gridTemplateColumns.split(' ').length,overflow:document.documentElement.scrollWidth>innerWidth}));
  expect(layout).toEqual({columns:2,overflow:false});
  await page.locator('#cinema-query').fill('Resultado');await page.locator('#cinema-search button').click();
  await expect(page.getByRole('button',{name:'Resultado 2026'})).toBeVisible();
  await expect(page.locator('#cinema-popular')).toBeHidden();
  expect(errors).toEqual([]);
});

test('late or failed popular requests do not interrupt search or show broken posters',async({page})=>{
  let release;
  const delayed=new Promise(resolve=>{release=resolve;});
  await page.route('**/api/cinema/popular',async route=>{await delayed;await route.fulfill({json:{results:movies}});});
  await page.route('**/api/cinema/search?*',route=>route.fulfill({json:{results:[]}}));
  await page.route('https://image.tmdb.org/**',route=>route.abort('failed'));
  await page.goto('/#movies');
  await page.locator('#cinema-query').fill('Missing');await page.locator('#cinema-search button').click();
  await expect(page.locator('#cinema-message')).toHaveText('No se encontraron películas.');
  release();await expect(page.locator('#cinema-posters a')).toHaveCount(4);
  await expect(page.locator('#cinema-popular')).toBeHidden();
  await page.locator('#cinema-browse').click();
  await page.locator('#cinema-popular').scrollIntoViewIfNeeded();
  await expect(page.locator('#cinema-posters img')).toHaveCount(0);
  await expect(page.locator('#cinema-posters a')).toHaveCount(4);
  await page.unroute('**/api/cinema/popular');
  await page.route('**/api/cinema/popular',route=>route.fulfill({status:502,json:{detail:'source_unavailable'}}));
  await page.reload();
  await expect(page.locator('#cinema-search button')).toBeEnabled();
  await expect(page.locator('#cinema-error')).toBeHidden();
});

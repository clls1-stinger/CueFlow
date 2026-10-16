import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { parseSrt } from '../src/subtitles.js';
const fixture = name => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
async function select(page, name = 'Evening walk.wav') {
  await page.locator('#video-file').setInputFiles(fixture(name));
  await page.locator('#subtitle-file').setInputFiles(fixture('Evening walk.srt'));
  await expect(page.locator('#status')).toBeHidden({ timeout: 90000 });
  await expect(page.locator('#error')).toBeHidden();
}
test('real WASM decode, WebRTC VAD, multilingual alignment and UTF-8 download without uploads', async ({ page }) => {
  const uploads = [], errors = [];
  page.on('request', r => { if (!['GET','HEAD'].includes(r.method())) uploads.push(r.url()); });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/'); await select(page);
  await page.locator('#sync').click();
  await expect(page.locator('#result')).toBeVisible({ timeout: 90000 });
  const offset = Number((await page.locator('#offset-result').textContent()).replace(' s',''));
  expect(Math.abs(offset + 2)).toBeLessThan(.3);
  const pending = page.waitForEvent('download'); await page.locator('#download').click(); const download = await pending;
  const output = parseSrt(await readFile(await download.path(), 'utf8'));
  const source = parseSrt(await readFile(fixture('Evening walk.srt'), 'utf8'));
  expect(output.map(x=>x.text)).toEqual(source.map(x=>x.text)); expect(uploads).toEqual([]); expect(errors).toEqual([]);
  await page.screenshot({path:'test-results/result-desktop.png',fullPage:true});
  await page.locator('#reset').click(); await expect(page.locator('#sync')).toBeDisabled();
});
test('silent audio yields a useful error and no download', async ({ page }) => {
  await page.goto('/'); await select(page,'silence.wav'); await page.locator('#sync').click();
  await expect(page.locator('#error')).toBeVisible({timeout:90000}); await expect(page.locator('#error-message')).toContainText('voz'); await expect(page.locator('#result')).toBeHidden();
});
test('invalid SRT is rejected before analysis', async ({ page }) => {
  await page.goto('/'); await select(page);
  await page.locator('#subtitle-file').setInputFiles({name:'invalid.srt',mimeType:'text/plain',buffer:Buffer.from('Not subtitles')});
  await page.locator('#sync').click(); await expect(page.locator('#error-message')).toContainText('formato');
});
test('mobile, English, GitHub link, keyboard and no horizontal overflow', async ({page}) => {
  await page.setViewportSize({width:390,height:844}); await page.goto('/');
  await expect(page.locator('h1')).toContainText('Tus subtítulos');
  await expect(page.locator('nav a')).toHaveAttribute('href','https://github.com/clls1-stinger/CueFlow');
  await page.screenshot({path:'test-results/mobile-es.png',fullPage:true});
  await page.locator('#language').click(); await expect(page.locator('h1')).toContainText('Your subtitles');
  await page.reload(); await expect(page.locator('html')).toHaveAttribute('lang','en');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.locator('#video-file').focus(); await expect(page.locator('#video-file')).toBeFocused();
  await page.screenshot({path:'test-results/mobile-en.png',fullPage:true});
});
test('cancellation terminates preparation and permits retry', async ({page}) => {
  await page.goto('/'); await page.locator('#video-file').setInputFiles(fixture('Evening walk.wav'));
  await page.locator('#cancel').click(); await expect(page.locator('#status')).toBeHidden(); await expect(page.locator('#notice')).toContainText('cancelado');
  await page.locator('#subtitle-file').setInputFiles(fixture('Evening walk.srt')); await page.locator('#sync').click();
  await expect(page.locator('#result')).toBeVisible({timeout:90000});
});
test('selects the second audio track when the first is silent', async ({page}) => {
  await page.goto('/'); await select(page,'Two tracks.mka');
  await expect(page.locator('#audio-track option')).toHaveCount(2);
  await page.locator('#audio-track').selectOption('1'); await page.locator('#sync').click();
  await expect(page.locator('#result')).toBeVisible({timeout:90000});
  expect(Math.abs(Number((await page.locator('#offset-result').textContent()).replace(' s',''))+2)).toBeLessThan(.3);
});
test('desktop downloads expose real platform builds and hardware suggestions', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('.download-option')).toHaveCount(4);
  for (const link of await page.locator('.download-option').all()) {
    await expect(link).toHaveAttribute('href', /github\.com\/clls1-stinger\/CueFlow\/releases\/download\/v1\.1\.0\/CueFlow-1\.1\.0-/);
    await expect(link.locator('img')).toHaveAttribute('alt','CueFlow');
  }
  await page.locator('.recommendations summary').click(); await expect(page.locator('.spec-list')).toContainText('4 GB');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.locator('#offline').screenshot({path:'test-results/downloads-mobile.png'});
});
test('Android PWA caches the engine and completes a fresh sync while fully offline', async ({page,context}) => {
  await page.goto('/');
  const manifest = await (await page.request.get('/manifest.webmanifest')).json();
  expect(manifest.display).toBe('standalone'); expect(manifest.icons.some(i=>i.sizes==='512x512')).toBeTruthy();
  await page.locator('#install-app').click(); await expect(page.locator('#pwa-status')).toContainText('Chrome');
  await page.locator('#prepare-offline').click(); await expect(page.locator('#pwa-status')).toContainText('Modo offline listo',{timeout:90000});
  await context.setOffline(true);
  await page.reload(); await expect(page.locator('h1')).toBeVisible();
  await select(page); await page.locator('#sync').click(); await expect(page.locator('#result')).toBeVisible({timeout:90000});
  const pending=page.waitForEvent('download');await page.locator('#download').click();const download=await pending;
  expect(parseSrt(await readFile(await download.path(),'utf8'))).toHaveLength(10);
  await context.setOffline(false);
});

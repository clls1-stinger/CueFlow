import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = new URL('../', import.meta.url);
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1100, height: 1050 }, locale: 'es-MX' });
const frames = new URL('../test-results/demo/', import.meta.url); await mkdir(frames, { recursive: true });
const shot = n => page.screenshot({ path: fileURLToPath(new URL(`${n}.png`, frames)) });
try {
  await page.goto(process.env.CUEFLOW_URL || 'http://127.0.0.1:4173');
  await shot('01');
  await page.screenshot({ path: fileURLToPath(new URL('public/social.png', root)) });
  await page.locator('#video-file').setInputFiles(fileURLToPath(new URL('tests/fixtures/Two tracks.mka', root)));
  await page.locator('#subtitle-file').setInputFiles(fileURLToPath(new URL('tests/fixtures/Evening walk.srt', root)));
  await page.locator('#status').waitFor({ state: 'hidden', timeout: 90000 });
  await page.locator('#audio-track').selectOption('1'); await shot('02');
  await page.locator('#sync').click();
  await page.locator('#result').waitFor({ state: 'visible', timeout: 90000 }); await shot('03');
  await page.locator('#language').click(); await shot('04');
} finally { await browser.close(); }

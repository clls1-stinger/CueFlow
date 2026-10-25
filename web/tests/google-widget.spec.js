import { readFile } from 'node:fs/promises';
import { test, expect } from '@playwright/test';

const widgetSource = await readFile(new URL('../public/google-translate.js', import.meta.url), 'utf8');
const parentSource = await readFile(new URL('../src/google.js', import.meta.url), 'utf8');
const stylesheet = await readFile(new URL('../src/style.css', import.meta.url), 'utf8');
const widgetURL = 'https://cueflow-widget.test/google-translate.html';
const endpoint = 'https://translate.googleapis.com/widget-test';

// Exercise the real adapter and browser DOM. Only the third-party widget and its
// response are simulated, so these tests do not depend on Google's availability.
async function openWidget(page, texts, { translations = [], fail = false, noRequest = false, corruptMarkup = false } = {}) {
  await page.route(widgetURL, route => route.fulfill({ contentType: 'text/html', body: '<div id="google_translate_element"></div><main id="dialogue"></main><script src="/google-translate.js"></script>' }));
  await page.route('**/google-translate.js', route => route.fulfill({ contentType: 'text/javascript', body: widgetSource }));
  await page.route(endpoint, route => fail ? route.abort('failed') : route.fulfill({ contentType: 'application/json', body: JSON.stringify(translations), headers: { 'Access-Control-Allow-Origin': '*' } }));
  await page.route('https://translate.google.com/translate_a/element.js?*', route => route.fulfill({ contentType: 'text/javascript', body: `
    window.google = { translate: { TranslateElement: function () {
      const select = document.createElement('select'); select.className = 'goog-te-combo';
      select.append(new Option('Select', ''), new Option('Spanish', 'es'));
      document.getElementById('google_translate_element').append(select);
      select.addEventListener('change', () => {
        document.documentElement.classList.add('translated-ltr');
        if (${noRequest}) return;
        const request = new XMLHttpRequest(); request.open('GET', ${JSON.stringify(endpoint)});
        request.addEventListener('load', () => {
          if (request.status !== 200) return;
          const translations = JSON.parse(request.responseText);
          document.querySelectorAll('.cf-text').forEach((part, index) => {
            if (typeof translations[index] !== 'string') return;
            const font = document.createElement('font'); font.textContent = translations[index]; part.replaceChildren(font);
          });
          if (${corruptMarkup}) document.querySelector('.notranslate').textContent = '<b>';
        });
        request.send();
      });
    } } }; window.googleTranslateElementInit();
  ` }));
  await page.goto(widgetURL);
  await page.evaluate(texts => window.cueflowStart({ texts, source: 'en', target: 'es', ui: 'es' }), texts);
}

async function result(page) {
  await expect.poll(() => page.evaluate(() => window.cueflowResult), { timeout: 10000 }).not.toBeNull();
  return page.evaluate(() => window.cueflowResult);
}

test('Google widget completes a full batch, including names and numbers unchanged by translation', async ({ page }) => {
  const texts = ['Alice', '12345', 'Tokyo', ...Array.from({ length: 17 }, (_, i) => `Good morning, guest ${i}.`)];
  const translations = ['Alice', '12345', 'Tokio', ...Array.from({ length: 17 }, (_, i) => `Buenos días, huésped ${i}.`)];
  await openWidget(page, texts, { translations });
  expect(await result(page)).toEqual({ translations });
});

test('Google widget preserves line breaks and subtitle markup as inert text', async ({ page }) => {
  await openWidget(page, ['<i>Hello.</i>\n{\\an8}Goodbye.\\N[br]<script>window.injected=1</script>'], { translations: ['Hola.', 'Adiós.', 'window.injected=1'] });
  expect(await result(page)).toEqual({ translations: ['<i>Hola.</i>\n{\\an8}Adiós.\\N[br]<script>window.injected=1</script>'] });
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  expect(await page.locator('#dialogue script').count()).toBe(0);
});

test('Google widget reports a network failure without returning original text', async ({ page }) => {
  await openWidget(page, ['Hello.', 'Alice', '12345'], { fail: true });
  expect(await result(page)).toEqual({ error: 'googleUnavailable' });
});

test('Google widget does not mistake the translated page class for a response', async ({ page }) => {
  await page.clock.install();
  await openWidget(page, ['Hello.', 'Alice'], { noRequest: true });
  await expect(page.locator('html')).toHaveClass(/translated-ltr/);
  await page.clock.fastForward(5000);
  expect(await page.evaluate(() => window.cueflowResult)).toBeNull();
  await page.clock.fastForward(90001);
  expect(await result(page)).toEqual({ error: 'googleTimeout' });
});

test('Google widget rejects a partial response instead of returning mixed languages', async ({ page }) => {
  await page.clock.install();
  await openWidget(page, ['Hello.', 'Goodbye.'], { translations: ['Hola.'] });
  await expect(page.locator('.cf-text font')).toHaveCount(1);
  await page.clock.fastForward(5000);
  expect(await page.evaluate(() => window.cueflowResult)).toBeNull();
  await page.clock.fastForward(90001);
  expect(await result(page)).toEqual({ error: 'googleTimeout' });
});

test('Google widget rejects changed protected markup', async ({ page }) => {
  await openWidget(page, ['<i>Hello.</i>'], { translations: ['Hola.'], corruptMarkup: true });
  expect(await result(page)).toEqual({ error: 'translationInvalid' });
});

for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
  test(`Google widget stays visible while scrolling at ${viewport.width}px and disappears on cancel`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.route('https://cueflow-widget.test/long-page', route => route.fulfill({ contentType: 'text/html', body: '<link rel="stylesheet" href="/style.css"><div style="height:2200px"></div><div id="container"></div><div style="height:2200px"></div><script type="module" src="/parent.js"></script>' }));
    await page.route('**/style.css', route => route.fulfill({ contentType: 'text/css', body: stylesheet }));
    await page.route('**/parent.js', route => route.fulfill({ contentType: 'text/javascript', body: parentSource + '\nwindow.googleTranslate = googleTranslate;' }));
    await page.route(widgetURL, route => route.fulfill({ contentType: 'text/html', body: '<p>Google Translate</p><script>parent.postMessage({type:"cueflow-google-ready"}, "*");</script>' }));
    await page.goto('https://cueflow-widget.test/long-page');
    await page.evaluate(() => {
      window.translationAbort = new AbortController();
      window.googleTranslate(['Hello.'], 'en', 'es', 'es', document.getElementById('container'), window.translationAbort.signal).catch(() => {});
    });
    const frame = page.locator('.google-frame');
    await expect(frame).toBeInViewport({ ratio: 1 });
    await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
    await expect(frame).toBeInViewport({ ratio: 1 });
    await page.evaluate(() => scrollTo(0, 0));
    await expect(frame).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.evaluate(() => window.translationAbort.abort());
    await expect(frame).toHaveCount(0);
  });
}

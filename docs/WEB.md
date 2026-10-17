# CueFlow Web / CueFlow en el navegador

**Live / En línea:** https://cueflow.enriquepl.com/

**Source / Código:** https://github.com/clls1-stinger/CueFlow/tree/main/web

## Use it / Cómo usarlo

Choose a local video or audio file and its SRT. If the media has several audio tracks,
choose the one you will listen to. Press **Sync subtitles**, then download the result.
The original files are never modified. Subtitle text, line breaks and formatting tags
are preserved; only timestamps and sequential cue numbers change.

Elige un video o audio de tu dispositivo y su SRT. Si contiene varias pistas, elige
la que vas a escuchar. Pulsa **Sincronizar subtítulos** y descarga el resultado.
Los originales permanecen intactos. Se conservan el texto, los saltos de línea y las
etiquetas de formato; cambian los tiempos y la numeración secuencial.

The interface is in English and Spanish. Synchronization uses speech timing, so audio
and subtitle languages need not match. Track names come from container metadata, not
language recognition. Synchronization does not translate or generate subtitles. The separate Translate & edit tool uses Google Translate after consent. See [TRANSLATION.md](TRANSLATION.md).

La interfaz está en español e inglés. La sincronización compara tiempos de voz, por
lo que el audio y el SRT pueden estar en idiomas distintos. Los nombres de las pistas
proceden del archivo; no se reconoce automáticamente el idioma hablado.

## Privacy and limits / Privacidad y límites

- Media, subtitle contents and filenames stay in the browser. There is no upload API,
  analytics script, account or API key requirement. Ordinary page requests reach
  Cloudflare; your language preference may be stored in localStorage.
- The engine downloads on first use: approximately 32 MB. Browser caching can reuse it.
- The web UI accepts media up to **2 GiB**, **4 hours**, and SRTs up to **10 MiB / 20,000 cues**.
  These are application ceilings, not a guarantee that every device can process that size.
  Use the [desktop app](https://github.com/clls1-stinger/CueFlow/releases/latest) for larger
  files, limited-memory devices or unsupported codecs.
- Modern browsers with WebAssembly, module Workers and secure contexts are required.
  Chromium is covered by end-to-end CI. Other browsers are not covered by that CI.
- UTF-8 and UTF-16 BOMs are detected. For legacy subtitle files, choose the encoding in
  Options. Invalid Unicode triggers an error rather than silently replacing characters.
  Unlike desktop, the web edition does not repair mojibake or automatically detect legacy encodings.
- Processing can be cancelled. Decoding has a ten-minute timeout; a job has a fifteen-minute
  watchdog. Closing the tab loses the result unless you have downloaded it.
- Review dialogue near the start, middle and end. Different cuts, dubs, long music passages,
  sparse dialogue or discontinuous timing errors can prevent a useful global alignment.

El navegador procesa los archivos localmente. El límite de la web es 2 GiB y 4 horas;
la memoria del dispositivo puede imponer un límite menor. La primera carga descarga
el motor. Si el SRT usa una codificación antigua, selecciónala en Opciones. Comprueba
el resultado en varios puntos: la herramienta no corrige por separado escenas añadidas
o eliminadas. Para archivos grandes o incompatibles, usa escritorio.

## Offline downloads and Android

The page includes CueFlow icons and direct release downloads for Windows x64,
macOS Apple Silicon, macOS Intel and Linux x64. Suggested desktop hardware is a
64-bit dual-core processor, 4 GB RAM (8 GB for long movies or multitasking), and
1 GB free for the app and temporary files, in addition to media storage. These
are practical recommendations, not measured minimum hardware requirements.

**Android is an installable PWA**, using the browser engine. Open the site in an
updated Chrome for Android, choose **Install on Android**, then **Prepare offline
mode** while connected. If the browser does not offer an automatic prompt, use
Chrome's menu and choose Install app or Add to Home screen. This distribution uses
browser installation rather than a standalone APK or a Play Store listing.

The offline action saves the app shell, audio engine and VAD assets on the device.
Only public application assets are cached, never your selected media or subtitles.
A fresh reload and complete sync are tested with Chromium's network disabled.
No physical Android device compatibility or performance certification is claimed.

Suggested phone hardware: 4 GB RAM or more and at least 100 MB free for application
assets. Start with short clips; available browser memory varies, so use desktop for
large movies. Android and the browser may evict offline caches under storage pressure.
Reopen the site online and prepare offline mode again if that happens.

**Android usa una PWA instalable.** Abre la web en Chrome, instala CueFlow y prepara
el modo offline con conexión una vez. Después puedes abrir la app y sincronizar sin
internet. Se recomienda empezar con archivos pequeños; para películas largas usa
escritorio. Las cifras de memoria y espacio son sugerencias, no mínimos medidos.

The service worker caches a versioned shell on installation. The engine is cached
only after the explicit offline action. New versions activate after existing CueFlow
tabs close, and old caches are removed. Updating the app may require downloading the
engine again. The health API and external download links are never cached.

## Architecture

`web/` is a Vite application with plain JavaScript and CSS. Its design follows the
existing desktop system and [Refero reference lock](WEB_DESIGN.md).

1. FFmpeg WebAssembly reads the local `File` through `WORKERFS`, without copying the
   whole movie into the virtual filesystem. ffprobe reads duration and audio metadata.
2. The selected track is decoded to 8 kHz mono signed PCM. The FFmpeg worker is terminated
   after extraction to release its memory before alignment.
3. A separate browser Worker runs libfvad (WebRTC VAD) on 20 ms frames and correlates
   speech activity with subtitle activity using FFT. It searches a bounded offset and
   common frame-rate ratios, then refines small drift around the best ratio.
4. Invalid output bounds and weak matches are rejected. Accepted timings are applied to
   the original text and offered as a local UTF-8 Blob download.

This is a JavaScript alignment implementation, not ffsubsync running in the browser;
it can produce different timing results from desktop. The correlation threshold is a
heuristic, not a calibrated confidence measure or a word-level accuracy guarantee.

The FFmpeg WASM binary exceeds Cloudflare Pages' 25 MiB per-file limit. The build splits
it into four chunks smaller than that limit and creates a SHA-256 manifest. The browser
checks and joins those chunks before loading the engine. All assets come from the same
origin; no runtime CDN or external model service is needed.

Cloudflare **Pages** serves the frontend. Its advanced-mode **Pages Function runs on
Workers** for `/api/health` and `/download`. There is no separate paid processing backend.
`_routes.json` keeps ordinary static requests outside the Worker. The health endpoint
reports the exact source commit. The Worker only accepts GET and HEAD requests.

Official references: [FFmpeg browser API](https://ffmpegwasm.netlify.app/docs/api/ffmpeg/classes/ffmpeg/),
[Pages file limits](https://developers.cloudflare.com/pages/platform/limits/),
[Pages advanced mode](https://developers.cloudflare.com/pages/functions/advanced-mode/).

## Build and test

Use Node.js 22 or newer and FFmpeg for the synthetic multitrack test fixture:

```sh
cd web
npm ci
npm test
npm run build
npm run fixtures
npx playwright install --with-deps chromium
npm run test:e2e
npm run preview
```

For development, run `npm run build` once to prepare the engine files, then `npm run dev`.
On NixOS, point `CHROMIUM_PATH` at a working system Chromium executable for Playwright.
Set `CUEFLOW_URL=https://cueflow.enriquepl.com` to run the browser checks against production.
All committed test assets are generated from original synthetic audio; no film or third-party
subtitle content is included in the repository.

## Deployment and rollback

Project: `cueflow`. Pages hostname: `cueflow-dhh.pages.dev`.
Custom domain: `cueflow.enriquepl.com` (proxied CNAME to the Pages hostname).

`.github/workflows/web.yml` installs locked dependencies, runs calculation and browser tests,
builds the frontend and Worker, then deploys only pushes to `main` or manual runs on `main`.
Pull requests run checks without receiving deployment credentials.

GitHub Actions uses the encrypted `CLOUDFLARE_API_TOKEN` secret and the
`CLOUDFLARE_ACCOUNT_ID` repository variable. No credentials belong in source control.
For manual deployment, supply those variables through a credential manager and run:

```sh
cd web
npm ci
npm run build
npm run deploy
```

After deployment, check `/api/health` for the expected commit and run the real browser
synchronization test against the public domain. To roll back, select a previously successful
production deployment in Cloudflare Pages, or revert the relevant Git commit and push `main`.
The desktop release workflow is separate and remains available for desktop source changes.

## Licenses

CueFlow's own code is MIT. The browser engine `@ffmpeg/core` 0.12.10 is GPL-2.0-or-later,
which is distinct from the minimal LGPL FFmpeg build shipped with the desktop app.
The website distributes the engine separately and links its license, exact upstream
source revision and build instructions. Keep the license notices when redistributing.

- [FFmpeg WASM source/build, revision 71aa99d](https://github.com/ffmpegwasm/ffmpeg.wasm/tree/71aa99d37c02a7b4c435275ca9ef50e612f6efa1)
- [libfvad-wasm source](https://github.com/OzymandiasTheGreat/libfvad-wasm) (BSD-3-Clause)
- [fft.js](https://github.com/indutny/fft.js) (MIT)
- [Website license notices](https://cueflow.enriquepl.com/licenses.html)

## Google translation and local editing / Google y edición local

Open `/#translate` for Google translation, a cue editor and six-format conversion.
Translation uses Google’s Website Translator widget directly in the browser, after
consent. It sends dialogue text to Google. It requires internet in the PWA too.
Editing/conversion stays local, and there is no server translation API or API key.
See [the complete flow and privacy details](TRANSLATION.md).

Abre `/#translate` para traducir con Google, editar o convertir. Google recibe el texto
solo al aceptar la traducción. Editar y convertir funciona sin conexión.

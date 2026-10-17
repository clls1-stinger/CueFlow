# Google subtitle translation / Traducción de subtítulos con Google

CueFlow 1.2 uses the public **Google Website Translator widget**, the same translation
mechanism observed on [Subtitles Translator](https://subtitlestranslator.com/en/).
The implementation is independent. No code, branding, assets, private upload endpoint
or server-side file storage from that site is used.

CueFlow 1.2 usa el **widget público de Google Translate**, el mismo mecanismo observado
en Subtitles Translator. El código del editor, los lectores de formatos y la integración
son propios. No se envían archivos al sitio de referencia.

## Workflow

Files are parsed locally. After consent, up to 20 cue texts / 6,000 characters are placed
in a dedicated browser document. The widget translates that document. Original timestamps,
filenames and media stay outside it. Formatting tokens and line breaks are marked as
non-translatable. CueFlow waits for translated DOM nodes to settle and validates the
protected fragments before replacing a batch. An incomplete batch leaves the previous
text intact. Cancel stops the current browser frame; finished batches remain available
for review, download or retry until the session is closed.

The public web app runs Google's script on the alternate CueFlow hosting origin,
separate from the main page holding local file inputs. It validates the message source
and origin. The desktop app uses a visible Qt WebEngine window with a separate,
non-persistent browser profile. Google's attribution remains visible during translation.
The offline audio engine never loads Google's script.

Los archivos se leen localmente. Con tu consentimiento, Google traduce bloques de texto
en una vista separada. CueFlow conserva los tiempos y valida las etiquetas antes de
aplicar el resultado. Si un bloque falla, puedes reintentar; los bloques completados se
conservan durante la sesión. Descarga el resultado antes de cerrar.

## Formats and precision

| Format | Reading / Escritura | Notes / Notas |
| --- | --- | --- |
| SRT | Read and write / Lectura y escritura | Millisecond timestamps; UTF-8 output |
| VTT | Read and write | Keep headers, cue IDs, settings, notes, STYLE and REGION on same-format export |
| ASS | Read and write | Keep styles, event fields and override tags on same-format export; hundredths |
| SBV | Read and write | YouTube timed text; milliseconds |
| SUB | Read and write | SubViewer, not MicroDVD; hundredths |
| STL | Read and write | Spruce text, not binary EBU; select 24, 25 or 30 fps before importing |

Conversion between different formats preserves dialogue and timing at the target
format's precision, and simplifies formatting/positioning. Unsupported files are rejected.
Source encoding can be selected before import. Output uses UTF-8. The batch limit is
20 files and 1 MB combined, with at most 20,000 cues per document.

Convertir simplifica los estilos y las posiciones. ASS/SUB redondean a centésimas;
STL redondea al fotograma. Revisa el resultado si necesitas conservar maquetación compleja.

## Languages, availability and privacy

The selector snapshot contains **249 language options** from the live widget on
2026-10-17 UTC. Google decides which options are available at runtime. There is automatic
source detection, but detection and translation can be inaccurate, particularly for
short dialogue, names, dialects and low-resource languages. The English/Spanish interface
is independent of the subtitle languages. No “all languages” or translation-quality
guarantee is made.

Translation requires internet and loads third-party Google scripts after consent.
Google receives subtitle text and ordinary web metadata such as IP address and browser
information, and may set cookies. Its [privacy policy](https://policies.google.com/privacy)
applies. CueFlow does not collect translated text on its server. There is no CueFlow
translation API, provider key, Makima integration, transcription or audio dubbing.

El selector contiene 249 opciones observadas en Google; su disponibilidad puede cambiar.
Traducir requiere internet y envía el texto a Google. La sincronización, edición y
conversión siguen siendo locales. No se usa Makima ni un proveedor adicional de traducción. No requiere claves de API.

The Website Translator widget is an external dependency, not a paid Google Cloud
Translation API integration or a service-level guarantee. Google changes, network
failures, content blockers or throttling can stop a batch. CueFlow reports the failure
and keeps completed work. It does not rotate proxies, bypass CAPTCHA, or silently
substitute another translation provider. The Android version remains an installable PWA.

## Public research

Observed reference flow: choose up to 20 files / 1 MB, select language, translate,
edit start/end/text, then export. Public `/en/translate.php` loads
`translate.google.com/translate_a/element.js` and creates a `google.translate.TranslateElement`.
Its page script reads translated DOM text back into cue objects. CueFlow independently
implements that interaction with local parsing, protected formatting, validation,
explicit consent, cancellation and a dedicated translation document.

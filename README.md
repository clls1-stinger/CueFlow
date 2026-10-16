<p align="center"><img src="docs/assets/cueflow.png" width="96" alt="CueFlow"></p>

# CueFlow

**Right words. Right moment. / Cada frase, a su tiempo.**

A desktop app that synchronizes an existing SRT with the voices in a video.
Runs locally, without uploading your movie, transcribing it or requiring an API key.

Una aplicación de escritorio que sincroniza un SRT existente con las voces de un video.
Funciona localmente, sin subir la película, transcribirla ni pedir claves de API.

[Download / Descargar](https://github.com/clls1-stinger/CueFlow/releases/latest) ·
[English](#english) · [Español](#español) · [Build from source](docs/BUILDING.md)

![Actual CueFlow interface: select files, synchronize and view the result in English and Spanish](docs/assets/demo.gif)

The GIF records the actual application using an original synthetic audio fixture.
El GIF muestra la aplicación real con un audio sintético de prueba creado para este proyecto.

## English

### What it does

Give CueFlow a video and its SRT. It detects when people are speaking, compares those
intervals with the subtitle timings and finds a time shift and playback-speed correction.
This fixes subtitles that start too early or late, as well as timing drift caused by
common frame-rate differences.

CueFlow is a graphical interface around [ffsubsync](https://github.com/smacke/ffsubsync),
the engine that performs the alignment. [FFmpeg](https://ffmpeg.org/) reads the audio,
and WebRTC VAD detects speech. CueFlow adds English and Spanish controls, drag and drop,
encoding options, cancellation, input validation and safe output naming.

It uses speech timing rather than the meaning of words, so the video and subtitles can
be in different languages. It does not translate, generate subtitles, edit the video or
guarantee word-perfect alignment. Review a scene near the start, middle and end.

### Download and run

Open [Releases](https://github.com/clls1-stinger/CueFlow/releases/latest) and choose your platform.
Release automation publishes the downloads only after all four builds and their tests pass.

| Platform | File | How to open |
| --- | --- | --- |
| Windows 10/11, x64 | `CueFlow-1.0.0-windows-x64.zip` | Extract the whole ZIP; run `CueFlow.exe`. |
| macOS 12+, Apple Silicon | `CueFlow-1.0.0-macos-arm64.zip` | Extract and open `CueFlow.app`. |
| macOS 12+, Intel | `CueFlow-1.0.0-macos-x64.zip` | Extract and open `CueFlow.app`. |
| Linux x64, Ubuntu 22.04+ or compatible | `CueFlow-1.0.0-linux-x64.tar.gz` | Extract; run `./CueFlow/CueFlow`. |

The downloads include Python, the application libraries, FFmpeg and ffprobe. Keep the
extracted folder together. Linux still needs a graphical desktop and standard OpenGL,
font and X11/Wayland libraries; see [building and troubleshooting](docs/BUILDING.md).
NixOS users can run from source using the included `shell.nix`.

These initial builds are unsigned and macOS builds are not notarized. Your OS may ask
you to approve opening a downloaded app. On macOS, use Privacy & Security → Open Anyway
if you trust the downloaded release. Android, iOS, Windows ARM and Linux ARM binaries
are not included in this release. Source availability is not a promise of support for every OS.

### Use it

1. Choose or drop your video and `.srt` file.
2. Choose where to save the result. The video folder is selected by default.
3. Click **Synchronize subtitles**.
4. Open the output folder and load the new SRT in your player.

The result is named `video.synced.srt`. If that name exists, CueFlow creates
`video.synced.1.srt`, then `.2.srt`, and so on. Neither input is overwritten.
If your player needs an exact filename match, select the subtitle manually or rename
the result after checking that you will not replace another file.

Advanced options let you choose a subtitle encoding, disable encoding repair, disable
speed correction or change the maximum shift (default: five minutes).
Encoding repair uses `ftfy.fix_encoding`; it does not paraphrase or translate dialogue.
All output is UTF-8. Unsupported or malformed input produces an error rather than a
partially parsed subtitle file.

### What to expect

- Best results: matching editions with a fixed delay or uniform timing drift.
- Uses the first audio track. For another language or commentary track, remux the desired track first.
- Music, sparse speech, unrelated subtitles or different movie cuts can produce poor alignment.
- Missing scenes and multiple discontinuities may need manual editing. This release applies one global transform.
- No confidence percentage is claimed. The reported shift and scale describe the applied correction.
- Processing time depends on duration, codec and hardware. No transcription service is used.

## Español

### Qué hace

Elige un video y su SRT. CueFlow detecta los intervalos en los que hay voces, los compara
con los tiempos del subtítulo y calcula un desplazamiento y una corrección de velocidad.
Así puede corregir subtítulos adelantados, atrasados o que se desajustan progresivamente
por diferencias de fotogramas por segundo.

El motor de sincronización es [ffsubsync](https://github.com/smacke/ffsubsync).
[FFmpeg](https://ffmpeg.org/) lee el audio y WebRTC VAD detecta las voces.
CueFlow añade una interfaz en español e inglés, arrastrar y soltar, opciones de
codificación, cancelación, validación de archivos y guardado sin sobrescribir.

Compara los tiempos de las voces, no el significado de las palabras. El video y los
subtítulos pueden estar en idiomas diferentes. No traduce, genera subtítulos ni modifica
el video. Tampoco garantiza precisión palabra por palabra: revisa una escena al inicio,
a la mitad y al final.

### Descargar y abrir

Entra en [Releases](https://github.com/clls1-stinger/CueFlow/releases/latest) y descarga
el archivo para tu equipo. La publicación automática espera a que las cuatro compilaciones
y sus pruebas terminen correctamente.

| Sistema | Archivo | Cómo abrirlo |
| --- | --- | --- |
| Windows 10/11, x64 | `CueFlow-1.0.0-windows-x64.zip` | Extrae todo el ZIP y ejecuta `CueFlow.exe`. |
| macOS 12+, Apple Silicon | `CueFlow-1.0.0-macos-arm64.zip` | Extrae y abre `CueFlow.app`. |
| macOS 12+, Intel | `CueFlow-1.0.0-macos-x64.zip` | Extrae y abre `CueFlow.app`. |
| Linux x64, Ubuntu 22.04+ o compatible | `CueFlow-1.0.0-linux-x64.tar.gz` | Extrae y ejecuta `./CueFlow/CueFlow`. |

Las descargas incluyen Python, las bibliotecas, FFmpeg y ffprobe. Conserva completa la
carpeta extraída. Linux requiere un escritorio gráfico y sus bibliotecas habituales;
consulta [compilación y solución de problemas](docs/BUILDING.md). En NixOS puedes usar
el código fuente con el archivo `shell.nix` incluido.

Las primeras compilaciones no tienen firma de editor y las de macOS no están notarizadas.
El sistema puede pedirte que autorices abrir la aplicación descargada. En macOS puedes
usar Privacidad y seguridad → Abrir igualmente si confías en la descarga. Esta versión
no incluye binarios para Android, iOS, Windows ARM ni Linux ARM.

### Cómo usarla

1. Selecciona o arrastra el video y el archivo `.srt`.
2. Elige la carpeta de destino. Por defecto se usa la del video.
3. Pulsa **Sincronizar subtítulos**.
4. Abre la carpeta del resultado y carga el nuevo SRT en tu reproductor.

El resultado se llama `video.synced.srt`. Si ya existe, se guarda como
`video.synced.1.srt`, después `.2.srt`, etc. Los originales se conservan.
Si tu reproductor exige que los nombres coincidan exactamente, selecciona el subtítulo
manualmente o renómbralo después de comprobar que no reemplazará otro archivo.

En las opciones avanzadas puedes elegir la codificación, desactivar su reparación,
desactivar la corrección de velocidad o cambiar el desfase máximo, que por defecto es
de cinco minutos. La reparación usa `ftfy.fix_encoding` y no reescribe ni traduce los
diálogos. El resultado se guarda en UTF-8.

### Límites

- Funciona mejor con la misma edición del video y un desfase fijo o progresivo uniforme.
- Usa la primera pista de audio. Si quieres otra, prepara un archivo con esa pista primero.
- La música, pocas voces, subtítulos ajenos o cortes diferentes pueden empeorar el resultado.
- Las escenas eliminadas y varios saltos de tiempo pueden requerir edición manual.
- No muestra un porcentaje de precisión: el desfase y el factor indican la corrección aplicada.
- El tiempo depende de la duración, el códec y el equipo. No se usan servicios de transcripción.

## Development / Desarrollo

```bash
uv sync --frozen --python 3.12 --extra dev
uv run python -m cueflow
```

Source runs need `ffmpeg` and `ffprobe` on `PATH` or a build in `vendor/ffmpeg`.
Para ejecutar el código fuente necesitas `ffmpeg` y `ffprobe` en el `PATH` o compilados
en `vendor/ffmpeg`.

See [BUILDING.md](docs/BUILDING.md) for tests, native packaging and release instructions.
Consulta [BUILDING.md](docs/BUILDING.md) para las pruebas, compilación y publicación.

## Credits and license / Créditos y licencia

CueFlow's code is MIT licensed. It builds on ffsubsync, FFmpeg, WebRTC VAD, PySide6,
NumPy, srt, ftfy and other open-source projects. They retain their own licenses.
See [THIRD_PARTY.md](THIRD_PARTY.md) and the bundled license notices.

El código de CueFlow usa la licencia MIT. Sus dependencias conservan sus propias
licencias. Consulta [THIRD_PARTY.md](THIRD_PARTY.md) y los avisos incluidos.

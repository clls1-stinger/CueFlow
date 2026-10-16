## English

CueFlow 1.1.0 makes multilingual subtitle synchronization easier to use:

- Choose any embedded audio track, including a different dubbed language. Track titles
  and language tags come from the media file; CueFlow does not guess the spoken language.
- Sync audio and SRT files in different languages using local speech timing. No
  translation, transcription, uploads or API keys are required.
- Read UTF-32 automatically and choose additional legacy encodings for Japanese,
  Chinese, Korean, Cyrillic, Arabic, Hebrew, Thai, Greek, Turkish and Vietnamese text.
- Preserve multilingual dialogue, formatting and input files. Results remain UTF-8 SRT.
- Read the expanded English/Spanish README, subtitle-sync FAQ and command-line examples.

Choose the archive for your operating system and processor. Extract the whole archive
before opening the app. FFmpeg, ffprobe and Python are included. These builds are
unsigned; macOS builds are not notarized. See the README for opening instructions.

Each download passes source tests and a frozen-app test that selects the second audio
track, aligns synthetic speech-like audio and preserves multilingual subtitle text.
These tests verify functionality; they do not measure accuracy across all spoken languages.
Check the adjacent `.sha256` file to verify your download. The FFmpeg source archive is
provided for license compliance; it is not the desktop app.

## Español

CueFlow 1.1.0 facilita la sincronización de subtítulos en distintos idiomas:

- Elige cualquier pista de audio, incluido otro doblaje. Los títulos e idiomas se leen
  de las etiquetas del archivo; CueFlow no adivina el idioma hablado.
- Sincroniza audio y SRT en idiomas diferentes mediante los tiempos de las voces.
  No requiere traducción, transcripción, subir archivos ni claves de API.
- Detecta UTF-32 y permite elegir más codificaciones para texto japonés, chino, coreano,
  cirílico, árabe, hebreo, tailandés, griego, turco y vietnamita.
- Conserva los diálogos, su formato y los archivos originales. El resultado es un SRT UTF-8.
- Incluye un README ampliado en español e inglés, preguntas frecuentes y ejemplos de consola.

Elige el paquete de tu sistema y procesador. Extrae todo el contenido antes de abrir la
aplicación. Incluye FFmpeg, ffprobe y Python. Las compilaciones no tienen firma de editor
y las de macOS no están notarizadas. Consulta las instrucciones del README.

Cada descarga supera pruebas del código y del ejecutable: selección de la segunda pista,
ajuste de audio sintético y conservación de texto multilingüe. Estas pruebas verifican el
funcionamiento; no miden la precisión con todos los idiomas hablados. El archivo `.sha256`
permite comprobar la descarga. El código fuente de FFmpeg se incluye por su licencia.

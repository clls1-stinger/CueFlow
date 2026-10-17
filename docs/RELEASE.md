## English

CueFlow 1.2.0 adds Google subtitle translation, a local editor and six-format conversion.

- Translate with Google's public Website Translator widget, without API keys or an LLM gateway.
- Choose from 249 language options captured from Google; availability is checked during translation.
- Load up to 20 files / 1 MB: SRT, VTT, ASS, SBV, SubViewer SUB and text Spruce STL.
- Keep timestamps and formatting markers, review original and translated dialogue, edit times/text, and export one file or a ZIP.
- Cancel and resume batches without losing completed work in the current session.
- Synchronization, editing and conversion work offline. Translation requires internet and consent to send text to Google.

Choose your OS and processor, extract the entire archive, and open CueFlow. The app
includes Python, FFmpeg, ffprobe and Qt WebEngine. Builds are unsigned; macOS builds
are not notarized. The browser runtime makes downloads larger than 1.1.0. See the
README and BUILDING guide for system libraries and installation help.

The release pipeline tests native synchronization and the packaged browser runtime.
The Google widget is an external service and can change or become unavailable. No
accuracy guarantee across all languages is made. Check the adjacent SHA-256 file.

## Español

CueFlow 1.2.0 añade traducción con Google, editor local y conversión de seis formatos.

- Traduce con el widget público de Google Translate, sin claves de API ni Makima.
- Elige entre 249 opciones de idioma observadas en Google; se comprueba su disponibilidad al traducir.
- Abre hasta 20 archivos / 1 MB: SRT, VTT, ASS, SBV, SubViewer SUB y Spruce STL de texto.
- Conserva los tiempos y etiquetas, compara el original con la traducción, edita los diálogos y descarga un archivo o ZIP.
- Cancela y continúa sin perder los bloques terminados durante la sesión.
- Sincronizar, editar y convertir funciona sin conexión. Traducir requiere internet y aceptar enviar el texto a Google.

Extrae el paquete completo correspondiente a tu sistema. Incluye Python, FFmpeg,
ffprobe y Qt WebEngine. Las compilaciones no tienen firma de editor y macOS no está
notarizado. El navegador integrado aumenta el tamaño respecto a 1.1.0. Google puede
cambiar o interrumpir su widget; revisa las traducciones antes de usarlas.

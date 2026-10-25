# Películas y subtítulos temporales

La pestaña Películas consulta StreamIMDB, permite elegir una película, la versión de subtítulos y una calidad de hasta 480p o 720p. La reproducción empieza por segmentos mientras Oracle descarga el video. Después ejecuta el mismo motor de sincronización de la aplicación de escritorio y genera un MP4 con una pista de subtítulos seleccionable. También entrega SRT y VTT sincronizados. Los subtítulos se alinean con la actividad de voz del audio; conviene revisar algunos diálogos al principio y al final.

La búsqueda incluye los idiomas que devuelva OpenSubtitles y los subtítulos anunciados por el reproductor. Cuando falta un idioma, el usuario puede traducir una versión encontrada con Google, con consentimiento explícito. La traducción empieza con los subtítulos disponibles y muestra cada tanda terminada. Al completarse la sincronización, se aplican los tiempos verificados a todos los diálogos traducidos antes de generar el MP4. Los lotes ya traducidos se conservan en la pestaña para reintentar un fallo. Su disponibilidad y calidad dependen del idioma y del proveedor. La descarga completa y el análisis pueden tardar varios minutos; no bloquean el inicio de la reproducción. La traducción necesita la pestaña y el panel de Google visibles: una pestaña oculta o el video en pantalla completa pueden pausarla.

## Inicio rápido y sincronización

El servidor comparte una caché de segmentos entre reproducción, muestras de audio y descarga completa. Las solicitudes de reproducción tienen prioridad sobre los trabajos de fondo. El límite de cuatro descargas simultáneas se comparte entre todas las sesiones; los reintentos esperan fuera de ese límite. Adelantar el video solicita el segmento correspondiente sin esperar a los anteriores.

Se intenta un ajuste preliminar con una muestra de unos 120 segundos de diálogo. El resultado debe concordar entre tres regiones y superar comprobaciones de voz y contraste. Si la muestra no aporta evidencia suficiente, se conservan los subtítulos originales con el aviso de sincronización pendiente. Un ajuste preliminar no confirma la escala temporal de toda la película. El motor completo sigue siendo la verificación final.

La interfaz distingue subtítulos originales, ajuste preliminar y sincronización verificada. La descarga del MP4 queda disponible al terminar el procesamiento. Un reproductor que ya está usando HLS conserva su fuente durante ese cambio, para no interrumpirlo. Tras reiniciar el servicio, las sesiones completas se reproducen desde el MP4.

## Almacenamiento y enlaces

Cada preparación recibe un identificador aleatorio de 256 bits. El enlace de reproducción contiene ese identificador en el fragmento del navegador. Quien tenga el enlace puede abrir esa sesión: no debe compartirse como enlace privado entre cuentas.

- Borrado tras una hora sin actividad; el navegador renueva la actividad mientras se usa la pestaña o se reproduce el video.
- Caducidad máxima de seis horas, incluso con actividad.
- Limpieza cada 30 segundos y al arrancar el servicio. Los trabajos interrumpidos se descartan al reiniciar.
- Cancelar o borrar una sesión detiene sus procesos y elimina sus archivos.
- Hasta dos trabajos simultáneos, seis sesiones y 12 GiB de almacenamiento temporal. Cada descarga tiene un límite de 2 GiB y cuatro horas; se reservan al menos 6 GiB libres.
- No se guardan películas en el service worker. Las respuestas de sesiones y archivos usan `private, no-store`. Las descargas que el usuario guarde en su equipo permanecen allí.

El MP4 soporta peticiones Range. Los manifiestos HLS contienen únicamente rutas de la propia sesión; los segmentos conservan la misma caducidad que el MP4. El enlace permanente de una película es `/#movie/<slug>`; un enlace `/#watch/<token>/<slug>` recupera la sesión mientras exista y vuelve a ofrecer la película cuando caduque.

## Fuente y límites

El adaptador interpreta las fichas públicas y las peticiones que realiza el reproductor. No ejecuta sus anuncios ni su JavaScript en Oracle. Solo permite hosts explícitos, comprueba direcciones públicas y redirecciones, limita respuestas y descarga los segmentos por separado. FFmpeg recibe un manifiesto local que no puede abrir recursos de red. No hay endpoint para descargar una URL arbitraria.

Se admiten listas HLS VOD con segmentos MPEG-TS. Las listas con claves, rangos de bytes, mapas de inicialización u otros formatos no admitidos producen un error visible. El adaptador requiere que la API devuelva enlaces de stream como una lista; no resuelve retos de acceso. Si el proveedor cambia su contrato, debe actualizarse el adaptador con evidencia nueva.

La investigación se realizó sobre el reproductor de Cutie Honey: Tears, TMDB `436022`, IMDb `tt5520970`. Se verificaron la búsqueda, metadatos, manifiesto de 5,535.572 segundos y descarga de segmentos. REA 6.8.0 analizó el módulo de transporte: evidencia `ev_ab6f0f6969f481822e1be475139648b03cdb9fb2ff3773357a6d57ed288655eb`. El análisis completo del reproductor agotó su límite de 60 segundos; se redujo el alcance al módulo pertinente. Las observaciones estáticas y las peticiones reales se contrastaron por separado.

## Operación

El backend usa `server/compose.yaml` en Oracle y la red existente `vegacore_vega-net`. No publica un puerto del host. El túnel de Oracle dirige `cueflow-api.enriquepl.com` a `http://cueflow-cinema:8080`; Pages reenvía exclusivamente `/api/cinema/*` a ese dominio. El resto de CueFlow conserva la sincronización local.

Construcción y arranque, desde la raíz del repositorio:

```sh
export CUEFLOW_COMMIT="$(git rev-parse HEAD)"
docker compose -f server/compose.yaml build
docker compose -f server/compose.yaml up -d
```

`CUEFLOW_IDLE_SECONDS` y `CUEFLOW_MAX_AGE_SECONDS` permiten cambiar la retención. El volumen `cueflow-media` contiene únicamente datos temporales. El contenedor usa un usuario sin privilegios, raíz de solo lectura, dos CPU y 3 GiB de memoria. Uvicorn no registra URLs de acceso porque contienen los identificadores de sesión.

Comprueba `/api/cinema/health`, el commit anunciado, una búsqueda real y la reproducción antes de dar por terminado un despliegue. Para revertir, vuelve a la imagen anterior y al despliegue anterior de Pages; conserva el volumen para que se aplique la caducidad. No cambies las otras rutas del túnel de Oracle.

## Verificación

```sh
python -m pytest server/tests -q
cd web
npm test
npm run build
npm run test:e2e
```

Las pruebas del servidor incluyen una película sintética que recorre HLS local, sincronización real, conservación del texto y pista de subtítulos en MP4; también cubren caducidad tras reinicio, cancelación, enlaces, Range y rechazo de destinos ajenos. Las pruebas de interfaz cubren selección, idiomas, descarga, recuperación de sesión, caducidad y móvil, además de reproducción HLS y búsqueda de un punto del video antes de terminar el MP4. Comprueban también traducción progresiva, conservación de los tiempos finales y visibilidad del panel de Google. La película de referencia produjo 639 diálogos traducidos en 105.373 segundos, con sus tiempos y marcas de formato intactos; esta medición depende del proveedor y no constituye una garantía de latencia. El proveedor de las pruebas automáticas es simulado para que no dependan de una película ajena.

Story Vega: `f4189c54-8cba-420d-87d0-fcdb83f0bf6e`.

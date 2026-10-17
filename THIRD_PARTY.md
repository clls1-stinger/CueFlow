# Third-party software

CueFlow is an independent graphical frontend. It does not claim authorship of its
synchronization algorithm or affiliation with the projects below.

| Component | Purpose | License / source |
| --- | --- | --- |
| ffsubsync 0.5.1 | Speech timing alignment | MIT · https://github.com/smacke/ffsubsync |
| FFmpeg 8.1.3 | Audio decoding and probing | LGPL 2.1 or later for the included configuration · https://ffmpeg.org/ |
| PySide6 / Qt 6.8.3 | Desktop interface | LGPLv3 / GPL / commercial options · https://www.qt.io/qt-for-python |
| WebRTC VAD / webrtcvad-wheels | Speech activity detection | BSD-style · https://github.com/daanzu/py-webrtcvad-wheels |
| NumPy | Numerical alignment | BSD-3-Clause · https://numpy.org/ |
| srt | SRT parsing and writing | MIT · https://github.com/cdown/srt |
| ftfy | Encoding repair | MIT · https://github.com/rspeer/python-ftfy |
| psutil | Cancelling subprocess trees | BSD-3-Clause · https://github.com/giampaolo/psutil |
| PyInstaller | Application freezing | GPL with distribution exception · https://pyinstaller.org/ |

The dependency versions are locked in `uv.lock`. Release archives include distribution
license files and a dependency manifest under `_internal/licenses` (inside the application
bundle on macOS). The MIT license applies only to CueFlow's own code.

FFmpeg is built from the unmodified official `ffmpeg-8.1.3.tar.xz`, SHA-256
`7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3`.
The release includes that corresponding source archive. The exact configuration and
build commands are in `scripts/build_ffmpeg.sh`. The build disables GPL, nonfree,
network and external optional components; FFmpeg runs as a separate executable.
Its LGPL notice is included beside the binaries.

The Qt and PySide libraries are dynamically bundled and may be replaced by compatible
modified libraries. The one-directory package does not intentionally prevent that
replacement or reverse engineering for debugging modifications to LGPL components.
Matching upstream source archives are available from
[Qt's 6.8.3 archive](https://download.qt.io/archive/qt/6.8/6.8.3/) and
[PySide's 6.8.3 archive](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/).
Build instructions are maintained by [Qt for Python](https://doc.qt.io/qtforpython-6/building_from_source/index.html).

No user media or third-party movie subtitles are distributed. Demo audio and captions
are generated from the original fixture in `cueflow/smoke.py`.

## Español

CueFlow es una interfaz independiente. La sincronización la realiza ffsubsync; FFmpeg
lee el audio y WebRTC VAD detecta las voces. Los proyectos citados conservan su autoría
y sus licencias. La licencia MIT de CueFlow no sustituye las de sus dependencias.

Las descargas incluyen los avisos de licencia y permiten reemplazar las bibliotecas
dinámicas de Qt por versiones compatibles modificadas. El código fuente correspondiente
de FFmpeg se adjunta a la publicación; su compilación está descrita en
`scripts/build_ffmpeg.sh`. El repositorio no distribuye películas ni subtítulos de terceros.

## Google Website Translator and Qt WebEngine

Translation loads Google's public Website Translator widget only after user consent.
It is an external service, not code licensed or redistributed under CueFlow's MIT license.
Google retains its branding and policies: https://policies.google.com/privacy.
The desktop build includes Qt WebEngine and Chromium through PySide6. Their license
notices are included in the dependency bundle.

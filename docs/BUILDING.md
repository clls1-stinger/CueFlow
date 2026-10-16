# Building CueFlow / Compilar CueFlow

## English

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). The lockfile records exact dependencies.

```bash
uv sync --frozen --python 3.12 --extra dev
uv run python -m cueflow
```

For a source run, install FFmpeg and ffprobe in the same directory on `PATH`.
Alternatively, point `CUEFLOW_FFMPEG_DIR` at a directory containing both binaries.
On NixOS, enter `nix-shell` first to supply the Qt runtime libraries.

### Tests

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q
uv run ruff check cueflow tests scripts
```

On PowerShell, set `$env:QT_QPA_PLATFORM = "offscreen"` and run `uv run pytest -q`.
Tests cover a real synthetic-audio alignment, the GUI-to-worker flow, multilingual
text preservation, encoding choices, silence rejection, malformed SRTs and output collisions.

### Native builds

Build on the target OS. PyInstaller does not cross-compile Windows, macOS and Linux apps.
The GitHub Actions matrix builds Windows x64, Linux x64, macOS ARM64 and macOS x64.
It tests the source and frozen executable before uploading each artifact.

```bash
bash scripts/build_ffmpeg.sh
uv run python scripts/collect_licenses.py
uv run pyinstaller --noconfirm --clean CueFlow.spec
./dist/CueFlow/CueFlow --self-test
uv run python scripts/package.py
```

On Windows, build FFmpeg in an MSYS2 MINGW64 shell with GCC, make, diffutils, tar,
xz and curl. Run the Python commands in your normal shell and use
`dist/CueFlow/CueFlow.exe --self-test`. The workflow contains the complete setup.
macOS builds produce a `.app` and retain a command-line copy for the smoke test.

Linux builds use Ubuntu 22.04 as the baseline. Required system packages include
`libgl1`, `libegl1`, `libxkbcommon0`, `libdbus-1-3`, `libxcb-cursor0`, `libfontconfig1`
and the ordinary libraries installed by a graphical desktop. These are runtime OS
dependencies, not bundled Python modules. For headless tests, use the offscreen Qt platform.

The included Dockerfile builds and tests a Linux archive on that baseline:

```bash
docker build -t cueflow-build .
docker create --name cueflow-artifacts cueflow-build
docker cp cueflow-artifacts:/app/dist ./release-dist
docker rm cueflow-artifacts
```

### Publish

After all checks pass, push a version tag matching `pyproject.toml` and `scripts/package.py`:

```bash
git tag v1.0.0
git push origin main v1.0.0
```

The release job waits for every matrix build, then publishes all archives, SHA-256
files and the exact FFmpeg source archive to the tagged GitHub Release. The workflow
uses GitHub's repository-scoped token; no private API key belongs in the repository.

### Demo assets

```bash
uv run python scripts/make_icon.py
QT_QPA_PLATFORM=offscreen uv run python scripts/record_demo.py
```

The recording drives the actual application with generated fixtures. It does not show
a simulated success state. The timeline at the top of the window is a schematic logo
element, not a visualization of the user's audio.

## Español

Usa Python 3.12 y `uv`. Ejecuta `uv sync --frozen --python 3.12 --extra dev` y después
`uv run python -m cueflow`. Para el código fuente necesitas FFmpeg y ffprobe en el
`PATH`, o puedes indicar su carpeta con `CUEFLOW_FFMPEG_DIR`. En NixOS entra primero
en `nix-shell`.

Las pruebas se ejecutan con `QT_QPA_PLATFORM=offscreen uv run pytest -q`. En PowerShell,
define `$env:QT_QPA_PLATFORM = "offscreen"` antes de ejecutar `uv run pytest -q`.

Cada aplicación se compila en su propio sistema: PyInstaller no compila para Windows
o macOS desde Linux. GitHub Actions realiza las cuatro compilaciones, ejecuta las pruebas
y abre cada binario en modo de comprobación antes de preparar los archivos descargables.
Los comandos de compilación, el entorno MSYS2 de Windows y las bibliotecas necesarias
en Linux están descritos arriba y en `.github/workflows/build.yml`.

Para publicar, sube `main` y una etiqueta como `v1.0.0`. El trabajo de publicación espera
a que todas las plataformas pasen sus pruebas. Después adjunta los paquetes, sus sumas
SHA-256 y el código fuente exacto de FFmpeg a GitHub Releases.

El GIF se graba con `scripts/record_demo.py`: usa la aplicación real y archivos de prueba
originales. No necesita ni incorpora películas o subtítulos aportados por usuarios.

from pathlib import Path
import sys

root = Path(SPECPATH)
suffix = '.exe' if sys.platform == 'win32' else ''
binaries = [(str(root / 'vendor' / 'ffmpeg' / (name + suffix)), 'vendor/ffmpeg')
            for name in ('ffmpeg', 'ffprobe')]
datas = [(str(root / 'build/licenses'), 'licenses'),
         (str(root / 'docs/assets/cueflow.png'), 'docs/assets'),
         (str(root / 'LICENSE'), '.'),
         (str(root / 'cueflow/google_languages.json'), 'cueflow'),
         (str(root / 'THIRD_PARTY.md'), '.'),
         (str(root / 'vendor/ffmpeg/COPYING.LGPLv2.1'), 'vendor/ffmpeg')]
a = Analysis(['launcher.py'], pathex=[str(root)], binaries=binaries, datas=datas,
             hookspath=[str(root / 'scripts/hooks')],
             hiddenimports=['_webrtcvad', 'charset_normalizer.md'],
             excludes=['tkinter', 'pytest', 'PIL'], noarchive=False)
pyz = PYZ(a.pure)
# Console bootloader preserves worker stdio on Windows. Hide the parent console at launch.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CueFlow', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True,
          icon=str(root / 'docs/assets/cueflow.ico') if sys.platform == 'win32' else None,
          contents_directory='_internal')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CueFlow')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='CueFlow.app', icon=str(root / 'docs/assets/cueflow.icns'),
                 bundle_identifier='com.cueflow.desktop',
                 info_plist={'NSHighResolutionCapable': True,
                             'CFBundleShortVersionString': '1.3.0',
                             'LSMinimumSystemVersion': '12.0'})

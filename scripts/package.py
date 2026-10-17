"""Create an OS-specific archive and a checksum after testing the frozen app."""

import hashlib
import platform
import shutil
import sys
from pathlib import Path

system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
name = f"CueFlow-1.2.0-{system}-{arch}"
base = Path("dist")
if system == "macos":
    import subprocess

    archive = base / f"{name}.zip"
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(base / "CueFlow.app"),
            str(archive),
        ],
        check=True,
    )
else:
    extension = "zip" if system == "windows" else "gztar"
    archive = Path(
        shutil.make_archive(str(base / name), extension, root_dir=base, base_dir="CueFlow")
    )
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
print(archive)

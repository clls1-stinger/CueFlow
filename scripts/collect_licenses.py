"""Collect distribution license files without including project paths or credentials."""

import importlib.metadata
import json
from pathlib import Path

root = Path("build/licenses")
root.mkdir(parents=True, exist_ok=True)
manifest = []
for dist in importlib.metadata.distributions():
    name = dist.metadata["Name"]
    if name.lower() == "cueflow":
        continue
    manifest.append(
        {
            "name": name,
            "version": dist.version,
            "source": f"https://pypi.org/project/{name}/{dist.version}/#files",
        }
    )
    for file in dist.files or []:
        if any(part.lower().startswith(("license", "copying", "notice")) for part in file.parts):
            path = Path(dist.locate_file(file))
            if path.is_file() and path.stat().st_size < 2_000_000:
                output = root / name / Path(*file.parts[-2:])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(path.read_bytes())
(root / "DEPENDENCIES.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

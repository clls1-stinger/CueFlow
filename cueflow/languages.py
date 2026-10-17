"""Language choices captured from the public Google Translate widget."""
import json
from importlib.resources import files


def languages():
    return json.loads(files("cueflow").joinpath("google_languages.json").read_text(encoding="utf-8"))

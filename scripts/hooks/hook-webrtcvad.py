"""ffsubsync uses webrtcvad-wheels, whose import name remains webrtcvad."""

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("webrtcvad-wheels")
hiddenimports = ["_webrtcvad"]

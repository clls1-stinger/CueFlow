"""Draw the app's original two-track cue mark, without external artwork."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path("docs/assets")
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGBA", (1024, 1024), (8, 9, 10, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((100, 100, 924, 924), radius=180, fill="#141516", outline="#34343a", width=8)
for y, offset, color in [(350, 90, "#737984"), (550, 0, "#ff4700")]:
    for start, width in [(210, 190), (450, 120), (620, 100)]:
        draw.rounded_rectangle(
            (start + offset, y, start + offset + width, y + 100), radius=22, fill=color
        )
image.save(root / "cueflow.png")
image.save(
    root / "cueflow.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
)
image.save(root / "cueflow.icns")

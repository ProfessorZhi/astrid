from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image


ASCII_RAMP = " .,:;irsXA253hMHGS#9B&@"


@dataclass(slots=True)
class ImportedPet:
    name: str
    source: str
    ansi_sprite: str
    ascii_sprite: str


def _load_image(source: str) -> Image.Image:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        with urlopen(source, timeout=15) as response:  # noqa: S310
            data = response.read()
        image = Image.open(BytesIO(data))
    else:
        image = Image.open(Path(source))
    return image.convert("RGBA")


def _trim_transparency(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        return image.crop(bbox)
    return image


def _resize_image(image: Image.Image, width: int = 20, height: int = 14) -> Image.Image:
    trimmed = _trim_transparency(image)
    resized = trimmed.copy()
    resized.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    offset_x = max(0, (width - resized.width) // 2)
    offset_y = max(0, (height - resized.height) // 2)
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas


def _rgb_to_ansi(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _render_ansi(image: Image.Image) -> str:
    rows: list[str] = []
    for y in range(image.height):
        row_parts: list[str] = []
        for x in range(image.width):
            r, g, b, a = image.getpixel((x, y))
            if a < 48:
                row_parts.append("  ")
                continue
            row_parts.append(f"{_rgb_to_ansi(r, g, b)}██\x1b[0m")
        rows.append("".join(row_parts).rstrip())
    return "\n".join(rows).rstrip()


def _render_ascii(image: Image.Image) -> str:
    rows: list[str] = []
    for y in range(image.height):
        chars: list[str] = []
        for x in range(image.width):
            r, g, b, a = image.getpixel((x, y))
            if a < 48:
                chars.append(" ")
                continue
            luminance = int((0.2126 * r) + (0.7152 * g) + (0.0722 * b))
            index = int((luminance / 255) * (len(ASCII_RAMP) - 1))
            chars.append(ASCII_RAMP[index])
        rows.append("".join(chars).rstrip())
    return "\n".join(rows).rstrip()


def import_pet_sprite(source: str, *, width: int = 20, height: int = 14) -> ImportedPet:
    image = _resize_image(_load_image(source), width=width, height=height)
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        name = Path(parsed.path).stem or "imported-pet"
    else:
        name = Path(source).stem or "imported-pet"
    return ImportedPet(
        name=name,
        source=source,
        ansi_sprite=_render_ansi(image),
        ascii_sprite=_render_ascii(image),
    )

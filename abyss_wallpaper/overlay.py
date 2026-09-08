"""Compose an unobtrusive metadata panel onto a wallpaper image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from abyss_wallpaper.config import OverlayConfig
from abyss_wallpaper.models import Discovery

_FONT_CANDIDATES = (
    "DejaVuSans.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def compose_overlay(
    image_path: Path,
    discovery: Discovery,
    output_path: Path,
    overlay: OverlayConfig,
) -> Path:
    image = Image.open(image_path).convert("RGBA")
    if not overlay.enabled:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(output_path, format="JPEG", quality=92)
        return output_path

    lines = _overlay_lines(discovery)
    panel = _render_panel(image.size, lines, overlay)
    composed = Image.alpha_composite(image, panel)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_path, format="JPEG", quality=92)
    return output_path


def _overlay_lines(discovery: Discovery) -> list[str]:
    lines = [discovery.display_title()]
    facts: list[str] = []
    if discovery.depth_m is not None:
        facts.append(f"{discovery.depth_m:,.0f} m")
    if discovery.coordinates is not None:
        facts.append(discovery.coordinates.format())
    if facts:
        lines.append(" · ".join(facts))
    source_bits = [discovery.source_name]
    if discovery.published is not None:
        source_bits.append(discovery.published.date().isoformat())
    lines.append(" · ".join(source_bits))
    if discovery.attribution:
        lines.append(discovery.attribution)
    return lines


FontT = ImageFont.FreeTypeFont | ImageFont.ImageFont


def _font(size: int, bold: bool = False) -> FontT:
    names: tuple[str, ...] = _FONT_CANDIDATES
    if bold:
        names = ("DejaVuSans-Bold.ttf", *_FONT_CANDIDATES)
    for candidate in names:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: FontT, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _render_panel(
    size: tuple[int, int],
    lines: list[str],
    overlay: OverlayConfig,
) -> Image.Image:
    width, height = size
    max_width = max(280, int(width * overlay.max_width_ratio))
    title_font = _font(max(18, width // 70), bold=True)
    body_font = _font(max(14, width // 90))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    wrapped: list[tuple[str, FontT]] = []
    inner_width = max_width - overlay.padding * 2
    for index, line in enumerate(lines):
        font = title_font if index == 0 else body_font
        wrapped.extend((part, font) for part in _wrap(draw, line, font, inner_width))
    line_gap = 8
    text_height = 0.0
    for text, font in wrapped:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_height += (bbox[3] - bbox[1]) + line_gap
    panel_w = max_width
    panel_h = int(text_height + overlay.padding * 2 - line_gap)
    left, top = _corner_origin(overlay.corner, width, height, panel_w, panel_h, overlay.margin)
    opacity = max(0, min(255, overlay.opacity))
    draw.rounded_rectangle(
        (left, top, left + panel_w, top + panel_h),
        radius=18,
        fill=(8, 16, 28, opacity),
    )
    y = float(top + overlay.padding)
    for text, font in wrapped:
        draw.text((left + overlay.padding, y), text, font=font, fill=(236, 242, 248, 235))
        bbox = draw.textbbox((0, 0), text, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return canvas


def _corner_origin(
    corner: str, width: int, height: int, panel_w: int, panel_h: int, margin: int
) -> tuple[int, int]:
    key = corner.replace("_", "-").lower()
    if key == "top-left":
        return margin, margin
    if key == "top-right":
        return width - panel_w - margin, margin
    if key == "bottom-right":
        return width - panel_w - margin, height - panel_h - margin
    return margin, height - panel_h - margin

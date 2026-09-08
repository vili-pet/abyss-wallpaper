"""Offline fixture source so the tool can run without the network."""

from __future__ import annotations

import json
from importlib import resources
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import HttpClient
from abyss_wallpaper.metadata import parse_coordinates, parse_datetime, stable_id
from abyss_wallpaper.models import Coordinates, Discovery
from abyss_wallpaper.sources.base import source_name


class FixtureSource:
    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.id = config.id
        self.name = source_name(config, "Local fixture")
        self.fallback_only = bool(config.extra.get("fallback_only", True))

    def fetch(self, client: HttpClient, limit: int) -> list[Discovery]:
        records = _load_records(self.config)
        discoveries: list[Discovery] = []
        for record in records[:limit]:
            discoveries.append(_record_to_discovery(record, self.id, self.name))
        return discoveries


def generate_placeholder_image(title: str, width: int = 1920, height: int = 1080) -> bytes:
    """A dark gradient with a simple glass-sponge silhouette — no third-party assets."""
    image = Image.new("RGB", (width, height), (4, 10, 22))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        tone = int(8 + (y / height) * 46)
        for x in range(width):
            drift = int((x / width) * 18)
            pixels[x, y] = (4 + drift // 3, 12 + tone // 4, 28 + tone)
    draw = ImageDraw.Draw(image)
    cx, base = width // 2, int(height * 0.82)
    draw.ellipse((cx - 220, base - 40, cx + 320, base + 70), fill=(18, 28, 36))
    draw.line((cx, int(height * 0.28), cx, base), fill=(168, 196, 206), width=10)
    draw.ellipse((cx - 90, int(height * 0.18), cx + 130, int(height * 0.42)), fill=(186, 206, 214))
    for offset in (-70, -20, 40, 90):
        draw.ellipse(
            (cx + offset - 28, int(height * 0.22), cx + offset + 36, int(height * 0.34)),
            fill=(150, 176, 188),
        )
    draw.text((48, height - 64), title[:60], fill=(210, 224, 230))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


def _as_records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _load_records(config: SourceConfig) -> list[dict[str, Any]]:
    explicit = config.extra.get("path")
    if explicit:
        return _as_records(json.loads(Path(str(explicit)).read_text(encoding="utf-8")))
    data = resources.files("abyss_wallpaper.data").joinpath("sample_discoveries.json")
    return _as_records(json.loads(data.read_text(encoding="utf-8")))


def _record_to_discovery(record: dict[str, Any], source_id: str, source_name: str) -> Discovery:
    coords = record.get("coordinates")
    coordinates = None
    if isinstance(coords, dict):
        lat = _as_number(coords.get("latitude"))
        lon = _as_number(coords.get("longitude"))
        if lat is not None and lon is not None:
            coordinates = Coordinates(lat, lon)
    else:
        lat = _as_number(record.get("latitude"))
        lon = _as_number(record.get("longitude"))
        if lat is not None and lon is not None:
            coordinates = parse_coordinates(f"{lat}, {lon}") or Coordinates(lat, lon)
    image_url = str(record.get("image_url") or "generated://abyss/default")
    return Discovery(
        id=str(record.get("id") or stable_id(source_id, str(record.get("title")))),
        source_id=source_id,
        source_name=source_name,
        title=str(record.get("title") or "Sample discovery"),
        page_url=str(record.get("page_url") or ""),
        image_url=image_url,
        published=parse_datetime(str(record.get("published") or "")),
        depth_m=_as_number(record.get("depth_m")),
        coordinates=coordinates,
        attribution=str(record.get("attribution") or "Locally generated sample illustration."),
        summary=str(record.get("summary") or ""),
        extras={"generated": image_url.startswith("generated://")},
    )

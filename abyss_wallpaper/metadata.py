"""Extract depth, coordinates, dates, and image preference from free text."""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from abyss_wallpaper.models import Coordinates, Discovery

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_DEPTH_RE = re.compile(
    r"""
    (?:at\s+a\s+depth\s+of\s+|depth(?:s)?(?:\s+of)?\s+|approximately\s+)?
    (?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,5}(?:\.\d+)?)
    \s*(?P<unit>meters?|metres?|m(?![a-z])|feet|ft)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
_COORD_RE = re.compile(
    r"""
    (?P<lat>-?\d{1,2}(?:\.\d+)?)
    \s*[, ]\s*
    (?P<lon>-?\d{1,3}(?:\.\d+)?)
    """,
    re.VERBOSE,
)
_COORD_HEM_RE = re.compile(
    r"""
    (?P<lat>\d{1,2}(?:\.\d+)?)\s*°?\s*(?P<lat_hem>[NSns])
    \s*[, ]\s*
    (?P<lon>\d{1,3}(?:\.\d+)?)\s*°?\s*(?P<lon_hem>[EWew])
    """,
    re.VERBOSE,
)

UNDERWATER_TERMS = (
    "abyssal",
    "benthic",
    "coral",
    "crustacean",
    "dive",
    "hydrothermal",
    "octopus",
    "rov",
    "seafloor",
    "seamount",
    "sponge",
    "squid",
    "vent",
    "wreck",
    "scicam",
    "deep-sea",
    "deep sea",
)

SURFACE_TERMS = (
    "award",
    "portrait",
    "headshot",
    "lab work",
    "control room",
    "ship_",
    "scientist sits",
    "press conference",
    "favicon",
    "logo",
    "headshot",
)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", value))
    return _WS_RE.sub(" ", text).strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_depth_m(text: str | None) -> float | None:
    if not text:
        return None
    matches = list(_DEPTH_RE.finditer(text))
    if not matches:
        return None
    # Prefer stated meters over converted feet, and skip organism-height values.
    meters_values: list[float] = []
    feet_values: list[float] = []
    for match in matches:
        number = float(match.group("value").replace(",", ""))
        unit = match.group("unit").lower()
        if unit.startswith("ft") or unit == "feet":
            meters = round(number * 0.3048, 1)
            if 20 <= meters <= 12000:
                feet_values.append(meters)
        elif 20 <= number <= 12000:
            meters_values.append(number)
    pool = meters_values or feet_values
    if not pool:
        return None
    return max(pool)


def parse_coordinates(text: str | None) -> Coordinates | None:
    if not text:
        return None
    hem = _COORD_HEM_RE.search(text)
    if hem:
        lat = float(hem.group("lat"))
        lon = float(hem.group("lon"))
        if hem.group("lat_hem").upper() == "S":
            lat = -lat
        if hem.group("lon_hem").upper() == "W":
            lon = -lon
        if _valid_coords(lat, lon):
            return Coordinates(latitude=lat, longitude=lon)
    plain = _COORD_RE.search(text)
    if plain and ("lat" in text.lower() or "coord" in text.lower() or "°" in text):
        lat = float(plain.group("lat"))
        lon = float(plain.group("lon"))
        if _valid_coords(lat, lon):
            return Coordinates(latitude=lat, longitude=lon)
    return None


def _valid_coords(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


def image_preference_score(url: str, caption: str = "", title: str = "") -> int:
    haystack = f"{url} {caption} {title}".lower()
    score = 0
    for term in UNDERWATER_TERMS:
        if term in haystack:
            score += 3
    for term in SURFACE_TERMS:
        if term in haystack:
            score -= 4
    parsed = urlparse(url)
    name = parsed.path.rsplit("/", 1)[-1].lower()
    if any(token in name for token in ("logo", "favicon", "icon", "sprite")):
        score -= 12
    if "scicam" in name or "dive" in name:
        score += 4
    return score


def discovery_score(discovery: Discovery, prefer_underwater: bool = True) -> tuple[int, float]:
    score = 0
    if discovery.image_url:
        score += 8
    if discovery.depth_m is not None:
        score += 5
    if discovery.coordinates is not None:
        score += 3
    if discovery.attribution:
        score += 1
    if discovery.width and discovery.height:
        score += 2 if discovery.width >= 1280 else 0
    if prefer_underwater:
        score += image_preference_score(discovery.image_url, discovery.summary, discovery.title)
    published = discovery.published.timestamp() if discovery.published else 0.0
    return score, published


def rank_discoveries(
    discoveries: Iterable[Discovery], prefer_underwater: bool = True
) -> list[Discovery]:
    return sorted(
        discoveries,
        key=lambda item: discovery_score(item, prefer_underwater),
        reverse=True,
    )


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def choose_largest_src(src: str | None, srcset: str | None) -> str | None:
    candidates: list[tuple[int, str]] = []
    if src:
        candidates.append((0, src.strip()))
    if srcset:
        for chunk in srcset.split(","):
            bits = chunk.strip().split()
            if not bits:
                continue
            width = 0
            if len(bits) > 1 and bits[1].endswith("w"):
                try:
                    width = int(bits[1][:-1])
                except ValueError:
                    width = 0
            candidates.append((width, bits[0]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]

"""WordPress REST media parser (used by NOAA and optional custom sources)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import HttpClient
from abyss_wallpaper.metadata import (
    parse_coordinates,
    parse_datetime,
    parse_depth_m,
    stable_id,
    strip_html,
)
from abyss_wallpaper.models import Discovery
from abyss_wallpaper.sources.base import source_attribution, source_name


class WordPressMediaSource:
    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.id = config.id
        self.name = source_name(config, "WordPress media")
        self.fallback_only = bool(config.extra.get("fallback_only", False))

    def fetch(self, client: HttpClient, limit: int) -> list[Discovery]:
        url = _media_url(self.config.url, limit)
        payload = client.get_json(url)
        if not isinstance(payload, list):
            return []
        return parse_wordpress_media(
            payload,
            source_id=self.id,
            source_name=self.name,
            attribution=source_attribution(self.config, self.name),
            limit=limit,
        )


def _media_url(base: str, limit: int) -> str:
    if "?" in base:
        return base
    query = urlencode(
        {
            "media_type": "image",
            "per_page": min(limit, 40),
            "orderby": "date",
            "order": "desc",
        }
    )
    return f"{base.rstrip('/')}?{query}"


def parse_wordpress_media(
    items: list[dict[str, Any]],
    *,
    source_id: str,
    source_name: str,
    attribution: str,
    limit: int,
) -> list[Discovery]:
    discoveries: list[Discovery] = []
    for item in items:
        discovery = _media_item(item, source_id, source_name, attribution)
        if discovery is not None:
            discoveries.append(discovery)
        if len(discoveries) >= limit:
            break
    return discoveries


def _rendered(node: Any) -> str:
    if isinstance(node, dict):
        return strip_html(str(node.get("rendered") or ""))
    return strip_html(str(node or ""))


def _media_item(
    item: dict[str, Any], source_id: str, source_name: str, attribution: str
) -> Discovery | None:
    if item.get("media_type") not in {None, "image"}:
        return None
    image_url = str(item.get("source_url") or "")
    if not image_url:
        return None
    raw_details = item.get("media_details")
    details: dict[str, Any] = raw_details if isinstance(raw_details, dict) else {}
    raw_meta = details.get("image_meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    title = _rendered(item.get("title")) or str(meta.get("title") or "") or "Untitled image"
    caption = _rendered(item.get("caption")) or str(meta.get("caption") or "")
    alt = str(item.get("alt_text") or "")
    credit = (
        str(meta.get("copyright") or "").strip()
        or str(meta.get("credit") or "").strip()
        or attribution
    )
    text = " ".join(part for part in (title, caption, alt, credit) if part)
    if any(token in image_url.lower() for token in ("favicon", "logo", "sprite")):
        return None
    raw_width = details.get("width")
    raw_height = details.get("height")
    width = raw_width if isinstance(raw_width, int) else None
    height = raw_height if isinstance(raw_height, int) else None
    return Discovery(
        id=stable_id(source_id, str(item.get("id") or image_url)),
        source_id=source_id,
        source_name=source_name,
        title=title,
        page_url=str(item.get("link") or image_url),
        image_url=image_url,
        published=parse_datetime(str(item.get("date_gmt") or item.get("date") or "")),
        depth_m=parse_depth_m(text),
        coordinates=parse_coordinates(text),
        attribution=credit,
        summary=caption[:400],
        content_type=str(item.get("mime_type") or "image/jpeg"),
        width=width,
        height=height,
    )

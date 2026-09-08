"""Generic RSS/Atom parser used by Schmidt, MBARI, and custom feeds."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import HttpClient
from abyss_wallpaper.metadata import parse_coordinates, parse_datetime, parse_depth_m, stable_id, strip_html
from abyss_wallpaper.models import Discovery
from abyss_wallpaper.sources.base import source_attribution, source_name
from abyss_wallpaper.sources.htmlutil import extract_images

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


class RssSource:
    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.id = config.id
        self.name = source_name(config, config.id)
        self.fallback_only = bool(config.extra.get("fallback_only", False))

    def fetch(self, client: HttpClient, limit: int) -> list[Discovery]:
        xml_text = client.get_text(self.config.url)
        return parse_rss(
            xml_text,
            source_id=self.id,
            source_name=self.name,
            attribution=source_attribution(self.config, self.name),
            limit=limit,
        )


def parse_rss(
    xml_text: str,
    *,
    source_id: str,
    source_name: str,
    attribution: str,
    limit: int,
) -> list[Discovery]:
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    if not items:
        items = root.findall("atom:entry", _NS)
    discoveries: list[Discovery] = []
    for item in items:
        discovery = _item_to_discovery(item, source_id, source_name, attribution)
        if discovery is not None:
            discoveries.append(discovery)
        if len(discoveries) >= limit:
            break
    return discoveries


def _child_text(item: ET.Element, *names: str) -> str:
    for name in names:
        node = item.find(name, _NS) if ":" in name else item.find(name)
        if node is not None and (node.text or "").strip():
            return (node.text or "").strip()
        if node is not None and name.endswith("encoded"):
            return "".join(node.itertext())
    return ""


def _item_to_discovery(
    item: ET.Element, source_id: str, source_name: str, attribution: str
) -> Discovery | None:
    title = strip_html(_child_text(item, "title"))
    link = _child_text(item, "link", "atom:link")
    if not link:
        atom_link = item.find("atom:link", _NS)
        if atom_link is not None:
            link = atom_link.attrib.get("href", "")
    guid = _child_text(item, "guid", "id") or link or title
    description = _child_text(item, "description", "summary")
    content = _child_text(item, "content:encoded", "content") or description
    published = _parse_item_date(item)
    images = extract_images(content, link or "https://example.invalid/")
    enclosure = item.find("enclosure")
    if enclosure is not None:
        enc_url = enclosure.attrib.get("url")
        enc_type = enclosure.attrib.get("type", "")
        if enc_url and enc_type.startswith("image/"):
            images.insert(0, (enc_url, title))
    media = item.find("media:content", _NS) or item.find("media:thumbnail", _NS)
    if media is not None and media.attrib.get("url"):
        images.insert(0, (media.attrib["url"], title))
    if not images:
        return None
    image_url, caption = _best_image(images, title, description)
    text = " ".join(part for part in (title, caption, strip_html(content)) if part)
    return Discovery(
        id=stable_id(source_id, guid, image_url),
        source_id=source_id,
        source_name=source_name,
        title=title or "Untitled discovery",
        page_url=link,
        image_url=image_url,
        published=published,
        depth_m=parse_depth_m(text),
        coordinates=parse_coordinates(text),
        attribution=_extract_credit(text, attribution),
        summary=strip_html(description)[:400],
    )


def _parse_item_date(item: ET.Element) -> datetime | None:
    return parse_datetime(_child_text(item, "pubDate", "published", "updated", "dc:date"))


def _best_image(images: list[tuple[str, str]], title: str, description: str) -> tuple[str, str]:
    from abyss_wallpaper.metadata import image_preference_score

    return max(images, key=lambda pair: image_preference_score(pair[0], pair[1], f"{title} {description}"))


def _extract_credit(text: str, fallback: str) -> str:
    lowered = text.lower()
    for marker in ("image courtesy of", "image:", "credit:", "©"):
        idx = lowered.find(marker)
        if idx != -1:
            snippet = text[idx : idx + 180].split(".")[0].strip()
            if snippet:
                return snippet
    return fallback

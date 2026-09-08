"""Nautilus Live / Ocean Exploration Trust gallery and photo albums."""

from __future__ import annotations

import re
from html import unescape

from bs4 import Tag

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import HttpClient
from abyss_wallpaper.metadata import parse_coordinates, parse_datetime, parse_depth_m, stable_id, strip_html
from abyss_wallpaper.models import Discovery
from abyss_wallpaper.sources.base import source_attribution, source_name
from abyss_wallpaper.sources.htmlutil import absolutize, parse_html, unwrap_drupal_style

_ALBUM_HREF = re.compile(r"^/album/\d{4}/\d{2}/\d{2}/")


class NautilusSource:
    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.id = config.id
        self.name = source_name(config, "Nautilus Live / Ocean Exploration Trust")
        self.fallback_only = bool(config.extra.get("fallback_only", False))

    def fetch(self, client: HttpClient, limit: int) -> list[Discovery]:
        gallery_html = client.get_text(self.config.url)
        albums = parse_gallery_albums(gallery_html, self.config.url)
        max_albums = int(self.config.extra.get("max_albums") or 3)
        discoveries: list[Discovery] = []
        for album_url, album_title, published in albums[:max_albums]:
            album_html = client.get_text(album_url)
            discoveries.extend(
                parse_album(
                    album_html,
                    album_url=album_url,
                    album_title=album_title,
                    published=published,
                    source_id=self.id,
                    source_name=self.name,
                    attribution=source_attribution(self.config, "Ocean Exploration Trust"),
                    limit=max(1, limit // max(len(albums[:max_albums]), 1)),
                )
            )
            if len(discoveries) >= limit:
                break
        return discoveries[:limit]


def parse_gallery_albums(markup: str, base: str) -> list[tuple[str, str, None]]:
    soup = parse_html(markup)
    albums: list[tuple[str, str, None]] = []
    seen: set[str] = set()
    for article in soup.select("article.node--type-album"):
        link = article.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        href = str(link.get("href") or "")
        url = absolutize(href, base)
        if not url or url in seen:
            continue
        title_node = article.select_one(".field--name-title") or link
        title = title_node.get_text(" ", strip=True)
        seen.add(url)
        albums.append((url, title, None))
    if albums:
        return albums
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        href = str(link.get("href") or "")
        if not _ALBUM_HREF.match(href):
            continue
        url = absolutize(href, base)
        if not url or url in seen:
            continue
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        seen.add(url)
        albums.append((url, title, None))
    return albums


def parse_album(
    markup: str,
    *,
    album_url: str,
    album_title: str,
    published: None,
    source_id: str,
    source_name: str,
    attribution: str,
    limit: int,
) -> list[Discovery]:
    soup = parse_html(markup)
    body = soup.select_one(".field--name-body")
    summary = body.get_text(" ", strip=True) if body else ""
    published_at = parse_datetime(_album_date_from_url(album_url))
    discoveries: list[Discovery] = []
    for anchor in soup.select("a.photoswipe"):
        if not isinstance(anchor, Tag):
            continue
        raw_url = str(anchor.get("href") or "")
        image_url = unwrap_drupal_style(raw_url)
        image_url = absolutize(image_url, album_url) or ""
        if not image_url:
            continue
        caption_html = unescape(str(anchor.get("data-overlay-title") or ""))
        caption = strip_html(caption_html)
        credit = _credit_from_overlay(caption_html) or attribution
        img = anchor.find("img")
        alt = str(img.get("alt") or "") if isinstance(img, Tag) else ""
        title = alt.title() if alt else album_title
        text = " ".join(part for part in (title, caption, summary) if part)
        discoveries.append(
            Discovery(
                id=stable_id(source_id, album_url, image_url),
                source_id=source_id,
                source_name=source_name,
                title=title or album_title,
                page_url=album_url,
                image_url=image_url,
                published=published_at,
                depth_m=parse_depth_m(text),
                coordinates=parse_coordinates(text),
                attribution=credit,
                summary=(caption or summary)[:400],
                extras={"album_title": album_title},
            )
        )
        if len(discoveries) >= limit:
            break
    return discoveries


def _album_date_from_url(url: str) -> str | None:
    match = re.search(r"/album/(\d{4})/(\d{2})/(\d{2})/", url)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}T00:00:00+00:00"


def _credit_from_overlay(caption_html: str) -> str:
    match = re.search(r'class="credit">(.*?)</div>', caption_html, re.IGNORECASE | re.DOTALL)
    if match:
        return strip_html(match.group(1))
    return ""

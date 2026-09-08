"""HTML helpers shared by RSS and gallery parsers."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from abyss_wallpaper.metadata import choose_largest_src


def parse_html(markup: str) -> BeautifulSoup:
    return BeautifulSoup(markup, "html.parser")


def unwrap_drupal_style(url: str) -> str:
    """Turn a Drupal image-style URL into the original public file when possible."""
    marker = "/styles/"
    public_marker = "/public/"
    if marker not in url or public_marker not in url:
        return url.split("?", 1)[0]
    prefix, rest = url.split(marker, 1)
    _, after_public = rest.split(public_marker, 1)
    cleaned = after_public.split("?", 1)[0].lstrip("/")
    return f"{prefix.rstrip('/')}/{cleaned}"


def absolutize(url: str | None, base: str) -> str | None:
    if not url:
        return None
    absolute = urljoin(base, url.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return absolute


def extract_images(markup: str, base: str) -> list[tuple[str, str]]:
    """Return (image_url, caption) pairs from HTML, largest srcset variant preferred."""
    soup = parse_html(markup)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        raw = choose_largest_src(
            str(img.get("src") or img.get("data-src") or ""),
            str(img.get("srcset") or img.get("data-srcset") or ""),
        )
        url = absolutize(raw, base)
        if not url or url in seen:
            continue
        caption = _nearest_caption(img)
        seen.add(url)
        found.append((url, caption))
    return found


def _nearest_caption(img: Tag) -> str:
    alt = str(img.get("alt") or "").strip()
    figure = img.find_parent("figure")
    if figure:
        figcaption = figure.find("figcaption")
        if figcaption:
            text = figcaption.get_text(" ", strip=True)
            if text:
                return text
    parent = img.find_parent()
    if parent:
        credit = parent.find(class_="credit")
        if credit:
            extra = credit.get_text(" ", strip=True)
            if extra:
                return f"{alt} {extra}".strip()
    return alt

"""MBARI news RSS."""

from __future__ import annotations

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.sources.rss import RssSource


class MbariSource(RssSource):
    def __init__(self, config: SourceConfig) -> None:
        if not config.url:
            config.url = "https://www.mbari.org/feed/"
        config.extra.setdefault("source_name", "MBARI")
        config.extra.setdefault(
            "attribution",
            "© MBARI. Personal/educational use; review MBARI terms before redistribution.",
        )
        super().__init__(config)

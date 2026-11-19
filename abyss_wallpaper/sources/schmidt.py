"""Schmidt Ocean Institute news RSS."""

from __future__ import annotations

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.sources.rss import RssSource


class SchmidtSource(RssSource):
    def __init__(self, config: SourceConfig) -> None:
        if not config.url:
            config.url = "https://schmidtocean.org/feed/"
        config.extra.setdefault("source_name", "Schmidt Ocean Institute")
        config.extra.setdefault("attribution", "Schmidt Ocean Institute.")
        super().__init__(config)

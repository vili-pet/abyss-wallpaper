"""NOAA Ocean Exploration — public WordPress media API."""

from __future__ import annotations

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.sources.wordpress import WordPressMediaSource


class NoaaSource(WordPressMediaSource):
    def __init__(self, config: SourceConfig) -> None:
        if not config.url:
            config.url = "https://oceanexplorer.noaa.gov/wp-json/wp/v2/media"
        config.extra.setdefault("source_name", "NOAA Ocean Exploration")
        config.extra.setdefault(
            "attribution",
            "Image courtesy of NOAA Ocean Exploration. Public domain U.S. government work.",
        )
        super().__init__(config)

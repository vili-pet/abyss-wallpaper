"""Configurable discovery sources."""

from __future__ import annotations

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.sources.base import Source, SourceError
from abyss_wallpaper.sources.fixture import FixtureSource
from abyss_wallpaper.sources.mbari import MbariSource
from abyss_wallpaper.sources.nautilus import NautilusSource
from abyss_wallpaper.sources.noaa import NoaaSource
from abyss_wallpaper.sources.rss import RssSource
from abyss_wallpaper.sources.schmidt import SchmidtSource
from abyss_wallpaper.sources.wordpress import WordPressMediaSource

_REGISTRY: dict[str, type] = {
    "noaa": NoaaSource,
    "nautilus": NautilusSource,
    "schmidt": SchmidtSource,
    "mbari": MbariSource,
    "rss": RssSource,
    "wordpress": WordPressMediaSource,
    "fixture": FixtureSource,
}


def build_source(config: SourceConfig) -> Source:
    try:
        cls = _REGISTRY[config.kind]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY))
        raise SourceError(f"Unknown source kind {config.kind!r}. Known: {known}") from exc
    return cls(config)  # type: ignore[no-any-return]


def enabled_sources(configs: list[SourceConfig], *, include_fallback: bool = True) -> list[Source]:
    sources: list[Source] = []
    for config in configs:
        if not config.enabled:
            continue
        source = build_source(config)
        if source.fallback_only and not include_fallback:
            continue
        sources.append(source)
    return sources


__all__ = ["Source", "SourceError", "build_source", "enabled_sources"]

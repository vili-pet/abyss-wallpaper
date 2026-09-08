"""Source adapter protocol."""

from __future__ import annotations

from typing import Protocol

from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import HttpClient
from abyss_wallpaper.models import Discovery


class Source(Protocol):
    id: str
    name: str
    fallback_only: bool

    def fetch(self, client: HttpClient, limit: int) -> list[Discovery]: ...


class SourceError(RuntimeError):
    """A source failed in a recoverable way."""


def source_name(config: SourceConfig, default: str) -> str:
    return str(config.extra.get("source_name") or default)


def source_attribution(config: SourceConfig, default: str) -> str:
    return str(config.extra.get("attribution") or default)

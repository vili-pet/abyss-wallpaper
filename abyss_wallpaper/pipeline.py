"""Fetch, cache, compose, and optionally apply a discovery wallpaper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from abyss_wallpaper.cache import ImageCache
from abyss_wallpaper.config import AppConfig
from abyss_wallpaper.http import HttpClient, HttpError, StdHttpClient
from abyss_wallpaper.metadata import rank_discoveries
from abyss_wallpaper.models import AppState, Discovery
from abyss_wallpaper.overlay import compose_overlay
from abyss_wallpaper.sources import Source, SourceError, enabled_sources
from abyss_wallpaper.sources.fixture import generate_placeholder_image
from abyss_wallpaper.state import StateStore
from abyss_wallpaper.wallpaper import PreviewWallpaperSetter, WallpaperSetter, default_setter

LOGGER = logging.getLogger("abyss_wallpaper")


@dataclass(slots=True)
class UpdateResult:
    action: str
    discovery: Discovery | None
    wallpaper_path: Path | None
    image_hash: str | None
    reason: str
    dry_run: bool
    state: AppState

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "image_hash": self.image_hash,
            "wallpaper_path": str(self.wallpaper_path) if self.wallpaper_path else None,
            "discovery": self.discovery.to_dict() if self.discovery else None,
            "state": self.state.to_dict(),
        }


class WallpaperPipeline:
    def __init__(
        self,
        config: AppConfig,
        *,
        http: HttpClient | None = None,
        store: StateStore | None = None,
        cache: ImageCache | None = None,
        setter: WallpaperSetter | None = None,
    ) -> None:
        self.config = config
        self.http = http or StdHttpClient(
            user_agent=config.user_agent,
            timeout=config.request_timeout_seconds,
            respect_robots=config.respect_robots,
            crawl_delay_seconds=config.crawl_delay_seconds,
        )
        self.store = store or StateStore(config.state_path)
        self.cache = cache or ImageCache(config.cache_dir)
        self.setter = setter or default_setter()

    def fetch_discoveries(self, source_id: str | None = None, *, offline: bool = False) -> list[Discovery]:
        sources = self._select_sources(source_id, offline=offline)
        live_sources = [source for source in sources if not source.fallback_only]
        fallback_sources = [source for source in sources if source.fallback_only]
        collected: list[Discovery] = []
        for source in live_sources:
            collected.extend(self._safe_fetch(source))
        if not collected:
            for source in fallback_sources:
                collected.extend(self._safe_fetch(source))
        return rank_discoveries(collected, self.config.prefer_underwater)

    def _safe_fetch(self, source: Source) -> list[Discovery]:
        try:
            items = source.fetch(self.http, self.config.max_discoveries_per_source)
        except (HttpError, SourceError, OSError, ValueError) as exc:
            LOGGER.warning("Source %s failed: %s", source.id, exc)
            return []
        LOGGER.info("Source %s returned %s discoveries", source.id, len(items))
        return [item for item in items if item.image_url]

    def preview(
        self,
        *,
        source_id: str | None = None,
        output: Path | None = None,
        offline: bool = False,
    ) -> UpdateResult:
        return self.update(
            source_id=source_id,
            force=True,
            dry_run=True,
            apply_wallpaper=False,
            output=output or self.config.preview_path,
            offline=offline,
        )

    def update(
        self,
        *,
        source_id: str | None = None,
        force: bool = False,
        dry_run: bool | None = None,
        apply_wallpaper: bool | None = None,
        output: Path | None = None,
        offline: bool = False,
        now: datetime | None = None,
    ) -> UpdateResult:
        dry = self.config.dry_run if dry_run is None else dry_run
        should_apply = self.config.set_wallpaper if apply_wallpaper is None else apply_wallpaper
        state = self.store.load()
        discoveries = self.fetch_discoveries(source_id, offline=offline)
        if not discoveries:
            return UpdateResult(
                action="noop",
                discovery=None,
                wallpaper_path=None,
                image_hash=None,
                reason="no discoveries with images were found",
                dry_run=dry,
                state=state,
            )
        discovery = discoveries[0]
        image_bytes, content_type = self._load_image(discovery)
        if len(image_bytes) > self.config.max_image_bytes:
            return UpdateResult(
                action="noop",
                discovery=discovery,
                wallpaper_path=None,
                image_hash=None,
                reason=f"image exceeds max_image_bytes ({len(image_bytes)} > {self.config.max_image_bytes})",
                dry_run=dry,
                state=state,
            )
        cached_path, digest = self.cache.store(discovery, image_bytes, content_type)
        composed_path = output or (self.config.composed_dir / f"{digest}.jpg")
        compose_overlay(cached_path, discovery, composed_path, self.config.overlay)
        skip_reason = self.store.should_skip(
            state,
            digest,
            timedelta(hours=self.config.update_interval_hours),
            force=force or dry or not should_apply,
            now=now,
        )
        if skip_reason:
            return UpdateResult(
                action="skipped",
                discovery=discovery,
                wallpaper_path=composed_path,
                image_hash=digest,
                reason=skip_reason,
                dry_run=dry,
                state=state,
            )
        if dry or not should_apply:
            return UpdateResult(
                action="preview" if not should_apply else "dry-run",
                discovery=discovery,
                wallpaper_path=composed_path,
                image_hash=digest,
                reason="composed locally; desktop wallpaper not changed",
                dry_run=True,
                state=state,
            )
        self.setter.set_wallpaper(composed_path)
        state = self.store.record(state, discovery, digest, composed_path, now=now or datetime.now(timezone.utc))
        return UpdateResult(
            action="applied",
            discovery=discovery,
            wallpaper_path=composed_path,
            image_hash=digest,
            reason="desktop wallpaper updated",
            dry_run=False,
            state=state,
        )

    def status(self) -> AppState:
        return self.store.load()

    def _select_sources(self, source_id: str | None, *, offline: bool) -> list[Source]:
        sources = enabled_sources(self.config.sources, include_fallback=True)
        if source_id:
            sources = [source for source in sources if source.id == source_id]
            if not sources:
                raise SourceError(f"Source {source_id!r} is not enabled")
        if offline:
            sources = [source for source in sources if source.id == "fixture" or source.fallback_only]
            if not sources:
                raise SourceError("Offline mode requires an enabled fixture source")
        return sources

    def _load_image(self, discovery: Discovery) -> tuple[bytes, str]:
        if discovery.image_url.startswith("generated://"):
            return generate_placeholder_image(discovery.display_title()), "image/jpeg"
        fetched = self.http.get_bytes(discovery.image_url)
        return fetched, discovery.content_type


def build_preview_pipeline(config: AppConfig, http: HttpClient | None = None) -> WallpaperPipeline:
    return WallpaperPipeline(config, http=http, setter=PreviewWallpaperSetter())

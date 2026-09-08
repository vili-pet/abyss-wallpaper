"""Persistent local state so the same wallpaper is not applied repeatedly."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from abyss_wallpaper.models import AppState, Discovery


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AppState()
        if not isinstance(payload, dict):
            return AppState()
        return AppState.from_dict(payload)

    def save(self, state: AppState) -> None:
        self.path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")

    def should_skip(
        self,
        state: AppState,
        image_hash: str,
        interval: timedelta,
        *,
        force: bool = False,
        now: datetime | None = None,
    ) -> str | None:
        if force:
            return None
        if state.last_image_hash == image_hash:
            return "image already applied"
        current = now or datetime.now(UTC)
        if state.last_update is not None:
            elapsed = current - state.last_update
            if elapsed < interval:
                remaining = interval - elapsed
                hours = remaining.total_seconds() / 3600
                return f"update interval not elapsed ({hours:.1f}h remaining)"
        return None

    def record(
        self,
        state: AppState,
        discovery: Discovery,
        image_hash: str,
        wallpaper_path: Path,
        *,
        now: datetime | None = None,
    ) -> AppState:
        stamp = now or datetime.now(UTC)
        entry = {
            "id": discovery.id,
            "title": discovery.display_title(),
            "source": discovery.source_name,
            "hash": image_hash,
            "applied_at": stamp.isoformat(),
        }
        history = [entry, *state.history][:20]
        updated = AppState(
            last_update=stamp,
            last_discovery_id=discovery.id,
            last_image_hash=image_hash,
            last_wallpaper_path=str(wallpaper_path),
            last_title=discovery.display_title(),
            last_source_name=discovery.source_name,
            last_page_url=discovery.page_url,
            last_attribution=discovery.attribution,
            last_depth_m=discovery.depth_m,
            last_coordinates=discovery.coordinates.format() if discovery.coordinates else None,
            history=history,
        )
        self.save(updated)
        return updated

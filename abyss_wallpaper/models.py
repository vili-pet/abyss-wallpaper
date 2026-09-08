"""Shared data models for discoveries and local application state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float

    def format(self) -> str:
        lat_hem = "N" if self.latitude >= 0 else "S"
        lon_hem = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.3f}°{lat_hem}, {abs(self.longitude):.3f}°{lon_hem}"


@dataclass(slots=True)
class Discovery:
    """A single deep-sea image plus the metadata we can recover for it."""

    id: str
    source_id: str
    source_name: str
    title: str
    page_url: str
    image_url: str
    published: datetime | None = None
    depth_m: float | None = None
    coordinates: Coordinates | None = None
    attribution: str = ""
    summary: str = ""
    content_type: str = "image/jpeg"
    width: int | None = None
    height: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def display_title(self) -> str:
        return self.title.strip() or "Untitled deep-sea discovery"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.published is not None:
            payload["published"] = self.published.isoformat()
        if self.coordinates is not None:
            payload["coordinates"] = {
                "latitude": self.coordinates.latitude,
                "longitude": self.coordinates.longitude,
                "formatted": self.coordinates.format(),
            }
        return payload


@dataclass(slots=True)
class AppState:
    last_update: datetime | None = None
    last_discovery_id: str | None = None
    last_image_hash: str | None = None
    last_wallpaper_path: str | None = None
    last_title: str | None = None
    last_source_name: str | None = None
    last_page_url: str | None = None
    last_attribution: str | None = None
    last_depth_m: float | None = None
    last_coordinates: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_discovery_id": self.last_discovery_id,
            "last_image_hash": self.last_image_hash,
            "last_wallpaper_path": self.last_wallpaper_path,
            "last_title": self.last_title,
            "last_source_name": self.last_source_name,
            "last_page_url": self.last_page_url,
            "last_attribution": self.last_attribution,
            "last_depth_m": self.last_depth_m,
            "last_coordinates": self.last_coordinates,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppState:
        raw_update = data.get("last_update")
        last_update = datetime.fromisoformat(raw_update) if raw_update else None
        return cls(
            last_update=last_update,
            last_discovery_id=data.get("last_discovery_id"),
            last_image_hash=data.get("last_image_hash"),
            last_wallpaper_path=data.get("last_wallpaper_path"),
            last_title=data.get("last_title"),
            last_source_name=data.get("last_source_name"),
            last_page_url=data.get("last_page_url"),
            last_attribution=data.get("last_attribution"),
            last_depth_m=data.get("last_depth_m"),
            last_coordinates=data.get("last_coordinates"),
            history=list(data.get("history") or []),
        )

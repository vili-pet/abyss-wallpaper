"""TOML configuration with safe defaults and platform data directories."""

from __future__ import annotations

import os
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = (
    "AbyssWallpaper/0.1 (+https://github.com/vili-pet/abyss-wallpaper; personal desktop use)"
)


def default_data_dir() -> Path:
    override = os.environ.get("ABYSS_WALLPAPER_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "AbyssWallpaper"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AbyssWallpaper"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "abyss-wallpaper"
    return Path.home() / ".local" / "share" / "abyss-wallpaper"


def default_config_search_paths() -> list[Path]:
    paths = [
        Path.cwd() / "config.toml",
        Path.cwd() / "abyss-wallpaper.toml",
    ]
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        paths.append(Path(root) / "AbyssWallpaper" / "config.toml")
    elif sys.platform == "darwin":
        paths.append(Path.home() / "Library" / "Application Support" / "AbyssWallpaper" / "config.toml")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        config_root = Path(xdg) if xdg else Path.home() / ".config"
        paths.append(config_root / "abyss-wallpaper" / "config.toml")
    return paths


@dataclass(slots=True)
class OverlayConfig:
    enabled: bool = True
    corner: str = "bottom-left"
    max_width_ratio: float = 0.38
    margin: int = 36
    padding: int = 22
    opacity: int = 168


@dataclass(slots=True)
class SourceConfig:
    id: str
    kind: str
    enabled: bool = True
    url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    data_dir: Path = field(default_factory=default_data_dir)
    update_interval_hours: float = 24.0
    max_discoveries_per_source: int = 12
    max_image_bytes: int = 12_000_000
    request_timeout_seconds: float = 25.0
    crawl_delay_seconds: float = 1.0
    respect_robots: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    dry_run: bool = False
    set_wallpaper: bool = True
    prefer_underwater: bool = True
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    sources: list[SourceConfig] = field(default_factory=list)

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def image_dir(self) -> Path:
        return self.cache_dir / "images"

    @property
    def composed_dir(self) -> Path:
        return self.data_dir / "composed"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def preview_path(self) -> Path:
        return self.data_dir / "preview.jpg"


def default_sources() -> list[SourceConfig]:
    return [
        SourceConfig(
            id="noaa",
            kind="noaa",
            url="https://oceanexplorer.noaa.gov/wp-json/wp/v2/media",
            extra={
                "attribution": "Image courtesy of NOAA Ocean Exploration.",
                "source_name": "NOAA Ocean Exploration",
            },
        ),
        SourceConfig(
            id="nautilus",
            kind="nautilus",
            url="https://nautiluslive.org/gallery",
            extra={
                "attribution": "Ocean Exploration Trust / Nautilus Live.",
                "source_name": "Nautilus Live / Ocean Exploration Trust",
                "max_albums": 3,
            },
        ),
        SourceConfig(
            id="schmidt",
            kind="schmidt",
            url="https://schmidtocean.org/feed/",
            extra={
                "attribution": "Schmidt Ocean Institute.",
                "source_name": "Schmidt Ocean Institute",
            },
        ),
        SourceConfig(
            id="mbari",
            kind="mbari",
            url="https://www.mbari.org/feed/",
            extra={
                "attribution": "© MBARI. All rights reserved; used under source terms for personal wallpaper.",
                "source_name": "MBARI",
            },
        ),
        SourceConfig(
            id="fixture",
            kind="fixture",
            enabled=True,
            extra={
                "source_name": "Local fixture",
                "fallback_only": True,
            },
        ),
    ]


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_float(value: Any, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _as_int(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _load_overlay(raw: Mapping[str, Any] | None) -> OverlayConfig:
    data = raw or {}
    overlay = OverlayConfig()
    overlay.enabled = _as_bool(data.get("enabled"), overlay.enabled)
    overlay.corner = str(data.get("corner") or overlay.corner)
    overlay.max_width_ratio = _as_float(data.get("max_width_ratio"), overlay.max_width_ratio)
    overlay.margin = _as_int(data.get("margin"), overlay.margin)
    overlay.padding = _as_int(data.get("padding"), overlay.padding)
    overlay.opacity = _as_int(data.get("opacity"), overlay.opacity)
    return overlay


def _load_sources(raw: Mapping[str, Any] | None) -> list[SourceConfig]:
    defaults = {item.id: item for item in default_sources()}
    if not raw:
        return list(defaults.values())

    sources: list[SourceConfig] = []
    seen: set[str] = set()
    for source_id, payload in raw.items():
        if not isinstance(payload, Mapping):
            continue
        base = defaults.get(source_id, SourceConfig(id=source_id, kind=str(payload.get("kind") or source_id)))
        extra = dict(base.extra)
        extra.update({k: v for k, v in payload.items() if k not in {"kind", "enabled", "url"}})
        sources.append(
            SourceConfig(
                id=source_id,
                kind=str(payload.get("kind") or base.kind),
                enabled=_as_bool(payload.get("enabled"), base.enabled),
                url=str(payload.get("url") or base.url),
                extra=extra,
            )
        )
        seen.add(source_id)
    for source_id, base in defaults.items():
        if source_id not in seen:
            sources.append(base)
    return sources


def config_from_mapping(data: Mapping[str, Any] | None = None) -> AppConfig:
    payload = data or {}
    general_raw = payload.get("general")
    general: Mapping[str, Any] = general_raw if isinstance(general_raw, Mapping) else payload
    wallpaper_raw = payload.get("wallpaper")
    wallpaper: Mapping[str, Any] = wallpaper_raw if isinstance(wallpaper_raw, Mapping) else {}
    cfg = AppConfig()
    data_dir = general.get("data_dir")
    if data_dir:
        cfg.data_dir = Path(str(data_dir)).expanduser()
    cfg.update_interval_hours = _as_float(general.get("update_interval_hours"), cfg.update_interval_hours)
    cfg.max_discoveries_per_source = _as_int(
        general.get("max_discoveries_per_source"), cfg.max_discoveries_per_source
    )
    cfg.max_image_bytes = _as_int(general.get("max_image_bytes"), cfg.max_image_bytes)
    cfg.request_timeout_seconds = _as_float(
        general.get("request_timeout_seconds"), cfg.request_timeout_seconds
    )
    cfg.crawl_delay_seconds = _as_float(general.get("crawl_delay_seconds"), cfg.crawl_delay_seconds)
    cfg.respect_robots = _as_bool(general.get("respect_robots"), cfg.respect_robots)
    cfg.user_agent = str(general.get("user_agent") or cfg.user_agent)
    cfg.dry_run = _as_bool(general.get("dry_run"), cfg.dry_run)
    cfg.set_wallpaper = _as_bool(wallpaper.get("set_wallpaper"), cfg.set_wallpaper)
    cfg.prefer_underwater = _as_bool(wallpaper.get("prefer_underwater"), cfg.prefer_underwater)
    cfg.overlay = _load_overlay(payload.get("overlay") if isinstance(payload.get("overlay"), Mapping) else None)
    if "enabled" in wallpaper:
        cfg.overlay.enabled = _as_bool(wallpaper.get("compose_overlay"), cfg.overlay.enabled)
    if wallpaper.get("overlay_corner"):
        cfg.overlay.corner = str(wallpaper["overlay_corner"])
    cfg.sources = _load_sources(payload.get("sources") if isinstance(payload.get("sources"), Mapping) else None)
    return cfg


def load_config(path: Path | None = None) -> AppConfig:
    env_path = os.environ.get("ABYSS_WALLPAPER_CONFIG")
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    elif env_path:
        candidates.append(Path(env_path).expanduser())
    else:
        candidates.extend(default_config_search_paths())

    for candidate in candidates:
        if candidate.is_file():
            with candidate.open("rb") as handle:
                return config_from_mapping(tomllib.load(handle))
    return config_from_mapping({})

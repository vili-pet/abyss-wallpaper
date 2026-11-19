from __future__ import annotations

from pathlib import Path

import pytest

from abyss_wallpaper.config import AppConfig, SourceConfig, config_from_mapping
from abyss_wallpaper.http import MappingHttpClient
from abyss_wallpaper.pipeline import WallpaperPipeline
from abyss_wallpaper.wallpaper import PreviewWallpaperSetter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    cfg = config_from_mapping(
        {
            "general": {"data_dir": str(tmp_path / "data"), "update_interval_hours": 24},
            "sources": {
                "noaa": {"enabled": False},
                "nautilus": {"enabled": False},
                "schmidt": {"enabled": False},
                "mbari": {"enabled": False},
                "fixture": {"enabled": True, "fallback_only": False},
            },
        }
    )
    return cfg


@pytest.fixture
def pipeline(app_config: AppConfig) -> WallpaperPipeline:
    return WallpaperPipeline(app_config, setter=PreviewWallpaperSetter())


@pytest.fixture
def http_client(fixtures_dir: Path) -> MappingHttpClient:
    return MappingHttpClient(
        {
            "https://oceanexplorer.noaa.gov/wp-json/wp/v2/media": (
                fixtures_dir / "noaa_media.json"
            ).read_text(encoding="utf-8"),
            "https://www.mbari.org/feed/": (fixtures_dir / "rss_mbari.xml").read_text(encoding="utf-8"),
            "https://schmidtocean.org/feed/": (fixtures_dir / "rss_schmidt.xml").read_text(
                encoding="utf-8"
            ),
            "https://nautiluslive.org/gallery": (fixtures_dir / "nautilus_gallery.html").read_text(
                encoding="utf-8"
            ),
            "https://nautiluslive.org/album/2026/08/17/curious-crustaceans": (
                fixtures_dir / "nautilus_album.html"
            ).read_text(encoding="utf-8"),
        }
    )


@pytest.fixture
def live_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        data_dir=tmp_path / "data",
        sources=[
            SourceConfig(
                id="noaa",
                kind="noaa",
                url="https://oceanexplorer.noaa.gov/wp-json/wp/v2/media",
            ),
            SourceConfig(
                id="mbari",
                kind="mbari",
                url="https://www.mbari.org/feed/",
            ),
            SourceConfig(
                id="schmidt",
                kind="schmidt",
                url="https://schmidtocean.org/feed/",
            ),
            SourceConfig(
                id="nautilus",
                kind="nautilus",
                url="https://nautiluslive.org/gallery",
                extra={"max_albums": 1},
            ),
            SourceConfig(id="fixture", kind="fixture", extra={"fallback_only": True}),
        ],
    )

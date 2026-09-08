from datetime import datetime, timezone
from pathlib import Path

from abyss_wallpaper.config import AppConfig, SourceConfig
from abyss_wallpaper.http import MappingHttpClient
from abyss_wallpaper.pipeline import WallpaperPipeline
from abyss_wallpaper.sources.fixture import generate_placeholder_image
from abyss_wallpaper.wallpaper import PreviewWallpaperSetter


def test_offline_preview_creates_image(pipeline: WallpaperPipeline, tmp_path: Path) -> None:
    output = tmp_path / "preview.jpg"
    result = pipeline.preview(offline=True, output=output)
    assert result.action in {"preview", "dry-run"}
    assert result.discovery is not None
    assert result.discovery.depth_m == 1378
    assert output.exists()
    assert output.stat().st_size > 1000


def test_update_skips_duplicate_hash(app_config: AppConfig, tmp_path: Path) -> None:
    setter = PreviewWallpaperSetter()
    pipe = WallpaperPipeline(app_config, setter=setter)
    first = pipe.update(offline=True, force=True, apply_wallpaper=True)
    assert first.action == "applied"
    assert setter.last_path is not None
    second = pipe.update(offline=True, force=False, apply_wallpaper=True)
    assert second.action == "skipped"
    assert second.reason == "image already applied"


def test_live_sources_with_fixtures(
    live_config: AppConfig, http_client: MappingHttpClient, tmp_path: Path
) -> None:
    image = generate_placeholder_image("live")
    client = MappingHttpClient(
        {
            **http_client.mapping,
            "https://oceanexplorer.noaa.gov/wp-content/uploads/2026/09/ex2606-dive07-sponge.jpg": image,
            "https://www.mbari.org/wp-content/uploads/SeamountHotspotsExpedition_Magnapinna_1150.jpg": image,
            "https://schmidtocean.org/wp-content/uploads/FKt260629-S0950-scicam-EelPoutOnSeep-2048x1152.jpg": image,
            "https://nautiluslive.org/sites/default/files/images/2026-08/shrimp.jpg": image,
        }
    )
    pipe = WallpaperPipeline(live_config, http=client, setter=PreviewWallpaperSetter())
    items = pipe.fetch_discoveries()
    assert {item.source_id for item in items} >= {"noaa", "mbari", "schmidt", "nautilus"}
    result = pipe.update(force=True, apply_wallpaper=False, now=datetime(2026, 9, 8, tzinfo=timezone.utc))
    assert result.discovery is not None
    assert result.wallpaper_path is not None
    assert Path(result.wallpaper_path).exists()


def test_missing_image_falls_back_to_fixture(tmp_path: Path) -> None:
    cfg = AppConfig(
        data_dir=tmp_path / "data",
        sources=[
            SourceConfig(id="broken", kind="rss", url="https://example.invalid/feed.xml"),
            SourceConfig(id="fixture", kind="fixture", extra={"fallback_only": True}),
        ],
    )
    client = MappingHttpClient({})
    pipe = WallpaperPipeline(cfg, http=client, setter=PreviewWallpaperSetter())
    items = pipe.fetch_discoveries()
    assert items
    assert items[0].source_id == "fixture"

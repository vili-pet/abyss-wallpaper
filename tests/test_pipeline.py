from contextlib import nullcontext
from datetime import UTC, datetime
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import Mock

import pytest

from abyss_wallpaper.config import AppConfig, SourceConfig
from abyss_wallpaper.http import MappingHttpClient, StdHttpClient
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
    result = pipe.update(force=True, apply_wallpaper=False, now=datetime(2026, 9, 8, tzinfo=UTC))
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


def _rss(*entries: tuple[str, str]) -> str:
    items = "".join(
        f'<item><title>{title}</title><enclosure type="image/jpeg" url="{url}"/></item>'
        for title, url in entries
    )
    return f"<rss><channel>{items}</channel></rss>"


def test_malformed_rss_does_not_hide_other_sources(tmp_path: Path) -> None:
    broken_feed = "https://example.org/broken.xml"
    good_feed = "https://example.org/good.xml"
    config = AppConfig(
        data_dir=tmp_path,
        sources=[
            SourceConfig(id="broken", kind="rss", url=broken_feed),
            SourceConfig(id="good", kind="rss", url=good_feed),
        ],
    )
    client = MappingHttpClient(
        {broken_feed: "<rss>", good_feed: _rss(("Deep-sea sponge", "https://example.org/sponge.jpg"))}
    )
    pipe = WallpaperPipeline(config, http=client, setter=PreviewWallpaperSetter())

    assert [item.source_id for item in pipe.fetch_discoveries()] == ["good"]


@pytest.mark.parametrize("failure", ["download", "decode", "size"])
def test_update_tries_next_image(failure: str, tmp_path: Path) -> None:
    feed_url = "https://example.org/feed.xml"
    bad_url = "https://example.org/broken.jpg"
    good_url = "https://example.org/working.jpg"
    image = generate_placeholder_image("working")
    config = AppConfig(
        data_dir=tmp_path,
        max_image_bytes=len(image),
        sources=[SourceConfig(id="live", kind="rss", url=feed_url)],
    )
    feed = _rss(("ROV deep sea sponge at 2800 m", bad_url), ("Research ship", good_url))
    client = MappingHttpClient({feed_url: feed, good_url: image})
    if failure == "decode":
        client.mapping[bad_url] = b"not an image"
    elif failure == "size":
        client.mapping[bad_url] = bytes(len(image) + 1)
    setter = PreviewWallpaperSetter()
    pipe = WallpaperPipeline(config, http=client, setter=setter)

    assert [item.image_url for item in pipe.fetch_discoveries()] == [bad_url, good_url]
    result = pipe.update()
    assert result.action == "applied"
    assert result.discovery is not None and result.discovery.image_url == good_url
    assert setter.last_path == result.wallpaper_path
    assert pipe.status().last_discovery_id == result.discovery.id


def test_update_uses_fixture_after_live_images_fail(tmp_path: Path) -> None:
    feed_url = "https://example.org/feed.xml"
    config = AppConfig(
        data_dir=tmp_path,
        sources=[
            SourceConfig(id="live", kind="rss", url=feed_url),
            SourceConfig(id="fixture", kind="fixture", extra={"fallback_only": True}),
        ],
    )
    client = MappingHttpClient({feed_url: _rss(("Deep-sea sponge", "https://example.org/missing.jpg"))})
    setter = PreviewWallpaperSetter()
    pipe = WallpaperPipeline(config, http=client, setter=setter)

    failure = pipe.update(source_id="live")
    assert failure.action == "noop"
    assert setter.last_path is None
    assert pipe.status().last_discovery_id is None

    result = pipe.preview()
    assert result.action == "preview"
    assert result.discovery is not None and result.discovery.source_id == "fixture"


def test_update_uses_fixture_after_incomplete_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        sources=[
            SourceConfig(id="live", kind="rss", url="https://example.org/feed.xml"),
            SourceConfig(id="fixture", kind="fixture", extra={"fallback_only": True}),
        ],
    )
    client = StdHttpClient(user_agent=config.user_agent, respect_robots=False, crawl_delay_seconds=0)
    feed = _rss(("Deep-sea sponge", "https://example.org/sponge.jpg"))
    monkeypatch.setattr(client, "get_text", lambda _: feed)
    response = Mock()
    response.read.side_effect = IncompleteRead(b"partial", 10)
    monkeypatch.setattr("abyss_wallpaper.http.urlopen", lambda *args, **kwargs: nullcontext(response))
    pipe = WallpaperPipeline(config, http=client, setter=PreviewWallpaperSetter())

    result = pipe.preview()
    assert result.action == "preview"
    assert result.discovery is not None and result.discovery.source_id == "fixture"

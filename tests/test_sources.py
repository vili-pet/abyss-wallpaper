from abyss_wallpaper.config import SourceConfig
from abyss_wallpaper.http import MappingHttpClient
from abyss_wallpaper.sources.htmlutil import unwrap_drupal_style
from abyss_wallpaper.sources.mbari import MbariSource
from abyss_wallpaper.sources.nautilus import NautilusSource
from abyss_wallpaper.sources.noaa import NoaaSource
from abyss_wallpaper.sources.schmidt import SchmidtSource


def test_noaa_parser_extracts_depth_and_skips_favicon(http_client: MappingHttpClient) -> None:
    source = NoaaSource(SourceConfig(id="noaa", kind="noaa", url="https://oceanexplorer.noaa.gov/wp-json/wp/v2/media"))
    items = source.fetch(http_client, limit=10)
    assert len(items) == 1
    assert items[0].title == "Stalked Sponge"
    assert items[0].depth_m == 1378
    assert "NOAA" in items[0].attribution


def test_mbari_rss_prefers_underwater_image(http_client: MappingHttpClient) -> None:
    source = MbariSource(SourceConfig(id="mbari", kind="mbari", url="https://www.mbari.org/feed/"))
    items = source.fetch(http_client, limit=5)
    assert len(items) == 1
    assert "Magnapinna" in items[0].image_url or "squid" in items[0].title.lower()
    assert items[0].depth_m == 3277
    assert items[0].coordinates is not None


def test_schmidt_rss_picks_scicam_over_portrait(http_client: MappingHttpClient) -> None:
    source = SchmidtSource(SourceConfig(id="schmidt", kind="schmidt", url="https://schmidtocean.org/feed/"))
    items = source.fetch(http_client, limit=5)
    assert items
    assert "scicam" in items[0].image_url
    assert items[0].depth_m == 1900


def test_nautilus_gallery_and_album(http_client: MappingHttpClient) -> None:
    source = NautilusSource(
        SourceConfig(
            id="nautilus",
            kind="nautilus",
            url="https://nautiluslive.org/gallery",
            extra={"max_albums": 1},
        )
    )
    items = source.fetch(http_client, limit=5)
    assert items
    assert items[0].title.lower().startswith("red shrimp") or "shrimp" in items[0].title.lower()
    assert items[0].image_url.endswith("/images/2026-08/shrimp.jpg")
    assert items[0].depth_m == 2140
    assert items[0].attribution == "Ocean Exploration Trust"


def test_unwrap_drupal_style_keeps_scheme() -> None:
    url = (
        "https://nautiluslive.org/sites/default/files/styles/photoswipe_display/"
        "public/images/2026-08/shrimp.jpg?itok=abc"
    )
    assert (
        unwrap_drupal_style(url)
        == "https://nautiluslive.org/sites/default/files/images/2026-08/shrimp.jpg"
    )

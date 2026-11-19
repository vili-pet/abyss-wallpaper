from pathlib import Path

from abyss_wallpaper.cache import ImageCache
from abyss_wallpaper.models import Discovery


def test_cache_stores_once(tmp_path: Path) -> None:
    cache = ImageCache(tmp_path)
    discovery = Discovery(
        id="one",
        source_id="fixture",
        source_name="Local",
        title="Sponge",
        page_url="",
        image_url="https://example.org/a.jpg",
    )
    payload = b"jpeg-bytes"
    path_a, digest_a = cache.store(discovery, payload, "image/jpeg")
    path_b, digest_b = cache.store(discovery, payload, "image/jpeg")
    assert digest_a == digest_b
    assert path_a == path_b
    assert path_a.exists()
    assert cache.lookup(digest_a) == path_a

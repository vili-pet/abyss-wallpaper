from pathlib import Path

from PIL import Image

from abyss_wallpaper.config import OverlayConfig
from abyss_wallpaper.models import Coordinates, Discovery
from abyss_wallpaper.overlay import compose_overlay


def test_overlay_writes_jpeg(tmp_path: Path) -> None:
    source = Image.new("RGB", (1280, 720), (10, 20, 40))
    discovery = Discovery(
        id="x",
        source_id="fixture",
        source_name="NOAA Ocean Exploration",
        title="Stalked Sponge",
        page_url="https://example.org",
        image_url="https://example.org/a.jpg",
        depth_m=1378,
        coordinates=Coordinates(-14.271, -170.132),
        attribution="Image courtesy of NOAA Ocean Exploration.",
    )
    output = tmp_path / "out.jpg"
    compose_overlay(source, discovery, output, OverlayConfig())
    assert output.exists()
    composed = Image.open(output)
    assert composed.size == (1280, 720)

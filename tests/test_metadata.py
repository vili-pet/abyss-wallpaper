from abyss_wallpaper.metadata import (
    image_preference_score,
    parse_coordinates,
    parse_datetime,
    parse_depth_m,
    rank_discoveries,
    strip_html,
)
from abyss_wallpaper.models import Discovery


def test_parse_depth_prefers_ocean_depth_over_organism_height() -> None:
    text = (
        "this large Caulophacus sponge that measured approximately 2 meters high "
        "was observed at a depth of 1,378 meters (4,521 feet)"
    )
    assert parse_depth_m(text) == 1378


def test_parse_depth_from_feet() -> None:
    assert parse_depth_m("approximately 10,751 feet underwater") == 3276.9


def test_parse_depth_ignores_years_and_org_names() -> None:
    assert parse_depth_m("Image: Steve Litvin © 2026 MBARI") is None


def test_parse_hemisphere_coordinates() -> None:
    coords = parse_coordinates("35.720 N, 122.720 W")
    assert coords is not None
    assert coords.latitude == 35.72
    assert coords.longitude == -122.72
    assert "W" in coords.format()


def test_parse_datetime_rss_and_iso() -> None:
    rss = parse_datetime("Wed, 02 Sep 2026 16:00:55 +0000")
    iso = parse_datetime("2026-09-02T16:00:55Z")
    assert rss is not None and iso is not None
    assert rss.year == 2026
    assert iso.hour == 16


def test_strip_html_unescapes() -> None:
    assert strip_html("<p>Image courtesy of NOAA &amp; partners</p>") == "Image courtesy of NOAA & partners"


def test_image_preference_prefers_scicam() -> None:
    good = image_preference_score(
        "https://example.org/FKt-scicam-EelPoutOnSeep.jpg", "cold seep", "expedition"
    )
    bad = image_preference_score("https://example.org/award-portrait.jpeg", "award", "portrait")
    assert good > bad


def test_rank_discoveries_uses_metadata() -> None:
    weak = Discovery(
        id="a",
        source_id="x",
        source_name="X",
        title="Lab portrait",
        page_url="",
        image_url="https://example.org/portrait.jpg",
    )
    strong = Discovery(
        id="b",
        source_id="x",
        source_name="X",
        title="Stalked sponge",
        page_url="",
        image_url="https://example.org/dive-sponge.jpg",
        depth_m=1378,
    )
    ranked = rank_discoveries([weak, strong])
    assert ranked[0].id == "b"

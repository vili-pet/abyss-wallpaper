from pathlib import Path

from abyss_wallpaper.config import config_from_mapping, load_config


def test_defaults_include_core_sources() -> None:
    cfg = config_from_mapping({})
    ids = {source.id for source in cfg.sources}
    assert {"noaa", "nautilus", "schmidt", "mbari", "fixture"} <= ids
    assert cfg.respect_robots is True
    assert cfg.overlay.enabled is True


def test_toml_overrides(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        """
[general]
data_dir = "/tmp/abyss-test"
update_interval_hours = 6
dry_run = true

[sources.noaa]
enabled = false
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.data_dir == Path("/tmp/abyss-test")
    assert cfg.update_interval_hours == 6
    assert cfg.dry_run is True
    noaa = next(source for source in cfg.sources if source.id == "noaa")
    assert noaa.enabled is False
    assert any(source.id == "fixture" for source in cfg.sources)


def test_missing_config_uses_defaults(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("ABYSS_WALLPAPER_CONFIG", raising=False)
    monkeypatch.setattr(
        "abyss_wallpaper.config.default_config_search_paths",
        lambda: [tmp_path / "missing.toml"],
    )
    cfg = load_config()
    assert cfg.update_interval_hours == 24

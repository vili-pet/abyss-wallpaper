from pathlib import Path

import pytest

from abyss_wallpaper.wallpaper import (
    LinuxWallpaperSetter,
    PreviewWallpaperSetter,
    WallpaperError,
    default_setter,
)


def test_preview_setter_records_path(tmp_path: Path) -> None:
    setter = PreviewWallpaperSetter()
    setter.set_wallpaper(tmp_path / "wall.jpg")
    assert setter.last_path == tmp_path / "wall.jpg"


def test_default_setter_windows_mapping() -> None:
    setter = default_setter("win32")
    assert setter.platform == "windows"


def test_default_setter_macos_and_linux() -> None:
    assert default_setter("darwin").platform == "macos"
    assert default_setter("linux").platform == "linux"


def test_unknown_platform() -> None:
    with pytest.raises(WallpaperError):
        default_setter("plan9")


def test_linux_setter_errors_without_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.setattr("abyss_wallpaper.wallpaper.shutil.which", lambda _name: None)
    with pytest.raises(WallpaperError):
        LinuxWallpaperSetter().set_wallpaper(tmp_path / "wall.jpg")

"""Desktop wallpaper setters with a Windows-first implementation and OS hooks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol


class WallpaperError(RuntimeError):
    """The OS wallpaper API or helper command failed."""


class WallpaperSetter(Protocol):
    platform: str

    def set_wallpaper(self, path: Path) -> None: ...


class WindowsWallpaperSetter:
    platform = "windows"

    def set_wallpaper(self, path: Path) -> None:
        if sys.platform != "win32":  # pragma: no cover - exercised via tests with a stub
            raise WallpaperError("Windows wallpaper API is only available on Windows")
        import ctypes

        resolved = str(path.resolve())
        spi_setdeskwallpaper = 20
        update_ini = 0x01
        send_change = 0x02
        ok = ctypes.windll.user32.SystemParametersInfoW(
            spi_setdeskwallpaper, 0, resolved, update_ini | send_change
        )
        if not ok:
            raise WallpaperError("SystemParametersInfoW failed")


class MacWallpaperSetter:
    platform = "macos"

    def set_wallpaper(self, path: Path) -> None:
        resolved = str(path.resolve())
        script = (
            'tell application "System Events" to tell every desktop '
            f'to set picture to POSIX file "{resolved}"'
        )
        _run(["osascript", "-e", script], "macOS wallpaper update")


class LinuxWallpaperSetter:
    platform = "linux"

    def set_wallpaper(self, path: Path) -> None:
        resolved = path.resolve()
        uri = resolved.as_uri()
        desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
        errors: list[str] = []
        if "gnome" in desktop or "unity" in desktop or "cinnamon" in desktop:
            if _try(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                errors,
            ):
                _try(
                    ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                    errors,
                )
                return
        if "kde" in desktop or "plasma" in desktop:
            script = (
                "var allDesktops = desktops();"
                f'for (i=0;i<allDesktops.length;i++) {{ d=allDesktops[i]; d.wallpaperPlugin="org.kde.image";'
                f'd.currentConfigGroup=Array("Wallpaper","org.kde.image","General");'
                f'd.writeConfig("Image","{uri}"); }}'
            )
            kde = ["qdbus", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script]
            if _try(kde, errors):
                return
        if "xfce" in desktop:
            if _try(
                [
                    "xfconf-query",
                    "-c",
                    "xfce4-desktop",
                    "-p",
                    "/backdrop/screen0/monitor0/workspace0/last-image",
                    "-s",
                    str(resolved),
                ],
                errors,
            ):
                return
        if shutil.which("swaybg"):
            subprocess.Popen(["swaybg", "-i", str(resolved), "-m", "fill"], start_new_session=True)
            return
        if shutil.which("feh"):
            _run(["feh", "--bg-fill", str(resolved)], "feh wallpaper update")
            return
        raise WallpaperError(
            "No supported Linux wallpaper helper found "
            f"(tried gsettings/qdbus/xfconf/swaybg/feh). Desktop={desktop or 'unknown'}"
        )


class PreviewWallpaperSetter:
    """Records the path that would be applied without touching the desktop."""

    platform = "preview"

    def __init__(self) -> None:
        self.last_path: Path | None = None

    def set_wallpaper(self, path: Path) -> None:
        self.last_path = path


def default_setter(platform: str | None = None) -> WallpaperSetter:
    name = (platform or sys.platform).lower()
    if name in {"win32", "windows"}:
        return WindowsWallpaperSetter()
    if name in {"darwin", "macos", "mac"}:
        return MacWallpaperSetter()
    if name.startswith("linux"):
        return LinuxWallpaperSetter()
    raise WallpaperError(f"Unsupported platform {name!r}")


def _run(command: list[str], label: str) -> None:
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise WallpaperError(f"{label} failed: command not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise WallpaperError(f"{label} failed: {detail or exc}") from exc
    if completed.returncode != 0:  # pragma: no cover
        raise WallpaperError(f"{label} failed")


def _try(command: list[str], errors: list[str]) -> bool:
    try:
        _run(command, command[0])
    except WallpaperError as exc:
        errors.append(str(exc))
        return False
    return True

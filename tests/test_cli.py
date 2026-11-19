from pathlib import Path

from abyss_wallpaper.cli import main


def test_cli_offline_preview_and_status(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    data_dir = tmp_path / "data"
    assert (
        main(["--data-dir", str(data_dir), "--offline", "preview", "--out", str(tmp_path / "p.jpg")])
        == 0
    )
    out = capsys.readouterr().out
    assert "Caulophacus" in out or "preview" in out
    assert (tmp_path / "p.jpg").exists()
    assert main(["--data-dir", str(data_dir), "status"]) == 0


def test_cli_sources_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--data-dir", str(tmp_path), "--json", "sources"]) == 0
    assert '"id": "noaa"' in capsys.readouterr().out


def test_cli_fetch_offline(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--data-dir", str(tmp_path), "--offline", "fetch"]) == 0
    assert "Caulophacus" in capsys.readouterr().out

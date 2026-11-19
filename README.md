# Abyss Wallpaper

A small, local-first utility that fetches recent **deep-sea discovery imagery** from public ocean-exploration sources and can set the newest suitable image as your desktop wallpaper. Metadata is painted into a quiet corner overlay — no notifications, no research spam, no telemetry.

The default sources are:

| Source | What we read | Typical credit |
| --- | --- | --- |
| [NOAA Ocean Exploration](https://oceanexplorer.noaa.gov/) | Public WordPress media API (`/wp-json/wp/v2/media`) | NOAA Ocean Exploration (U.S. government work) |
| [Nautilus Live / Ocean Exploration Trust](https://nautiluslive.org/) | Gallery + photo-album pages | Ocean Exploration Trust |
| [Schmidt Ocean Institute](https://schmidtocean.org/) | Public news RSS (`/feed/`) | Schmidt Ocean Institute |
| [MBARI](https://www.mbari.org/) | Public news RSS (`/feed/`) | © MBARI |

A bundled **fixture source** keeps the tool usable offline, in tests, and when a live site is down.

## Requirements

- Python 3.11+
- `pip` (or another installer that understands `pyproject.toml`)
- Optional OS helpers only if you want the wallpaper actually applied:
  - **Windows:** built-in `SystemParametersInfoW` (supported first)
  - **macOS:** `osascript` / System Events
  - **Linux:** `gsettings` (GNOME), Plasma `qdbus`, `xfconf-query`, `swaybg`, or `feh`

## Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

For a user install without a checkout:

```bash
pip install .
```

This registers the `abyss-wallpaper` console script.

## Quick start (safe)

These commands never change the desktop:

```bash
# Offline sample image + overlay (no network)
abyss-wallpaper --offline preview

# Show configured sources
abyss-wallpaper sources

# Fetch live listings only (respects robots.txt; does not set wallpaper)
abyss-wallpaper fetch

# Compose the current pick to ~/.local/share/abyss-wallpaper/preview.jpg
abyss-wallpaper preview
```

Apply the wallpaper (Windows, macOS, or a supported Linux desktop):

```bash
abyss-wallpaper update
abyss-wallpaper status
```

`--dry-run` composes the file and prints what would happen without calling the OS wallpaper API:

```bash
abyss-wallpaper --dry-run update
```

`--json` is available on every command if you want to script the tool.

## How it works

1. **Fetch** each enabled source (RSS, WordPress media JSON, or carefully scoped HTML).
2. **Parse** title, caption, publication date, attribution, and — when the text has them — depth and coordinates.
3. **Score** candidates so underwater ROV/science-camera frames beat portraits, logos, and lab shots.
4. **Download** the chosen image into a content-addressed cache.
5. **Compose** an optional translucent info panel (name, depth, coordinates, source, date, credit).
6. **Remember** the image hash and timestamp in `state.json` so the same wallpaper is not applied again and the update interval is honored.
7. **Set** the desktop wallpaper only when you run `update` without `--dry-run`.

Missing metadata is simply omitted from the overlay. A source that fails or returns no images is skipped; if nothing live works, the fixture source is used.

## Configuration

Copy [`config.example.toml`](config.example.toml) to one of:

- `./config.toml` (current working directory)
- `$XDG_CONFIG_HOME/abyss-wallpaper/config.toml` (Linux)
- `~/Library/Application Support/AbyssWallpaper/config.toml` (macOS)
- `%APPDATA%\AbyssWallpaper\config.toml` (Windows)

Or set `ABYSS_WALLPAPER_CONFIG`. Local state lives under `ABYSS_WALLPAPER_HOME` if set, otherwise:

- Linux: `~/.local/share/abyss-wallpaper`
- macOS: `~/Library/Application Support/AbyssWallpaper`
- Windows: `%LOCALAPPDATA%\AbyssWallpaper`

Useful knobs:

| Key | Meaning |
| --- | --- |
| `general.update_interval_hours` | Minimum time between applied wallpapers (default 24) |
| `general.respect_robots` | Honor each host’s `robots.txt` (default true) |
| `general.crawl_delay_seconds` | Pause between requests to the same host |
| `general.max_image_bytes` | Reject oversized downloads |
| `wallpaper.set_wallpaper` | Allow OS wallpaper changes |
| `overlay.corner` | `bottom-left` (default), `bottom-right`, `top-left`, `top-right` |
| `sources.<id>.enabled` | Turn a source off without deleting it |
| `sources.<id>.kind` | `noaa`, `nautilus`, `schmidt`, `mbari`, `rss`, `wordpress`, `fixture` |
| `sources.<id>.url` | Override the listing endpoint |
| `sources.fixture.fallback_only` | Use fixtures only when live sources fail (default) |

Custom RSS or WordPress media endpoints can be added:

```toml
[sources.my_feed]
enabled = true
kind = "rss"
url = "https://example.org/ocean/feed/"
source_name = "Example Ocean Lab"
attribution = "Example Ocean Lab"
```

## Background / scheduled operation

The process is silent: no popups, no toast spam. Schedule `abyss-wallpaper update` however you already schedule jobs.

**Linux (systemd user timer)** — `~/.config/systemd/user/abyss-wallpaper.service`:

```ini
[Unit]
Description=Abyss Wallpaper update

[Service]
Type=oneshot
ExecStart=%h/.local/bin/abyss-wallpaper update
```

`~/.config/systemd/user/abyss-wallpaper.timer`:

```ini
[Unit]
Description=Daily Abyss Wallpaper

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Then: `systemctl --user enable --now abyss-wallpaper.timer`.

**cron**

```cron
30 7 * * * /home/you/.local/bin/abyss-wallpaper update >/tmp/abyss-wallpaper.log 2>&1
```

**Windows Task Scheduler**

```bat
schtasks /Create /SC DAILY /TN "AbyssWallpaper" /TR "\"C:\Path\To\python.exe\" -m abyss_wallpaper update" /ST 07:30
```

**macOS launchd** — a `StartCalendarInterval` LaunchAgent that runs `abyss-wallpaper update`.

`update` is idempotent: if the newest image hash is already applied, or the interval has not elapsed, it exits after a `skipped` status. Use `--force` to override.

## Packaging for desktop use

The project is a standard setuptools package with a console entry point, so it can be:

- Installed into a venv and wrapped by a shortcut / `.desktop` file / scheduled task
- Frozen with PyInstaller later (`abyss-wallpaper` as the script, include `abyss_wallpaper/data`)
- Vendored as a wheel (`python -m build`)

There is no GUI, ad SDK, updater phone-home, or analytics. A GUI is intentionally omitted; preview/status cover the “what would this do?” case.

## Attribution, terms, and privacy

- Images remain copyrighted (or public-domain) **by their original institutions**. This tool only copies publicly advertised files for **personal desktop use**.
- NOAA Ocean Exploration media used here is typically a U.S. government work and should be credited “Image courtesy of NOAA Ocean Exploration.”
- Nautilus Live, Schmidt Ocean Institute, and MBARI images usually require visible credit and may restrict redistribution. Read each organization’s media/terms page before sharing a composed wallpaper.
- Requests send a descriptive `User-Agent`, honor `robots.txt`, and apply a crawl delay. Gallery HTML is parsed only for album/image links already linked from public listing pages — we do not spider the whole site.
- No accounts, cookies, or analytics. Cache and state stay on disk under the data directory. Delete that folder to wipe local copies.

If a source asks you to stop automated access, disable it in config (`enabled = false`).

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy abyss_wallpaper tests
```

Parser, state, overlay, and update-skip tests use the HTML/JSON/RSS snapshots in `tests/fixtures/`. They do not need the network. Live fetches are optional and can be checked with `abyss-wallpaper fetch -v`.

## License

The **code** is MIT (see [`LICENSE`](LICENSE)). Upstream photographs are **not** covered by that license. The bundled fixture images are generated locally as illustrations and are not official expedition photos.

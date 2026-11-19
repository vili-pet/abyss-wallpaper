"""Command-line interface for Abyss Wallpaper."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from abyss_wallpaper import __version__
from abyss_wallpaper.config import AppConfig, load_config
from abyss_wallpaper.pipeline import WallpaperPipeline
from abyss_wallpaper.sources import SourceError, enabled_sources
from abyss_wallpaper.wallpaper import WallpaperError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abyss-wallpaper",
        description="Fetch recent deep-sea discoveries and set one as the desktop wallpaper.",
    )
    parser.add_argument("--config", type=Path, help="Path to a TOML config file.")
    parser.add_argument("--data-dir", type=Path, help="Override the local state/cache directory.")
    parser.add_argument("--dry-run", action="store_true", help="Compose locally without changing the desktop.")
    parser.add_argument("--offline", action="store_true", help="Use bundled fixtures only.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log fetch details to stderr.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show the last applied wallpaper and local state.")
    sub.add_parser("sources", help="List configured sources.")

    fetch = sub.add_parser("fetch", help="Fetch discoveries without changing the wallpaper.")
    fetch.add_argument("--source", help="Limit to one configured source id.")

    preview = sub.add_parser("preview", help="Compose the newest discovery to a preview file.")
    preview.add_argument("--source", help="Limit to one configured source id.")
    preview.add_argument("--out", type=Path, help="Preview image path.")

    update = sub.add_parser("update", help="Fetch, compose, and set the desktop wallpaper.")
    update.add_argument("--source", help="Limit to one configured source id.")
    update.add_argument("--force", action="store_true", help="Ignore interval and duplicate-hash skips.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    if args.data_dir:
        config.data_dir = args.data_dir.expanduser()
    if args.dry_run:
        config.dry_run = True
    pipeline = WallpaperPipeline(config)
    try:
        return _dispatch(args, config, pipeline)
    except (SourceError, WallpaperError) as exc:
        _emit_error(str(exc), as_json=args.as_json)
        return 2


def _dispatch(args: argparse.Namespace, config: AppConfig, pipeline: WallpaperPipeline) -> int:
    if args.command == "status":
        return _print_status(pipeline, as_json=args.as_json)
    if args.command == "sources":
        return _print_sources(config, as_json=args.as_json)
    if args.command == "fetch":
        items = pipeline.fetch_discoveries(args.source, offline=args.offline)
        if args.as_json:
            print(json.dumps([item.to_dict() for item in items], indent=2))
        else:
            if not items:
                print("No discoveries found.")
                return 1
            for item in items:
                depth = f"{item.depth_m:.0f} m" if item.depth_m is not None else "depth unknown"
                print(f"{item.source_id:10}  {item.display_title()}  ({depth})")
                if item.page_url:
                    print(f"{'':10}  {item.page_url}")
        return 0 if items else 1
    if args.command == "preview":
        result = pipeline.preview(source_id=args.source, output=args.out, offline=args.offline)
        return _print_result(result, as_json=args.as_json)
    if args.command == "update":
        result = pipeline.update(
            source_id=args.source,
            force=args.force,
            dry_run=args.dry_run,
            offline=args.offline,
        )
        return _print_result(result, as_json=args.as_json)
    raise AssertionError(f"unhandled command {args.command}")


def _print_status(pipeline: WallpaperPipeline, *, as_json: bool) -> int:
    state = pipeline.status()
    if as_json:
        print(json.dumps(state.to_dict(), indent=2))
        return 0
    if not state.last_update:
        print("No wallpaper has been applied yet. Try: abyss-wallpaper preview --offline")
        return 0
    print("Abyss Wallpaper")
    print(f"  last update : {state.last_update.isoformat()}")
    print(f"  title       : {state.last_title or '—'}")
    print(f"  source      : {state.last_source_name or '—'}")
    print(f"  depth       : {state.last_depth_m if state.last_depth_m is not None else '—'}")
    print(f"  coordinates : {state.last_coordinates or '—'}")
    print(f"  attribution : {state.last_attribution or '—'}")
    print(f"  page        : {state.last_page_url or '—'}")
    print(f"  wallpaper   : {state.last_wallpaper_path or '—'}")
    print(f"  image hash  : {state.last_image_hash or '—'}")
    return 0


def _print_sources(config: AppConfig, *, as_json: bool) -> int:
    rows = []
    for source in enabled_sources(config.sources, include_fallback=True):
        rows.append(
            {
                "id": source.id,
                "name": source.name,
                "fallback_only": source.fallback_only,
            }
        )
    if as_json:
        print(json.dumps(rows, indent=2))
        return 0
    for row in rows:
        flag = " (fallback)" if row["fallback_only"] else ""
        print(f"{row['id']:12}  {row['name']}{flag}")
    return 0


def _print_result(result: object, *, as_json: bool) -> int:
    from abyss_wallpaper.pipeline import UpdateResult

    assert isinstance(result, UpdateResult)
    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        title = result.discovery.display_title() if result.discovery else "none"
        print(f"{result.action}: {title}")
        print(result.reason)
        if result.wallpaper_path:
            print(f"image: {result.wallpaper_path}")
        if result.discovery:
            if result.discovery.depth_m is not None:
                print(f"depth: {result.discovery.depth_m:.0f} m")
            if result.discovery.coordinates is not None:
                print(f"coords: {result.discovery.coordinates.format()}")
            if result.discovery.attribution:
                print(f"credit: {result.discovery.attribution}")
    return 0 if result.action != "noop" else 1


def _emit_error(message: str, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"error": message}), file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)

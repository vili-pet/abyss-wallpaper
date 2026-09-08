"""On-disk image cache keyed by content hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from abyss_wallpaper.models import Discovery


class ImageCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.images = root / "images"
        self.meta = root / "metadata"
        self.images.mkdir(parents=True, exist_ok=True)
        self.meta.mkdir(parents=True, exist_ok=True)

    def path_for_hash(self, digest: str, suffix: str = ".jpg") -> Path:
        return self.images / f"{digest}{suffix}"

    def store(self, discovery: Discovery, payload: bytes, content_type: str = "") -> tuple[Path, str]:
        digest = hashlib.sha256(payload).hexdigest()
        suffix = _suffix_for(discovery.image_url, content_type or discovery.content_type)
        path = self.path_for_hash(digest, suffix)
        if not path.exists():
            path.write_bytes(payload)
        record = {
            "hash": digest,
            "bytes": len(payload),
            "discovery": discovery.to_dict(),
        }
        (self.meta / f"{discovery.id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        return path, digest

    def lookup(self, digest: str) -> Path | None:
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            path = self.path_for_hash(digest, suffix)
            if path.exists():
                return path
        return None


def _suffix_for(url: str, content_type: str) -> str:
    lowered = (content_type or "").lower()
    if "png" in lowered:
        return ".png"
    if "webp" in lowered:
        return ".webp"
    path = url.split("?", 1)[0].lower()
    for suffix in (".png", ".webp", ".jpeg", ".jpg"):
        if path.endswith(suffix):
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"

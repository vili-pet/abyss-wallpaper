"""Robots-aware HTTP client built on the standard library."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from email.message import Message
from http.client import HTTPException
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

LOGGER = logging.getLogger("abyss_wallpaper.http")


class HttpError(RuntimeError):
    """Raised when a remote fetch fails or is disallowed."""


class HttpClient(Protocol):
    def get_text(self, url: str) -> str: ...

    def get_bytes(self, url: str) -> bytes: ...

    def get_json(self, url: str) -> Any: ...


@dataclass
class UrlFetch:
    url: str
    body: bytes
    content_type: str = "application/octet-stream"


@dataclass
class StdHttpClient:
    user_agent: str
    timeout: float = 25.0
    respect_robots: bool = True
    crawl_delay_seconds: float = 1.0
    _robots: dict[str, RobotFileParser] = field(default_factory=dict)
    _last_host_hit: dict[str, float] = field(default_factory=dict)

    def get_text(self, url: str) -> str:
        return self.fetch(url).body.decode("utf-8", errors="replace")

    def get_bytes(self, url: str) -> bytes:
        return self.fetch(url).body

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_text(url))

    def fetch(self, url: str) -> UrlFetch:
        if self.respect_robots and not self.allowed(url):
            raise HttpError(f"robots.txt disallows {url}")
        self._throttle(url)
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                content_type = _content_type(response.headers)
                final_url = response.geturl()
        except HTTPError as exc:
            raise HttpError(f"HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise HttpError(f"Failed to fetch {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise HttpError(f"Timed out fetching {url}") from exc
        except HTTPException as exc:
            raise HttpError(f"Failed to read response for {url}: {exc}") from exc
        LOGGER.debug("Fetched %s (%s bytes)", final_url, len(body))
        return UrlFetch(url=final_url, body=body, content_type=content_type)

    def allowed(self, url: str) -> bool:
        parser = self._robot_parser(url)
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:  # noqa: BLE001 - robots parsers can be messy
            return True

    def _robot_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots.get(origin)
        if cached is not None:
            return cached
        robots_url = urljoin(origin, "/robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            request = Request(robots_url, headers={"User-Agent": self.user_agent})
            with urlopen(request, timeout=self.timeout) as response:
                parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
        except Exception:  # noqa: BLE001
            parser.parse(["User-agent: *", "Allow: /"])
        self._robots[origin] = parser
        return parser

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_host_hit.get(host)
        if last is not None:
            wait = self.crawl_delay_seconds - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_host_hit[host] = time.monotonic()


def _content_type(headers: Message) -> str:
    raw = headers.get("Content-Type", "application/octet-stream")
    return raw.split(";", 1)[0].strip().lower()


class MappingHttpClient:
    """Deterministic client for tests and offline fixtures."""

    def __init__(self, mapping: dict[str, str | bytes] | None = None) -> None:
        self.mapping = mapping or {}

    def get_text(self, url: str) -> str:
        payload = self._lookup(url)
        return payload.decode("utf-8") if isinstance(payload, bytes) else payload

    def get_bytes(self, url: str) -> bytes:
        payload = self._lookup(url)
        return payload if isinstance(payload, bytes) else payload.encode("utf-8")

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_text(url))

    def _lookup(self, url: str) -> str | bytes:
        if url in self.mapping:
            return self.mapping[url]
        for key, value in self.mapping.items():
            if url.startswith(key):
                return value
        raise HttpError(f"No fixture for {url}")

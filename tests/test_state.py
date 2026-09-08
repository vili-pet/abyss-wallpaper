from datetime import UTC, datetime, timedelta
from pathlib import Path

from abyss_wallpaper.models import AppState, Discovery
from abyss_wallpaper.state import StateStore


def test_state_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    original = AppState(last_title="Sponge", last_image_hash="abc")
    store.save(original)
    loaded = store.load()
    assert loaded.last_title == "Sponge"
    assert loaded.last_image_hash == "abc"


def test_corrupt_state_is_reset(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not-json", encoding="utf-8")
    assert StateStore(path).load().last_update is None


def test_skip_same_hash_and_interval(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    now = datetime(2026, 9, 8, tzinfo=UTC)
    state = AppState(last_update=now, last_image_hash="same")
    assert store.should_skip(state, "same", timedelta(hours=24), now=now) == "image already applied"
    later = now + timedelta(hours=3)
    reason = store.should_skip(AppState(last_update=now, last_image_hash="old"), "new", timedelta(hours=24), now=later)
    assert reason is not None and "remaining" in reason
    assert (
        store.should_skip(state, "same", timedelta(hours=24), force=True, now=now) is None
    )


def test_record_history(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    discovery = Discovery(
        id="d1",
        source_id="fixture",
        source_name="Local",
        title="Sponge",
        page_url="https://example.org",
        image_url="generated://x",
    )
    updated = store.record(AppState(), discovery, "hash", tmp_path / "wall.jpg")
    assert updated.last_discovery_id == "d1"
    assert updated.history[0]["hash"] == "hash"

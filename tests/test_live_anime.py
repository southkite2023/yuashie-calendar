"""Offline live-ingestion tests; production API is never required for pytest."""
import copy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from yuashie_calendar.anilist import UpstreamError, fetch_window, normalize
from yuashie_calendar.render import project, render
from yuashie_calendar.validation import validate_package


NOW = datetime(2026, 10, 29, 5, 0, tzinfo=timezone.utc)
AIRING = int((NOW + timedelta(days=1)).timestamp())
EMPTY = {"schema_version": 1, "events": []}


def episode(airing=AIRING, title="架空アニメ"):
    return {"media_id": 123456, "episode": 2, "airing": airing, "title": title}


def page(rows, has_next=False):
    return {"airingSchedules": rows, "pageInfo": {"hasNextPage": has_next}}


def api_row(**overrides):
    row = {
        "airingAt": AIRING, "episode": 2, "mediaId": 123456,
        "media": {
            "id": 123456, "type": "ANIME", "format": "TV",
            "isAdult": False, "countryOfOrigin": "JP",
            "title": {"native": "架空アニメ", "romaji": "Kakuu Anime"}
        }
    }
    for key, value in overrides.items():
        row[key] = value
    return row


def test_live_identity_and_revision_survive_refetch():
    first = normalize([episode()], EMPTY, NOW)
    initial = first["events"][0]
    validate_package(first)
    assert UUID(initial["id"]).version == 4
    assert initial["revision"] == 0
    assert initial["start"].endswith("+09:00")
    assert initial["start"].startswith("2026-10-30T14:00:00")

    second = normalize([episode()], first, NOW + timedelta(hours=2))
    unchanged = second["events"][0]
    assert unchanged["id"] == initial["id"]
    assert unchanged["updated_at"] == initial["updated_at"]
    assert unchanged["revision"] == 0
    assert unchanged["sources"][0]["checked_at"] != initial["sources"][0]["checked_at"]

    later = normalize([episode(AIRING + 3600)], second, NOW + timedelta(hours=3))
    revised = later["events"][0]
    assert revised["id"] == initial["id"]
    assert revised["revision"] == 1
    assert revised["updated_at"] != initial["updated_at"]
    assert revised["start"] != initial["start"]
    assert project(revised, "start")["start"] == "2026-10-30"

    records = {revised["id"]: {
        "event": revised,
        "published": {mode: project(revised, mode) for mode in ("start", "span")}
    }}
    assert b"BEGIN:VEVENT" in render(records)["calendar/v1/anime/span.ics"]


def test_no_schedule_never_replaces_existing_snapshot():
    with pytest.raises(UpstreamError, match="no qualifying"):
        fetch_window(NOW, get_page=lambda page_number, after, before: page([]))


def test_malformed_schedule_or_conflicting_rows_rejected():
    with pytest.raises(UpstreamError, match="identity/time"):
        fetch_window(NOW, get_page=lambda p, a, b: page([api_row(airingAt="invalid")]))
    different = api_row(airingAt=AIRING + 3600)
    with pytest.raises(UpstreamError, match="Conflicting"):
        fetch_window(NOW, get_page=lambda p, a, b: page([api_row(), different]))


def test_japanese_tv_filter_and_bounded_pagination():
    other = api_row(mediaId=123457, media={
        "id": 123457, "type": "ANIME", "format": "MOVIE",
        "isAdult": False, "countryOfOrigin": "JP",
        "title": {"native": "Movie"}
    })
    def fake(p, a, b):
        return page([other], has_next=True) if p == 1 else page([api_row()])
    rows = fetch_window(NOW, get_page=fake)
    assert len(rows) == 1
    assert all(rows[0][key] == episode()[key] for key in ("media_id", "episode", "airing", "title"))
    assert "Kakuu Anime" in rows[0]["aliases"]
    calls = []
    with pytest.raises(UpstreamError, match="bounded page"):
        fetch_window(NOW, get_page=lambda p, a, b: calls.append(p) or page([api_row()], has_next=True))
    assert len(calls) == 8


def test_missing_episode_does_not_automatically_cancel():
    one = normalize([episode()], EMPTY, NOW)
    another = {"media_id": 999999, "episode": 1, "airing": AIRING + 1800, "title": "別の新番"}
    next_package = normalize([another], one, NOW + timedelta(days=1))
    assert len(next_package["events"]) == 2
    assert next(e for e in next_package["events"] if e["anime"]["series_id"] == "anilist:123456")["status"] == "confirmed"

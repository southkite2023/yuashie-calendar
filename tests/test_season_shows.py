"""Current-season catalog and long-lived individual subscription URL tests."""
import json
from datetime import datetime, timezone

from icalendar import Calendar

from yuashie_calendar.anilist import normalize
from yuashie_calendar.season_shows import build_show_feeds, current_season


NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)
EVENT = {"media_id": 206401, "episode": 5, "airing": 1793340000,
         "title": "FX戦士くるみちゃん", "season": "FALL", "season_year": 2026}


def test_current_season_jst_boundaries():
    assert current_season(NOW) == ("FALL", 2026)
    assert current_season(datetime(2026, 12, 31, 15, 30, tzinfo=timezone.utc)) == ("WINTER", 2027)


def test_single_show_feeds_stable_and_season_filter(tmp_path):
    original = {"schema_version": 1, "events": []}
    package = normalize([EVENT], original, NOW)
    prior = {"schema_version": 1, "shows": [
        {"id": 111111, "title": "旧番", "season": "SUMMER", "season_year": 2026}
    ]}
    registry, catalog = build_show_feeds([EVENT], package, NOW, prior, tmp_path)
    assert {s["id"] for s in registry["shows"]} == {111111, 206401}
    assert [s["id"] for s in catalog["shows"]] == [206401]

    single = Calendar.from_ical((tmp_path / "shows/206401/span.ics").read_bytes())
    events = single.walk("VEVENT")
    assert len(events) == 1
    assert str(events[0].get("URL")) == "https://anilist.co/anime/206401"
    assert str(events[0].get("UID")) == package["events"][0]["id"] + "@calendar.yuashie.cn"

    archived = Calendar.from_ical((tmp_path / "shows/111111/span.ics").read_bytes())
    assert archived.walk("VEVENT") == []  # no 404 even when a show has ended

    registry2, catalog2 = build_show_feeds([EVENT], package, NOW, registry, tmp_path)
    assert registry2 == registry
    assert catalog2["shows"] == catalog["shows"]


def test_unknown_season_does_not_invent_a_show_listing(tmp_path):
    event = {k: v for k, v in EVENT.items() if k not in ("season", "season_year")}
    package = normalize([event], {"schema_version": 1, "events": []}, NOW)
    prior = {"schema_version": 1, "shows": [
        {"id": 206401, "title": EVENT["title"], "season": "FALL", "season_year": 2026}
    ]}
    registry, catalog = build_show_feeds([event], package, NOW, prior, tmp_path)
    assert len(registry["shows"]) == 1
    assert [s["id"] for s in catalog["shows"]] == [206401]
    assert catalog["shows"][0]["next_airing_at"] is None

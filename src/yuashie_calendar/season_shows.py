"""Build stable per-title AniList calendars and the current-season selector catalog.

GitHub Pages is static: users subscribe to a separate stable URL for each
checked series, NOT one dynamically combined subscription URL.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar

from .render import component, project
from .validation import MODES

SEASONS = ("WINTER", "SPRING", "SUMMER", "FALL")


def current_season(now):
    local = now.astimezone(ZoneInfo("Asia/Tokyo"))
    return SEASONS[(local.month - 1) // 3], local.year


def make_calendar(events, mode, title):
    calendar = Calendar()
    calendar.add("version", "2.0")
    calendar.add("prodid", "-//yuashie-calendar//AniList show subscriptions//ZH")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", title)
    for event in sorted(events, key=lambda e: (e["start"], e["id"])):
        projection = project(event, mode)
        if projection:
            calendar.add_component(component(event, projection))
    return calendar.to_ical()


def build_show_feeds(raw, package, now, previous, output):
    """Return a new public registry and current-season catalog.

    Retain all old series IDs to keep an existing subscription URL accessible
    even after a show ends and its events age out of the rolling event ledger.
    """
    if not isinstance(previous, dict) or previous.get("schema_version") != 1 or not isinstance(previous.get("shows"), list):
        raise ValueError("Invalid saved anime show registry")
    all_shows = {}
    for show in previous["shows"]:
        if (not isinstance(show, dict) or
                set(show) != {"id", "title", "season", "season_year"} or
                type(show["id"]) is not int or show["id"] <= 0 or
                not isinstance(show["title"], str) or not show["title"].strip() or
                show["season"] not in SEASONS or
                type(show["season_year"]) is not int):
            raise ValueError("Invalid historical AniList show entry")
        if show["id"] in all_shows:
            raise ValueError("Duplicate historical AniList show ID")
        all_shows[show["id"]] = show.copy()

    next_airings = {}
    for row in raw:
        media_id = row["media_id"]
        season, year = row.get("season"), row.get("season_year")
        if season not in SEASONS or type(year) is not int:
            continue
        current = {"id": media_id, "title": row["title"], "season": season, "season_year": year}
        old = all_shows.get(media_id)
        if old and (old["season"], old["season_year"]) != (season, year):
            # Do not change a pre-existing historical series' season identity.
            current["season"], current["season_year"] = old["season"], old["season_year"]
        all_shows[media_id] = current
        candidate = {"at": row["airing"], "episode": row["episode"]}
        if media_id not in next_airings or candidate["at"] < next_airings[media_id]["at"]:
            next_airings[media_id] = candidate

    if not all_shows:
        raise ValueError("No shows with valid AniList season metadata; retaining old publication")

    events_by_id = {}
    for event in package["events"]:
        raw_id = event["anime"]["series_id"]
        if not raw_id.startswith("anilist:"):
            raise ValueError("Non-AniList event found in live show feeds")
        media_id = int(raw_id.split(":", 1)[1])
        events_by_id.setdefault(media_id, []).append(event)

    output = Path(output)
    for media_id, show in sorted(all_shows.items()):
        # A show may have zero events once its history has aged out. Still
        # publish valid empty ICS so existing subscriptions don't turn 404.
        for mode in MODES:
            source = make_calendar(
                events_by_id.get(media_id, []), mode,
                f"Yuashie Calendar · {show['title']} · {mode}",
            )
            path = output / "shows" / str(media_id) / f"{mode}.ics"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source)

    season, year = current_season(now)
    eligible = []
    for show in all_shows.values():
        if (show["season"], show["season_year"]) != (season, year):
            continue
        upcoming = next_airings.get(show["id"])
        eligible.append({
            "id": show["id"], "title": show["title"],
            "next_airing_at": upcoming["at"] if upcoming else None,
            "next_episode": upcoming["episode"] if upcoming else None,
        })
    eligible.sort(key=lambda s: (s["next_airing_at"] is None, s["next_airing_at"] or 0, s["title"]))
    catalog = {
        "schema_version": 1,
        "season": season,
        "year": year,
        "updated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "shows": eligible,
    }
    path = output / "catalog" / "current-season.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    registry = {"schema_version": 1, "shows": sorted(all_shows.values(), key=lambda s: s["id"])}
    return registry, catalog

"""Small-window public AniList airing schedule fetcher and stateful normalizer.

This is an aggregator schedule, NOT a guarantee of the Japanese broadcaster's
first-air time. Query only a two-week window; never infer cancelled episodes
from a missing response. Existing event IDs and revisions live in a committed,
public, non-secret snapshot; private generator state is never served.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from .build import semantic
from .validation import validate_package

ENDPOINT = "https://graphql.anilist.co"
MAX_PAGES = 8
PAGE_SIZE = 50
LOOKAHEAD_DAYS = 14
RETAIN_PAST_DAYS = 45
QUERY = """
query ($page: Int!, $after: Int!, $before: Int!) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    airingSchedules(airingAt_greater: $after, airingAt_lesser: $before, sort: TIME) {
      airingAt episode mediaId
      media {
        id type format isAdult countryOfOrigin
        title { native romaji english }
      }
    }
  }
}
"""


class UpstreamError(RuntimeError):
    """Upstream failure: keep the previously published Pages site untouched."""


def request_page(page, after, before, opener=urlopen):
    body = json.dumps({
        "query": QUERY,
        "variables": {"page": page, "after": after, "before": before}
    }).encode("utf-8")
    request = Request(
        ENDPOINT, data=body,
        headers={"User-Agent": "yuashie-calendar/0.1 (+https://github.com/southkite2023/yuashie-calendar)",
                 "Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    for attempt in range(3):
        try:
            with opener(request, timeout=20) as response:
                data = json.loads(response.read(2_000_000))
            if not isinstance(data, dict) or data.get("errors") or not isinstance(data.get("data"), dict):
                raise UpstreamError("AniList GraphQL returned errors or malformed data")
            page_data = data["data"].get("Page")
            if not isinstance(page_data, dict) or not isinstance(page_data.get("airingSchedules"), list):
                raise UpstreamError("AniList schedule missing")
            info = page_data.get("pageInfo")
            if not isinstance(info, dict) or type(info.get("hasNextPage")) is not bool:
                raise UpstreamError("AniList pageInfo missing")
            return page_data
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise UpstreamError(f"AniList HTTP {exc.code}") from exc
            delay = min(int(exc.headers.get("Retry-After", "5")), 30) if exc.code == 429 else 5
            time.sleep(delay)
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            if attempt == 2:
                raise UpstreamError("AniList network or JSON failure") from exc
            time.sleep(3)
    raise UpstreamError("AniList requests exhausted")


def fetch_window(now, get_page=request_page):
    """Fetch a strictly bounded subset, abort on empty/incomplete response."""
    after = int(now.timestamp()) - 60
    before = int((now + timedelta(days=LOOKAHEAD_DAYS)).timestamp())
    collected = {}
    for page in range(1, MAX_PAGES + 1):
        result = get_page(page, after, before)
        for row in result["airingSchedules"]:
            if not isinstance(row, dict):
                raise UpstreamError("Invalid airing schedule object")
            media = row.get("media")
            if not isinstance(media, dict):
                continue
            if media.get("type") != "ANIME" or media.get("format") not in ("TV", "TV_SHORT"):
                continue
            if media.get("countryOfOrigin") != "JP" or media.get("isAdult") is not False:
                continue
            media_id = row.get("mediaId")
            episode = row.get("episode")
            airing = row.get("airingAt")
            if (type(media_id) is not int or media_id <= 0 or
                    type(episode) is not int or episode <= 0 or
                    type(airing) is not int or not after < airing < before or
                    media.get("id") != media_id):
                raise UpstreamError("Invalid airing schedule identity/time")
            titles = media.get("title")
            if not isinstance(titles, dict):
                continue
            title = next((v.strip() for k in ("native", "romaji", "english")
                          if isinstance((v := titles.get(k)), str) and v.strip()), None)
            if not title:
                continue
            key = f"{media_id}:{episode}"
            candidate = {"media_id": media_id, "episode": episode, "airing": airing, "title": title}
            if key in collected and collected[key] != candidate:
                raise UpstreamError(f"Conflicting AniList schedule: {key}")
            collected[key] = candidate
        if not result["pageInfo"]["hasNextPage"]:
            break
        if page == MAX_PAGES:
            raise UpstreamError("AniList schedule exceeds bounded page limit; do not publish incomplete data")
        time.sleep(2)
    if not collected:
        raise UpstreamError("AniList returned no qualifying upcoming Japanese TV episodes")
    return list(collected.values())


def normalize(raw, prior, now):
    """Preserve UUID4 and SEQUENCE by stable media_id+episode crosswalk."""
    if not isinstance(prior, dict) or prior.get("schema_version") != 1:
        raise ValueError("Invalid prior ledger schema")
    existing = prior.get("events")
    if not isinstance(existing, list):
        raise ValueError("Invalid prior ledger events")
    if existing:
        validate_package(prior)
    prior_by_key = {}
    for e in existing:
        if e.get("category") != "anime" or e.get("sources", [{}])[0].get("provider") != "anilist":
            raise ValueError("Non-AniList content in production anime ledger")
        key = e["sources"][0]["source_id"]
        if key in prior_by_key:
            raise ValueError("Duplicate crosswalk in prior ledger")
        prior_by_key[key] = e

    stamp = now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tokyo = ZoneInfo("Asia/Tokyo")
    results = dict(prior_by_key)
    for row in raw:
        key = f"{row['media_id']}:{row['episode']}"
        old = prior_by_key.get(key)
        local = datetime.fromtimestamp(row["airing"], timezone.utc).astimezone(tokyo)
        source_url = f"https://anilist.co/anime/{row['media_id']}"
        item = {
            "id": old["id"] if old else str(uuid4()),
            "category": "anime",
            "event_type": "episode_airing",
            "title": f"{row['title']} · 第 {row['episode']} 集",
            "description": "AniList 社区汇总的播出预告，可能调整；并非日本电视台官方首播保证。",
            "status": "confirmed",
            "schedule_state": "scheduled",
            "time_kind": "datetime",
            "start": local.isoformat(timespec="seconds"),
            "end": None,
            "timezone": "Asia/Tokyo",
            "url": source_url,
            "sources": [{
                "provider": "anilist", "source_id": key, "url": source_url,
                "checked_at": stamp, "authority": "aggregator"
            }],
            "revision": old["revision"] if old else 0,
            "created_at": old["created_at"] if old else stamp,
            "updated_at": old["updated_at"] if old else stamp,
            "anime": {
                "series_id": f"anilist:{row['media_id']}",
                "episode_id": str(row["episode"]),
                "episode_label": f"第 {row['episode']} 集",
                "channel": "anilist-schedule"
            }
        }
        if old:
            # Successful re-checks update the source timestamp without changing
            # the actual event revision, unless the normalized meaning changed.
            if semantic(old) != semantic(item):
                item["revision"] += 1
                if stamp <= old["updated_at"]:
                    raise ValueError("Clock did not advance since prior semantic revision")
                item["updated_at"] = stamp
        results[key] = item

    # Only expire events from long ago; disappearance from a schedule is not cancellation.
    cutoff = (now.astimezone(tokyo) - timedelta(days=RETAIN_PAST_DAYS)).date()
    retained = [e for e in results.values()
                if datetime.fromisoformat(e["start"]).astimezone(tokyo).date() >= cutoff]
    output = {"schema_version": 1, "events": sorted(retained, key=lambda e: (e["start"], e["id"]))}
    validate_package(output)
    if not any(e["sources"][0]["checked_at"] == stamp for e in output["events"]):
        raise ValueError("No fresh events in resulting ledger")
    return output

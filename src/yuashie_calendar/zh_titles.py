"""Verified Chinese-title enrichment without inventing Japanese-to-Chinese names.

AniList has no first-class Chinese field. Bangumi's name_cn is community-edited,
not an official publisher title. A reviewed, explicitly sourced override may
indicate an official localized title. Match Bangumi by exact normalized original
Japanese title only; never accept fuzzy matches or silently declare them official.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BANGUMI_SEARCH = "https://api.bgm.tv/v0/search/subjects?limit=10"
MAX_RESPONSE_BYTES = 350_000
MAX_NEW_LOOKUPS = 32
MAX_TITLE_LENGTH = 160
USER_AGENT = "YuashieCalendar/1.0 (https://github.com/southkite2023/yuashie-calendar; language titles)"

class TranslationLookupError(RuntimeError):
    pass

def normalized_title(value):
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

def valid_title(value):
    return (
        isinstance(value, str) and bool(value.strip()) and
        len(value) <= MAX_TITLE_LENGTH and
        not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
    )

def lookup_bangumi(native_title, season_year, opener=urlopen):
    """One bounded exact-name lookup, never an official-title certification."""
    if not valid_title(native_title):
        return None
    body = json.dumps({
        "keyword": native_title,
        "sort": "match",
        "filter": {"type": [2]},
    }, ensure_ascii=False).encode("utf-8")
    request = Request(
        BANGUMI_SEARCH, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with opener(request, timeout=12) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise TranslationLookupError("Bangumi response exceeded bound")
        data = json.loads(payload)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise TranslationLookupError("Bangumi API unavailable") from exc
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise TranslationLookupError("Bangumi API search schema invalid")
    matching = []
    key = normalized_title(native_title)
    for subject in data["data"]:
        if not isinstance(subject, dict) or subject.get("type") != 2:
            continue
        if normalized_title(subject.get("name")) != key:
            continue
        translated = subject.get("name_cn")
        subject_id = subject.get("id")
        if not valid_title(translated) or type(subject_id) is not int or subject_id <= 0:
            continue
        date = subject.get("date")
        if isinstance(date, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            if abs(int(date[:4]) - season_year) > 1:
                continue
        matching.append((subject_id, translated.strip()))
    # Multiple originals with an identical Japanese name are ambiguous:
    # never randomly pick a potentially wrong sequel/remake.
    if len(matching) != 1:
        return None
    subject_id, title = matching[0]
    return {"zh_hans": title, "source": "bangumi",
            "source_url": f"https://bgm.tv/subject/{subject_id}"}

def _load_existing(previous):
    if not isinstance(previous, dict) or previous.get("schema_version") != 1 or not isinstance(previous.get("entries"), list):
        raise ValueError("Invalid saved Chinese title registry")
    entries = {}
    for item in previous["entries"]:
        if (not isinstance(item, dict) or
            type(item.get("anilist_id")) is not int or item["anilist_id"] <= 0 or
            not valid_title(item.get("native_title")) or
            item.get("source") not in ("bangumi", "official", "none") or
            (item.get("zh_hans") is not None and not valid_title(item["zh_hans"])) or
            type(item.get("revision")) is not int or item["revision"] < 0 or
            not isinstance(item.get("updated_at"), str) or
            not isinstance(item.get("checked_at"), str)):
            raise ValueError("Invalid saved Chinese title item")
        if item["anilist_id"] in entries:
            raise ValueError("Duplicate Chinese title Anilist ID")
        entries[item["anilist_id"]] = item.copy()
    return entries

def _load_official(reviewed):
    if not isinstance(reviewed, dict) or reviewed.get("schema_version") != 1 or not isinstance(reviewed.get("titles"), list):
        raise ValueError("Invalid reviewed official title schema")
    overrides = {}
    for item in reviewed["titles"]:
        if (not isinstance(item, dict) or
            type(item.get("anilist_id")) is not int or item["anilist_id"] <= 0 or
            not valid_title(item.get("native_title")) or
            not valid_title(item.get("zh_hans")) or
            not isinstance(item.get("source_url"), str) or
            not item["source_url"].startswith("https://") or
            len(item["source_url"]) > 500 or
            not isinstance(item.get("evidence_note"), str) or not item["evidence_note"].strip()):
            raise ValueError("Official title requires a reviewed original, exact Chinese name and official source URL")
        if item["anilist_id"] in overrides:
            raise ValueError("Duplicate reviewed title entry")
        overrides[item["anilist_id"]] = item
    return overrides

def enrich_chinese_titles(raw, previous, reviewed, now, lookup=lookup_bangumi, max_new=MAX_NEW_LOOKUPS, sleeper=time.sleep):
    """Return durable translation registry (includes misses) and stats.

    Failure to reach the auxiliary Chinese source never corrupts the working
    Japanese schedule or deletes a previously sourced translation.
    """
    existing = _load_existing(previous)
    official = _load_official(reviewed)
    stamp = now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    unique = {}
    for row in raw:
        media_id = row["media_id"]
        unique.setdefault(media_id, row)
    attempted = 0
    matched = 0
    errors = 0
    for media_id, row in sorted(unique.items()):
        native = row["title"]
        if not valid_title(native):
            continue
        old = existing.get(media_id)
        manual = official.get(media_id)
        candidate = None
        if manual is not None:
            if normalized_title(manual["native_title"]) != normalized_title(native):
                raise ValueError(f"Reviewed official title original mismatch for {media_id}")
            candidate = {"zh_hans": manual["zh_hans"], "source": "official",
                         "source_url": manual["source_url"]}
        elif old and old["source"] != "official" and normalized_title(old["native_title"]) == normalized_title(native):
            # A verified match or a completed no-result lookup stays cached.
            # Rechecking source on every GitHub Action would be excessive.
            continue
        elif old and old["source"] == "official":
            # Do not lose official names when a manual override is temporarily
            # absent; corrections must be explicit and reviewed.
            continue
        elif attempted < max_new:
            attempted += 1
            try:
                candidate = lookup(native, row.get("season_year", now.year))
                sleeper(0.45)
            except TranslationLookupError:
                errors += 1
                if errors >= 2:
                    break  # Stop hammering a failing third-party API.
                continue
        else:
            continue

        zh_title = candidate["zh_hans"] if candidate else None
        source = candidate["source"] if candidate else "none"
        source_url = candidate["source_url"] if candidate else None
        changed = old is not None and (
            (old.get("zh_hans"), old["source"]) != (zh_title, source)
        )
        first = old is None
        revision = ((old["revision"] + 1) if changed else old["revision"]) if old else (1 if zh_title else 0)
        previous_updated = old["updated_at"] if old else stamp
        result = {
            "anilist_id": media_id,
            "native_title": native,
            "zh_hans": zh_title,
            "source": source,
            "source_url": source_url,
            "revision": revision,
            "updated_at": stamp if changed or first else previous_updated,
            "checked_at": stamp,
        }
        existing[media_id] = result
        if zh_title:
            matched += 1
    return {
        "schema_version": 1,
        "entries": sorted(existing.values(), key=lambda r: r["anilist_id"]),
    }, {"attempted": attempted, "matched_new_or_reviewed": matched, "lookup_errors": errors}

def title_for_entry(native, entry):
    if entry and valid_title(entry.get("zh_hans")):
        return entry["zh_hans"]
    return native

def localize_package(package, registry):
    """Localized ICS projection; keep canonical Japanese event state unchanged.

    Translation revisions are additive on top of AniList event revisions,
    so edits to Japanese schedules and to the translated name both cause
    SEQUENCE to increase while UID and original timing stay fixed.
    """
    from copy import deepcopy
    from .validation import validate_package
    entries = _load_existing(registry)
    localized = deepcopy(package)
    for event in localized["events"]:
        media_id = int(event["anime"]["series_id"].split(":", 1)[1])
        entry = entries.get(media_id)
        suffix = " · " + event["anime"]["episode_label"]
        if not event["title"].endswith(suffix):
            raise ValueError("Unexpected canonical AniList episode title")
        original = event["title"][:-len(suffix)]
        title = title_for_entry(original, entry)
        event["title"] = title + suffix
        if entry and entry["zh_hans"]:
            if entry["source"] == "official":
                origin = "经人工核对的官方中文译名"
            else:
                origin = "Bangumi 社区中文名称（不保证为官方译名）"
            event["description"] += f"\\n中文名称来源：{origin}；{entry['source_url']}"
            event["revision"] += entry["revision"]
            event["updated_at"] = max(event["updated_at"], entry["updated_at"])
        else:
            event["description"] += "\\n未核实可靠中文译名，保留日文原名。"
    validate_package(localized)
    return localized

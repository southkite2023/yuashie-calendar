"""Zero-network checks of Chinese anime titles, source integrity and ICS identity."""
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

from icalendar import Calendar
import pytest

from yuashie_calendar.anilist import normalize
from yuashie_calendar.render import component, project
from yuashie_calendar.zh_titles import (
    TranslationLookupError, enrich_chinese_titles, localize_package,
    lookup_bangumi,
)

NOW = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)
RAW = [{"media_id": 206401, "episode": 5, "airing": int((NOW + timedelta(days=1)).timestamp()),
        "title": "FX戦士くるみちゃん", "season": "FALL", "season_year": 2026}]
EMPTY = {"schema_version": 1, "entries": []}
OFFICIAL_EMPTY = {"schema_version": 1, "titles": []}


class MockOpen:
    def __init__(self, data):
        self.body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def read(self, size):
        return self.body[:size]


def search_response(subjects):
    return {"data": subjects, "total": len(subjects)}


def fake_opener(response):
    def opener(req, timeout):
        assert req.full_url.startswith("https://api.bgm.tv/v0/search/subjects")
        body = json.loads(req.data)
        assert body["keyword"] == "FX戦士くるみちゃん"
        assert body["filter"]["type"] == [2]
        return MockOpen(response)
    return opener


def test_exact_original_title_matching_does_not_invent_official_source():
    data = search_response([
        {"id": 1, "name": "FX戦士くるみちゃん", "name_cn": "FX战士久留美",
         "type": 2, "date": "2026-10-01"},
        {"id": 2, "name": "FX戦士くるみちゃん 2", "name_cn": "别的作品", "type": 2}
    ])
    matched = lookup_bangumi(RAW[0]["title"], 2026, opener=fake_opener(data))
    assert matched == {
        "zh_hans": "FX战士久留美", "source": "bangumi",
        "source_url": "https://bgm.tv/subject/1",
    }
    assert lookup_bangumi(RAW[0]["title"], 2026, opener=fake_opener(
        search_response([{"id": 1, "name": "FX戦士", "name_cn": "不确定", "type": 2}])
    )) is None
    assert lookup_bangumi(RAW[0]["title"], 2026, opener=fake_opener(
        search_response([
            {"id": 1, "name": RAW[0]["title"], "name_cn": "版本A", "type": 2},
            {"id": 2, "name": RAW[0]["title"], "name_cn": "版本B", "type": 2}
        ])
    )) is None


def test_community_title_cached_and_same_uid_and_date():
    lookup = lambda original, year: {
        "zh_hans": "FX战士久留美", "source": "bangumi",
        "source_url": "https://bgm.tv/subject/1"
    }
    first, stats = enrich_chinese_titles(RAW, EMPTY, OFFICIAL_EMPTY, NOW, lookup=lookup, sleeper=lambda _: None)
    assert stats["matched_new_or_reviewed"] == 1
    assert first["entries"][0]["revision"] == 1
    again, stats2 = enrich_chinese_titles(
        RAW, first, OFFICIAL_EMPTY, NOW + timedelta(hours=1),
        lookup=lambda *_: pytest.fail("cached title should not refetch"), sleeper=lambda _: None
    )
    assert stats2["attempted"] == 0
    assert again == first

    canonical = normalize(RAW, {"schema_version": 1, "events": []}, NOW)
    localized = localize_package(canonical, first)
    jp, cn = canonical["events"][0], localized["events"][0]
    assert jp["title"].startswith("FX戦士")
    assert cn["title"].startswith("FX战士久留美")
    assert cn["id"] == jp["id"] and cn["start"] == jp["start"]
    assert cn["revision"] == jp["revision"] + 1
    assert "社区" in cn["description"]
    e_native = component(jp, project(jp, "span"))
    e_chinese = component(cn, project(cn, "span"))
    assert str(e_native["UID"]) == str(e_chinese["UID"])
    assert e_native["DTSTART"] == e_chinese["DTSTART"]
    assert str(e_chinese["SEQUENCE"]) == "1"


def test_reviewed_official_overrides_community_and_increments_revision():
    community, _ = enrich_chinese_titles(RAW, EMPTY, OFFICIAL_EMPTY, NOW,
        lookup=lambda *_: {"zh_hans": "社区译名", "source": "bangumi",
                            "source_url": "https://bgm.tv/subject/1"},
        sleeper=lambda _: None)
    reviewed = {"schema_version": 1, "titles": [{
        "anilist_id": 206401, "native_title": "FX戦士くるみちゃん",
        "zh_hans": "官方译名（测试）", "source_url": "https://example.org/official",
        "evidence_note": "用于测试的官方发行页核对"
    }]}
    updated, _ = enrich_chinese_titles(RAW, community, reviewed, NOW + timedelta(days=1),
                                        lookup=lambda *_: pytest.fail("no lookup"), sleeper=lambda _: None)
    assert updated["entries"][0]["revision"] == 2
    assert updated["entries"][0]["source"] == "official"
    package = normalize(RAW, {"schema_version": 1, "events": []}, NOW)
    assert localize_package(package, updated)["events"][0]["revision"] == 2


def test_missing_translation_falls_back_to_original_and_source_failure_preserves_cache():
    empty, stats = enrich_chinese_titles(RAW, EMPTY, OFFICIAL_EMPTY, NOW,
                                          lookup=lambda *_: None, sleeper=lambda _: None)
    assert stats["attempted"] == 1
    assert empty["entries"][0]["zh_hans"] is None
    package = normalize(RAW, {"schema_version": 1, "events": []}, NOW)
    assert localize_package(package, empty)["events"][0]["title"] == package["events"][0]["title"]
    broken, stats = enrich_chinese_titles(
        RAW, EMPTY, OFFICIAL_EMPTY, NOW,
        lookup=lambda *_: (_ for _ in ()).throw(TranslationLookupError("offline")),
        sleeper=lambda _: None,
    )
    assert broken["entries"] == []
    assert stats["lookup_errors"] == 1


def test_manual_official_requires_evidence():
    manual = {"schema_version": 1, "titles": [{
        "anilist_id": 206401, "native_title": RAW[0]["title"], "zh_hans": "test",
        "source_url": "", "evidence_note": ""
    }]}
    with pytest.raises(ValueError, match="Official title"):
        enrich_chinese_titles(RAW, EMPTY, manual, NOW, sleeper=lambda _: None)

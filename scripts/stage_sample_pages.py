"""Stage only verified, fictional ICS data for GitHub Pages.

Do not upload the generator's state.json, generations/ or source fixtures.
"""
from __future__ import annotations

import shutil
from html import escape
from pathlib import Path

from icalendar import Calendar


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dist/sample-calendar/current/calendar/v1"
LIFECYCLE_SOURCE = ROOT / "dist/lifecycle-test-calendar/current/calendar/v1/anime"
REAL_SOURCE = ROOT / "dist/real-anime"
PUBLIC = ROOT / "dist/pages-site"
COUNTS = {
    "genshin": 4,
    "starrail": 1,
    "zzz": 1,
    "arknights": 1,
    "anime": 2,
    "game-releases": 2,
}
MODES = ("start", "span")


def verify(source: Path) -> int:
    try:
        cal = Calendar.from_ical(source.read_bytes())
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Unparseable ICS: {source}") from exc
    if str(cal.get("VERSION")) != "2.0":
        raise RuntimeError(f"Unexpected ICS VERSION: {source}")
    events = cal.walk("VEVENT")
    if not events:
        raise RuntimeError(f"Empty test calendar: {source}")
    for event in events:
        title = str(event.get("SUMMARY", ""))
        url = str(event.get("URL", ""))
        uid = str(event.get("UID", ""))
        if not (title.startswith("[虚构测试] ") or title.startswith("延期，时间待定：[虚构测试] ")):
            raise RuntimeError(f"An event is not visibly marked fictional: {title}")
        if not url.startswith("https://example.invalid/"):
            raise RuntimeError(f"Unexpected non-fictional source URL in {source}: {url}")
        if not uid.endswith("@calendar.yuashie.cn"):
            raise RuntimeError(f"Unstable test UID: {uid}")
    return len(events)


def verify_real(source: Path) -> int:
    """Independent validation: never confuse real and fictional events."""
    cal = Calendar.from_ical(source.read_bytes())
    if str(cal.get("VERSION")) != "2.0":
        raise RuntimeError(f"Invalid real ICS version: {source}")
    events = cal.walk("VEVENT")
    if not events:
        raise RuntimeError("No real events: do not publish an empty live feed")
    for event in events:
        title = str(event.get("SUMMARY", ""))
        url = str(event.get("URL", ""))
        uid = str(event.get("UID", ""))
        if "[虚构测试]" in title or not url.startswith("https://anilist.co/anime/"):
            raise RuntimeError(f"Invalid real provenance: {title}")
        if not uid.endswith("@calendar.yuashie.cn"):
            raise RuntimeError(f"Unstable real event UID: {uid}")
        if int(event.get("SEQUENCE", -1)) < 0:
            raise RuntimeError("Invalid real event revision")
    return len(events)


def main() -> None:
    if not SOURCE.is_dir():
        raise RuntimeError(f"Generate fictional calendars first: {SOURCE}")
    verified = []
    for feed, count in COUNTS.items():
        for mode in MODES:
            rel = Path("calendar/v1") / feed / f"{mode}.ics"
            src = SOURCE / feed / f"{mode}.ics"
            if verify(src) != count:
                raise RuntimeError(f"Unexpected event count in {src}")
            verified.append((rel, src))
    if sum(COUNTS.values()) * len(MODES) != 22 or len(verified) != 12:
        raise RuntimeError("The expected 12-file / 22-event test set has changed")

    # Separate lifecycle URLs never alter the 12 already-subscribed base feeds.
    for mode in MODES:
        rel = Path("calendar/v1/lifecycle-test") / f"{mode}.ics"
        src = LIFECYCLE_SOURCE / f"{mode}.ics"
        if verify(src) != 1:
            raise RuntimeError(f"Lifecycle test must have one event in {src}")
        verified.append((rel, src))

    counts = []
    for mode in MODES:
        src = REAL_SOURCE / f"{mode}.ics"
        counts.append(verify_real(src))
        verified.append((Path("calendar/real/v1/anime") / f"{mode}.ics", src))
    if counts[0] != counts[1]:
        raise RuntimeError("Real anime modes have different event counts")

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    links = []
    real_links = []
    for rel, src in verified:
        target = PUBLIC / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        element = (
            f'<li><a href="{escape(rel.as_posix())}">'
            f'{escape(rel.parent.name)} / {escape(rel.stem)}.ics</a></li>'
        )
        (real_links if rel.parts[1] == "real" else links).append(element)

    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    (PUBLIC / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Yuashie Calendar — 真实动漫与虚构测试</title>'
        '<style>body{max-width:780px;margin:5rem auto;padding:0 1.4rem;'
        'font:16px/1.75 system-ui,sans-serif}a{color:inherit}'
        'li{margin:.45rem 0}</style></head><body>'
        '<h1>Yuashie Calendar</h1>'
        '<h2>真实动漫播出排期（AniList 汇总）</h2>'
        '<p>来自 AniList 公开 API 的日本 TV 动漫未来两周播出安排。'
        '可能延播或调整，非电视台官方保证；当地显示时间由日历客户端转换。'
        '这是独立订阅，不会覆盖原来的虚构测试日历。</p>'
        '<p lang="en">REAL ANIME: Community-maintained AniList upcoming airings, '
        'not broadcaster-confirmed.</p>'
        '<ul>' + "".join(real_links) + '</ul>'
        '<h2>虚构测试订阅（2030 年）</h2>'
        '<p><strong>警告：</strong>以下所有游戏和动漫测试事件均为虚构数据，'
        '日期是 2030 年，不代表真实排期。</p>'
        '<p lang="en">FICTIONAL TEST DATA ONLY below.</p>'
        '<p><strong>lifecycle-test</strong> 是独立的改期/取消测试源，'
        '其内容会按测试阶段变化；其他 12 份虚构基础订阅不会受到影响。</p>'
        '<ul>' + "".join(links) + '</ul>'
        '<p><a href="https://github.com/southkite2023/yuashie-calendar">'
        'GitHub 仓库与测试说明</a></p></body></html>\n',
        encoding="utf-8",
    )
    staged = sorted(p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob("*") if p.is_file())
    allowed = {rel.as_posix() for rel, _ in verified} | {"index.html", "robots.txt", ".nojekyll"}
    if set(staged) != allowed:
        raise RuntimeError("Unexpected public contents: " + repr(staged))
    print(f"Verified 12 fictional base ICS + 2 lifecycle ICS + 2 real AniList ICS ({counts[0]} episodes).")
    print("Only ICS files, index.html, robots.txt and .nojekyll will be public; no ledger or state.json.")


if __name__ == "__main__":
    main()

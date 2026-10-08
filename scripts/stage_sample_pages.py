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
        if not title.startswith("[虚构测试] "):
            raise RuntimeError(f"An event is not visibly marked fictional: {title}")
        if not url.startswith("https://example.invalid/"):
            raise RuntimeError(f"Unexpected non-fictional source URL in {source}: {url}")
        if not uid.endswith("@calendar.yuashie.cn"):
            raise RuntimeError(f"Unstable test UID: {uid}")
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

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    links = []
    for rel, src in verified:
        target = PUBLIC / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        links.append(
            f'<li><a href="{escape(rel.as_posix())}">'
            f'{escape(rel.parent.name)} / {escape(rel.stem)}.ics</a></li>'
        )

    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    (PUBLIC / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Yuashie Calendar — 虚构测试订阅</title>'
        '<style>body{max-width:780px;margin:5rem auto;padding:0 1.4rem;'
        'font:16px/1.75 system-ui,sans-serif}a{color:inherit}'
        'li{margin:.45rem 0}</style></head><body>'
        '<h1>Yuashie Calendar · 虚构测试订阅</h1>'
        '<p><strong>警告：</strong>这里的所有事件均为虚构测试，'
        '日期是 2030 年，不代表游戏、动漫或新游的真实排期。'
        '请不要将这些内容用于正式提醒。</p>'
        '<p lang="en"><strong>FICTIONAL TEST DATA ONLY.</strong> '
        'All events are made up and dated 2030. '
        'Not a real release schedule or production feed.</p>'
        '<p>此页面仅用于检验日历客户端是否能订阅、解析 ICS。'
        '订阅地址可能需要你在日历软件中手动添加。</p>'
        '<ul>' + "".join(links) + '</ul>'
        '<p><a href="https://github.com/southkite2023/yuashie-calendar">'
        'GitHub 仓库与测试说明</a></p></body></html>\n',
        encoding="utf-8",
    )
    staged = sorted(p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob("*") if p.is_file())
    if len(staged) != 15 or any("state.json" in p or "generations/" in p for p in staged):
        raise RuntimeError("Unexpected public contents: " + repr(staged))
    print("Verified and staged 12 explicitly fictional ICS files, 22 VEVENTs.")
    print("Only ICS files, index.html, robots.txt and .nojekyll will be public.")


if __name__ == "__main__":
    main()

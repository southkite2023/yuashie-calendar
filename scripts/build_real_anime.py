"""Build actual upcoming AniList TV schedule as separate real ICS feeds."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar

from yuashie_calendar.anilist import fetch_window, normalize
from yuashie_calendar.render import project, render
from yuashie_calendar.validation import MODES, read_json, validate_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded AniList API -> live anime ICS + durable ledger")
    parser.add_argument("--ledger", type=Path, default=Path("data/real/anime-events.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/real-anime"))
    parser.add_argument("--snapshot", type=Path, default=Path("dist/anime-events-new.json"))
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    prior = read_json(args.ledger)
    episodes = fetch_window(now)
    package = normalize(episodes, prior, now)
    validate_package(package)

    records = {}
    for event in package["events"]:
        projections = {mode: project(event, mode) for mode in MODES}
        records[event["id"]] = {
            "event": event,
            "published": {mode: value for mode, value in projections.items() if value is not None},
        }
    files = render(records)
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        calendar = Calendar.from_ical(files[f"calendar/v1/anime/{mode}.ics"])
        # Distinguish operational AniList subscriptions from fictional test feeds.
        calendar["X-WR-CALNAME"] = f"Yuashie Calendar · AniList 动漫播出 · {mode}"
        parsed = calendar.walk("VEVENT")
        if len(parsed) != len(package["events"]):
            raise ValueError("Real calendar count mismatch")
        target = args.output / f"{mode}.ics"
        target.write_bytes(calendar.to_ical())

    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"AniList checked: {len(episodes)} upcoming JP TV episodes; "
          f"{len(package['events'])} retained; start/span ICS generated.")
    print("This is an aggregator schedule, not guaranteed broadcaster-confirmed times.")


if __name__ == "__main__":
    main()

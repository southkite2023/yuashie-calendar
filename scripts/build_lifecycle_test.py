"""Rebuild an isolated, reproducible lifecycle test feed.

Each CI run starts from the initial fixture and replays snapshots through the
committed stage. This keeps UID and SEQUENCE consistent without persisting
private state in the Pages artifact or depending on a GitHub Actions cache.
"""
from __future__ import annotations

import json
from pathlib import Path

from icalendar import Calendar

from yuashie_calendar.build import publish

ROOT = Path(__file__).resolve().parents[1]
STAGE_FILE = ROOT / "config/lifecycle-stage.txt"
FIXTURE = ROOT / "data/samples/lifecycle.json"
OUTPUT = ROOT / "dist/lifecycle-test-calendar"


def main() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    stages = data["steps"]
    names = [step["name"] for step in stages]
    selected = STAGE_FILE.read_text(encoding="utf-8").strip()
    if selected not in names:
        raise RuntimeError(f"Invalid lifecycle stage {selected!r}; choose one of: {', '.join(names)}")

    for step in stages[:names.index(selected) + 1]:
        publish({"schema_version": 1, "events": [step["event"]]}, OUTPUT, allow_samples=True)

    for mode in ("start", "span"):
        source = OUTPUT / "current/calendar/v1/anime" / f"{mode}.ics"
        entries = Calendar.from_ical(source.read_bytes()).walk("VEVENT")
        if len(entries) != 1:
            raise RuntimeError(f"Lifecycle {mode} fixture must contain exactly one event")
        entry = entries[0]
        exp = stages[names.index(selected)]["expected"]
        if str(entry.get("UID")) != exp["uid"]:
            raise RuntimeError("Lifecycle UID changed unexpectedly")
        if int(entry.get("SEQUENCE")) != exp["sequence"]:
            raise RuntimeError("Lifecycle SEQUENCE mismatch")
        if str(entry.get("STATUS")) != exp["status"]:
            raise RuntimeError("Lifecycle STATUS mismatch")
        if "[虚构测试]" not in str(entry.get("SUMMARY")):
            raise RuntimeError("Lifecycle title not marked fictional")
        print(f"Lifecycle {selected}: {mode} UID stable, sequence={exp['sequence']}, status={exp['status']}")

    print(f"Prepared isolated lifecycle stage: {selected}")


if __name__ == "__main__":
    main()

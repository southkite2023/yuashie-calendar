"""Run with PYTHONPATH=src python -m yuashie_calendar."""
import argparse
import sys
from pathlib import Path

from .build import publish
from .validation import ValidationError, read_json, validate_package


def main():
    parser = argparse.ArgumentParser(description='Validate CalendarEvent v1 and generate 12 offline ICS feeds (Python 3.11+, macOS/Linux).')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('dist/calendar'))
    parser.add_argument('--allow-samples', action='store_true', help='explicitly allow fictional fixture data')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    try:
        package = read_json(args.input)
        if args.validate_only:
            count = len(validate_package(package))
            print(f'Validated {count} events; no files written.')
        else:
            current = publish(package, args.output, allow_samples=args.allow_samples)
            print(f'Generated 12 ICS files: {current / "calendar/v1"}')
            print('Local files only; no website or subscription URL has been deployed.')
        return 0
    except (ValidationError, OSError, OverflowError) as exc:
        print(f'Build failed; previous publication preserved: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

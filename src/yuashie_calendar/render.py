"""Pure display projection and RFC 5545 serialization."""
from datetime import date, timedelta, timezone

from icalendar import Calendar, Event

from .validation import FEEDS, MODES, feed, timestamp


def project(e, mode):
    if e['schedule_state'] == 'tbd':
        return None
    if mode == 'start' or e['time_kind'] == 'date':
        start = date.fromisoformat(e['start']) if e['time_kind'] == 'date' else timestamp(e['start'], 'start').date()
        end = date.fromisoformat(e['end']) if mode == 'span' and e['end'] else start + timedelta(days=1)
        return {'kind': 'date', 'start': start.isoformat(), 'end': end.isoformat()}
    return {'kind': 'datetime', 'start': e['start'], 'end': e['end']}


def decode_boundary(value, kind):
    return date.fromisoformat(value) if kind == 'date' else timestamp(value, 'boundary').astimezone(timezone.utc)


def component(e, projection):
    event = Event()
    postponed = e['schedule_state'] == 'tbd'
    event.add('uid', e['id'] + '@calendar.yuashie.cn')
    event.add('summary', ('延期，时间待定：' if postponed else '') + e['title'])
    event.add('status', 'CANCELLED' if postponed else e['status'].upper())
    event.add('sequence', e['revision'])
    event.add('created', timestamp(e['created_at'], 'created_at'))
    for prop in ('last-modified', 'dtstamp'):
        event.add(prop, timestamp(e['updated_at'], 'updated_at'))
    event.add('dtstart', decode_boundary(projection['start'], projection['kind']))
    if projection['end'] is not None:
        event.add('dtend', decode_boundary(projection['end'], projection['kind']))
    details = [e.get('description', '')]
    if postponed:
        details.append('延期，时间待定；此取消标记保留上次发布的日期，恢复后将更新同一事件。')
    else:
        details.append(f"原始时间：{e['start']} → {e['end'] or '结束时间未知'}（{e['timezone']}；结束边界不含）")
    if e.get('date_hint'):
        details.append(e['date_hint'])
    details.extend(f"来源：{s['provider']} {s['url']}" for s in e['sources'])
    event.add('description', '\n'.join(x for x in details if x))
    event.add('url', e['url'])
    event.add('transp', 'TRANSPARENT')
    return event


def render(records):
    calendars = {}
    for name in FEEDS:
        for mode in MODES:
            cal = Calendar()
            cal.add('version', '2.0')
            cal.add('prodid', '-//yuashie-calendar//CalendarEvent v1//ZH')
            cal.add('calscale', 'GREGORIAN')
            cal.add('x-wr-calname', f'yuashie-calendar · {name} · {mode}')
            for event_id in sorted(records):
                record = records[event_id]
                e = record['event']
                projection = record['published'].get(mode)
                if feed(e) == name and projection:
                    cal.add_component(component(e, projection))
            calendars[f'calendar/v1/{name}/{mode}.ics'] = cal.to_ical()
    return calendars

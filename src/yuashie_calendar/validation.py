"""Validate the normalized event contract before touching any published output."""
import json
import re
from datetime import date, datetime
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

GAMES = ('genshin', 'starrail', 'zzz', 'arknights')
FEEDS = (*GAMES, 'anime', 'game-releases')
MODES = ('start', 'span')
TYPES = {'game': ('livestream', 'version_update', 'banner'),
         'anime': ('episode_airing',), 'release': ('game_release',)}
EXTENSIONS = {'game': {'game_id', 'server', 'version'},
              'anime': {'series_id', 'episode_id', 'episode_label', 'channel'},
              'release': {'game_id', 'platform', 'region', 'release_stage'}}
REQUIRED = set('id category event_type title status schedule_state time_kind start end timezone url sources revision created_at updated_at'.split())
OPTIONAL = {'description', 'date_hint', *TYPES}
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})\Z')
DAY = re.compile(r'\d{4}-\d{2}-\d{2}\Z')


class ValidationError(ValueError):
    """Input or persisted history violates the publication contract."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def text(value, field):
    require(isinstance(value, str) and bool(value.strip()), f'{field}: expected nonempty text')
    require(not any(ord(c) < 32 and c not in '\n\t' for c in value), f'{field}: control character')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise ValidationError(f'{field}: invalid Unicode') from exc


def timestamp(value, field, utc=False):
    require(isinstance(value, str) and STAMP.fullmatch(value), f'{field}: expected second-precision timestamp with offset')
    require(not utc or value.endswith('Z'), f'{field}: must use UTC Z')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValidationError(f'{field}: invalid timestamp') from exc


def https(value, field):
    text(value, field)
    try:
        parsed = urlsplit(value)
        require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                and not any(c.isspace() for c in value), f'{field}: expected HTTPS URL without credentials')
        parsed.port
    except ValueError as exc:
        raise ValidationError(f'{field}: invalid URL') from exc


def read_json(path):
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            require(k not in obj, f'duplicate JSON key: {k}')
            obj[k] = v
        return obj
    def bad_constant(value):
        raise ValidationError(f'non-JSON number: {value}')
    try:
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f'{path}: invalid UTF-8 JSON') from exc


def validate_event(e):
    require(isinstance(e, dict), 'event must be an object')
    require(REQUIRED <= e.keys(), f'missing fields: {sorted(REQUIRED - e.keys())}')
    require(not e.keys() - REQUIRED - OPTIONAL, 'unknown event fields')
    for k in ('id', 'category', 'event_type', 'title', 'status', 'schedule_state', 'time_kind', 'timezone'):
        text(e[k], k)
    try:
        uid = UUID(e['id'])
        require(uid.version == 4 and str(uid) == e['id'], 'id: expected canonical UUID v4')
    except ValueError as exc:
        raise ValidationError('id: expected canonical UUID v4') from exc
    category = e['category']
    require(category in TYPES, 'invalid category')
    require(e['event_type'] in TYPES[category], 'event_type does not match category')
    require(set(e) & set(TYPES) == {category}, 'category extension mismatch')
    extension = e[category]
    require(isinstance(extension, dict), 'extension must be an object')
    keys = EXTENSIONS[category] | ({'banner_id'} if e['event_type'] == 'banner' else set())
    require(set(extension) == keys, 'invalid extension fields')
    for k, v in extension.items():
        text(v, k)
    if category == 'game':
        require(extension['game_id'] in GAMES, 'unknown game_id')
    else:
        key = 'series_id' if category == 'anime' else 'game_id'
        require(re.fullmatch(r'[^\s:]+:[^\s]+', extension[key]), f'{key}: expected namespaced ID')
    if category == 'release':
        require(extension['release_stage'] == 'full_release', 'unsupported release_stage')
    require(e['status'] in ('tentative', 'confirmed', 'cancelled'), 'invalid status')
    require(type(e['revision']) is int and e['revision'] >= 0, 'revision must be a nonnegative integer')
    created = timestamp(e['created_at'], 'created_at', utc=True)
    updated = timestamp(e['updated_at'], 'updated_at', utc=True)
    require(updated >= created, 'updated_at precedes created_at')
    for k in ('description', 'date_hint'):
        if k in e:
            text(e[k], k)
    https(e['url'], 'url')
    require(isinstance(e['sources'], list) and e['sources'], 'at least one source is required')
    seen = set()
    for s in e['sources']:
        require(isinstance(s, dict) and set(s) == {'provider', 'source_id', 'url', 'checked_at', 'authority'}, 'invalid source fields')
        for k in ('provider', 'source_id', 'authority'):
            text(s[k], k)
        require(s['authority'] in ('official', 'wiki', 'aggregator', 'manual'), 'invalid source authority')
        https(s['url'], 'source.url')
        require(timestamp(s['checked_at'], 'checked_at', utc=True) >= created, 'checked_at precedes creation')
        key = (s['provider'], s['source_id'])
        require(key not in seen, 'duplicate source')
        seen.add(key)
    try:
        zone = ZoneInfo(e['timezone'])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError('timezone: expected IANA time zone') from exc
    if e['schedule_state'] == 'tbd':
        require(e['time_kind'] == 'unknown' and e['start'] is None and e['end'] is None, 'tbd must have unknown time and null boundaries')
        return
    require(e['schedule_state'] == 'scheduled' and e['time_kind'] in ('date', 'datetime'), 'invalid schedule/time kind')
    require(e['start'] is not None, 'scheduled event needs start')
    bounds = []
    for k in ('start', 'end'):
        value = e[k]
        if value is None:
            continue
        if e['time_kind'] == 'date':
            require(isinstance(value, str) and DAY.fullmatch(value), f'{k}: expected YYYY-MM-DD')
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError(f'{k}: invalid date') from exc
        else:
            parsed = timestamp(value, k)
            local = parsed.astimezone(zone)
            require(parsed.utcoffset() == local.utcoffset() and parsed.replace(tzinfo=None) == local.replace(tzinfo=None), f'{k}: offset or local time inconsistent with timezone')
        bounds.append(parsed)
    require(len(bounds) < 2 or bounds[1] > bounds[0], 'end must be later than start')


def scope(e):
    """Stable matching scope, excluding corrected display labels."""
    ext = e[e['category']]
    keys = {'game': ('game_id', 'server', 'version', 'banner_id'),
            'anime': ('series_id', 'episode_id', 'channel'),
            'release': ('game_id', 'platform', 'region', 'release_stage')}[e['category']]
    return (e['category'], e['event_type'], *(ext.get(k) for k in keys))


def validate_package(package):
    require(isinstance(package, dict) and set(package) == {'schema_version', 'events'}, 'expected schema_version and events only')
    require(type(package['schema_version']) is int and package['schema_version'] == 1, 'unsupported schema_version')
    events = package['events']
    require(isinstance(events, list) and events, 'empty input rejected; keeping the previous publication')
    ids, aliases = set(), {}
    for index, e in enumerate(events):
        try:
            validate_event(e)
            require(e['id'] not in ids, 'duplicate event id')
            ids.add(e['id'])
            for s in e['sources']:
                key = (s['provider'], s['source_id'], scope(e))
                require(key not in aliases or aliases[key] == e['id'], 'source identity maps to multiple event IDs')
                aliases[key] = e['id']
        except ValidationError as exc:
            raise ValidationError(f'events[{index}]: {exc}') from exc
    return events


def feed(e):
    return e['game']['game_id'] if e['category'] == 'game' else ('anime' if e['category'] == 'anime' else 'game-releases')

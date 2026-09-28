import copy
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest
import vobject
from icalendar import Calendar

from yuashie_calendar.build import publish
from yuashie_calendar.validation import ValidationError, read_json, validate_package

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'data/samples'


def fixture(name):
    return json.loads((SAMPLES / name).read_text())


@pytest.fixture
def package():
    return fixture('events.json')


def build(package, path):
    return publish(package, path, allow_samples=True)


def as_package(event):
    return {'schema_version': 1, 'events': [event]}


def parse(current, feed, mode):
    return Calendar.from_ical((current / f'calendar/v1/{feed}/{mode}.ics').read_bytes()).walk('VEVENT')


def assert_projection(event, expected):
    assert event['DTSTART'].to_ical().decode() == expected['dtstart']
    assert event['DTSTART'].params.get('VALUE', 'DATE-TIME') == expected['value_type']
    if expected['dtend'] is None:
        assert 'DTEND' not in event
    else:
        assert event['DTEND'].to_ical().decode() == expected['dtend']


def snapshot(current):
    return {str(p.relative_to(current)): p.read_bytes() for p in current.rglob('*') if p.is_file()}


def test_baseline_matches_all_hand_authored_expectations(package, tmp_path):
    original = copy.deepcopy(package)
    current = build(package, tmp_path)
    expected = fixture('expected-projections.json')
    assert len(list(current.rglob('*.ics'))) == 12
    for mode in ('start', 'span'):
        found = {}
        for feed, count in expected['feed_counts_per_mode'].items():
            items = parse(current, feed, mode)
            assert len(items) == count
            found.update({str(e['UID']): e for e in items})
        assert len(found) == expected['exported_per_mode']
        for e in expected['events']:
            actual = found[e['uid']]
            assert_projection(actual, e[mode])
            assert str(actual['STATUS']) == e['status']
            assert int(actual['SEQUENCE']) == e['sequence']
        for e in expected['omitted']:
            assert e['event_id'] + '@calendar.yuashie.cn' not in found
    assert package == original


def test_independent_parser_and_wire_format(package, tmp_path):
    current = build(package, tmp_path)
    for path in current.rglob('*.ics'):
        raw = path.read_bytes()
        assert raw.endswith(b'END:VCALENDAR\r\n')
        assert b'\n' not in raw.replace(b'\r\n', b'')
        assert all(len(line) <= 75 for line in raw.split(b'\r\n'))
        parsed = vobject.readOne(raw.decode('utf-8'))
        assert str(parsed.version.value) == '2.0'
        for e in parsed.contents.get('vevent', []):
            assert e.uid.value.endswith('@calendar.yuashie.cn')
            assert e.transp.value == 'TRANSPARENT'
            assert 'valarm' not in e.contents
            if isinstance(e.dtstart.value, datetime):
                assert e.dtstart.value.utcoffset().total_seconds() == 0
            else:
                assert isinstance(e.dtstart.value, date)
        assert 'method' not in parsed.contents


def test_lifecycle_persists_across_builds(tmp_path):
    steps = fixture('lifecycle.json')['steps']
    before = None
    for step in steps:
        current = build(as_package(step['event']), tmp_path)
        for mode in ('start', 'span'):
            items = parse(current, 'anime', mode)
            assert len(items) == 1
            e = items[0]
            expected = step['expected']
            assert_projection(e, expected[mode])
            assert str(e['UID']) == expected['uid']
            assert int(e['SEQUENCE']) == expected['sequence']
            assert str(e['STATUS']) == expected['status']
            assert e['DTSTAMP'].dt == datetime.fromisoformat(expected['dtstamp'].replace('Z', '+00:00'))
            assert e['LAST-MODIFIED'].dt == e['DTSTAMP'].dt
            assert str(e['SUMMARY']).count('延期，时间待定：') <= 1
        files = {str(p.relative_to(current)): p.read_bytes() for p in current.rglob('*.ics')}
        if step['name'] == 'checked-only':
            assert files == before
        before = files


@pytest.mark.parametrize('case', fixture('invalid-events.json')['cases'], ids=lambda c: c['name'])
def test_invalid_fixtures_rejected(case):
    with pytest.raises(ValidationError):
        validate_package(as_package(case['event']))


def test_repeat_is_byte_identical_and_does_not_switch_generation(package, tmp_path):
    current = build(package, tmp_path)
    previous = current.resolve()
    content = snapshot(current)
    build(copy.deepcopy(package), tmp_path)
    assert current.resolve() == previous
    assert snapshot(current) == content


@pytest.mark.parametrize('failure', ['invalid', 'empty', 'revision', 'timestamp', 'io'])
def test_failed_build_keeps_entire_previous_generation(package, tmp_path, failure):
    current = build(package, tmp_path)
    target, content = current.resolve(), snapshot(current)
    changed = copy.deepcopy(package)
    if failure == 'invalid':
        changed['events'][0]['start'] = 'bad'
    elif failure == 'empty':
        changed['events'] = []
    elif failure == 'revision':
        changed['events'][0]['title'] += ' changed'
    elif failure == 'timestamp':
        changed['events'][0].update(title='changed', revision=1)
    else:
        changed['events'][0].update(title='changed', revision=1, updated_at='2030-01-02T00:00:00Z')
    if failure == 'io':
        with patch('yuashie_calendar.build.os.replace', side_effect=OSError('simulated failure')):
            with pytest.raises(OSError):
                build(changed, tmp_path)
    else:
        with pytest.raises(ValidationError):
            build(changed, tmp_path)
    assert current.resolve() == target
    assert snapshot(current) == content


def test_missing_event_is_retained_not_cancelled(package, tmp_path):
    current = build(package, tmp_path)
    before = snapshot(current)
    build(as_package(package['events'][0]), tmp_path)
    assert snapshot(current) == before


def test_cross_source_alias_keeps_uid(package, tmp_path):
    current = build(package, tmp_path)
    case = fixture('source-scenarios.json')['cases'][0]
    e = next(e for e in package['events'] if e['id'] == case['existing_event_id'])
    e['sources'].append(case['additional_source'])
    e.update(revision=1, updated_at='2030-01-02T00:00:00Z')
    build(as_package(e), tmp_path)
    items = parse(current, 'genshin', 'span')
    assert len(items) == 4
    actual = next(x for x in items if str(x['UID']).startswith(e['id']))
    assert int(actual['SEQUENCE']) == 1
    assert 'sample-wiki' in str(actual['DESCRIPTION'])


def test_source_alias_cannot_silently_change_uuid(package, tmp_path):
    current = build(package, tmp_path)
    old = snapshot(current)
    changed = copy.deepcopy(package['events'][0])
    changed['id'] = str(uuid4())
    with pytest.raises(ValidationError, match='source identity'):
        build(as_package(changed), tmp_path)
    assert snapshot(current) == old


def test_special_characters_round_trip_and_long_unicode_folding(package, tmp_path):
    e = package['events'][0]
    e['title'] = '虚构，测试;逗号,反斜杠\\中文' * 30
    e['description'] = '第一行\n第二行,分号;反斜杠\\中文'
    current = build(as_package(e), tmp_path)
    raw = (current / 'calendar/v1/genshin/start.ics').read_bytes()
    parsed = vobject.readOne(raw.decode()).vevent
    assert parsed.summary.value == e['title']
    assert parsed.description.value.startswith(e['description'])
    assert all(len(line) <= 75 for line in raw.split(b'\r\n'))


@pytest.mark.parametrize('change', [
    {'revision': True}, {'start': '2030-02-30T20:00:00+08:00'},
    {'timezone': 'Not/AZone'}, {'sources': 'not a list'},
    {'url': 'https://user:password@example.com'}, {'category': 'unknown'},
    {'end': '2030-01-25'}, {'description': 'bad\x00text'},
])
def test_additional_malformed_values(package, change):
    e = package['events'][0]
    e.update(change)
    with pytest.raises(ValidationError):
        validate_package(as_package(e))


@pytest.mark.parametrize('raw', ['{"schema_version":1,"schema_version":1,"events":[]}', '{"x": NaN}', '{broken'])
def test_malformed_json_rejected(tmp_path, raw):
    path = tmp_path / 'input.json'
    path.write_text(raw)
    with pytest.raises(ValidationError):
        read_json(path)


def test_explicit_dst_offset_resolves_fold_but_gap_is_rejected(package):
    e = package['events'][0]
    e['timezone'] = 'America/New_York'
    for start in ('2030-11-03T01:30:00-04:00', '2030-11-03T01:30:00-05:00'):
        e['start'] = start
        validate_package(as_package(e))
    e['start'] = '2030-03-10T02:30:00-05:00'
    with pytest.raises(ValidationError):
        validate_package(as_package(e))


def test_corrupt_history_does_not_reset(package, tmp_path):
    current = build(package, tmp_path)
    (current / 'state.json').write_text('{broken')
    original = current.resolve()
    with pytest.raises(ValidationError):
        build(package, tmp_path)
    assert current.resolve() == original


def test_sample_guard(package, tmp_path):
    with pytest.raises(ValidationError, match='allow-samples'):
        publish(package, tmp_path)
    assert not (tmp_path / 'current').exists()


def test_cli_success_and_failure(tmp_path):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    cmd = [sys.executable, '-m', 'yuashie_calendar', '--input', str(SAMPLES / 'events.json'), '--output', str(tmp_path / 'out')]
    valid = subprocess.run(cmd + ['--validate-only'], env=env, capture_output=True, text=True)
    assert valid.returncode == 0
    assert not (tmp_path / 'out').exists()
    denied = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert denied.returncode == 1 and 'allow-samples' in denied.stderr
    good = subprocess.run(cmd + ['--allow-samples'], env=env, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert len(list((tmp_path / 'out/current').rglob('*.ics'))) == 12


def test_lock_rejects_concurrent_writer(package, tmp_path):
    import fcntl
    with (tmp_path / '.build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValidationError, match='another build'):
            build(package, tmp_path)
    assert not (tmp_path / 'current').exists()


def test_restart_in_fresh_process_uses_history(tmp_path):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    steps = fixture('lifecycle.json')['steps']
    for step in steps[:3]:
        path = tmp_path / 'input.json'
        path.write_text(json.dumps(as_package(step['event'])))
        result = subprocess.run([sys.executable, '-m', 'yuashie_calendar', '--input', str(path), '--output', str(tmp_path / 'out'), '--allow-samples'], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    e = parse(tmp_path / 'out/current', 'anime', 'span')[0]
    assert str(e['STATUS']) == 'CANCELLED'
    assert int(e['SEQUENCE']) == 2
    assert_projection(e, steps[2]['expected']['span'])


def test_corrupt_projection_keeps_previous_pointer(package, tmp_path):
    current = build(package, tmp_path)
    path = current / 'state.json'
    state = json.loads(path.read_text())
    record = next(iter(state['records'].values()))
    record['published']['start']['end'] = 'nonsense'
    path.write_text(json.dumps(state))
    original = current.resolve()
    with pytest.raises(ValidationError):
        build(package, tmp_path)
    assert current.resolve() == original


def test_missing_history_projection_is_not_silently_dropped(package, tmp_path):
    current = build(package, tmp_path)
    path = current / 'state.json'
    state = json.loads(path.read_text())
    state['records'][package['events'][0]['id']]['published'] = {}
    path.write_text(json.dumps(state))
    with pytest.raises(ValidationError, match='history projection'):
        build(as_package(package['events'][1]), tmp_path)

"""Persist revisions and publish one complete generation with an atomic pointer."""
import copy
import fcntl
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from .render import project, render
from .validation import MODES, ValidationError, feed, read_json, require, timestamp, validate_package


def semantic(e):
    value = copy.deepcopy(e)
    for k in ('revision', 'created_at', 'updated_at'):
        value.pop(k)
    for source in value['sources']:
        source.pop('checked_at')
    return value


def merge(events, previous):
    records = copy.deepcopy(previous)
    for event in events:
        e = copy.deepcopy(event)
        old = records.get(e['id'])
        if old:
            before = old['event']
            require(e['created_at'] == before['created_at'], 'created_at cannot change')
            require(feed(e) == feed(before), 'existing event cannot move between feeds')
            changed = semantic(e) != semantic(before)
            if changed:
                require(e['revision'] > before['revision'], 'semantic changes require a higher revision')
                require(timestamp(e['updated_at'], 'updated_at') > timestamp(before['updated_at'], 'updated_at'), 'semantic changes require a later updated_at')
            else:
                require(e['revision'] == before['revision'] and e['updated_at'] == before['updated_at'], 'unchanged event must keep revision and updated_at')
            published = copy.deepcopy(old['published'])
        else:
            require(e['revision'] == 0, 'new event must start at revision 0; restore history before applying later revisions')
            published = {}
        for mode in MODES:
            projection = project(e, mode)
            if projection:
                published[mode] = projection
        records[e['id']] = {'event': e, 'published': published}
    # Catch alias collisions against retained events, not just the incoming batch.
    validate_package({'schema_version': 1, 'events': [r['event'] for r in records.values()]})
    return records


def load_history(current):
    if not current.exists():
        require(not current.is_symlink(), 'current is a broken symlink; restore publication history')
        return {}
    state = read_json(current / 'state.json')
    require(isinstance(state, dict) and type(state.get('state_version')) is int and state['state_version'] == 1 and isinstance(state.get('records'), dict), 'invalid history format')
    records = state['records']
    require(records, 'empty publication history')
    try:
        validate_package({'schema_version': 1, 'events': [r['event'] for r in records.values()]})
        for key, record in records.items():
            require(key == record['event']['id'] and isinstance(record['published'], dict), 'invalid history record')
            require(set(record['published']) in (set(), set(MODES)), 'incomplete history modes')
            if record['event']['schedule_state'] == 'scheduled':
                require(record['published'] == {mode: project(record['event'], mode) for mode in MODES}, 'history projection does not match event')
            for mode, projection in record['published'].items():
                require(isinstance(projection, dict) and set(projection) == {'kind', 'start', 'end'}, 'invalid history projection')
                check = copy.deepcopy(record['event'])
                check.update(time_kind=projection['kind'], start=projection['start'], end=projection['end'], schedule_state='scheduled')
                # start-mode dates have already been projected; valid date boundaries suffice.
                validate_package({'schema_version': 1, 'events': [check]})
    except (KeyError, TypeError) as exc:
        raise ValidationError('invalid history record') from exc
    return records


def publish(package, output, *, allow_samples=False):
    events = validate_package(package)
    sample_input = any('sample' in s['provider'] or '.invalid' in s['url'] for e in events for s in e['sources'])
    require(allow_samples or not sample_input, 'fictional samples require --allow-samples')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / '.build.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValidationError('another build is using this output directory') from exc
        current = output / 'current'
        require(not current.exists() or current.is_symlink(), 'current must be a managed symlink')
        previous = load_history(current)
        records = merge(events, previous)
        retained_samples = any('sample' in s['provider'] or '.invalid' in s['url']
                               for r in records.values() for s in r['event']['sources'])
        require(allow_samples or not retained_samples, 'retained fictional history requires --allow-samples')
        files = render(records)
        if records == previous and all((current / name).read_bytes() == data for name, data in files.items()):
            return current
        generations = output / 'generations'
        generations.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='build-', dir=generations))
        pointer = output / ('.current-' + uuid4().hex)
        try:
            for name, data in files.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (stage / 'state.json').write_text(json.dumps({'state_version': 1, 'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            pointer.symlink_to(Path('generations') / stage.name, target_is_directory=True)
            os.replace(pointer, current)
        except BaseException:
            pointer.unlink(missing_ok=True)
            shutil.rmtree(stage)
            raise
        return current

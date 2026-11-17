from __future__ import annotations

import json
from datetime import datetime, timezone

from oracle_db_unloader.state import (
    get_last_unload_at,
    load_state,
    save_state,
    set_last_unload_at,
    state_path,
)


def test_missing_state_file(tmp_path):
    assert get_last_unload_at(load_state(tmp_path, 'SCOTT'), 'TABLE') is None


def test_watermark_roundtrip_per_type(tmp_path):
    when = datetime(2026, 11, 16, 8, 0, 0, 123456)
    later = datetime(2026, 11, 16, 9, 0, 0, 654321)
    state = set_last_unload_at({}, when, 'TABLE')
    state = set_last_unload_at(state, later, 'VIEW')
    save_state(tmp_path, 'scott', state)
    loaded = load_state(tmp_path, 'SCOTT')
    assert get_last_unload_at(loaded, 'TABLE') == datetime(2026, 11, 16, 8, 0, 0)
    assert get_last_unload_at(loaded, 'VIEW') == datetime(2026, 11, 16, 9, 0, 0)
    assert state_path(tmp_path, 'SCOTT').is_file()
    assert not (tmp_path / '.unloader_state.json').exists()
    assert get_last_unload_at(load_state(tmp_path, 'HR'), 'TABLE') is None


def test_old_schema_watermark_is_fallback():
    when = datetime(2026, 11, 16, 8, 0, 0)
    state = {'last_unload_at': when.isoformat()}
    assert get_last_unload_at(state, 'TABLE') == when


def test_aware_timestamp_is_stored_naive():
    when = datetime(2026, 11, 16, 8, 0, 0, 1, tzinfo=timezone.utc)
    loaded = get_last_unload_at(
        set_last_unload_at({}, when, 'TABLE'),
        'TABLE',
    )
    assert loaded == datetime(2026, 11, 16, 8, 0, 0)
    assert loaded.tzinfo is None


def test_legacy_root_state_is_split_on_save(tmp_path):
    when = datetime(2026, 11, 16, 8, 0, 0)
    later = datetime(2026, 11, 16, 9, 0, 0)
    (tmp_path / '.unloader_state.json').write_text(
        json.dumps(
            {
                'schemas': {
                    'SCOTT': {
                        'types': {'TABLE': {'last_ddl_time': when.isoformat()}}
                    },
                    'HR': {
                        'types': {'TABLE': {'last_ddl_time': later.isoformat()}}
                    },
                }
            }
        ),
        encoding='utf-8',
    )
    scott = load_state(tmp_path, 'SCOTT')
    assert get_last_unload_at(scott, 'TABLE') == when
    save_state(tmp_path, 'SCOTT', scott)
    assert get_last_unload_at(load_state(tmp_path, 'HR'), 'TABLE') == later
    assert not (tmp_path / '.unloader_state.json').exists()
    assert state_path(tmp_path, 'HR').is_file()

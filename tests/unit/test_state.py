from __future__ import annotations

from datetime import datetime, timezone

from oracle_db_unloader.state import (
    get_last_unload_at,
    load_state,
    save_state,
    set_last_unload_at,
    state_path,
)


def test_missing_state_file(tmp_path):
    state = load_state(tmp_path)
    assert state == {'schemas': {}}
    assert get_last_unload_at(state, 'SCOTT', 'TABLE') is None


def test_watermark_roundtrip_per_type(tmp_path):
    when = datetime(2026, 11, 16, 8, 0, 0, 123456)
    later = datetime(2026, 11, 16, 9, 0, 0, 654321)
    state = set_last_unload_at({'schemas': {}}, 'scott', when, 'TABLE')
    state = set_last_unload_at(state, 'scott', later, 'VIEW')
    save_state(tmp_path, state)
    loaded = load_state(tmp_path)
    assert get_last_unload_at(loaded, 'SCOTT', 'TABLE') == datetime(2026, 11, 16, 8, 0, 0)
    assert get_last_unload_at(loaded, 'SCOTT', 'VIEW') == datetime(2026, 11, 16, 9, 0, 0)
    payload = state_path(tmp_path).read_text(encoding='utf-8')
    assert '2026-11-16T08:00:00' in payload
    assert '.123456' not in payload
    assert 'last_ddl_time' in payload


def test_old_schema_watermark_is_fallback():
    when = datetime(2026, 11, 16, 8, 0, 0)
    state = {
        'schemas': {
            'SCOTT': {'last_unload_at': when.isoformat()},
        }
    }
    assert get_last_unload_at(state, 'SCOTT', 'TABLE') == when


def test_aware_timestamp_is_stored_naive():
    when = datetime(2026, 11, 16, 8, 0, 0, 1, tzinfo=timezone.utc)
    state = set_last_unload_at({'schemas': {}}, 'HR', when, 'TABLE')
    loaded = get_last_unload_at(state, 'HR', 'TABLE')
    assert loaded == datetime(2026, 11, 16, 8, 0, 0)
    assert loaded.tzinfo is None


def test_type_watermark_does_not_clobber_other_types():
    when = datetime(2026, 11, 16, 8, 0, 0)
    later = datetime(2026, 11, 16, 9, 0, 0)
    state = set_last_unload_at({'schemas': {}}, 'HR', when, 'TABLE')
    state = set_last_unload_at(state, 'HR', later, 'PACKAGE')
    assert get_last_unload_at(state, 'HR', 'TABLE') == when
    assert get_last_unload_at(state, 'SCOTT', 'TABLE') is None

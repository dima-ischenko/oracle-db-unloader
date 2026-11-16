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
    assert get_last_unload_at(state, 'SCOTT') is None


def test_watermark_roundtrip(tmp_path):
    when = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)
    state = set_last_unload_at({'schemas': {}}, 'scott', when)
    save_state(tmp_path, state)
    assert state_path(tmp_path).is_file()
    loaded = load_state(tmp_path)
    assert get_last_unload_at(loaded, 'SCOTT') == when
    assert '2026-11-16T08:00:00+00:00' in state_path(tmp_path).read_text(
        encoding='utf-8'
    )


def test_failed_schema_does_not_have_to_advance():
    when = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)
    state = set_last_unload_at({'schemas': {}}, 'HR', when)
    assert get_last_unload_at(state, 'SCOTT') is None
    assert get_last_unload_at(state, 'HR') == when

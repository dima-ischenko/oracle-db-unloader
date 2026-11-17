from __future__ import annotations

from datetime import datetime, timezone

from oracle_db_unloader.state import get_last_unload_at, load_state, save_state, set_last_unload_at


def test_missing_state_file(tmp_path):
    assert get_last_unload_at(load_state(tmp_path), 'SCOTT', 'TABLE') is None


def test_watermark_roundtrip_per_type(tmp_path):
    when = datetime(2026, 11, 16, 8, 0, 0, 123456)
    later = datetime(2026, 11, 16, 9, 0, 0, 654321)
    state = set_last_unload_at({'schemas': {}}, 'scott', when, 'TABLE')
    state = set_last_unload_at(state, 'scott', later, 'VIEW')
    save_state(tmp_path, state)
    loaded = load_state(tmp_path)
    assert get_last_unload_at(loaded, 'SCOTT', 'TABLE') == datetime(2026, 11, 16, 8, 0, 0)
    assert get_last_unload_at(loaded, 'SCOTT', 'VIEW') == datetime(2026, 11, 16, 9, 0, 0)


def test_old_schema_watermark_is_fallback():
    when = datetime(2026, 11, 16, 8, 0, 0)
    state = {'schemas': {'SCOTT': {'last_unload_at': when.isoformat()}}}
    assert get_last_unload_at(state, 'SCOTT', 'TABLE') == when


def test_aware_timestamp_is_stored_naive():
    when = datetime(2026, 11, 16, 8, 0, 0, 1, tzinfo=timezone.utc)
    loaded = get_last_unload_at(
        set_last_unload_at({'schemas': {}}, 'HR', when, 'TABLE'),
        'HR',
        'TABLE',
    )
    assert loaded == datetime(2026, 11, 16, 8, 0, 0)
    assert loaded.tzinfo is None

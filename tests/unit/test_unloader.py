from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from oracle_db_unloader.inventory import DbObject
from oracle_db_unloader.state import get_last_unload_at, load_state
from oracle_db_unloader.unloader import UnloadError, unload


def _obj(schema, name, object_type='TABLE', when=None):
    return DbObject(
        schema=schema,
        owner=schema,
        name=name,
        object_type=object_type,
        last_ddl_time=when or datetime(2026, 11, 16, 8, 0, 0),
    )


def test_first_exception_stops_remaining_types_and_schemas(monkeypatch, tmp_path, caplog):
    inventory = {
        'SCOTT': [_obj('SCOTT', 'EMP'), _obj('SCOTT', 'V_EMP', 'VIEW')],
        'HR': [_obj('HR', 'DEPT')],
    }
    written = []

    def fake_inventory(_engine, schema):
        return list(inventory[schema])

    def fake_write(_engine, obj, output_dir):
        written.append((obj.owner, obj.object_type, obj.name))
        if obj.owner == 'SCOTT' and obj.object_type == 'VIEW':
            raise RuntimeError('view boom')
        path = output_dir / obj.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('-- ok\n', encoding='utf-8')

    monkeypatch.setattr('oracle_db_unloader.unloader.fetch_inventory', fake_inventory)
    monkeypatch.setattr('oracle_db_unloader.unloader.write_object', fake_write)

    caplog.set_level(logging.INFO, logger='oracle_db_unloader')
    with pytest.raises(UnloadError, match='VIEW SCOTT.V_EMP'):
        unload(
            MagicMock(),
            ['SCOTT', 'HR'],
            tmp_path,
            object_types=['table', 'view'],
            max_connections=1,
        )

    assert written == [('SCOTT', 'TABLE', 'EMP'), ('SCOTT', 'VIEW', 'V_EMP')]
    scott = load_state(tmp_path, 'SCOTT')
    assert get_last_unload_at(scott, 'TABLE') is not None
    assert get_last_unload_at(scott, 'VIEW') is None
    assert get_last_unload_at(load_state(tmp_path, 'HR'), 'TABLE') is None


def test_same_type_failure_does_not_write_remaining(monkeypatch, tmp_path):
    written = []

    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [_obj('SCOTT', 'T1'), _obj('SCOTT', 'T2')],
    )

    def fake_write(_engine, obj, output_dir):
        written.append(obj.name)
        if obj.name == 'T1':
            raise RuntimeError('boom')

    monkeypatch.setattr('oracle_db_unloader.unloader.write_object', fake_write)

    with pytest.raises(UnloadError, match='TABLE SCOTT.T1'):
        unload(
            MagicMock(),
            ['SCOTT'],
            tmp_path,
            object_types=['table'],
            max_connections=1,
        )
    assert written == ['T1']


def test_progress_and_summary_logging(monkeypatch, tmp_path, caplog):
    emp = _obj('SCOTT', 'EMP')
    gone = tmp_path / 'scott' / 'tables' / 'gone.sql'
    gone.parent.mkdir(parents=True)
    gone.write_text('-- gone\n', encoding='utf-8')

    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [emp],
    )

    def fake_write(_engine, obj, output_dir):
        path = output_dir / obj.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('-- emp\n', encoding='utf-8')

    monkeypatch.setattr('oracle_db_unloader.unloader.write_object', fake_write)

    caplog.set_level(logging.INFO, logger='oracle_db_unloader')
    unload(
        MagicMock(),
        ['SCOTT'],
        tmp_path,
        object_types=['table'],
        max_connections=1,
    )

    assert 'unload complete added=1 updated=0 deleted=1' in caplog.text
    assert not gone.exists()

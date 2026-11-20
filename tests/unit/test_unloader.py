from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from oracle_db_unloader.inventory import DbObject
from oracle_db_unloader.state import get_last_unload_at, load_state, state_path
from oracle_db_unloader.unloader import UnloadError, Unloader


def _obj(schema, name, object_type='TABLE', when=None):
    return DbObject(
        schema=schema,
        owner=schema,
        name=name,
        object_type=object_type,
        last_ddl_time=when or datetime(2026, 11, 16, 8, 0, 0),
    )


def _ddl(tmp_path, object_types, schemas=None, **kwargs):
    Unloader(
        MagicMock(),
        schemas or ['SCOTT'],
        tmp_path,
        object_types=object_types,
        max_workers=1,
    ).ddl(**kwargs)


def test_first_exception_stops_remaining_types_and_schemas(
    monkeypatch, tmp_path, caplog
):
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
        _ddl(tmp_path, ['table', 'view'], schemas=['SCOTT', 'HR'])

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
        _ddl(tmp_path, ['table'])
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
    _ddl(tmp_path, ['table'])

    assert 'ddl complete added=1 updated=0 deleted=1' in caplog.text
    assert not gone.exists()


def test_empty_schema_writes_nothing(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [],
    )
    caplog.set_level(logging.INFO, logger='oracle_db_unloader')
    _ddl(tmp_path, ['table'], schemas=['EMPTY'])
    assert not (tmp_path / 'empty').exists()
    assert not state_path(tmp_path, 'EMPTY').exists()
    assert 'inventory=0 write=0 delete=0' in caplog.text
    assert 'ddl complete added=0 updated=0 deleted=0' in caplog.text


def test_empty_schema_deletes_stale_files(monkeypatch, tmp_path):
    stale = tmp_path / 'empty' / 'tables' / 'gone.sql'
    stale.parent.mkdir(parents=True)
    stale.write_text('-- gone\n', encoding='utf-8')
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [],
    )
    _ddl(tmp_path, ['table'], schemas=['EMPTY'])
    assert not stale.exists()
    assert get_last_unload_at(load_state(tmp_path, 'EMPTY'), 'TABLE') is None


def test_unloader_stages_are_independent(monkeypatch, tmp_path):
    called = []

    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [_obj('SCOTT', 'EMP')],
    )

    def fake_write(_engine, obj, output_dir):
        called.append('ddl')
        path = output_dir / obj.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('-- emp\n', encoding='utf-8')

    monkeypatch.setattr('oracle_db_unloader.unloader.write_object', fake_write)
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.dump_dependencies',
        lambda *args, **kwargs: called.append('deps') or 1,
    )
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.dump_custom_sql',
        lambda *args, **kwargs: called.append('custom') or 0,
    )

    client = Unloader(
        MagicMock(),
        ['SCOTT'],
        tmp_path,
        object_types=['table'],
        max_workers=1,
    )
    client.dependencies()
    assert called == ['deps']
    client.custom_sql()
    assert called == ['deps', 'custom']
    client.ddl()
    assert called == ['deps', 'custom', 'ddl']
    assert (tmp_path / 'scott' / 'tables' / 'emp.sql').is_file()

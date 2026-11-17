from __future__ import annotations

from oracle_db_unloader.resources import (
    SQL_DIR,
    bind_params,
    ensure_semicolon,
    format_oracle_ident,
    split_statements,
    strip_owner_qualifiers,
)

SQLPLUS_MARKERS = ('define ', 'spool ', '&1', '&v_', 'prompt ')


def test_unload_scripts_use_bind_variables():
    unload_files = sorted(SQL_DIR.glob('unload_*.sql'))
    assert unload_files
    for path in unload_files:
        sql = path.read_text(encoding='utf-8')
        lowered = sql.lower()
        for marker in SQLPLUS_MARKERS:
            assert marker not in lowered, path.name
        binds = bind_params(sql, {'schema': 'SCOTT', 'obj_name': 'EMP', 'obj_type': 'TABLE'})
        assert 'schema' in binds, path.name
        assert 'obj_name' in binds, path.name
        assert 'upper(:obj_name)' not in sql, path.name


def test_inventory_tracks_partitions_and_indexes():
    inventory = (SQL_DIR / 'inventory.sql').read_text(encoding='utf-8')
    assert ':schema' in inventory
    assert 'TABLE PARTITION' in inventory
    assert 'dba_indexes' in inventory
    transform = (SQL_DIR / 'set_transform_params.sql').read_text(encoding='utf-8')
    assert 'EMIT_SCHEMA' in transform


def test_split_statements_on_slash():
    statements = split_statements(
        'select :schema from dual\n/\nselect :obj_name from dual\n'
    )
    assert len(statements) == 2


def test_ensure_semicolon():
    assert ensure_semicolon('create table emp') == 'create table emp;\n'
    assert ensure_semicolon('end;\n/\n') == 'end;\n/\n'


def test_format_oracle_ident():
    assert format_oracle_ident('EMP_HEAP') == 'emp_heap'
    assert format_oracle_ident('CUSTOM_metrics') == '"CUSTOM_metrics"'


def test_strip_owner_qualifiers():
    ddl = 'create table "SCOTT"."EMP" (\n  id number\n)\n'
    assert strip_owner_qualifiers(ddl, 'SCOTT') == 'create table "EMP" (\n  id number\n)\n'

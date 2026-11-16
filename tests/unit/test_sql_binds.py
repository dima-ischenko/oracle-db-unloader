from __future__ import annotations

from pathlib import Path

from oracle_db_unloader.resources import SQL_DIR, bind_params, split_statements

SQLPLUS_MARKERS = ('define ', 'spool ', '&1', '&v_', 'prompt ')


def test_unload_scripts_use_bind_variables():
    unload_files = sorted(SQL_DIR.glob('unload_*.sql'))
    assert unload_files, 'expected packaged unload SQL scripts'
    for path in unload_files:
        sql = path.read_text(encoding='utf-8')
        lowered = sql.lower()
        for marker in SQLPLUS_MARKERS:
            assert marker not in lowered, f'{path.name} still has sqlplus marker {marker!r}'
        binds = bind_params(sql, {'schema': 'SCOTT', 'obj_name': 'EMP', 'obj_type': 'TABLE'})
        assert 'schema' in binds, f'{path.name} must bind :schema'
        assert 'obj_name' in binds, f'{path.name} must bind :obj_name'


def test_inventory_and_metadata_sql_use_binds():
    inventory = (SQL_DIR / 'inventory.sql').read_text(encoding='utf-8')
    assert ':schema' in inventory
    assert '&' not in inventory
    assert split_statements(inventory) == [inventory.strip()]

    stats = (SQL_DIR / 'table_stats.sql').read_text(encoding='utf-8')
    assert bind_params(stats, {'schema': 'X', 'obj_name': 'T'}) == {
        'schema': 'X',
        'obj_name': 'T',
    }

    part = (SQL_DIR / 'partition_info.sql').read_text(encoding='utf-8')
    assert ':schema' in part and ':obj_name' in part


def test_split_statements_on_slash():
    sql = 'select :schema from dual\n/\nselect :obj_name from dual\n'
    statements = split_statements(sql)
    assert len(statements) == 2
    assert ':schema' in statements[0]
    assert ':obj_name' in statements[1]


def test_sql_dir_is_packaged():
    assert Path(SQL_DIR).is_dir()
    assert (SQL_DIR / 'set_transform_params.sql').is_file()

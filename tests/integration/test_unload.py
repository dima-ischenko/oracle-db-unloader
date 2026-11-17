from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import text

from oracle_db_unloader import unload
from oracle_db_unloader.inventory import fetch_inventory, max_last_ddl_time, normalize_ddl_time
from oracle_db_unloader.state import get_last_unload_at, load_state


def _unload(
    engine,
    tmp_path,
    custom_sql_dir=None,
    full=False,
    lookback_minutes=0,
    object_types=None,
):
    unload(
        engine,
        schemas=['TEST'],
        output_dir=tmp_path,
        max_connections=2,
        custom_sql_dir=custom_sql_dir,
        object_types=object_types,
        full=full,
        lookback_minutes=lookback_minutes,
    )


def test_unload_writes_expected_files_and_headers(fresh_schema, tmp_path):
    time.sleep(1.1)
    meta = tmp_path / '_meta'
    meta.mkdir()
    (meta / 'currency.sql').write_text(
        'select :schema as owner, code, name from currency_dict order by code',
        encoding='utf-8',
    )
    _unload(fresh_schema, tmp_path)

    table = Path(tmp_path) / 'test' / 'tables' / 'emp_heap.sql'
    sales = Path(tmp_path) / 'test' / 'tables' / 'sales_part.sql'
    camel = Path(tmp_path) / 'test' / 'tables' / 'custom_metrics.sql'
    view = Path(tmp_path) / 'test' / 'views' / 'emp_v.sql'
    pkg_s = Path(tmp_path) / 'test' / 'packages' / 'pkg_demo_s.sql'
    dml = Path(tmp_path) / 'test' / '_meta' / 'currency.txt'

    for path in (table, sales, camel, view, pkg_s, dml):
        assert path.is_file(), path

    table_sql = table.read_text(encoding='utf-8').lower()
    assert 'create table test.' not in table_sql
    assert 'create table emp_heap' in table_sql or 'create table "emp_heap"' in table_sql

    sales_sql = sales.read_text(encoding='utf-8').lower()
    assert 'alter table sales_part modify' in sales_sql
    assert 'partition p2024' not in sales_sql

    camel_sql = camel.read_text(encoding='utf-8')
    assert '"CUSTOM_metrics"' in camel_sql

    dml_text = dml.read_text(encoding='utf-8')
    assert 'USD' in dml_text
    assert 'null' in dml_text

    table_stamp = get_last_unload_at(load_state(tmp_path), 'TEST', 'TABLE')
    tables = [
        obj for obj in fetch_inventory(fresh_schema, 'TEST') if obj.object_type == 'TABLE'
    ]
    assert normalize_ddl_time(table_stamp) == max_last_ddl_time(tables)


def test_incremental_refresh_and_delete(fresh_schema, tmp_path):
    time.sleep(1.1)
    _unload(fresh_schema, tmp_path)

    pkg = Path(tmp_path) / 'test' / 'packages' / 'pkg_demo_s.sql'
    emp = Path(tmp_path) / 'test' / 'tables' / 'emp_heap.sql'
    view = Path(tmp_path) / 'test' / 'views' / 'emp_v.sql'
    emp_before = emp.read_text(encoding='utf-8')

    with fresh_schema.begin() as conn:
        conn.execute(
            text(
                """
                create or replace package pkg_demo as
                  function ping return number;
                  function pong return number;
                end pkg_demo;
                """
            )
        )
        conn.execute(text('drop view emp_v'))

    time.sleep(1.1)
    _unload(fresh_schema, tmp_path)

    assert 'pong' in pkg.read_text(encoding='utf-8').lower()
    assert emp.read_text(encoding='utf-8') == emp_before
    assert not view.exists()


def test_object_type_filter_keeps_other_types(fresh_schema, tmp_path):
    time.sleep(1.1)
    _unload(fresh_schema, tmp_path)
    view = Path(tmp_path) / 'test' / 'views' / 'emp_v.sql'
    assert view.is_file()

    with fresh_schema.begin() as conn:
        conn.execute(text('drop view emp_v'))

    time.sleep(1.1)
    _unload(fresh_schema, tmp_path, object_types=['TABLE'])
    assert view.is_file()

    _unload(fresh_schema, tmp_path, object_types=['VIEW'])
    assert not view.exists()


def test_index_change_rewrites_table(fresh_schema, tmp_path):
    time.sleep(1.1)
    _unload(fresh_schema, tmp_path, object_types=['TABLE'])
    emp = Path(tmp_path) / 'test' / 'tables' / 'emp_heap.sql'
    before = emp.read_text(encoding='utf-8')
    assert 'emp_heap_name_i' not in before.lower()

    with fresh_schema.begin() as conn:
        conn.execute(text('create index emp_heap_name_i on emp_heap (name)'))

    time.sleep(1.1)
    _unload(fresh_schema, tmp_path, object_types=['TABLE'])
    after = emp.read_text(encoding='utf-8')
    assert 'emp_heap_name_i' in after.lower()

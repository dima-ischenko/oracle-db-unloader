from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from oracle_db_unloader.dml import (
    discover_custom_sql,
    dump_custom_sql,
    format_table,
    stringify_cell,
)


def test_github_table_layout_and_nulls():
    rendered = format_table(
        ['ID', 'NAME'],
        [
            [1, 'abc'],
            [None, 'x'],
        ],
    )
    lines = rendered.splitlines()
    assert lines[0].startswith('|')
    assert 'ID' in lines[0]
    assert 'NAME' in lines[0]
    assert lines[1].replace(' ', '').startswith('|---')
    assert 'abc' in rendered
    assert 'null' in rendered


def test_stringify_cell_formats_types():
    assert stringify_cell(None) is None
    assert stringify_cell(Decimal('10.50')) == '10.5'
    assert stringify_cell(datetime(2026, 11, 16, 8, 0, 0)) == '16-nov-2026 08:00:00'


def test_discover_custom_sql_underscore_dirs(tmp_path):
    meta = tmp_path / '_meta'
    other = tmp_path / 'tables'
    meta.mkdir()
    other.mkdir()
    (meta / 'get_table_stats.sql').write_text(
        'select :schema as owner from dual',
        encoding='utf-8',
    )
    (other / 'ignored.sql').write_text('select 1 from dual', encoding='utf-8')
    (tmp_path / 'legacy.sql').write_text('select 1 from dual', encoding='utf-8')
    found = discover_custom_sql(tmp_path)
    assert found == [(meta / 'get_table_stats.sql', '_meta/get_table_stats')]


def test_dump_custom_sql_binds_schema_and_writes_per_schema(tmp_path):
    sql_dir = tmp_path / 'sql'
    meta = sql_dir / '_meta'
    meta.mkdir(parents=True)
    (meta / 'get_table_stats.sql').write_text(
        'select owner from dba_tables where owner = :schema',
        encoding='utf-8',
    )
    output = tmp_path / 'out'
    conn = _FakeConnection(
        columns=['OWNER'],
        rows_by_schema={'SCOTT': [['SCOTT']], 'HR': [['HR']]},
    )
    dumped = dump_custom_sql(
        _FakeEngine(conn),
        output,
        ['scott', 'hr'],
        custom_sql_dir=sql_dir,
    )
    assert dumped == 2
    assert [params['schema'] for _sql, params in conn.calls] == ['SCOTT', 'HR']
    scott = (output / 'scott' / '_meta' / 'get_table_stats.txt').read_text(
        encoding='utf-8'
    )
    hr = (output / 'hr' / '_meta' / 'get_table_stats.txt').read_text(encoding='utf-8')
    assert 'SCOTT' in scott
    assert 'HR' in hr


def test_dump_custom_sql_reads_underscore_dir_from_output_root(tmp_path):
    meta = tmp_path / '_meta'
    meta.mkdir()
    (meta / 'get_table_stats.sql').write_text(
        'select :schema as owner from dual',
        encoding='utf-8',
    )
    conn = _FakeConnection(columns=['OWNER'], rows_by_schema={'SCOTT': [['SCOTT']]})
    dumped = dump_custom_sql(_FakeEngine(conn), tmp_path, ['SCOTT'])
    assert dumped == 1
    target = tmp_path / 'scott' / '_meta' / 'get_table_stats.txt'
    assert target.is_file()
    assert 'SCOTT' in target.read_text(encoding='utf-8')


class _FakeResult:
    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows

    def keys(self):
        return self._columns

    def __iter__(self):
        return iter(self._rows)


class _FakeConnection:
    def __init__(self, columns, rows_by_schema):
        self.columns = columns
        self.rows_by_schema = rows_by_schema
        self.calls = []

    def execute(self, statement, params=None):
        sql = getattr(statement, 'text', None) or str(statement)
        self.calls.append((sql, params or {}))
        schema = (params or {}).get('schema')
        return _FakeResult(self.columns, self.rows_by_schema.get(schema, []))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn


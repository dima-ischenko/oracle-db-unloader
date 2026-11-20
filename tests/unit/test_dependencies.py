from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from oracle_db_unloader.dependencies import (
    DEP_COLUMNS,
    Node,
    build_graph,
    dependency_rows,
    dump_dependencies,
    write_schema_dependencies,
)
from oracle_db_unloader.inventory import DbObject
from oracle_db_unloader.unloader import unload


def _edge(src, dst):
    s_owner, s_name, s_type = src
    d_owner, d_name, d_type = dst
    return Node(s_owner, s_name, s_type), Node(d_owner, d_name, d_type)


def _obj(schema, name, object_type, owner=None):
    return DbObject(
        schema=schema,
        owner=owner or schema,
        name=name,
        object_type=object_type,
        last_ddl_time=datetime(2026, 11, 16, 8, 0, 0),
    )


def _rows_by_type(rows):
    return {
        'upstream': [row for row in rows if row.ref_type == 'upstream'],
        'downstream': [row for row in rows if row.ref_type == 'downstream'],
    }


def test_direct_downstream_includes_root():
    graph = build_graph(
        [
            _edge(('HR', 'EMP_V', 'VIEW'), ('SCOTT', 'EMP', 'TABLE')),
        ]
    )
    rows = _rows_by_type(dependency_rows(graph, Node('HR', 'EMP_V', 'VIEW')))
    assert [row.xref_path for row in rows['downstream']] == [
        'hr.emp_v(view) > scott.emp(table)'
    ]
    leaf = rows['downstream'][0]
    assert leaf.owner == 'SCOTT'
    assert leaf.name == 'EMP'
    assert leaf.type == 'TABLE'
    assert leaf.full_ref_object_name == 'scott.emp'
    assert leaf.priority == 1
    assert leaf.lvl == 1
    assert rows['upstream'] == []


def test_direct_upstream_includes_root():
    graph = build_graph(
        [
            _edge(('HR', 'P_REPORT', 'PROCEDURE'), ('SCOTT', 'EMP_V', 'VIEW')),
        ]
    )
    rows = _rows_by_type(dependency_rows(graph, Node('SCOTT', 'EMP_V', 'VIEW')))
    assert [row.xref_path for row in rows['upstream']] == [
        'hr.p_report(procedure) > scott.emp_v(view)'
    ]
    leaf = rows['upstream'][0]
    assert leaf.owner == 'HR'
    assert leaf.name == 'P_REPORT'
    assert leaf.type == 'PROCEDURE'
    assert leaf.full_ref_object_name == 'scott.emp_v'
    assert leaf.priority == 0
    assert leaf.lvl == 1
    assert rows['downstream'] == []


def test_multihop_and_diamond_paths():
    graph = build_graph(
        [
            _edge(('HR', 'PKG_REPORT', 'PACKAGE BODY'), ('SCOTT', 'EMP_V', 'VIEW')),
            _edge(('SCOTT', 'EMP_V', 'VIEW'), ('SCOTT', 'EMP_V2', 'VIEW')),
            _edge(('SCOTT', 'EMP_V', 'VIEW'), ('SCOTT', 'EMP', 'TABLE')),
            _edge(('SCOTT', 'EMP_V2', 'VIEW'), ('SCOTT', 'EMP', 'TABLE')),
            _edge(('HR', 'DEPT_V', 'VIEW'), ('SCOTT', 'EMP_V', 'VIEW')),
            _edge(('HR', 'DEPT_V2', 'VIEW'), ('HR', 'DEPT_V', 'VIEW')),
            _edge(('HR', 'OTHER_V', 'VIEW'), ('SCOTT', 'EMP_V', 'VIEW')),
        ]
    )
    down = _rows_by_type(
        dependency_rows(graph, Node('HR', 'PKG_REPORT', 'PACKAGE BODY'))
    )['downstream']
    assert [row.xref_path for row in down] == [
        'hr.pkg_report(package body) > scott.emp_v(view) > scott.emp(table)',
        'hr.pkg_report(package body) > scott.emp_v(view) > scott.emp_v2(view) > scott.emp(table)',
    ]
    assert down[0].lvl == 2
    assert down[1].lvl == 3
    assert down[1].full_ref_object_name == 'scott.emp'

    up = _rows_by_type(dependency_rows(graph, Node('SCOTT', 'EMP_V', 'VIEW')))[
        'upstream'
    ]
    assert [row.xref_path for row in up] == [
        'hr.dept_v2(view) > hr.dept_v(view) > scott.emp_v(view)',
        'hr.other_v(view) > scott.emp_v(view)',
        'hr.pkg_report(package body) > scott.emp_v(view)',
    ]
    assert [row.lvl for row in up] == [2, 1, 1]
    assert up[0].owner == 'HR'
    assert up[0].name == 'DEPT_V2'


def test_cycle_does_not_loop():
    graph = build_graph(
        [
            _edge(('A', 'T1', 'TABLE'), ('A', 'T2', 'TABLE')),
            _edge(('A', 'T2', 'TABLE'), ('A', 'T1', 'TABLE')),
        ]
    )
    rows = dependency_rows(graph, Node('A', 'T1', 'TABLE'))
    assert {row.xref_path for row in rows} == {
        'a.t2(table) > a.t1(table)',
        'a.t1(table) > a.t2(table)',
    }


def test_write_schema_dependencies_layout_and_stale_delete(tmp_path):
    graph = build_graph(
        [
            _edge(('SCOTT', 'EMP_V', 'VIEW'), ('SCOTT', 'EMP', 'TABLE')),
            _edge(('SCOTT', 'PKG_X', 'PACKAGE BODY'), ('SCOTT', 'EMP_V', 'VIEW')),
        ]
    )
    stale = tmp_path / 'scott' / '_deps' / 'views' / 'gone.md'
    stale.parent.mkdir(parents=True)
    stale.write_text('stale\n', encoding='utf-8')
    other_type = tmp_path / 'scott' / '_deps' / 'tables' / 'emp.md'
    other_type.parent.mkdir(parents=True)
    other_type.write_text('keep-if-not-selected\n', encoding='utf-8')
    empty_prev = tmp_path / 'scott' / '_deps' / 'views' / 'lonely.md'
    empty_prev.write_text('was-deps\n', encoding='utf-8')

    written = write_schema_dependencies(
        tmp_path,
        'SCOTT',
        [
            _obj('SCOTT', 'EMP_V', 'VIEW'),
            _obj('SCOTT', 'LONELY', 'VIEW'),
            _obj('SCOTT', 'PKG_X', 'PACKAGE BODY'),
            _obj('SCOTT', 'EMP', 'TABLE'),
        ],
        ['VIEW'],
        graph,
    )
    assert written == 1
    path = tmp_path / 'scott' / '_deps' / 'views' / 'emp_v.md'
    text = path.read_text(encoding='utf-8')
    assert 'xref_path' in text
    assert 'scott.pkg_x(package body) > scott.emp_v(view)' in text
    assert 'scott.emp_v(view) > scott.emp(table)' in text
    assert not stale.exists()
    assert not empty_prev.exists()
    assert other_type.read_text(encoding='utf-8') == 'keep-if-not-selected\n'
    assert not (tmp_path / 'scott' / '_deps' / 'packages' / 'pkg_x_b.md').exists()


def test_dump_dependencies_fetches_once_and_writes(monkeypatch, tmp_path):
    calls = {'edges': 0, 'inventory': 0}

    def fake_edges(_engine):
        calls['edges'] += 1
        return [
            _edge(('SCOTT', 'EMP_V', 'VIEW'), ('SCOTT', 'EMP', 'TABLE')),
            _edge(('HR', 'EMP_V', 'VIEW'), ('HR', 'EMP', 'TABLE')),
        ]

    def fake_inventory(_engine, schema):
        calls['inventory'] += 1
        return [_obj(schema, 'EMP_V', 'VIEW'), _obj(schema, 'EMP', 'TABLE')]

    monkeypatch.setattr(
        'oracle_db_unloader.dependencies.fetch_dependency_edges', fake_edges
    )
    monkeypatch.setattr(
        'oracle_db_unloader.dependencies.fetch_inventory', fake_inventory
    )

    dumped = dump_dependencies(
        MagicMock(), tmp_path, ['scott', 'hr'], ['VIEW', 'TABLE']
    )
    assert dumped == 4
    assert calls == {'edges': 1, 'inventory': 2}
    assert (tmp_path / 'scott' / '_deps' / 'views' / 'emp_v.md').is_file()
    assert (tmp_path / 'hr' / '_deps' / 'tables' / 'emp.md').is_file()


def test_unload_runs_dependencies_after_ddl(monkeypatch, tmp_path):
    order = []

    monkeypatch.setattr(
        'oracle_db_unloader.unloader.fetch_inventory',
        lambda _engine, _schema: [_obj('SCOTT', 'EMP', 'TABLE')],
    )

    def fake_write(_engine, obj, output_dir):
        order.append('ddl')
        path = output_dir / obj.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('-- emp\n', encoding='utf-8')

    monkeypatch.setattr('oracle_db_unloader.unloader.write_object', fake_write)
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.dump_dependencies',
        lambda *args, **kwargs: order.append('deps') or 1,
    )
    monkeypatch.setattr(
        'oracle_db_unloader.unloader.dump_custom_sql',
        lambda *args, **kwargs: order.append('custom') or 0,
    )

    unload(MagicMock(), ['SCOTT'], tmp_path, object_types=['table'], max_workers=1)
    assert order == ['ddl', 'custom']

    order.clear()
    unload(
        MagicMock(),
        ['SCOTT'],
        tmp_path,
        object_types=['table'],
        max_workers=1,
        dependencies=True,
    )
    assert order == ['ddl', 'deps', 'custom']


def test_dep_columns_match_sql_aliases():
    assert DEP_COLUMNS == (
        'xref_path',
        'owner',
        'name',
        'type',
        'ref_type',
        'full_ref_object_name',
        'priority',
        'lvl',
    )

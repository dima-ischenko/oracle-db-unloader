from __future__ import annotations

from datetime import datetime, timezone

from oracle_db_unloader.inventory import DbObject, object_relpath, plan_actions


def _obj(name, object_type, last_ddl, schema='SCOTT'):
    return DbObject(
        schema=schema,
        owner=schema,
        name=name,
        object_type=object_type,
        last_ddl_time=last_ddl,
    )


def test_object_relpath_suffixes():
    assert object_relpath('SCOTT', 'EMP', 'TABLE') == 'scott/tables/emp.sql'
    assert object_relpath('SCOTT', 'PKG_X', 'PACKAGE') == 'scott/packages/pkg_x_s.sql'
    assert object_relpath('SCOTT', 'PKG_X', 'PACKAGE BODY') == 'scott/packages/pkg_x_b.sql'
    assert object_relpath('HR', 'T', 'TYPE') == 'hr/types/t_s.sql'
    assert object_relpath('HR', 'T', 'TYPE BODY') == 'hr/types/t_b.sql'
    assert object_relpath('SCOTT', 'MV1', 'MATERIALIZED VIEW') == 'scott/mviews/mv1.sql'


def test_plan_write_when_missing_or_changed():
    stamp = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)
    emp = _obj('EMP', 'TABLE', datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc))
    pkg = _obj('PKG_X', 'PACKAGE', datetime(2026, 11, 16, 8, 10, tzinfo=timezone.utc))
    view = _obj('V_EMP', 'VIEW', datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc))
    objects = [emp, pkg, view]
    disk = {
        emp.relpath,
        pkg.relpath,
        'scott/views/gone.sql',
    }
    to_write, to_delete = plan_actions(
        objects,
        disk,
        last_unload_at=stamp,
        lookback_minutes=0,
    )
    written = {obj.relpath for obj in to_write}
    assert pkg.relpath in written
    assert view.relpath in written
    assert emp.relpath not in written
    assert to_delete == {'scott/views/gone.sql'}


def test_plan_full_when_no_watermark():
    emp = _obj('EMP', 'TABLE', datetime(2020, 1, 1, tzinfo=timezone.utc))
    to_write, to_delete = plan_actions([emp], set(), None, lookback_minutes=5)
    assert to_write == [emp]
    assert to_delete == set()


def test_plan_lookback_includes_recent_objects():
    last = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)
    emp = _obj('EMP', 'TABLE', datetime(2026, 11, 16, 7, 56, tzinfo=timezone.utc))
    to_write, _to_delete = plan_actions(
        [emp],
        {emp.relpath},
        last_unload_at=last,
        lookback_minutes=5,
    )
    assert to_write == [emp]

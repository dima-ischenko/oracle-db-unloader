from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from oracle_db_unloader.dml import format_table, stringify_cell


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

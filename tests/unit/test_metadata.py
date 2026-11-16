from __future__ import annotations

from datetime import datetime

import pytest

from oracle_db_unloader.inventory import DbObject
from oracle_db_unloader.metadata import (
    PartitionInfo,
    SubpartitionTemplate,
    format_llm_header,
    format_partition_header_lines,
    format_partition_template_block,
    row_count_label,
)


@pytest.mark.parametrize(
    'num_rows, expected',
    [
        (None, 'unknown'),
        (0, '1K'),
        (999, '1K'),
        (1_000, '1K'),
        (9_999, '1K'),
        (10_000, '10K'),
        (99_999, '10K'),
        (100_000, '100K'),
        (1_000_000, '1M'),
        (10_000_000, '10M'),
        (100_000_000, '100M'),
        (100_000_001, '100M+'),
        (5_000_000_000, '100M+'),
    ],
)
def test_row_count_label(num_rows, expected):
    assert row_count_label(num_rows) == expected


def test_compact_partition_comment():
    info = PartitionInfo(
        partitioning_type='RANGE',
        part_key='reporting_day',
        interval="NUMTOYMINTERVAL(1,'MONTH')",
        subpartitioning_type='LIST',
        subpart_key='source_id',
        template=(
            SubpartitionTemplate('p0_p_src_1', '1'),
            SubpartitionTemplate('p0_p_src_2', '2'),
        ),
    )
    lines = format_partition_header_lines(info)
    assert lines[0] == (
        "-- partitioned: RANGE (reporting_day) INTERVAL(NUMTOYMINTERVAL(1,'MONTH'))"
    )
    assert lines[1] == '--              LIST SUBPART (source_id) template 2 values'

    block = format_partition_template_block('RPD_LOAN_DAILY', info)
    assert 'alter table rpd_loan_daily modify partition by range (reporting_day)' in block
    assert "interval(numtoyminterval(1,'month'))" in block
    assert 'subpartition by list (source_id)' in block
    assert 'subpartition template' in block
    assert 'subpartition p0_p_src_1 values (1)' in block
    assert 'partition p202401' not in block
    assert 'values less than' not in block


def test_llm_header_includes_rows_and_partition():
    obj = DbObject(
        schema='RPD',
        owner='RPD',
        name='RPD_LOAN_DAILY',
        object_type='TABLE',
        last_ddl_time=datetime(2026, 11, 1, 12, 0, 0),
    )
    info = PartitionInfo(
        partitioning_type='RANGE',
        part_key='reporting_day',
        interval="NUMTOYMINTERVAL(1,'MONTH')",
        subpartitioning_type='LIST',
        subpart_key='source_id',
        template=tuple(SubpartitionTemplate(f's{i}', str(i)) for i in range(1, 10)),
    )
    header = format_llm_header(obj, 12_000_000, info)
    assert '-- object: TABLE RPD.RPD_LOAN_DAILY' in header
    assert '-- rows: 10M' in header
    assert '-- last_ddl: 2026-11-01 12:00:00' in header
    assert 'RANGE (reporting_day)' in header
    assert 'template 9 values' in header

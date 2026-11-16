from __future__ import annotations

from oracle_db_unloader.metadata import (
    PartitionInfo,
    SubpartitionTemplate,
    format_file_header,
    format_partition_header_lines,
    format_partition_template_block,
)


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


def test_file_header_is_partition_only():
    info = PartitionInfo(
        partitioning_type='RANGE',
        part_key='reporting_day',
        interval="NUMTOYMINTERVAL(1,'MONTH')",
        subpartitioning_type='LIST',
        subpart_key='source_id',
        template=tuple(SubpartitionTemplate(f's{i}', str(i)) for i in range(1, 10)),
    )
    header = format_file_header(info)
    assert '-- rows:' not in header
    assert '-- last_ddl:' not in header
    assert 'RANGE (reporting_day)' in header
    assert 'template 9 values' in header
    assert format_file_header(None) == ''

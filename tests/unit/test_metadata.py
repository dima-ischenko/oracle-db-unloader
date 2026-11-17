from __future__ import annotations

from oracle_db_unloader.metadata import (
    PartitionInfo,
    SubpartitionTemplate,
    format_file_header,
    format_partition_template_block,
)


def test_compact_partition_alter():
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
    block = format_partition_template_block('RPD_LOAN_DAILY', info)
    assert 'alter table rpd_loan_daily modify partition by range (reporting_day)' in block
    assert 'subpartition template' in block
    assert 'partition p202401' not in block
    assert block.rstrip().endswith(';')
    mixed = format_partition_template_block('CUSTOM_metrics', info)
    assert 'alter table "CUSTOM_metrics" modify' in mixed


def test_partition_alter_without_template():
    info = PartitionInfo(partitioning_type='RANGE', part_key='id')
    assert (
        format_partition_template_block('EMP', info).strip()
        == 'alter table emp modify partition by range (id);'
    )


def test_file_header_is_partition_only():
    info = PartitionInfo(
        partitioning_type='RANGE',
        part_key='reporting_day',
        interval="NUMTOYMINTERVAL(1,'MONTH')",
    )
    header = format_file_header(info)
    assert '-- rows:' not in header
    assert '-- last_ddl:' not in header
    assert format_file_header(None) == ''

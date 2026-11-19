from __future__ import annotations

from oracle_db_unloader.metadata import (
    PartitionInfo,
    SubpartitionTemplate,
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
            SubpartitionTemplate('P0_P_SRC_1', '1'),
            SubpartitionTemplate('P0_P_SRC_2', '2'),
        ),
    )
    block = format_partition_template_block('RPD_LOAN_DAILY', info)
    expected = 'ALTER TABLE rpd_loan_daily MODIFY PARTITION BY RANGE (reporting_day)'
    assert expected in block
    assert "INTERVAL(NUMTOYMINTERVAL(1,'MONTH'))" in block
    assert 'SUBPARTITION BY LIST (source_id)' in block
    assert 'SUBPARTITION TEMPLATE' in block
    assert 'SUBPARTITION p0_p_src_1 VALUES (1)' in block
    assert 'partition p202401' not in block
    assert block.rstrip().endswith(';')
    mixed = format_partition_template_block('MixedCase_metrics', info)
    assert 'ALTER TABLE "MixedCase_metrics" MODIFY' in mixed


def test_partition_alter_without_template():
    info = PartitionInfo(partitioning_type='RANGE', part_key='id')
    assert (
        format_partition_template_block('EMP', info).strip()
        == 'ALTER TABLE emp MODIFY PARTITION BY RANGE (id);'
    )

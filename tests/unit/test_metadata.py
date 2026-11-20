from __future__ import annotations

from oracle_db_unloader.metadata import (
    PartitionInfo,
    SubpartitionTemplate,
    format_partition_template_block,
    is_partition_shape_supported,
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


def test_hash_partition_uses_partition_count():
    info = PartitionInfo(partitioning_type='HASH', part_key='id', partition_count=4)
    assert (
        format_partition_template_block('EMP', info).strip()
        == 'ALTER TABLE emp MODIFY PARTITION BY HASH (id) PARTITIONS 4;'
    )


def test_composite_hash_uses_subpartition_count():
    info = PartitionInfo(
        partitioning_type='COMPOSITE_HASH',
        part_key='id',
        partition_count=4,
        subpartitioning_type='HASH',
        subpart_key='source_id',
        subpartition_count=3,
    )
    block = format_partition_template_block('EMP', info)
    assert 'ALTER TABLE emp MODIFY PARTITION BY HASH (id) PARTITIONS 4' in block
    assert 'SUBPARTITION BY HASH (source_id)' in block
    assert 'SUBPARTITIONS 3' in block


def test_range_subpartition_template_uses_values_less_than():
    info = PartitionInfo(
        partitioning_type='COMPOSITE_RANGE',
        part_key='sale_date',
        subpartitioning_type='RANGE',
        subpart_key='source_id',
        template=(
            SubpartitionTemplate('S1', '10'),
            SubpartitionTemplate('S2', '20'),
        ),
    )
    block = format_partition_template_block('EMP', info)
    assert 'SUBPARTITION s1 VALUES LESS THAN (10),' in block
    assert 'SUBPARTITION s2 VALUES LESS THAN (20)' in block


def test_list_subpartition_without_bound_renders_default():
    info = PartitionInfo(
        partitioning_type='COMPOSITE_LIST',
        part_key='region',
        subpartitioning_type='LIST',
        subpart_key='source_id',
        template=(
            SubpartitionTemplate('S1', '1'),
            SubpartitionTemplate('SDEFAULT', ''),
        ),
    )
    block = format_partition_template_block('EMP', info)
    assert 'SUBPARTITION s1 VALUES (1),' in block
    assert 'SUBPARTITION sdefault DEFAULT' in block


def test_system_partitioning_has_no_key():
    info = PartitionInfo(partitioning_type='SYSTEM', part_key='', partition_count=4)
    assert (
        format_partition_template_block('EMP', info).strip()
        == 'ALTER TABLE emp MODIFY PARTITION BY SYSTEM PARTITIONS 4;'
    )


def test_shape_guard():
    assert is_partition_shape_supported(
        PartitionInfo(partitioning_type='RANGE', part_key='id')
    )
    assert is_partition_shape_supported(
        PartitionInfo(
            partitioning_type='COMPOSITE_RANGE',
            part_key='d',
            subpartitioning_type='LIST',
            subpart_key='s',
            template=(SubpartitionTemplate('S1', '1'),),
        )
    )
    assert not is_partition_shape_supported(
        PartitionInfo(partitioning_type='HASH', part_key='id')
    )
    assert not is_partition_shape_supported(
        PartitionInfo(
            partitioning_type='COMPOSITE_LIST',
            part_key='r',
            subpartitioning_type='LIST',
            subpart_key='s',
        )
    )
    assert not is_partition_shape_supported(
        PartitionInfo(partitioning_type='REFERENCE', part_key='id')
    )

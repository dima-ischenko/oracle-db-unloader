from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .inventory import DbObject
from .resources import bind_params, load_sql

ROW_BUCKETS = (
    (1_000, '1K'),
    (10_000, '10K'),
    (100_000, '100K'),
    (1_000_000, '1M'),
    (10_000_000, '10M'),
    (100_000_000, '100M'),
)


@dataclass(frozen=True)
class SubpartitionTemplate:
    name: str
    high_bound: str


@dataclass(frozen=True)
class PartitionInfo:
    partitioning_type: str
    part_key: str
    interval: Optional[str] = None
    subpartitioning_type: Optional[str] = None
    subpart_key: Optional[str] = None
    template: Sequence[SubpartitionTemplate] = field(default_factory=tuple)


def row_count_label(num_rows: Optional[int]) -> str:
    if num_rows is None:
        return 'unknown'
    n = int(num_rows)
    if n > 100_000_000:
        return '100M+'
    label = '1K'
    for threshold, name in ROW_BUCKETS:
        if n >= threshold:
            label = name
        else:
            break
    return label


def format_last_ddl(value: Optional[datetime]) -> str:
    if value is None:
        return 'unknown'
    return value.strftime('%Y-%m-%d %H:%M:%S')


def format_partition_header_lines(info: Optional[PartitionInfo]) -> List[str]:
    if info is None:
        return []
    line = f'-- partitioned: {info.partitioning_type} ({info.part_key})'
    if info.interval:
        line += f' INTERVAL({info.interval})'
    lines = [line]
    sub_type = info.subpartitioning_type
    if sub_type and sub_type.upper() != 'NONE' and info.subpart_key:
        sub = f'--              {sub_type} SUBPART ({info.subpart_key})'
        if info.template:
            sub += f' template {len(info.template)} values'
        lines.append(sub)
    return lines


def format_partition_template_block(
    table_name: str,
    info: Optional[PartitionInfo],
) -> str:
    if info is None:
        return ''
    part_by = f'partition by {info.partitioning_type.lower()} ({info.part_key})'
    if info.interval:
        part_by += f' interval({info.interval.lower()})'
    lines = [
        '/*',
        f'alter table {table_name.lower()} modify {part_by}',
    ]
    sub_type = info.subpartitioning_type
    if sub_type and sub_type.upper() != 'NONE' and info.subpart_key:
        lines.append(
            f'subpartition by {sub_type.lower()} ({info.subpart_key})'
        )
        if info.template:
            lines.append('   subpartition template')
            lines.append('   (')
            last = len(info.template) - 1
            for i, item in enumerate(info.template):
                comma = ',' if i < last else ''
                lines.append(
                    f'    subpartition {item.name.lower()} values ({item.high_bound}){comma}'
                )
            lines.append('  )')
    lines.append('*/')
    return '\n'.join(lines)


def format_llm_header(
    obj: DbObject,
    num_rows: Optional[int],
    partition: Optional[PartitionInfo],
) -> str:
    lines = [
        f'-- object: {obj.object_type} {obj.owner}.{obj.name}',
        f'-- rows: {row_count_label(num_rows)}',
        f'-- last_ddl: {format_last_ddl(obj.last_ddl_time)}',
    ]
    lines.extend(format_partition_header_lines(partition))
    return '\n'.join(lines) + '\n\n'


def fetch_num_rows(conn: Connection, obj: DbObject) -> Optional[int]:
    sql = load_sql('table_stats.sql')
    params = bind_params(sql, {'schema': obj.owner, 'obj_name': obj.name})
    row = conn.execute(text(sql), params).first()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def fetch_partition_info(conn: Connection, obj: DbObject) -> Optional[PartitionInfo]:
    info_sql = load_sql('partition_info.sql')
    params = bind_params(info_sql, {'schema': obj.owner, 'obj_name': obj.name})
    row = conn.execute(text(info_sql), params).first()
    if row is None:
        return None

    template_sql = load_sql('partition_template.sql')
    template_params = bind_params(
        template_sql, {'schema': obj.owner, 'obj_name': obj.name}
    )
    templates = []
    for name, high_bound, _position in conn.execute(text(template_sql), template_params):
        templates.append(
            SubpartitionTemplate(
                name=name,
                high_bound='' if high_bound is None else str(high_bound),
            )
        )

    partitioning_type, subpartitioning_type, interval, part_key, subpart_key = row
    return PartitionInfo(
        partitioning_type=partitioning_type,
        part_key=part_key or '',
        interval=interval,
        subpartitioning_type=subpartitioning_type,
        subpart_key=subpart_key,
        template=tuple(templates),
    )

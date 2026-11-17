from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .inventory import DbObject
from .resources import (
    bind_params,
    ensure_semicolon,
    format_oracle_ident,
    format_oracle_ident_list,
    load_sql,
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
        f'alter table {format_oracle_ident(table_name)} modify {part_by}',
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
                    f'    subpartition {format_oracle_ident(item.name)} values ({item.high_bound}){comma}'
                )
            lines.append('  )')
    return ensure_semicolon('\n'.join(lines)).rstrip() + '\n'


def format_file_header(partition: Optional[PartitionInfo]) -> str:
    lines = format_partition_header_lines(partition)
    if not lines:
        return ''
    return '\n'.join(lines) + '\n\n'


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
        part_key=format_oracle_ident_list(part_key),
        interval=interval,
        subpartitioning_type=subpartitioning_type,
        subpart_key=format_oracle_ident_list(subpart_key) or None,
        template=tuple(templates),
    )

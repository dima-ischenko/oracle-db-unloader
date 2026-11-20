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
    partition_count: Optional[int] = None
    subpartition_count: Optional[int] = None


def _base_type(raw: Optional[str]) -> str:
    return (raw or '').upper().removeprefix('COMPOSITE_')


def is_partition_shape_supported(info: PartitionInfo) -> bool:
    """True when the partitioning shape can be reproduced by the alter block."""
    top = _base_type(info.partitioning_type)
    if top in ('RANGE', 'LIST'):
        if not info.part_key:
            return False
    elif top == 'HASH':
        if not info.part_key or info.partition_count is None:
            return False
    elif top != 'SYSTEM':
        return False
    sub = _base_type(info.subpartitioning_type)
    if sub in ('', 'NONE'):
        return True
    if sub in ('LIST', 'RANGE'):
        return bool(info.subpart_key) and bool(info.template)
    if sub == 'HASH':
        return bool(info.subpart_key) and info.subpartition_count is not None
    return sub == 'SYSTEM'


def _subpartition_values(item: SubpartitionTemplate, sub_type: str) -> str:
    if not item.high_bound:
        return 'DEFAULT'
    if sub_type == 'RANGE':
        return f'VALUES LESS THAN ({item.high_bound})'
    return f'VALUES ({item.high_bound})'


def _template_lines(
    template: Sequence[SubpartitionTemplate],
    sub_type: str,
) -> List[str]:
    lines = ['   SUBPARTITION TEMPLATE', '   (']
    last = len(template) - 1
    for i, item in enumerate(template):
        comma = ',' if i < last else ''
        lines.append(
            f'    SUBPARTITION {format_oracle_ident(item.name)} '
            f'{_subpartition_values(item, sub_type)}{comma}'
        )
    lines.append('  )')
    return lines


def format_partition_template_block(
    table_name: str,
    info: Optional[PartitionInfo],
) -> str:
    if info is None:
        return ''
    top = _base_type(info.partitioning_type)
    part_by = f'PARTITION BY {top}'
    if top in ('RANGE', 'LIST', 'HASH'):
        part_by += f' ({info.part_key})'
    if info.interval:
        part_by += f' INTERVAL({info.interval})'
    if top in ('HASH', 'SYSTEM') and info.partition_count is not None:
        part_by += f' PARTITIONS {info.partition_count}'
    lines = [f'ALTER TABLE {format_oracle_ident(table_name)} MODIFY {part_by}']
    sub = _base_type(info.subpartitioning_type)
    if sub not in ('', 'NONE'):
        sub_by = f'SUBPARTITION BY {sub}'
        if sub in ('LIST', 'RANGE', 'HASH'):
            sub_by += f' ({info.subpart_key})'
        lines.append(sub_by)
        if sub == 'HASH':
            lines.append(f'   SUBPARTITIONS {info.subpartition_count}')
        elif info.template:
            lines.extend(_template_lines(info.template, sub))
    return ensure_semicolon('\n'.join(lines)).rstrip() + '\n'


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

    (
        partitioning_type,
        subpartitioning_type,
        interval,
        partition_count,
        subpartition_count,
        part_key,
        subpart_key,
    ) = row
    return PartitionInfo(
        partitioning_type=partitioning_type,
        part_key=format_oracle_ident_list(part_key),
        interval=interval,
        subpartitioning_type=subpartitioning_type,
        subpart_key=format_oracle_ident_list(subpart_key) or None,
        template=tuple(templates),
        partition_count=partition_count,
        subpartition_count=subpartition_count,
    )

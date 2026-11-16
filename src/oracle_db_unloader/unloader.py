from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .dml import dump_custom_sql
from .engine import apply_session_transforms
from .inventory import (
    HEADER_TYPES,
    SOURCE_TYPES,
    UNLOAD_SQL,
    DbObject,
    fetch_inventory,
    next_watermark,
    normalize_object_types,
    plan_actions,
    walk_schema_files,
)
from .logger import get_logger
from .metadata import (
    fetch_partition_info,
    format_file_header,
    format_partition_template_block,
)
from .resources import (
    bind_params,
    concat_ddl,
    load_sql,
    split_statements,
    strip_owner_qualifiers,
)
from .state import get_last_unload_at, load_state, save_state, set_last_unload_at

logger = get_logger(__name__)


class UnloadError(RuntimeError):
    """Raised when one or more objects failed to unload."""


def fetch_object_ddl(conn: Connection, obj: DbObject) -> str:
    sql_name = UNLOAD_SQL[obj.object_type]
    params = {
        'schema': obj.owner,
        'obj_name': obj.name,
        'obj_type': obj.object_type,
    }
    parts: List[str] = []
    for statement in split_statements(load_sql(sql_name)):
        result = conn.execute(text(statement), bind_params(statement, params))
        if not result.returns_rows:
            continue
        for row in result:
            parts.append(row[0])
    ddl = strip_owner_qualifiers(concat_ddl(parts), obj.owner)
    if obj.object_type in SOURCE_TYPES:
        stripped = ddl.rstrip()
        if not stripped.endswith('/'):
            ddl = stripped + '\n/\n'
    return ddl


def write_object(engine: Engine, obj: DbObject, output_dir: Path) -> None:
    with engine.connect() as conn:
        apply_session_transforms(conn)
        ddl = fetch_object_ddl(conn, obj)
        header = ''
        footer = ''
        if obj.object_type in HEADER_TYPES:
            partition = fetch_partition_info(conn, obj)
            header = format_file_header(partition)
            footer = format_partition_template_block(obj.name, partition)
        content = header + ddl
        if footer:
            content = content.rstrip() + '\n\n' + footer + '\n'
        path = output_dir / obj.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        logger.info('unloaded %s', path.as_posix())


def _delete_files(output_dir: Path, relpaths: Iterable[str]) -> None:
    for relpath in sorted(relpaths):
        path = output_dir / relpath
        if path.is_file():
            path.unlink()
            logger.info('deleted %s', path.as_posix())


def _normalize_schemas(schemas: Sequence[str]) -> List[str]:
    seen = []
    for schema in schemas:
        name = schema.strip().upper()
        if name and name not in seen:
            seen.append(name)
    if not seen:
        raise ValueError('at least one schema is required')
    return seen


def _unload_object_type(
    engine: Engine,
    schema: str,
    object_type: str,
    objects: Sequence[DbObject],
    output_dir: Path,
    *,
    last_unload_at: Optional[datetime],
    lookback_minutes: int,
    max_connections: int,
    full: bool,
) -> None:
    disk = walk_schema_files(output_dir, schema, [object_type])
    watermark = None if full else last_unload_at
    to_write, to_delete = plan_actions(objects, disk, watermark, lookback_minutes)
    workers = max(1, min(max_connections, len(to_write) or 1))
    logger.info(
        'schema %s type %s: inventory=%d write=%d delete=%d workers=%d '
        'watermark=%s',
        schema,
        object_type,
        len(objects),
        len(to_write),
        len(to_delete),
        workers,
        watermark.isoformat() if watermark else 'none',
    )
    errors = []
    if to_write:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(write_object, engine, obj, output_dir): obj
                for obj in to_write
            }
            for future in as_completed(futures):
                obj = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.exception(
                        'failed to unload %s %s.%s',
                        obj.object_type,
                        obj.owner,
                        obj.name,
                    )
                    errors.append((obj, exc))
    _delete_files(output_dir, to_delete)
    if errors:
        names = ', '.join(f'{obj.owner}.{obj.name}' for obj, _exc in errors)
        raise UnloadError(
            f'failed to unload {len(errors)} {object_type} object(s) in {schema}: {names}'
        )


def unload_schema(
    engine: Engine,
    schema: str,
    output_dir: Path,
    *,
    object_types: Sequence[str],
    state: Dict[str, Any],
    lookback_minutes: int,
    max_connections: int,
    full: bool,
) -> Dict[str, Any]:
    inventory = fetch_inventory(engine, schema)
    by_type: Dict[str, List[DbObject]] = {
        object_type: [] for object_type in object_types
    }
    for obj in inventory:
        if obj.object_type in by_type:
            by_type[obj.object_type].append(obj)

    type_errors = []
    for object_type in object_types:
        try:
            _unload_object_type(
                engine,
                schema,
                object_type,
                by_type[object_type],
                output_dir,
                last_unload_at=get_last_unload_at(state, schema, object_type),
                lookback_minutes=lookback_minutes,
                max_connections=max_connections,
                full=full,
            )
        except Exception as exc:
            logger.exception('schema %s type %s failed', schema, object_type)
            type_errors.append((object_type, exc))
        else:
            watermark = next_watermark(
                get_last_unload_at(state, schema, object_type),
                by_type[object_type],
            )
            if watermark is not None:
                state = set_last_unload_at(state, schema, watermark, object_type)
                save_state(output_dir, state)
            logger.info(
                'schema %s type %s: done watermark=%s',
                schema,
                object_type,
                watermark.isoformat() if watermark else 'none',
            )
    if type_errors:
        names = ', '.join(object_type for object_type, _exc in type_errors)
        raise UnloadError(f'failed to unload type(s) in {schema}: {names}')
    return state


def unload(
    engine: Engine,
    schemas: Sequence[str],
    output_dir: Union[str, Path],
    *,
    max_connections: int = 5,
    custom_sql_dir: Union[str, Path, None] = None,
    object_types: Optional[Sequence[str]] = None,
    full: bool = False,
    lookback_minutes: int = 0,
) -> None:
    """Unload schema objects using a caller-owned SQLAlchemy engine.

    The engine is never disposed here. Apply pool sizing on the engine you
    pass in; ``max_connections`` only caps parallel workers.
    """
    if max_connections < 1:
        raise ValueError('max_connections must be >= 1')
    schema_list = _normalize_schemas(schemas)
    type_list = normalize_object_types(object_types)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    logger.info(
        'unload start schemas=%s object_types=%s output_dir=%s full=%s '
        'lookback_minutes=%s custom_sql_dir=%s',
        ','.join(schema_list),
        ','.join(type_list),
        target,
        full,
        lookback_minutes,
        custom_sql_dir or 'none',
    )
    state = load_state(target)
    schema_errors = []
    for schema in schema_list:
        logger.info('unloading schema %s to %s', schema, target)
        try:
            state = unload_schema(
                engine,
                schema,
                target,
                object_types=type_list,
                state=state,
                lookback_minutes=lookback_minutes,
                max_connections=max_connections,
                full=full,
            )
        except Exception as exc:
            logger.exception('schema %s failed', schema)
            schema_errors.append((schema, exc))
        else:
            logger.info('schema %s: done', schema)

    if custom_sql_dir is not None:
        dump_custom_sql(engine, Path(custom_sql_dir), target)

    elapsed = time.perf_counter() - started
    if schema_errors:
        names = ', '.join(schema for schema, _exc in schema_errors)
        logger.error('unload failed for schema(s): %s (%.1fs)', names, elapsed)
        raise UnloadError(f'unload failed for schema(s): {names}')
    logger.info('unload complete in %.1fs', elapsed)

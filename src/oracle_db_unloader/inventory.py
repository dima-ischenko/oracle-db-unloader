from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .resources import bind_params, load_sql

TYPE_FOLDERS = {
    'TABLE': 'tables',
    'VIEW': 'views',
    'MATERIALIZED VIEW': 'mviews',
    'PACKAGE': 'packages',
    'PACKAGE BODY': 'packages',
    'FUNCTION': 'functions',
    'PROCEDURE': 'procedures',
    'TRIGGER': 'triggers',
    'TYPE': 'types',
    'TYPE BODY': 'types',
    'SEQUENCE': 'sequences',
    'SYNONYM': 'synonyms',
}

TYPE_SUFFIX = {
    'PACKAGE': '_s',
    'PACKAGE BODY': '_b',
    'TYPE': '_s',
    'TYPE BODY': '_b',
}

UNLOAD_SQL = {
    'TABLE': 'unload_table.sql',
    'VIEW': 'unload_view.sql',
    'MATERIALIZED VIEW': 'unload_mview.sql',
    'PACKAGE': 'unload_source.sql',
    'PACKAGE BODY': 'unload_source.sql',
    'FUNCTION': 'unload_source.sql',
    'PROCEDURE': 'unload_source.sql',
    'TRIGGER': 'unload_source.sql',
    'TYPE': 'unload_source.sql',
    'TYPE BODY': 'unload_source.sql',
    'SEQUENCE': 'unload_sequence.sql',
    'SYNONYM': 'unload_synonym.sql',
}

SOURCE_TYPES = {
    'PACKAGE',
    'PACKAGE BODY',
    'FUNCTION',
    'PROCEDURE',
    'TRIGGER',
    'TYPE',
    'TYPE BODY',
}

HEADER_TYPES = {'TABLE', 'MATERIALIZED VIEW'}


@dataclass(frozen=True)
class DbObject:
    schema: str
    owner: str
    name: str
    object_type: str
    last_ddl_time: Optional[datetime]

    @property
    def relpath(self) -> str:
        return object_relpath(self.schema, self.name, self.object_type)


def object_relpath(schema: str, name: str, object_type: str) -> str:
    folder = TYPE_FOLDERS[object_type]
    suffix = TYPE_SUFFIX.get(object_type, '')
    filename = f'{name.lower()}{suffix}.sql'
    return f'{schema.lower()}/{folder}/{filename}'


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def plan_actions(
    objects: Iterable[DbObject],
    disk_relpaths: Set[str],
    last_unload_at: Optional[datetime],
    lookback_minutes: int,
) -> Tuple[List[DbObject], Set[str]]:
    object_list = list(objects)
    cutoff = None
    if last_unload_at is not None:
        cutoff = as_utc(last_unload_at) - timedelta(minutes=lookback_minutes)

    to_write: List[DbObject] = []
    known_paths = {obj.relpath for obj in object_list}
    for obj in object_list:
        missing = obj.relpath not in disk_relpaths
        if cutoff is None or missing:
            to_write.append(obj)
            continue
        ddl_time = as_utc(obj.last_ddl_time)
        if ddl_time is None or ddl_time >= cutoff:
            to_write.append(obj)

    to_delete = {path for path in disk_relpaths if path not in known_paths}
    return to_write, to_delete


def walk_schema_files(output_dir: Path, schema: str) -> Set[str]:
    root = output_dir / schema.lower()
    found: Set[str] = set()
    if not root.is_dir():
        return found
    folders = set(TYPE_FOLDERS.values())
    for folder in folders:
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in directory.glob('*.sql'):
            found.add(path.relative_to(output_dir).as_posix())
    return found


def fetch_inventory(engine: Engine, schema: str) -> List[DbObject]:
    sql = load_sql('inventory.sql')
    schema_u = schema.upper()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), bind_params(sql, {'schema': schema_u}))
        by_path = {}
        for owner, name, object_type, last_ddl_time in rows:
            obj = DbObject(
                schema=schema_u,
                owner=owner,
                name=name,
                object_type=object_type,
                last_ddl_time=last_ddl_time,
            )
            existing = by_path.get(obj.relpath)
            if existing is None or (
                existing.owner == 'PUBLIC' and obj.owner != 'PUBLIC'
            ):
                by_path[obj.relpath] = obj
        return list(by_path.values())

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine
from tabulate import tabulate

from .logger import get_logger
from .resources import bind_params

logger = get_logger(__name__)

NULL_TOKEN = 'null'
_MONTHS = (
    'jan',
    'feb',
    'mar',
    'apr',
    'may',
    'jun',
    'jul',
    'aug',
    'sep',
    'oct',
    'nov',
    'dec',
)


def stringify_cell(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        month = _MONTHS[value.month - 1]
        return f'{value.day:02d}-{month}-{value.year} {value:%H:%M:%S}'
    if isinstance(value, date):
        month = _MONTHS[value.month - 1]
        return f'{value.day:02d}-{month}-{value.year}'
    if isinstance(value, Decimal):
        rendered = format(value, 'f')
        if '.' in rendered:
            rendered = rendered.rstrip('0').rstrip('.')
        return rendered
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def format_table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> str:
    str_rows: List[List[str]] = []
    for row in rows:
        rendered_row = []
        for value in row:
            rendered = stringify_cell(value)
            rendered_row.append(NULL_TOKEN if rendered is None else rendered)
        str_rows.append(rendered_row)
    return (
        tabulate(
            str_rows,
            headers=list(columns),
            tablefmt='github',
            disable_numparse=True,
        )
        + '\n'
    )


def discover_custom_sql(root: Path) -> List[Tuple[Path, str]]:
    """Find ``_dir/*.sql`` scripts. Returns ``(path, relative stem)`` pairs.

    Relative stem is ``_meta/get_table_stats`` for ``_meta/get_table_stats.sql``.
    """
    sql_dir = Path(root)
    found: List[Tuple[Path, str]] = []
    if not sql_dir.is_dir():
        return found
    for directory in sorted(
        child
        for child in sql_dir.iterdir()
        if child.is_dir() and child.name.startswith('_')
    ):
        for path in sorted(directory.glob('*.sql')):
            found.append((path, f'{directory.name}/{path.stem}'))
    return found


def custom_sql_roots(
    output_dir: Path,
    custom_sql_dir: Optional[Path] = None,
) -> List[Path]:
    roots: List[Path] = []
    seen = set()
    for raw in (custom_sql_dir, output_dir):
        if raw is None:
            continue
        path = Path(raw)
        key = path.resolve() if path.exists() else path
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def _warn_legacy_flat_sql(root: Path) -> None:
    legacy = sorted(path for path in Path(root).glob('*.sql') if path.is_file())
    if not legacy:
        return
    example = legacy[0].name
    logger.warning(
        'custom sql ignored top-level %s under %s; put scripts in _<dir>/ '
        '(e.g. _meta/%s)',
        ', '.join(path.name for path in legacy),
        root,
        example,
    )


def dump_custom_sql(
    engine: Engine,
    output_dir: Path,
    schemas: Sequence[str],
    custom_sql_dir: Optional[Path] = None,
) -> int:
    roots = custom_sql_roots(Path(output_dir), custom_sql_dir)
    scripts: List[Tuple[Path, str]] = []
    seen_rel: Dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            if custom_sql_dir is not None and root == Path(custom_sql_dir):
                raise FileNotFoundError(f'custom SQL directory not found: {root}')
            continue
        _warn_legacy_flat_sql(root)
        for path, rel in discover_custom_sql(root):
            if rel in seen_rel:
                continue
            seen_rel[rel] = path
            scripts.append((path, rel))

    if not scripts:
        if custom_sql_dir is not None:
            logger.info('custom sql: 0 script(s) from %s', custom_sql_dir)
        return 0

    schema_list = [schema.strip().upper() for schema in schemas if schema.strip()]
    logger.info(
        'custom sql: %d script(s) for %d schema(s)',
        len(scripts),
        len(schema_list),
    )
    dumped = 0
    with engine.connect() as conn:
        for path, rel in scripts:
            sql = path.read_text(encoding='utf-8').strip()
            if not sql:
                logger.warning('custom sql skipped empty file %s', path.as_posix())
                continue
            for schema in schema_list:
                params = bind_params(sql, {'schema': schema})
                result = conn.execute(text(sql), params)
                columns = list(result.keys())
                rows = [list(row) for row in result]
                rendered = format_table(columns, rows)
                target = Path(output_dir) / schema.lower() / f'{rel}.txt'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rendered, encoding='utf-8')
                dumped += 1
                logger.info(
                    'custom sql %s schema=%s -> %s (%d rows)',
                    rel,
                    schema,
                    target.as_posix(),
                    len(rows),
                )
    logger.info('custom sql: wrote %d file(s)', dumped)
    return dumped

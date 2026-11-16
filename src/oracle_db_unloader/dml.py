from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine
from tabulate import tabulate

from .logger import get_logger

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


def dump_custom_sql(engine: Engine, custom_sql_dir: Path, output_dir: Path) -> None:
    sql_dir = Path(custom_sql_dir)
    if not sql_dir.is_dir():
        raise FileNotFoundError(f'custom SQL directory not found: {sql_dir}')
    dml_dir = Path(output_dir) / 'dml'
    dml_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(sql_dir.glob('*.sql'))
    logger.info('custom sql: %d script(s) from %s', len(files), sql_dir)
    dumped = 0
    with engine.connect() as conn:
        for path in files:
            sql = path.read_text(encoding='utf-8').strip()
            if not sql:
                logger.warning('custom sql skipped empty file %s', path.name)
                continue
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result]
            rendered = format_table(columns, rows)
            target = dml_dir / f'{path.stem}.txt'
            target.write_text(rendered, encoding='utf-8')
            dumped += 1
            logger.info(
                'custom sql %s -> %s (%d rows)',
                path.name,
                target.as_posix(),
                len(rows),
            )
    logger.info('custom sql: wrote %d file(s) to %s', dumped, dml_dir)

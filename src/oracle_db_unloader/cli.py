from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence
from urllib.parse import quote_plus

from sqlalchemy import create_engine

from .inventory import normalize_object_types
from .logger import configure_logging, get_logger
from .unloader import UnloadError, unload

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Unload Oracle schema objects to SQL files.',
    )
    parser.add_argument('--db-url', dest='db_url', help='SQLAlchemy Oracle URL')
    parser.add_argument('--db-login', dest='db_login', help='Oracle user')
    parser.add_argument('--db-pass', dest='db_pass', help='Oracle password')
    parser.add_argument('--db-tns', dest='db_tns', help='TNS alias or Easy Connect string')
    parser.add_argument(
        '--schemas',
        required=True,
        help='Comma-separated schema list',
    )
    parser.add_argument(
        '--output-dir',
        required=True,
        dest='output_dir',
        help='Directory for SQL files and per-schema .unloader_state.json',
    )
    parser.add_argument(
        '--max-workers',
        dest='max_workers',
        type=int,
        default=5,
        help='Parallel unload workers / SQLAlchemy pool size (default: 5)',
    )
    parser.add_argument(
        '--custom-sql-dir',
        dest='custom_sql_dir',
        default=None,
        help=(
            'Directory of underscore-prefixed folders with SELECT scripts '
            '(e.g. _meta/get_table_stats.sql). If omitted, scripts are read '
            'from output-dir. Bind :schema to run the same query for every '
            'schema. A script in <schema>/_meta/*.sql runs only for that '
            'schema. Results go to <schema>/_meta/<script>.md'
        ),
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Ignore watermarks and rewrite every object',
    )
    parser.add_argument(
        '--lookback-minutes',
        dest='lookback_minutes',
        type=int,
        default=0,
        help='Widen incremental cutoff by this many minutes (default: 0)',
    )
    parser.add_argument(
        '--log-level',
        dest='log_level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log verbosity (default: INFO)',
    )
    parser.add_argument(
        '--object-types',
        dest='object_types',
        default=None,
        help=(
            'Comma-separated object types (default: all). '
            'Examples: table,view,package,mview,function,procedure,'
            'trigger,type,sequence,synonym'
        ),
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.db_url and not (args.db_login and args.db_pass and args.db_tns):
        parser.error('provide --db-url or --db-login, --db-pass, and --db-tns')
    if args.max_workers < 1:
        parser.error('--max-workers must be >= 1')
    if args.lookback_minutes < 0:
        parser.error('--lookback-minutes must be >= 0')
    if args.object_types:
        try:
            args.object_types = normalize_object_types(_split_csv(args.object_types))
        except ValueError as exc:
            parser.error(str(exc))
    else:
        args.object_types = None
    return args


def _split_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(',') if part.strip()]


def _build_url(
    url: str | None = None,
    db_login: str | None = None,
    db_pass: str | None = None,
    db_tns: str | None = None,
) -> str:
    if url:
        return url
    if db_login and db_pass and db_tns:
        user = quote_plus(db_login)
        password = quote_plus(db_pass)
        return f'oracle+oracledb://{user}:{password}@{db_tns}'
    raise ValueError('Provide url or db_login, db_pass, and db_tns')


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    url = _build_url(
        url=args.db_url,
        db_login=args.db_login,
        db_pass=args.db_pass,
        db_tns=args.db_tns,
    )
    engine = create_engine(
        url,
        pool_size=args.max_workers,
        max_overflow=0,
        pool_pre_ping=True,
    )
    try:
        unload(
            engine,
            schemas=_split_csv(args.schemas),
            output_dir=args.output_dir,
            max_workers=args.max_workers,
            custom_sql_dir=args.custom_sql_dir,
            object_types=args.object_types,
            full=args.full,
            lookback_minutes=args.lookback_minutes,
        )
    except UnloadError as exc:
        logger.error('%s', exc)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == '__main__':
    sys.exit(main())

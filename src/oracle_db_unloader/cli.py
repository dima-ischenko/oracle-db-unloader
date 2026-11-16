from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .engine import build_url, create_unloader_engine
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
        help='Directory for SQL files and .unloader_state.json',
    )
    parser.add_argument(
        '--max-connections',
        dest='max_connections',
        type=int,
        default=5,
        help='SQLAlchemy pool size / parallel unload workers (default: 5)',
    )
    parser.add_argument(
        '--custom-sql-dir',
        dest='custom_sql_dir',
        default=None,
        help='Directory of SELECT scripts dumped as text tables under dml/',
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
    if args.max_connections < 1:
        parser.error('--max-connections must be >= 1')
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    url = build_url(
        url=args.db_url,
        db_login=args.db_login,
        db_pass=args.db_pass,
        db_tns=args.db_tns,
    )
    engine = create_unloader_engine(url, max_connections=args.max_connections)
    try:
        unload(
            engine,
            schemas=_split_csv(args.schemas),
            output_dir=args.output_dir,
            max_connections=args.max_connections,
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

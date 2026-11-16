from __future__ import annotations

import pytest

from oracle_db_unloader.cli import parse_args


def test_parse_db_url_and_defaults():
    args = parse_args(
        [
            '--db-url',
            'oracle+oracledb://u:p@localhost:1521/?service_name=FREEPDB1',
            '--schemas',
            'scott,hr',
            '--output-dir',
            '/tmp/ddl',
        ]
    )
    assert args.db_url.startswith('oracle+oracledb://')
    assert args.schemas == 'scott,hr'
    assert args.output_dir == '/tmp/ddl'
    assert args.max_connections == 5
    assert args.lookback_minutes == 5
    assert args.full is False
    assert args.custom_sql_dir is None
    assert args.log_level == 'INFO'


def test_parse_login_and_flags():
    args = parse_args(
        [
            '--db-login',
            'system',
            '--db-pass',
            'secret',
            '--db-tns',
            'orclpdb',
            '--schemas',
            'scott',
            '--output-dir',
            'out',
            '--max-connections',
            '3',
            '--custom-sql-dir',
            'sql',
            '--full',
            '--lookback-minutes',
            '0',
            '--log-level',
            'DEBUG',
        ]
    )
    assert args.db_login == 'system'
    assert args.db_tns == 'orclpdb'
    assert args.max_connections == 3
    assert args.custom_sql_dir == 'sql'
    assert args.full is True
    assert args.lookback_minutes == 0
    assert args.log_level == 'DEBUG'


def test_missing_connection_errors():
    with pytest.raises(SystemExit):
        parse_args(['--schemas', 'scott', '--output-dir', 'out'])

from __future__ import annotations

import pytest

from oracle_db_unloader.engine import build_url


def test_build_url_prefers_explicit_url():
    url = build_url(url='oracle+oracledb://a:b@x', db_login='l', db_pass='p', db_tns='t')
    assert url == 'oracle+oracledb://a:b@x'


def test_build_url_from_login():
    url = build_url(db_login='system', db_pass='p@ss', db_tns='orclpdb')
    assert url.startswith('oracle+oracledb://system:')
    assert url.endswith('@orclpdb')
    assert 'p%40ss' in url


def test_build_url_requires_connection():
    with pytest.raises(ValueError):
        build_url()

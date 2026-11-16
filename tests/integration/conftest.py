from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from .seed import reset_schema

DEFAULT_URL = 'oracle+oracledb://test:test_pass@localhost:1521/?service_name=FREEPDB1'


@pytest.fixture(scope='session')
def db_url():
    return os.environ.get('ORACLE_URL', DEFAULT_URL)


@pytest.fixture(scope='session')
def engine(db_url):
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text('select 1 from dual'))
    except Exception as exc:
        engine.dispose()
        if os.environ.get('CI'):
            raise
        pytest.skip(f'Oracle is not available: {exc}')
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_schema(engine):
    reset_schema(engine)
    return engine

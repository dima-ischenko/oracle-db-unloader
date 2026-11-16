from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from .resources import load_sql


def build_url(
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


def apply_session_transforms(conn: Connection) -> None:
    """Set dbms_metadata session transforms on an open connection."""
    conn.exec_driver_sql(load_sql('set_transform_params.sql'))


def create_unloader_engine(url: str, max_connections: int = 5) -> Engine:
    if max_connections < 1:
        raise ValueError('max_connections must be >= 1')
    return create_engine(
        url,
        pool_size=max_connections,
        max_overflow=0,
        pool_pre_ping=True,
    )

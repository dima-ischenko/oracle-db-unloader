from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

SQL_DIR = Path(__file__).resolve().parent / 'sql'
_BIND_RE = re.compile(r'(?<!:):([A-Za-z_][A-Za-z0-9_]*)')
_SIMPLE_IDENT_RE = re.compile(r'^[A-Z][A-Z0-9_$#]*$')


def load_sql(name: str) -> str:
    path = SQL_DIR / name
    return path.read_text(encoding='utf-8')


def split_statements(sql: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    for line in sql.splitlines():
        if line.strip() == '/':
            stmt = '\n'.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(line)
    stmt = '\n'.join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def bind_params(sql: str, params: Dict[str, Any]) -> Dict[str, Any]:
    names = set(_BIND_RE.findall(sql))
    return {name: params[name] for name in names if name in params}


def as_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8')
    read = getattr(value, 'read', None)
    if callable(read):
        data = read()
        return as_text(data)
    return str(value)


def format_oracle_ident(name: str) -> str:
    """Quote mixed-case and other non-simple Oracle identifiers."""
    if _SIMPLE_IDENT_RE.fullmatch(name or ''):
        return name.lower()
    return '"' + (name or '').replace('"', '""') + '"'


def strip_owner_qualifiers(ddl: str, owner: str) -> str:
    """Drop schema qualifiers; the output path already names the schema."""
    if not ddl or not owner:
        return ddl
    quoted = re.compile(re.escape(f'"{owner}"') + r'\.', re.IGNORECASE)
    unquoted = re.compile(
        r'(?<![\w"])' + re.escape(owner) + r'\.',
        re.IGNORECASE,
    )
    return unquoted.sub('', quoted.sub('', ddl))


def concat_ddl(parts: Iterable[Any]) -> str:
    chunks: List[str] = []
    for part in parts:
        text = as_text(part)
        if not text:
            continue
        if chunks and not chunks[-1].endswith('\n') and not text.startswith('\n'):
            chunks.append('\n')
        chunks.append(text)
    if not chunks:
        return ''
    joined = ''.join(chunks)
    return joined if joined.endswith('\n') else joined + '\n'

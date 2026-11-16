from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .inventory import normalize_ddl_time

STATE_FILENAME = '.unloader_state.json'


def state_path(output_dir: Path) -> Path:
    return Path(output_dir) / STATE_FILENAME


def load_state(output_dir: Path) -> Dict[str, Any]:
    path = state_path(output_dir)
    if not path.is_file():
        return {'schemas': {}}
    payload = json.loads(path.read_text(encoding='utf-8'))
    schemas = payload.get('schemas') or {}
    return {'schemas': schemas}


def save_state(output_dir: Path, state: Dict[str, Any]) -> None:
    path = state_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return normalize_ddl_time(datetime.fromisoformat(raw))


def _serialize_timestamp(value: datetime) -> str:
    naive = normalize_ddl_time(value)
    if naive is None:
        raise ValueError('timestamp is required')
    return naive.isoformat(timespec='microseconds')


def get_last_unload_at(
    state: Dict[str, Any],
    schema: str,
    object_type: Optional[str] = None,
) -> Optional[datetime]:
    entry = (state.get('schemas') or {}).get(schema.upper()) or {}
    if object_type:
        typed = (entry.get('types') or {}).get(object_type) or {}
        parsed = _parse_timestamp(
            typed.get('last_ddl_time') or typed.get('last_unload_at')
        )
        if parsed is not None:
            return parsed
    return _parse_timestamp(
        entry.get('last_ddl_time') or entry.get('last_unload_at')
    )


def set_last_unload_at(
    state: Dict[str, Any],
    schema: str,
    when: datetime,
    object_type: str,
) -> Dict[str, Any]:
    schemas = dict(state.get('schemas') or {})
    schema_key = schema.upper()
    entry = dict(schemas.get(schema_key) or {})
    types = dict(entry.get('types') or {})
    types[object_type] = {'last_ddl_time': _serialize_timestamp(when)}
    entry['types'] = types
    schemas[schema_key] = entry
    return {'schemas': schemas}

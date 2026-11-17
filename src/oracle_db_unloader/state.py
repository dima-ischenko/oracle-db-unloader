from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .inventory import normalize_ddl_time

STATE_FILENAME = '.unloader_state.json'


def state_path(output_dir: Path, schema: str) -> Path:
    return Path(output_dir) / schema.lower() / STATE_FILENAME


def legacy_state_path(output_dir: Path) -> Path:
    return Path(output_dir) / STATE_FILENAME


def load_state(output_dir: Path, schema: str) -> Dict[str, Any]:
    path = state_path(output_dir, schema)
    payload = _read_json(path)
    if payload is not None:
        return _schema_entry(payload, schema)
    legacy = _read_json(legacy_state_path(output_dir))
    if legacy is not None:
        return _schema_entry(legacy, schema)
    return {}


def save_state(output_dir: Path, schema: str, state: Dict[str, Any]) -> None:
    _write_json(state_path(output_dir, schema), state)
    _split_legacy_state(output_dir)


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return normalize_ddl_time(datetime.fromisoformat(raw))


def _serialize_timestamp(value: datetime) -> str:
    naive = normalize_ddl_time(value)
    if naive is None:
        raise ValueError('timestamp is required')
    return naive.isoformat(timespec='seconds')


def get_last_unload_at(
    state: Dict[str, Any],
    object_type: Optional[str] = None,
) -> Optional[datetime]:
    entry = state or {}
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
    when: datetime,
    object_type: str,
) -> Dict[str, Any]:
    entry = dict(state or {})
    types = dict(entry.get('types') or {})
    types[object_type] = {'last_ddl_time': _serialize_timestamp(when)}
    entry['types'] = types
    return entry


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, dict):
        return payload
    return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _schema_entry(payload: Dict[str, Any], schema: str) -> Dict[str, Any]:
    if 'types' in payload or 'last_unload_at' in payload or 'last_ddl_time' in payload:
        return payload
    schemas = payload.get('schemas') or {}
    entry = schemas.get(schema.upper())
    return dict(entry) if isinstance(entry, dict) else {}


def _split_legacy_state(output_dir: Path) -> None:
    path = legacy_state_path(output_dir)
    payload = _read_json(path)
    if payload is None:
        return
    schemas = payload.get('schemas') or {}
    for name, entry in schemas.items():
        dest = state_path(output_dir, str(name))
        if dest.is_file() or not isinstance(entry, dict):
            continue
        _write_json(dest, entry)
    path.unlink()

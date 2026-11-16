from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

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
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_last_unload_at(
    state: Dict[str, Any],
    schema: str,
    object_type: Optional[str] = None,
) -> Optional[datetime]:
    entry = (state.get('schemas') or {}).get(schema.upper()) or {}
    if object_type:
        typed = ((entry.get('types') or {}).get(object_type) or {}).get(
            'last_unload_at'
        )
        parsed = _parse_timestamp(typed)
        if parsed is not None:
            return parsed
    return _parse_timestamp(entry.get('last_unload_at'))


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
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    types[object_type] = {'last_unload_at': when.isoformat()}
    entry['types'] = types
    schemas[schema_key] = entry
    return {'schemas': schemas}

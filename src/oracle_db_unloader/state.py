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


def get_last_unload_at(state: Dict[str, Any], schema: str) -> Optional[datetime]:
    entry = (state.get('schemas') or {}).get(schema.upper()) or {}
    raw = entry.get('last_unload_at')
    if not raw:
        return None
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def set_last_unload_at(
    state: Dict[str, Any],
    schema: str,
    when: datetime,
) -> Dict[str, Any]:
    schemas = dict(state.get('schemas') or {})
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    schemas[schema.upper()] = {'last_unload_at': when.isoformat()}
    return {'schemas': schemas}

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .inventory import normalize_ddl_time

STATE_FILENAME = '.unloader_state.json'


def state_path(output_dir: Path, schema: str) -> Path:
    return Path(output_dir) / schema.lower() / STATE_FILENAME


def load_state(output_dir: Path, schema: str) -> Dict[str, Any]:
    path = state_path(output_dir, schema)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}


def save_state(output_dir: Path, schema: str, state: Dict[str, Any]) -> None:
    path = state_path(output_dir, schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def get_last_unload_at(state: Dict[str, Any], object_type: str) -> Optional[datetime]:
    typed = ((state or {}).get('types') or {}).get(object_type) or {}
    raw = typed.get('last_ddl_time')
    if not raw:
        return None
    return normalize_ddl_time(datetime.fromisoformat(raw))


def set_last_unload_at(
    state: Dict[str, Any],
    when: datetime,
    object_type: str,
) -> Dict[str, Any]:
    naive = normalize_ddl_time(when)
    if naive is None:
        raise ValueError('timestamp is required')
    types = dict((state or {}).get('types') or {})
    types[object_type] = {'last_ddl_time': naive.isoformat(timespec='seconds')}
    return {'types': types}

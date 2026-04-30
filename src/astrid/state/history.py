from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.config import ASTRID_DIR, ASTRID_HISTORY_PATH


def _strip_leading_bom_mojibake(text: str) -> str:
    cleaned = text.lstrip("\ufeff")
    slash_index = cleaned.find("/")
    if 0 < slash_index <= 3:
        prefix = cleaned[:slash_index]
        if all((ord(ch) > 127) or ch == "?" or (0xDC00 <= ord(ch) <= 0xDFFF) for ch in prefix):
            return cleaned[slash_index:]
    return cleaned


def _read_history_payload() -> dict[str, Any]:
    if not ASTRID_HISTORY_PATH.exists():
        return {}
    try:
        parsed = json.loads(ASTRID_HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_entry(entry: Any) -> str:
    text = str(entry)
    return _strip_leading_bom_mojibake(text).replace("\x00", "")


def _normalize_entries(entries: Any) -> list[str]:
    return [_normalize_entry(entry) for entry in entries] if isinstance(entries, list) else []


def _normalize_workspace_key(workspace: str | None) -> str | None:
    if not workspace:
        return None
    try:
        return str(Path(workspace).resolve())
    except OSError:
        return str(Path(workspace))


def load_history_entries(workspace: str | None = None) -> list[str]:
    parsed = _read_history_payload()
    workspace_key = _normalize_workspace_key(workspace)

    by_workspace = parsed.get("byWorkspace")
    if isinstance(by_workspace, dict) and workspace_key is not None:
        return _normalize_entries(by_workspace.get(workspace_key, []))

    if workspace_key is None:
        return _normalize_entries(parsed.get("entries", []))

    return []


def save_history_entries(entries: list[str], workspace: str | None = None) -> None:
    ASTRID_DIR.mkdir(parents=True, exist_ok=True)
    trimmed_entries = [_normalize_entry(entry) for entry in entries[-200:]]
    workspace_key = _normalize_workspace_key(workspace)

    if workspace_key is None:
        payload: dict[str, Any] = {"entries": trimmed_entries}
    else:
        parsed = _read_history_payload()
        existing = parsed.get("byWorkspace")
        by_workspace = dict(existing) if isinstance(existing, dict) else {}
        by_workspace[workspace_key] = trimmed_entries
        payload = {"byWorkspace": by_workspace}

    ASTRID_HISTORY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

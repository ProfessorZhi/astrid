from __future__ import annotations

import json
import os
from enum import Enum


class VerbMode(str, Enum):
    APPEND = "append"
    REPLACE = "replace"


DEFAULT_PHASE_VERBS: dict[str, tuple[str, ...]] = {
    "idle": ("Ready",),
    "planning": ("Unravelling", "Mapping", "Scoping"),
    "spawning": ("Dispatching", "Assigning", "Routing"),
    "running": ("Working", "Building", "Tracing"),
    "collecting": ("Gathering", "Collecting", "Folding"),
    "reviewing": ("Inspecting", "Reviewing", "Verifying"),
    "merging": ("Merging", "Stitching", "Consolidating"),
    "done": ("Ready",),
    "failed": ("Blocked", "Recovering", "Retrying"),
}


def _normalize_verbs(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    values = [str(item).strip() for item in raw if str(item).strip()]
    return tuple(values)


def _load_runtime_override() -> tuple[VerbMode, dict[str, tuple[str, ...]]]:
    raw = os.environ.get("ASTRID_SPINNER_VERBS", "").strip()
    if not raw:
        return VerbMode.APPEND, {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return VerbMode.APPEND, {}
    if not isinstance(payload, dict):
        return VerbMode.APPEND, {}
    mode = VerbMode(str(payload.get("mode", "append")).lower()) if str(payload.get("mode", "append")).lower() in {"append", "replace"} else VerbMode.APPEND
    phase_map = payload.get("phases", {})
    if not isinstance(phase_map, dict):
        return mode, {}
    normalized = {
        str(key).lower(): _normalize_verbs(value)
        for key, value in phase_map.items()
        if _normalize_verbs(value)
    }
    return mode, normalized


def get_phase_verbs(phase: str) -> tuple[str, ...]:
    normalized_phase = str(phase).lower()
    defaults = DEFAULT_PHASE_VERBS.get(normalized_phase, ("Coordinating",))
    mode, overrides = _load_runtime_override()
    custom = overrides.get(normalized_phase, ())
    if mode == VerbMode.REPLACE:
        return custom or defaults
    return defaults + custom if custom else defaults

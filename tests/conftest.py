from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_astrid_memory_root(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(tmp_path / "astrid-memories"))

"""Focused stability tests for context compaction and session resume."""

import astrid.session as session_mod
from astrid.context_manager import ContextManager
from astrid.session import create_new_session, load_session, save_session


def test_compaction_preserves_initial_user_task_and_recent_tool_context():
    manager = ContextManager(model="default", context_window=700)
    task = {
        "role": "user",
        "content": "CURRENT TASK: implement PR4 context memory stability",
    }
    recent_tool_call = {
        "role": "assistant_tool_call",
        "content": "read_file",
        "input": {"path": "astrid/context_manager.py"},
    }
    recent_tool_result = {
        "role": "tool_result",
        "content": "compact_messages currently drops old messages",
    }

    manager.add_message({"role": "system", "content": "You are Astrid."})
    manager.add_message(task)
    for index in range(30):
        manager.add_message({
            "role": "assistant_progress",
            "content": f"thinking {index} " + ("x" * 80),
        })
        manager.add_message({
            "role": "user",
            "content": f"old discussion {index} " + ("y" * 120),
        })
        manager.add_message({
            "role": "assistant",
            "content": f"old answer {index} " + ("z" * 120),
        })
    manager.add_message({"role": "user", "content": "Please inspect the file now."})
    manager.add_message(recent_tool_call)
    manager.add_message(recent_tool_result)

    compacted = manager.compact_messages()

    assert task in compacted
    assert recent_tool_call in compacted
    assert recent_tool_result in compacted


def test_session_resume_preserves_message_order_and_tool_payloads(tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    monkeypatch.setattr(session_mod, "ASTRID_DIR", tmp_path)
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", sessions_dir)

    session = create_new_session(workspace="/tmp/astrid")
    messages = [
        {"role": "user", "content": "CURRENT TASK: resume this exact work"},
        {
            "role": "assistant_tool_call",
            "content": "run_command",
            "input": {"command": "python -m pytest tests -q"},
        },
        {
            "role": "tool_result",
            "content": "1 failed, 20 passed",
            "metadata": {"exit_code": 1},
        },
        {"role": "assistant", "content": "The failing test proves the gap."},
    ]
    session.messages = messages

    save_session(session)
    loaded = load_session(session.session_id)

    assert loaded is not None
    assert loaded.messages == messages

from pathlib import Path

from astrid.permissions import PermissionManager
from astrid.tools.run_command import _build_execution_command, split_command_line
from astrid.tools.patch_file import patch_file_tool
from astrid.tools.multi_edit import multi_edit_tool
from astrid.tools.run_command import run_command_tool
from astrid.tools.todo_write import todo_write_tool
from astrid.tools.write_file import write_file_tool
from astrid.tooling import ToolContext


def test_split_command_line_supports_quotes() -> None:
    result = split_command_line("git commit -m 'hello world'")
    assert result[:3] == ["git", "commit", "-m"]
    assert result[3] == "hello world"


def test_write_file_tool_writes_after_review(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    result = write_file_tool.run(
        {"path": "demo.txt", "content": "hello"},
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is True
    assert (tmp_path / "demo.txt").read_text(encoding="utf-8") == "hello"


def test_patch_file_tool_applies_multiple_replacements(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    target = tmp_path / "demo.txt"
    target.write_text("hello world\nhello cc\n", encoding="utf-8")

    result = patch_file_tool.run(
        {
            "path": "demo.txt",
            "replacements": [
                {"search": "hello world", "replace": "hi world"},
                {"search": "hello cc", "replace": "hi cc"},
            ],
        },
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is True
    assert "2 replacement" in result.output
    assert target.read_text(encoding="utf-8") == "hi world\nhi cc\n"


def test_multi_edit_tool_requires_review(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=None)
    target = tmp_path / "demo.txt"
    target.write_text("hello world\n", encoding="utf-8")

    result = multi_edit_tool.run(
        {"changes": [{"file": "demo.txt", "old": "hello", "new": "hi"}], "dry_run": False},
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is False
    assert "requires approval" in result.output
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_multi_edit_tool_applies_after_review(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    target = tmp_path / "demo.txt"
    target.write_text("hello world\n", encoding="utf-8")

    result = multi_edit_tool.run(
        {"changes": [{"file": "demo.txt", "old": "hello", "new": "hi"}], "dry_run": False},
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "hi world\n"


def test_todo_write_nudges_when_multi_step_list_lacks_verification(tmp_path: Path) -> None:
    result = todo_write_tool.run(
        {
            "todos": [
                {"content": "Create index.html", "status": "completed"},
                {"content": "Implement game loop", "status": "completed"},
                {"content": "Write README", "status": "completed"},
            ]
        },
        ToolContext(cwd=str(tmp_path)),
    )

    assert result.ok is True
    assert "without a verification task" in result.output
    assert "Before finalizing" in result.output


def test_todo_write_skips_nudge_when_verification_task_exists(tmp_path: Path) -> None:
    result = todo_write_tool.run(
        {
            "todos": [
                {"content": "Create index.html", "status": "completed"},
                {"content": "Implement game loop", "status": "completed"},
                {"content": "Run browser smoke test", "status": "completed"},
            ]
        },
        ToolContext(cwd=str(tmp_path)),
    )

    assert result.ok is True
    assert "without a verification task" not in result.output


def test_build_execution_command_uses_cmd_for_windows_shell_builtins() -> None:
    command, args = _build_execution_command(
        "echo hello world",
        "echo",
        ["hello", "world"],
        use_shell=False,
        background_shell=False,
    )

    if __import__("os").name == "nt":
        assert command == "cmd"
        assert args[:3] == ["/d", "/s", "/c"]
        assert args[3] == "echo hello world"
    else:
        assert command == "echo"
        assert args == ["hello", "world"]


def test_run_command_tool_supports_echo_on_current_platform(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    result = run_command_tool.run(
        {"command": "echo hello"},
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is True
    assert "hello" in result.output.lower()


def test_split_command_line_unwraps_quoted_python_c_payload() -> None:
    result = split_command_line('python -c "import os;print(os.getcwd())"')

    assert result == ["python", "-c", "import os;print(os.getcwd())"]


def test_run_command_tool_executes_quoted_python_c_payload(tmp_path: Path) -> None:
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    result = run_command_tool.run(
        {"command": 'python -c "import os;print(os.getcwd())"'},
        ToolContext(cwd=str(tmp_path), permissions=permissions),
    )

    assert result.ok is True
    assert str(tmp_path) in result.output

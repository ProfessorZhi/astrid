import os
from pathlib import Path
from unittest.mock import patch

from astrid.mcp import _resolve_mcp_command, _validate_mcp_command, create_mcp_backed_tools
from astrid.tooling import ToolContext


def test_create_mcp_backed_tools_supports_newline_json(tmp_path: Path) -> None:
    server_script = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"
    mcp = create_mcp_backed_tools(
        cwd=str(tmp_path),
        mcp_servers={
            "fake": {
                "command": "python",
                "args": [str(server_script)],
                "protocol": "newline-json",
            }
        },
    )

    names = [tool.name for tool in mcp["tools"]]
    assert "mcp__fake__echo" in names
    assert "list_mcp_resources" in names
    assert "list_mcp_prompts" in names

    echo_tool = next(tool for tool in mcp["tools"] if tool.name == "mcp__fake__echo")
    result = echo_tool.run({"text": "hi"}, ToolContext(cwd=str(tmp_path)))
    assert result.ok is True
    assert result.output == "echo:hi"

    resource_tool = next(tool for tool in mcp["tools"] if tool.name == "read_mcp_resource")
    resource_result = resource_tool.run({"server": "fake", "uri": "fake://hello"}, ToolContext(cwd=str(tmp_path)))
    assert "hello resource" in resource_result.output

    prompt_tool = next(tool for tool in mcp["tools"] if tool.name == "get_mcp_prompt")
    prompt_result = prompt_tool.run({"server": "fake", "name": "hello", "arguments": {"name": "cc"}}, ToolContext(cwd=str(tmp_path)))
    assert "hello cc" in prompt_result.output

    mcp["dispose"]()


def test_validate_mcp_command_allows_windows_program_files_absolute_path() -> None:
    if os.name != "nt":
        return

    _validate_mcp_command(r"C:\Program Files\Acme Tool\tool.exe")


def test_validate_mcp_command_rejects_windows_program_files_prefix_lookalike() -> None:
    if os.name != "nt":
        return

    try:
        _validate_mcp_command(r"C:\Program FilesX\Acme Tool\tool.exe")
    except RuntimeError as error:
        assert "not in the allowed list" in str(error)
    else:
        raise AssertionError("expected lookalike Program Files path to be rejected")


def test_resolve_mcp_command_uses_cmd_wrapper_on_windows() -> None:
    if os.name != "nt":
        return

    with patch("astrid.mcp.shutil.which") as mock_which:
        mock_which.side_effect = [None, r"E:\develop\nodejs\npx.cmd"]

        assert _resolve_mcp_command("npx") == r"E:\develop\nodejs\npx.cmd"


def test_resolve_mcp_command_keeps_non_windows_command() -> None:
    if os.name == "nt":
        return

    assert _resolve_mcp_command("npx") == "npx"


def test_create_mcp_backed_tools_supports_default_content_length_protocol(tmp_path: Path) -> None:
    server_script = Path(__file__).parent / "fixtures" / "fake_mcp_server_content_length.py"
    mcp = create_mcp_backed_tools(
        cwd=str(tmp_path),
        mcp_servers={
            "fake": {
                "command": "python",
                "args": [str(server_script)],
            }
        },
    )

    try:
        echo_tool = next(tool for tool in mcp["tools"] if tool.name == "mcp__fake__echo")
        result = echo_tool.run({"text": "hi"}, ToolContext(cwd=str(tmp_path)))
    finally:
        mcp["dispose"]()

    assert result.ok is True
    assert result.output == "echo:hi"


def test_create_mcp_backed_tools_supports_bom_prefixed_newline_json(tmp_path: Path) -> None:
    server_script = Path(__file__).parent / "fixtures" / "fake_mcp_server_bom.py"
    mcp = create_mcp_backed_tools(
        cwd=str(tmp_path),
        mcp_servers={
            "fake": {
                "command": "python",
                "args": [str(server_script)],
                "protocol": "newline-json",
            }
        },
    )

    try:
        echo_tool = next(tool for tool in mcp["tools"] if tool.name == "mcp__fake__echo")
        result = echo_tool.run({"text": "bom"}, ToolContext(cwd=str(tmp_path)))
    finally:
        mcp["dispose"]()

    assert result.ok is True
    assert result.output == "echo:bom"

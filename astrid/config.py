from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


ASTRID_DIR = Path.home() / ".astrid"
ASTRID_SETTINGS_PATH = ASTRID_DIR / "settings.json"
ASTRID_HISTORY_PATH = ASTRID_DIR / "history.json"
ASTRID_PERMISSIONS_PATH = ASTRID_DIR / "permissions.json"
ASTRID_MCP_PATH = ASTRID_DIR / "mcp.json"
DEFAULT_MAX_OUTPUT_TOKENS = 12000
DEFAULT_MAX_TOOL_STEPS = 25
DEFAULT_MODEL_TIMEOUT_SECONDS = 180

# 已知的合法模型名称（用于拼写检查提示）
KNOWN_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-haiku-3-20240307",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "MiniMax-M2.7",
]


def _suggest_model_name(typed: str) -> str:
    """根据输入建议最接近的合法模型名称"""
    if not typed:
        return ""
    
    # 简单的前缀匹配
    for model in KNOWN_MODELS:
        if model.startswith(typed.lower()):
            return model
    
    # 模糊匹配：包含输入字符的模型
    for model in KNOWN_MODELS:
        if typed.lower() in model:
            return model
    
    return ""


def project_mcp_path(cwd: str | Path | None = None) -> Path:
    return Path(cwd or Path.cwd()) / ".mcp.json"


def _read_json_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8-sig"))


def read_settings_file(file_path: Path) -> dict[str, Any]:
    return _read_json_file(file_path)


def read_mcp_config_file(file_path: Path) -> dict[str, Any]:
    parsed = _read_json_file(file_path)
    if not isinstance(parsed, dict):
        return {}
    mcp_servers = parsed.get("mcpServers", {})
    return mcp_servers if isinstance(mcp_servers, dict) else {}


def merge_settings(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged_mcp = dict(base.get("mcpServers", {}))
    for name, server in override.get("mcpServers", {}).items():
        current = dict(merged_mcp.get(name, {}))
        next_server = dict(server)
        current.update(next_server)
        current["env"] = {
            **dict(merged_mcp.get(name, {}).get("env", {})),
            **dict(next_server.get("env", {})),
        }
        merged_mcp[name] = current

    return {
        **base,
        **override,
        "env": {
            **dict(base.get("env", {})),
            **dict(override.get("env", {})),
        },
        "mcpServers": merged_mcp,
    }


def load_effective_settings(cwd: str | Path | None = None) -> dict[str, Any]:
    global_mcp = read_mcp_config_file(ASTRID_MCP_PATH)
    project_mcp = read_mcp_config_file(project_mcp_path(cwd))
    mini_code_settings = read_settings_file(ASTRID_SETTINGS_PATH)

    return merge_settings(
        merge_settings(mini_code_settings, {"mcpServers": global_mcp}),
        {"mcpServers": project_mcp},
    )


def save_mini_code_settings(updates: dict[str, Any]) -> None:
    ASTRID_DIR.mkdir(parents=True, exist_ok=True)
    existing = read_settings_file(ASTRID_SETTINGS_PATH)
    next_settings = merge_settings(existing, updates)
    ASTRID_SETTINGS_PATH.write_text(
        json.dumps(next_settings, indent=2) + "\n",
        encoding="utf-8",
    )


def load_pet_settings() -> dict[str, Any]:
    settings = read_settings_file(ASTRID_SETTINGS_PATH)
    pet = settings.get("pet", {})
    return pet if isinstance(pet, dict) else {}


def save_pet_settings(updates: dict[str, Any]) -> None:
    current = load_pet_settings()
    current.update(updates)
    save_mini_code_settings({"pet": current})


def load_runtime_config(cwd: str | Path | None = None) -> dict[str, Any]:
    effective = load_effective_settings(cwd)
    configured_env = dict(effective.get("env", {}))
    process_env = os.environ
    model = (
        process_env.get("ASTRID_MODEL")
        or effective.get("model")
        or str(configured_env.get("ANTHROPIC_MODEL", "")).strip()
        or str(process_env.get("ANTHROPIC_MODEL", "")).strip()
    )
    base_url = (
        str(configured_env.get("ANTHROPIC_BASE_URL", "")).strip()
        or str(process_env.get("ANTHROPIC_BASE_URL", "")).strip()
        or "https://api.anthropic.com"
    )
    configured_auth_token = str(configured_env.get("ANTHROPIC_AUTH_TOKEN", "")).strip()
    configured_api_key = str(configured_env.get("ANTHROPIC_API_KEY", "")).strip()
    if configured_auth_token or configured_api_key:
        auth_token = configured_auth_token or None
        api_key = configured_api_key or None
    else:
        auth_token = str(process_env.get("ANTHROPIC_AUTH_TOKEN", "")).strip() or None
        api_key = str(process_env.get("ANTHROPIC_API_KEY", "")).strip() or None
    raw_max_output_tokens = (
        process_env.get("ASTRID_MAX_OUTPUT_TOKENS")
        or effective.get("maxOutputTokens")
        or configured_env.get("ASTRID_MAX_OUTPUT_TOKENS")
    )
    max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS
    if raw_max_output_tokens is not None:
        try:
            parsed = int(raw_max_output_tokens)
            if parsed > 0:
                max_output_tokens = parsed
        except (TypeError, ValueError):
            max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS
    raw_max_tool_steps = (
        process_env.get("ASTRID_MAX_TOOL_STEPS")
        or effective.get("maxToolSteps")
        or configured_env.get("ASTRID_MAX_TOOL_STEPS")
    )
    max_tool_steps = DEFAULT_MAX_TOOL_STEPS
    if raw_max_tool_steps is not None:
        try:
            parsed = int(raw_max_tool_steps)
            if parsed > 0:
                max_tool_steps = parsed
        except (TypeError, ValueError):
            max_tool_steps = DEFAULT_MAX_TOOL_STEPS
    raw_model_timeout_seconds = (
        process_env.get("ASTRID_MODEL_TIMEOUT_SECONDS")
        or effective.get("modelTimeoutSeconds")
        or configured_env.get("ASTRID_MODEL_TIMEOUT_SECONDS")
    )
    model_timeout_seconds = DEFAULT_MODEL_TIMEOUT_SECONDS
    if raw_model_timeout_seconds is not None:
        try:
            parsed = int(raw_model_timeout_seconds)
            if parsed > 0:
                model_timeout_seconds = parsed
        except (TypeError, ValueError):
            model_timeout_seconds = DEFAULT_MODEL_TIMEOUT_SECONDS

    if not model:
        raise RuntimeError("No model configured. Set ~/.astrid/settings.json or ANTHROPIC_MODEL.")
    if not auth_token and not api_key:
        raise RuntimeError(
            "No auth configured. Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY."
        )

    return {
        "model": model,
        "baseUrl": base_url,
        "authToken": auth_token,
        "apiKey": api_key,
        "maxOutputTokens": max_output_tokens,
        "maxToolSteps": max_tool_steps,
        "modelTimeoutSeconds": model_timeout_seconds,
        "mcpServers": effective.get("mcpServers", {}),
        "sourceSummary": f"config: {ASTRID_SETTINGS_PATH} > {ASTRID_MCP_PATH} > {project_mcp_path(cwd)} > process.env",
    }


def get_mcp_config_path(scope: str, cwd: str | Path | None = None) -> Path:
    return project_mcp_path(cwd) if scope == "project" else ASTRID_MCP_PATH


def load_scoped_mcp_servers(scope: str, cwd: str | Path | None = None) -> dict[str, Any]:
    return read_mcp_config_file(get_mcp_config_path(scope, cwd))


def save_scoped_mcp_servers(scope: str, servers: dict[str, Any], cwd: str | Path | None = None) -> None:
    target = get_mcp_config_path(scope, cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n", encoding="utf-8")


def validate_config(cwd: str | Path | None = None) -> tuple[bool, list[str]]:
    """验证配置完整性，返回 (是否有效，错误列表)
    
    检查项：
    1. 模型名称是否配置
    2. API key 是否配置
    3. 模型名称拼写是否正确
    4. MCP 配置文件是否合法
    """
    errors: list[str] = []
    warnings: list[str] = []
    
    try:
        config = load_runtime_config(cwd)
        
        # 检查模型名称拼写
        model = config.get("model", "")
        if model and not any(model.lower() == km.lower() for km in KNOWN_MODELS):
            suggestion = _suggest_model_name(model)
            if suggestion:
                warnings.append(
                    f"Unknown model '{model}'. Did you mean '{suggestion}'?"
                )
            else:
                warnings.append(
                    f"Unknown model '{model}'. Known models: {', '.join(KNOWN_MODELS[:3])}..."
                )
        
        # 检查 MCP 配置
        mcp_servers = config.get("mcpServers", {})
        for name, server in mcp_servers.items():
            if not server.get("command"):
                errors.append(f"MCP server '{name}' has no command configured")
        
        return len(errors) == 0, errors + warnings
        
    except RuntimeError as e:
        error_msg = str(e)
        
        # 提供友好的错误消息
        if "No model configured" in error_msg:
            suggestion = _suggest_model_name(os.environ.get("ASTRID_MODEL", ""))
            help_msg = (
                f"Error: {error_msg}\n\n"
                "How to fix:\n"
                "  1. Set model name: export ANTHROPIC_MODEL=claude-sonnet-4-20250514\n"
                "  2. Or edit ~/.astrid/settings.json:\n"
                f'     {{"model": "claude-sonnet-4-20250514"}}\n'
            )
            if suggestion:
                help_msg += f"\n  Did you mean: {suggestion}?\n"
            help_msg += f"\n  Known models: {', '.join(KNOWN_MODELS[:3])}..."
            errors.append(help_msg)
            
        elif "No auth configured" in error_msg:
            help_msg = (
                f"Error: {error_msg}\n\n"
                "How to fix:\n"
                "  1. Set API key: export ANTHROPIC_API_KEY=sk-ant-...\n"
                "  2. Or edit ~/.astrid/settings.json:\n"
                '     {"env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}\n'
            )
            errors.append(help_msg)
        else:
            errors.append(str(e))
        
        return False, errors
    except Exception as e:
        return False, [f"Unexpected error: {e}"]


def format_config_diagnostic(cwd: str | Path | None = None) -> str:
    """格式化配置诊断信息"""
    is_valid, messages = validate_config(cwd)
    
    lines = ["Configuration Diagnostics", "=" * 40, ""]
    
    if is_valid:
        lines.append("Status: OK")
        if messages:
            lines.append("")
            lines.append("Warnings:")
            for msg in messages:
                lines.append(f"  ⚠️  {msg}")
    else:
        lines.append("Status: ERRORS")
        lines.append("")
        lines.append("Errors:")
        for msg in messages:
            lines.append(f"  ❌ {msg}")
    
    # 显示当前配置摘要
    try:
        config = load_runtime_config(cwd)
        lines.append("")
        lines.append("Current Configuration")
        lines.append("-" * 40)
        lines.append(f"  Model: {config.get('model', 'not set')}")
        lines.append(f"  Base URL: {config.get('baseUrl', 'not set')}")
        auth_method = "ANTHROPIC_AUTH_TOKEN" if config.get("authToken") else ("ANTHROPIC_API_KEY" if config.get("apiKey") else "not set")
        lines.append(f"  Auth: {auth_method}")
        lines.append(f"  MCP Servers: {len(config.get('mcpServers', {}))}")
    except Exception:
        pass
    
    return "\n".join(lines)

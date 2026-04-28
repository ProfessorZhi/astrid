from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Tool metadata (inspired by Claude Code's Tool type)
# ---------------------------------------------------------------------------


class ToolCapability(str, Enum):
    """Tool capability flags."""

    READ_ONLY = "read_only"
    DESTRUCTIVE = "destructive"
    CONCURRENCY_SAFE = "concurrency_safe"
    REQUIRES_PERMISSION = "requires_permission"


@dataclass
class ToolMetadata:
    """Tool metadata for classification and discovery."""

    name: str
    description: str
    capabilities: set[ToolCapability] = field(default_factory=set)
    input_schema: dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    max_result_size_chars: int = 10_000
    tags: list[str] = field(default_factory=list)

    @property
    def is_read_only(self) -> bool:
        return ToolCapability.READ_ONLY in self.capabilities

    @property
    def is_destructive(self) -> bool:
        return ToolCapability.DESTRUCTIVE in self.capabilities

    @property
    def is_concurrency_safe(self) -> bool:
        return ToolCapability.CONCURRENCY_SAFE in self.capabilities


# ---------------------------------------------------------------------------
# Tool Protocol (inspired by Claude Code's Tool interface)
# ---------------------------------------------------------------------------


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description_template(self) -> str: ...

    def get_description(self, args: dict[str, Any], options: dict[str, Any] | None = None) -> str: ...

    def validate_input(self, args: dict[str, Any]) -> tuple[bool, str]: ...

    def check_permissions(self, args: dict[str, Any], context: "ToolContext") -> tuple[bool, str]: ...

    def call(
        self,
        args: dict[str, Any],
        context: "ToolContext",
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> "ToolResult": ...

    def is_enabled(self) -> bool: ...

    def is_read_only(self, args: dict[str, Any]) -> bool: ...

    def is_destructive(self, args: dict[str, Any]) -> bool: ...


@dataclass(slots=True)
class BackgroundTaskResult:
    taskId: str
    type: str
    command: str
    pid: int
    status: str
    startedAt: int


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str
    backgroundTask: BackgroundTaskResult | None = None
    awaitUser: bool = False


@dataclass(slots=True)
class ToolContext:
    cwd: str
    permissions: Any | None = None


Validator = Callable[[Any], Any]
Runner = Callable[[Any, ToolContext], ToolResult]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    validator: Validator
    run: Runner


@dataclass(slots=True)
class ToolCatalog:
    tools: list[ToolDefinition]
    skills: list[dict[str, Any]]
    mcp_servers: list[dict[str, Any]]
    disposer: Callable[[], Any] | None = None


class ToolRegistry:
    def __init__(
        self,
        tools: list[ToolDefinition],
        skills: list[dict[str, Any]] | None = None,
        mcp_servers: list[dict[str, Any]] | None = None,
        disposer: Callable[[], Any] | None = None,
        refresh_catalog: Callable[[], ToolCatalog] | None = None,
    ) -> None:
        self._tools = list(tools)
        self._skills = list(skills or [])
        self._mcp_servers = list(mcp_servers or [])
        self._disposer = disposer
        self._refresh_catalog = refresh_catalog

    def list(self) -> list[ToolDefinition]:
        return list(self._tools)

    def get_skills(self) -> list[dict[str, Any]]:
        return list(self._skills)

    def get_mcp_servers(self) -> list[dict[str, Any]]:
        return list(self._mcp_servers)

    def find(self, name: str) -> ToolDefinition | None:
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    def execute(self, tool_name: str, input_data: Any, context: ToolContext) -> ToolResult:
        tool = self.find(tool_name)
        if tool is None:
            return ToolResult(ok=False, output=f"Unknown tool: {tool_name}")

        try:
            parsed = tool.validator(input_data)
            return tool.run(parsed, context)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as error:  # noqa: BLE001
            return ToolResult(ok=False, output=f"{type(tool).__name__} error: {error}")

    def refresh_capabilities(self) -> None:
        if self._refresh_catalog is None:
            return
        catalog = self._refresh_catalog()
        old_disposer = self._disposer
        self._tools = list(catalog.tools)
        self._skills = list(catalog.skills)
        self._mcp_servers = list(catalog.mcp_servers)
        self._disposer = catalog.disposer
        if old_disposer is not None and old_disposer is not catalog.disposer:
            old_disposer()

    def dispose(self) -> None:
        if self._disposer is not None:
            self._disposer()

"""Layered memory system for cross-session knowledge retention.

Provides three-tier memory hierarchy:
- User memory (~/.astrid/memory/) - cross-project, persistent
- Project memory (.astrid-memory/) - shared across sessions, can be versioned
- Local memory (.astrid-memory-local/) - project-specific, not checked in

Memory is automatically injected into system prompts to give the agent
context about past decisions, codebase patterns, and project conventions.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from astrid.config import ASTRID_DIR


def memories_root() -> Path:
    """Return the unified Astrid memories root."""
    override = os.environ.get("ASTRID_MEMORIES_ROOT")
    if override:
        return Path(override).expanduser()
    return ASTRID_DIR / "memories"


def _normalize_workspace_path(workspace: str | Path) -> str:
    try:
        normalized = str(Path(workspace).expanduser().resolve())
    except OSError:
        normalized = str(Path(workspace).expanduser())
    return normalized.lower() if os.name == "nt" else normalized


def workspace_id(workspace: str | Path) -> str:
    """Return a stable short id for a workspace path."""
    digest = hashlib.sha256(_normalize_workspace_path(workspace).encode("utf-8")).hexdigest()
    return digest[:16]


def _backup_path(path: Path) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.backup-{timestamp}")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup-{timestamp}-{suffix}")
        suffix += 1
    return candidate


def backup_legacy_memory_dir(path: Path) -> Path | None:
    """Rename a legacy project memory directory after all known payloads moved."""
    if not path.exists():
        return None
    if not path.is_dir():
        raise RuntimeError(f"Legacy memory path is not a directory: {path}")
    try:
        if not any(path.iterdir()):
            path.rmdir()
            return None
        backup = _backup_path(path)
        path.rename(backup)
        return backup
    except OSError as exc:
        raise RuntimeError(f"Failed to back up legacy memory directory {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class MemoryScope(str, Enum):
    """Memory scope levels."""
    USER = "user"       # Cross-project, ~/.astrid/memory/
    PROJECT = "project" # Project-shared, .astrid-memory/
    LOCAL = "local"     # Project-local, .astrid-memory-local/


@dataclass
class MemoryEntry:
    """A single memory entry (fact, pattern, decision, etc.)."""
    id: str
    scope: MemoryScope
    category: str  # e.g., "architecture", "convention", "decision", "pattern"
    content: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0  # How often this was referenced
    workspace: str = ""
    workspace_id: str = ""
    source_path: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "scope": self.scope.value,
            "category": self.category,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "usage_count": self.usage_count,
            "workspace": self.workspace,
            "workspace_id": self.workspace_id,
            "source_path": self.source_path,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            scope=MemoryScope(data.get("scope", "user")),
            category=data.get("category", "general"),
            content=data["content"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            tags=data.get("tags", []),
            usage_count=data.get("usage_count", 0),
            workspace=data.get("workspace", ""),
            workspace_id=data.get("workspace_id", ""),
            source_path=data.get("source_path", ""),
        )


@dataclass
class MemoryFile:
    """Represents a MEMORY.md file content."""
    scope: MemoryScope
    entries: list[MemoryEntry] = field(default_factory=list)
    max_entries: int = 200  # Claude Code limit
    max_size_bytes: int = 25 * 1024  # 25KB limit
    
    @property
    def size_bytes(self) -> int:
        """Estimate size in bytes."""
        return sum(len(e.content) for e in self.entries)
    
    def add_entry(self, entry: MemoryEntry) -> None:
        """Add entry, respecting limits."""
        self.entries.append(entry)
        self._enforce_limits()
    
    def update_entry(self, entry_id: str, content: str) -> bool:
        """Update existing entry."""
        for entry in self.entries:
            if entry.id == entry_id:
                entry.content = content
                entry.updated_at = time.time()
                return True
        return False
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete entry."""
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                return True
        return False
    
    def get_entries_by_category(self, category: str) -> list[MemoryEntry]:
        """Get entries filtered by category."""
        return [e for e in self.entries if e.category == category]
    
    def search(self, query: str) -> list[MemoryEntry]:
        """Search entries by keyword."""
        query_lower = query.lower()
        results = []
        for entry in self.entries:
            if (query_lower in entry.content.lower() or
                query_lower in entry.category.lower() or
                any(query_lower in tag.lower() for tag in entry.tags)):
                results.append(entry)
        return results
    
    def _enforce_limits(self) -> None:
        """Remove oldest entries if exceeding limits."""
        # Check entry count
        while len(self.entries) > self.max_entries:
            self.entries.pop(0)  # Remove oldest
        
        # Check size
        while self.size_bytes > self.max_size_bytes and self.entries:
            self.entries.pop(0)
    
    def format_as_markdown(self, include_header: bool = True) -> str:
        """Format as MEMORY.md content."""
        lines = []
        
        if include_header:
            scope_names = {
                MemoryScope.USER: "User Memory",
                MemoryScope.PROJECT: "Project Memory",
                MemoryScope.LOCAL: "Local Memory",
            }
            lines.append(f"# {scope_names[self.scope]}")
            lines.append("")
            lines.append(f"*Last updated: {time.strftime('%Y-%m-%d %H:%M')}*")
            lines.append("")
        
        # Group by category
        categories: dict[str, list[MemoryEntry]] = {}
        for entry in self.entries:
            if entry.category not in categories:
                categories[entry.category] = []
            categories[entry.category].append(entry)
        
        for category, entries in categories.items():
            lines.append(f"## {category.title()}")
            lines.append("")
            for entry in entries:
                tags_str = f" `{' '.join(entry.tags)}`" if entry.tags else ""
                lines.append(f"- {entry.content}{tags_str}")
            lines.append("")
        
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Memory Manager
# ---------------------------------------------------------------------------

@dataclass
class MemoryPaths:
    """Paths for memory files at different scopes."""
    user_memory: Path
    project_memory: Path
    local_memory: Path
    root: Path
    workspace_id: str
    
    @classmethod
    def for_workspace(cls, workspace: str) -> "MemoryPaths":
        """Create memory paths for a workspace."""
        root = memories_root()
        wid = workspace_id(workspace)
        project_root = root / "projects" / wid
        
        return cls(
            user_memory=root,
            project_memory=project_root,
            local_memory=project_root / "local",
            root=root,
            workspace_id=wid,
        )


class MemoryManager:
    """Manages layered memory system."""
    
    def __init__(
        self,
        workspace: str | Path | None = None,
        *,
        project_root: str | Path | None = None,
    ):
        # Backward compatibility: older call sites pass `project_root=...`.
        resolved_workspace = workspace if workspace is not None else project_root
        if resolved_workspace is None:
            resolved_workspace = Path.cwd()

        self.workspace = str(resolved_workspace)
        self.paths = MemoryPaths.for_workspace(self.workspace)
        self.memories: dict[MemoryScope, MemoryFile] = {
            MemoryScope.USER: MemoryFile(scope=MemoryScope.USER),
            MemoryScope.PROJECT: MemoryFile(scope=MemoryScope.PROJECT),
            MemoryScope.LOCAL: MemoryFile(scope=MemoryScope.LOCAL),
        }
        self._migrate_legacy_project_memories()
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all memory files."""
        for scope in MemoryScope:
            self._load_scope(scope)
    
    def _load_scope(self, scope: MemoryScope) -> None:
        """Load memory file for a scope."""
        path = self._get_scope_path(scope)
        memory_md = path / "MEMORY.md"
        memory_json = path / "memory.json"
        
        if not memory_md.exists() and not memory_json.exists():
            return
        
        # Load JSON metadata if exists
        if memory_json.exists():
            try:
                data = json.loads(memory_json.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry.from_dict(entry_data)
                    self.memories[scope].entries.append(entry)
                return
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Load from MEMORY.md
        if memory_md.exists():
            content = memory_md.read_text(encoding="utf-8")
            self._parse_memory_md(content, scope)
    
    def _parse_memory_md(self, content: str, scope: MemoryScope) -> None:
        """Parse MEMORY.md file into entries."""
        lines = content.split("\n")
        current_category = "general"
        entry_counter = 0
        
        for line in lines:
            line = line.strip()
            
            # Skip headers and metadata
            if line.startswith("#") or line.startswith("*") or not line:
                if line.startswith("## "):
                    current_category = line[3:].strip().lower()
                continue
            
            # Parse list items
            if line.startswith("- "):
                entry_content = line[2:]
                
                # Extract tags
                tags = []
                if "`" in entry_content:
                    import re
                    tag_matches = re.findall(r"`([^`]+)`", entry_content)
                    for tag_match in tag_matches:
                        tags.extend(tag_match.split())
                    entry_content = re.sub(r"`[^`]+`", "", entry_content).strip()
                
                entry_counter += 1
                entry = MemoryEntry(
                    id=f"{scope.value}-{entry_counter}",
                    scope=scope,
                    category=current_category,
                    content=entry_content,
                    tags=tags,
                )
                self.memories[scope].entries.append(entry)

    def _read_basic_entries(self, path: Path, scope: MemoryScope) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        memory_json = path / "memory.json"
        memory_md = path / "MEMORY.md"

        if memory_json.exists():
            try:
                data = json.loads(memory_json.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entries.append(MemoryEntry.from_dict(entry_data))
                return entries
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise RuntimeError(f"Failed to migrate legacy memory file {memory_json}: {exc}") from exc

        if memory_md.exists():
            temp = MemoryFile(scope=scope)
            original = self.memories[scope]
            self.memories[scope] = temp
            try:
                self._parse_memory_md(memory_md.read_text(encoding="utf-8"), scope)
                entries = list(self.memories[scope].entries)
            finally:
                self.memories[scope] = original

        return entries

    def _merge_legacy_entries(self, source_path: Path, scope: MemoryScope) -> bool:
        entries = self._read_basic_entries(source_path, scope)
        if not entries:
            return False

        target_path = self._get_scope_path(scope)
        target_path.mkdir(parents=True, exist_ok=True)
        target_entries = self._read_basic_entries(target_path, scope)
        existing_ids = {entry.id for entry in target_entries}
        changed = False

        for entry in entries:
            if entry.id in existing_ids:
                continue
            entry.scope = scope
            if scope != MemoryScope.USER:
                entry.workspace = self.workspace
                entry.workspace_id = self.paths.workspace_id
            if not entry.source_path:
                entry.source_path = str(source_path)
            target_entries.append(entry)
            existing_ids.add(entry.id)
            changed = True

        if changed:
            target_memory = MemoryFile(scope=scope, entries=target_entries)
            data = {
                "scope": scope.value,
                "last_updated": time.time(),
                "entries": [entry.to_dict() for entry in target_memory.entries],
            }
            (target_path / "memory.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (target_path / "MEMORY.md").write_text(
                target_memory.format_as_markdown(),
                encoding="utf-8",
            )

        return True

    def _migrate_legacy_project_memories(self) -> None:
        workspace_path = Path(self.workspace)
        legacy_targets = [
            (workspace_path / ".astrid-memory", MemoryScope.PROJECT),
            (workspace_path / ".astrid-memory-local", MemoryScope.LOCAL),
        ]

        for legacy_path, scope in legacy_targets:
            if not legacy_path.exists():
                continue
            if not legacy_path.is_dir():
                raise RuntimeError(f"Legacy memory path is not a directory: {legacy_path}")

            migrated_basic = self._merge_legacy_entries(legacy_path, scope)
            has_advanced_payload = (legacy_path / "advanced_memory.json").exists()
            if migrated_basic and not has_advanced_payload:
                backup_legacy_memory_dir(legacy_path)
    
    def _get_scope_path(self, scope: MemoryScope) -> Path:
        """Get path for memory scope."""
        if scope == MemoryScope.USER:
            return self.paths.user_memory
        elif scope == MemoryScope.PROJECT:
            return self.paths.project_memory
        else:
            return self.paths.local_memory
    
    def _ensure_scope_path(self, scope: MemoryScope) -> None:
        """Ensure directory exists for scope."""
        path = self._get_scope_path(scope)
        path.mkdir(parents=True, exist_ok=True)
    
    def add_entry(
        self,
        scope: MemoryScope,
        category: str,
        content: str,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Add a new memory entry."""
        self._ensure_scope_path(scope)
        
        entry_id = f"{scope.value}-{int(time.time())}-{len(self.memories[scope].entries)}"
        entry = MemoryEntry(
            id=entry_id,
            scope=scope,
            category=category,
            content=content,
            tags=tags or [],
            workspace=self.workspace if scope != MemoryScope.USER else "",
            workspace_id=self.paths.workspace_id if scope != MemoryScope.USER else "",
        )
        
        self.memories[scope].add_entry(entry)
        self._save_scope(scope)
        return entry
    
    def update_entry(self, scope: MemoryScope, entry_id: str, content: str) -> bool:
        """Update an existing entry."""
        if self.memories[scope].update_entry(entry_id, content):
            self._save_scope(scope)
            return True
        return False
    
    def delete_entry(self, scope: MemoryScope, entry_id: str) -> bool:
        """Delete an entry."""
        if self.memories[scope].delete_entry(entry_id):
            self._save_scope(scope)
            return True
        return False
    
    def search(self, query: str, scope: MemoryScope | None = None) -> list[MemoryEntry]:
        """Search across memory scopes."""
        results = []
        
        scopes_to_search = [scope] if scope else list(MemoryScope)
        
        for s in scopes_to_search:
            results.extend(self.memories[s].search(query))
        
        # Sort by usage count (most used first)
        results.sort(key=lambda e: e.usage_count, reverse=True)
        return results
    
    def get_relevant_context(
        self,
        max_entries: int = 20,
        max_tokens: int = 8000,
    ) -> str:
        """Get relevant memory context for system prompt injection.
        
        Returns formatted MEMORY.md content from all scopes,
        respecting token limits.
        """
        from astrid.context_manager import estimate_tokens
        
        parts = []
        total_tokens = 0
        
        # Priority order: LOCAL > PROJECT > USER
        for scope in [MemoryScope.LOCAL, MemoryScope.PROJECT, MemoryScope.USER]:
            memory = self.memories[scope]
            if not memory.entries:
                continue
            
            formatted = memory.format_as_markdown(include_header=True)
            tokens = estimate_tokens(formatted)
            
            if total_tokens + tokens <= max_tokens:
                parts.append(formatted)
                total_tokens += tokens
            else:
                # Partial: include only recent entries
                remaining_tokens = max_tokens - total_tokens
                partial_entries = memory.entries[-max_entries:]
                partial_memory = MemoryFile(scope=scope, entries=partial_entries)
                formatted = partial_memory.format_as_markdown(include_header=True)
                
                if estimate_tokens(formatted) <= remaining_tokens:
                    parts.append(formatted)
                break
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)
    
    def _save_scope(self, scope: MemoryScope) -> None:
        """Save memory to disk."""
        path = self._get_scope_path(scope)
        self._ensure_scope_path(scope)
        
        # Save JSON metadata
        memory_json = path / "memory.json"
        data = {
            "scope": scope.value,
            "last_updated": time.time(),
            "entries": [e.to_dict() for e in self.memories[scope].entries],
        }
        memory_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        
        # Also update MEMORY.md for human readability
        memory_md = path / "MEMORY.md"
        memory_md.write_text(
            self.memories[scope].format_as_markdown(),
            encoding="utf-8",
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            scope.value: {
                "entries": len(memory.entries),
                "size_bytes": memory.size_bytes,
                "categories": list(set(e.category for e in memory.entries)),
            }
            for scope, memory in self.memories.items()
        }
    
    def format_stats(self) -> str:
        """Format memory stats for display."""
        stats = self.get_stats()
        lines = ["Memory System Status", "=" * 40, ""]
        
        for scope_name, scope_stats in stats.items():
            lines.append(f"{scope_name.title()} Memory:")
            lines.append(f"  Entries: {scope_stats['entries']}")
            lines.append(f"  Size: {scope_stats['size_bytes'] / 1024:.1f} KB")
            if scope_stats['categories']:
                lines.append(f"  Categories: {', '.join(scope_stats['categories'][:5])}")
            lines.append("")
        
        return "\n".join(lines)
    
    def clear_scope(self, scope: MemoryScope) -> None:
        """Clear all entries in a scope."""
        self.memories[scope] = MemoryFile(scope=scope)
        self._save_scope(scope)


# ---------------------------------------------------------------------------
# System prompt integration
# ---------------------------------------------------------------------------

def inject_memory_into_prompt(
    system_prompt: str,
    memory_manager: MemoryManager,
    max_tokens: int = 8000,
) -> str:
    """Inject memory context into system prompt."""
    memory_context = memory_manager.get_relevant_context(max_tokens=max_tokens)
    
    if not memory_context:
        return system_prompt
    
    return f"""{system_prompt}

## Project Memory & Context

The following information has been accumulated from previous sessions:

{memory_context}

Use this context to inform your decisions and follow established patterns."""


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def format_memory_list(scope: MemoryScope | None = None, category: str | None = None) -> str:
    """Format memory entries for CLI display."""
    # This would be called with a MemoryManager instance
    # Placeholder for CLI command formatting
    return "Memory listing not available without MemoryManager instance."

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(slots=True)
class OrchestrationWorker:
    name: str
    role: str
    mission: str
    status: Literal["queued", "running", "reporting", "blocked", "done", "failed"] = "queued"
    colorKey: str | None = None
    latestEvent: str = ""


@dataclass(slots=True)
class TranscriptEntry:
    id: int
    kind: Literal["user", "assistant", "progress", "tool", "orchestration"]
    body: str
    toolName: str | None = None
    status: Literal["running", "success", "error"] | None = None
    collapsed: bool = False
    collapsedSummary: str | None = None
    collapsePhase: Literal[1, 2, 3] | None = None
    narrativeLine: str | None = None
    phaseLabel: str | None = None
    workers: list[OrchestrationWorker] = field(default_factory=list)


# TranscriptEntry 对象池，减少频繁创建和 GC 压力
# Placed after the class definition so that runtime references resolve correctly.
_entry_pool: list[TranscriptEntry] = []
_POOL_MAX_SIZE = 100


def _create_transcript_entry(
    id: int,
    kind: Literal["user", "assistant", "progress", "tool", "orchestration"],
    body: str,
    toolName: str | None = None,
    status: Literal["running", "success", "error"] | None = None,
    collapsed: bool = False,
    collapsedSummary: str | None = None,
    collapsePhase: Literal[1, 2, 3] | None = None,
    narrativeLine: str | None = None,
    phaseLabel: str | None = None,
    workers: list[OrchestrationWorker] | None = None,
) -> TranscriptEntry:
    """创建 TranscriptEntry，使用对象池减少 GC 压力"""
    if _entry_pool:
        entry = _entry_pool.pop()
        entry.id = id
        entry.kind = kind
        entry.body = body
        entry.toolName = toolName
        entry.status = status
        entry.collapsed = collapsed
        entry.collapsedSummary = collapsedSummary
        entry.collapsePhase = collapsePhase
        entry.narrativeLine = narrativeLine
        entry.phaseLabel = phaseLabel
        entry.workers = list(workers or [])
        return entry
    else:
        return TranscriptEntry(
            id=id,
            kind=kind,
            body=body,
            toolName=toolName,
            status=status,
            collapsed=collapsed,
            collapsedSummary=collapsedSummary,
            collapsePhase=collapsePhase,
            narrativeLine=narrativeLine,
            phaseLabel=phaseLabel,
            workers=list(workers or []),
        )


def _recycle_transcript_entry(entry: TranscriptEntry) -> None:
    """回收 TranscriptEntry 到对象池"""
    if len(_entry_pool) < _POOL_MAX_SIZE:
        entry.narrativeLine = None
        entry.phaseLabel = None
        entry.workers = []
        _entry_pool.append(entry)

"""Advanced memory system for Astrid.

基于参考仓库 https://github.com/Ydy4HYW7ExA/agent 的理论和架构，
实现分层记忆系统，包含：
1. 分层记忆存储（用户、项目、本地、会话）
2. 技能(skill)管理系统
3. 术语治理(terminology-governance)系统
4. 协作对话记忆
5. 自举(self-bootstrapping)能力
6. 记忆关联网络

架构设计：
- 统一内存访问(UMA)模式：所有处理器共享全部物理内存
- 非统一内存访问(NUMA)模式：访问时间依赖于内存位置
- 技能依赖网络：技能间的依赖关系构成知识网络
- 术语一致性：确保概念定义的一致性
"""

from __future__ import annotations

import json
import time
import uuid
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from datetime import datetime

from astrid.config import ASTRID_DIR
from astrid.state import Store


# ---------------------------------------------------------------------------
# 核心类型定义
# ---------------------------------------------------------------------------

class MemoryScope(str, Enum):
    """记忆范围层级，参考Claude Code的三层架构"""
    SESSION = "session"     # 会话级记忆（临时）
    LOCAL = "local"         # 本地级记忆（项目特定）
    PROJECT = "project"     # 项目级记忆（共享）
    USER = "user"           # 用户级记忆（跨项目）
    SYSTEM = "system"       # 系统级记忆（全局）
    ALL = "all"             # 所有范围（用于搜索）

class MemoryType(str, Enum):
    """记忆类型，基于参考仓库的技能分类"""
    TERMINOLOGY = "terminology"      # 术语定义
    SKILL = "skill"                  # 技能定义
    DECISION = "decision"            # 决策记录
    PATTERN = "pattern"              # 模式识别
    CONTEXT = "context"              # 上下文信息
    COLLABORATION = "collaboration"  # 协作记录
    DOCUMENTATION = "documentation"  # 文档记录
    WORKFLOW = "workflow"            # 工作流记录

class MemoryPriority(int, Enum):
    """记忆优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ---------------------------------------------------------------------------
# 记忆条目定义
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """增强的记忆条目"""
    id: str
    scope: MemoryScope
    type: MemoryType
    content: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.MEDIUM
    usage_count: int = 0
    confidence: float = 1.0  # 置信度（0.0-1.0）
    
    # 关联关系
    dependencies: List[str] = field(default_factory=list)  # 依赖的记忆ID
    references: List[str] = field(default_factory=list)    # 引用的记忆ID
    related_skills: List[str] = field(default_factory=list)  # 相关技能
    
    # 上下文信息
    source: str = ""  # 来源（如：user_input, system_generated, tool_output）
    context_hash: str = ""  # 上下文哈希，用于关联
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于序列化"""
        return {
            "id": self.id,
            "scope": self.scope.value,
            "type": self.type.value,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "accessed_at": self.accessed_at,
            "tags": self.tags,
            "categories": self.categories,
            "priority": self.priority.value,
            "usage_count": self.usage_count,
            "confidence": self.confidence,
            "dependencies": self.dependencies,
            "references": self.references,
            "related_skills": self.related_skills,
            "source": self.source,
            "context_hash": self.context_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """从字典创建"""
        return cls(
            id=data["id"],
            scope=MemoryScope(data.get("scope", "user")),
            type=MemoryType(data.get("type", "context")),
            content=data["content"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            accessed_at=data.get("accessed_at", time.time()),
            tags=data.get("tags", []),
            categories=data.get("categories", []),
            priority=MemoryPriority(data.get("priority", 2)),
            usage_count=data.get("usage_count", 0),
            confidence=data.get("confidence", 1.0),
            dependencies=data.get("dependencies", []),
            references=data.get("references", []),
            related_skills=data.get("related_skills", []),
            source=data.get("source", ""),
            context_hash=data.get("context_hash", ""),
        )
    
    def mark_accessed(self) -> None:
        """标记为已访问"""
        self.accessed_at = time.time()
        self.usage_count += 1
    
    def update(self, content: str, confidence: float = None) -> None:
        """更新记忆内容"""
        self.content = content
        self.updated_at = time.time()
        if confidence is not None:
            self.confidence = confidence
    
    def add_dependency(self, memory_id: str) -> None:
        """添加依赖关系"""
        if memory_id not in self.dependencies:
            self.dependencies.append(memory_id)
            self.updated_at = time.time()
    
    def add_reference(self, memory_id: str) -> None:
        """添加引用关系"""
        if memory_id not in self.references:
            self.references.append(memory_id)
            self.updated_at = time.time()


# ---------------------------------------------------------------------------
# 技能定义
# ---------------------------------------------------------------------------

@dataclass
class SkillDefinition:
    """技能定义，参考仓库的五个核心技能"""
    name: str
    description: str
    version: str = "1.0.0"
    
    # 技能属性
    category: str = "general"
    dependencies: List[str] = field(default_factory=list)  # 依赖的技能名
    capabilities: List[str] = field(default_factory=list)  # 能力列表
    
    # 元数据
    author: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    
    # 执行信息
    entry_point: str = ""  # 入口点（函数名或模块路径）
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "dependencies": self.dependencies,
            "capabilities": self.capabilities,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "entry_point": self.entry_point,
            "config": self.config,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillDefinition":
        """从字典创建"""
        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0.0"),
            category=data.get("category", "general"),
            dependencies=data.get("dependencies", []),
            capabilities=data.get("capabilities", []),
            author=data.get("author", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            usage_count=data.get("usage_count", 0),
            entry_point=data.get("entry_point", ""),
            config=data.get("config", {}),
        )


# ---------------------------------------------------------------------------
# 术语定义
# ---------------------------------------------------------------------------

@dataclass
class TerminologyEntry:
    """术语定义条目"""
    term: str
    definition: str
    category: str = "general"
    aliases: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "term": self.term,
            "definition": self.definition,
            "category": self.category,
            "aliases": self.aliases,
            "examples": self.examples,
            "related_terms": self.related_terms,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerminologyEntry":
        """从字典创建"""
        return cls(
            term=data["term"],
            definition=data["definition"],
            category=data.get("category", "general"),
            aliases=data.get("aliases", []),
            examples=data.get("examples", []),
            related_terms=data.get("related_terms", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            usage_count=data.get("usage_count", 0),
        )


# ---------------------------------------------------------------------------
# 记忆管理器
# ---------------------------------------------------------------------------

class AdvancedMemoryManager:
    """增强的记忆管理器"""
    
    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace) if workspace else Path.cwd()
        
        # 记忆存储（ALL 不是存储范围，仅用于搜索）
        self.memories: Dict[MemoryScope, List[MemoryEntry]] = {
            scope: [] for scope in MemoryScope if scope != MemoryScope.ALL
        }
        
        # 技能管理
        self.skills: Dict[str, SkillDefinition] = {}
        
        # 术语治理
        self.terminology: Dict[str, TerminologyEntry] = {}
        
        # 关联网络
        self.association_graph: Dict[str, List[str]] = {}  # memory_id -> [related_ids]
        
        # 初始化
        self._load_all()
        self._initialize_core_skills()
    
    def _initialize_core_skills(self) -> None:
        """初始化核心技能，基于参考仓库的五个核心技能"""
        core_skills = [
            SkillDefinition(
                name="collaboration-dialogue",
                description="处理对话清洗和协作逻辑",
                category="communication",
                capabilities=["对话清洗", "协作逻辑", "意图识别"],
                dependencies=[],
            ),
            SkillDefinition(
                name="terminology-governance",
                description="管理共享术语定义，维护术语一致性",
                category="governance",
                capabilities=["术语定义", "一致性检查", "术语解析"],
                dependencies=[],
            ),
            SkillDefinition(
                name="documentation-authoring",
                description="负责文档创建和维护",
                category="documentation",
                capabilities=["文档生成", "文档维护", "格式标准化"],
                dependencies=["collaboration-dialogue", "terminology-governance"],
            ),
            SkillDefinition(
                name="skill-authoring",
                description="实现技能的自举（自我构建）能力",
                category="meta",
                capabilities=["技能创建", "技能验证", "依赖管理"],
                dependencies=["documentation-authoring", "terminology-governance"],
            ),
            SkillDefinition(
                name="repository-construction",
                description="综合运用前四个技能进行仓库架构建设",
                category="development",
                capabilities=["仓库架构", "项目规划", "工作流设计"],
                dependencies=[
                    "collaboration-dialogue",
                    "terminology-governance",
                    "documentation-authoring",
                ],
            ),
        ]
        
        for skill in core_skills:
            self.skills[skill.name] = skill
    
    def _load_all(self) -> None:
        """加载所有记忆数据"""
        # 加载记忆（跳过 ALL，它不是真正的存储范围）
        for scope in MemoryScope:
            if scope == MemoryScope.ALL:
                continue
            self._load_scope(scope)
        
        # 加载技能
        self._load_skills()
        
        # 加载术语
        self._load_terminology()
    
    def _load_scope(self, scope: MemoryScope) -> None:
        """加载特定范围的记忆"""
        scope_dir = self._get_scope_path(scope)
        memory_file = scope_dir / "advanced_memory.json"
        
        if not memory_file.exists():
            return
        
        try:
            data = json.loads(memory_file.read_text(encoding="utf-8"))
            for entry_data in data.get("entries", []):
                entry = MemoryEntry.from_dict(entry_data)
                self.memories[scope].append(entry)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading {scope.value} memory: {e}")
    
    def _load_skills(self) -> None:
        """加载技能定义"""
        skills_file = ASTRID_DIR / "advanced_skills.json"
        
        if not skills_file.exists():
            return
        
        try:
            data = json.loads(skills_file.read_text(encoding="utf-8"))
            for skill_data in data.get("skills", []):
                skill = SkillDefinition.from_dict(skill_data)
                self.skills[skill.name] = skill
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading skills: {e}")
    
    def _load_terminology(self) -> None:
        """加载术语定义"""
        terminology_file = ASTRID_DIR / "advanced_terminology.json"
        
        if not terminology_file.exists():
            return
        
        try:
            data = json.loads(terminology_file.read_text(encoding="utf-8"))
            for term_data in data.get("terms", []):
                term = TerminologyEntry.from_dict(term_data)
                self.terminology[term.term] = term
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading terminology: {e}")
    
    def _get_scope_path(self, scope: MemoryScope) -> Path:
        """获取范围的路径"""
        if scope == MemoryScope.SYSTEM:
            return ASTRID_DIR / "system_memory"
        elif scope == MemoryScope.USER:
            return ASTRID_DIR / "user_memory"
        elif scope == MemoryScope.PROJECT:
            return self.workspace / ".astrid-memory"
        elif scope == MemoryScope.LOCAL:
            return self.workspace / ".astrid-memory-local"
        else:  # SESSION
            return self.workspace / ".astrid-session-memory"
    
    def _save_scope(self, scope: MemoryScope) -> None:
        """保存特定范围的记忆"""
        scope_dir = self._get_scope_path(scope)
        scope_dir.mkdir(parents=True, exist_ok=True)
        
        memory_file = scope_dir / "advanced_memory.json"
        data = {
            "scope": scope.value,
            "last_updated": time.time(),
            "entries": [entry.to_dict() for entry in self.memories[scope]],
        }
        
        memory_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def _save_skills(self) -> None:
        """保存技能定义"""
        skills_file = ASTRID_DIR / "advanced_skills.json"
        skills_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "last_updated": time.time(),
            "skills": [skill.to_dict() for skill in self.skills.values()],
        }
        
        skills_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def _save_terminology(self) -> None:
        """保存术语定义"""
        terminology_file = ASTRID_DIR / "advanced_terminology.json"
        terminology_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "last_updated": time.time(),
            "terms": [term.to_dict() for term in self.terminology.values()],
        }
        
        terminology_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def save_all(self) -> None:
        """保存所有数据到磁盘（用于应用关闭时调用）"""
        for scope in self.memories:
            if self.memories[scope]:
                self._save_scope(scope)
        self._save_skills()
        self._save_terminology()
    
    # -----------------------------------------------------------------------
    # 记忆操作API
    # -----------------------------------------------------------------------
    
    def add_memory(
        self,
        scope: MemoryScope,
        type: MemoryType,
        content: str,
        tags: List[str] = None,
        categories: List[str] = None,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        source: str = "",
        context_hash: str = "",
    ) -> MemoryEntry:
        """添加新的记忆"""
        # 生成唯一ID
        memory_id = f"{scope.value}-{type.value}-{uuid.uuid4().hex[:8]}"
        
        # 创建记忆条目
        entry = MemoryEntry(
            id=memory_id,
            scope=scope,
            type=type,
            content=content,
            tags=tags or [],
            categories=categories or [],
            priority=priority,
            source=source,
            context_hash=context_hash or self._generate_context_hash(content),
        )
        
        # 添加到记忆列表
        self.memories[scope].append(entry)
        
        # 保存
        self._save_scope(scope)
        
        return entry
    
    def search_memories(
        self,
        query: str,
        scope: MemoryScope = None,
        type: MemoryType = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """搜索记忆"""
        results = []
        query_lower = query.lower()
        
        # 确定搜索范围（排除ALL）
        if scope and scope != MemoryScope.ALL:
            scopes_to_search = [scope]
        else:
            scopes_to_search = [s for s in MemoryScope if s != MemoryScope.ALL]
        
        for scope_ in scopes_to_search:
            for entry in self.memories[scope_]:
                # 检查类型筛选
                if type and entry.type != type:
                    continue
                
                # 检查置信度
                if entry.confidence < min_confidence:
                    continue
                
                # 搜索匹配
                if (query_lower in entry.content.lower() or
                    any(query_lower in tag.lower() for tag in entry.tags) or
                    any(query_lower in cat.lower() for cat in entry.categories)):
                    
                    entry.mark_accessed()
                    results.append(entry)
        
        # 按优先级和访问时间排序
        results.sort(key=lambda e: (
            -e.priority.value,  # 优先级高的在前
            -e.accessed_at,     # 最近访问的在前
            -e.usage_count,     # 使用次数多的在前
        ))
        
        return results[:limit]
    
    def get_contextual_memories(
        self,
        current_context: str,
        scope: MemoryScope = None,
        max_entries: int = 10,
    ) -> List[MemoryEntry]:
        """获取与当前上下文相关的记忆"""
        context_hash = self._generate_context_hash(current_context)
        
        # 首先查找直接关联的记忆
        direct_matches = []
        if scope:
            entries = self.memories.get(scope, [])
        else:
            # 遍历所有范围
            entries = []
            for scope_entries in self.memories.values():
                entries.extend(scope_entries)
        
        for entry in entries:
            if entry.context_hash == context_hash:
                entry.mark_accessed()
                direct_matches.append(entry)
        
        # 如果直接匹配不足，进行语义搜索
        if len(direct_matches) < max_entries:
            # 提取关键词（简化版本）
            keywords = self._extract_keywords(current_context)
            
            for keyword in keywords[:3]:  # 使用前3个关键词
                keyword_matches = self.search_memories(
                    keyword,
                    scope=scope,
                    limit=max_entries - len(direct_matches)
                )
                for match in keyword_matches:
                    if match not in direct_matches:
                        direct_matches.append(match)
        
        return direct_matches[:max_entries]
    
    def update_memory(
        self,
        memory_id: str,
        content: str = None,
        confidence: float = None,
        tags: List[str] = None,
    ) -> bool:
        """更新记忆"""
        # 查找记忆
        entry = self.find_memory_by_id(memory_id)
        if not entry:
            return False
        
        # 更新内容
        if content is not None:
            entry.content = content
            entry.updated_at = time.time()
        
        # 更新置信度
        if confidence is not None:
            entry.confidence = confidence
        
        # 更新标签
        if tags is not None:
            entry.tags = tags
        
        # 保存
        self._save_scope(entry.scope)
        
        return True
    
    def find_memory_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """通过ID查找记忆"""
        for scope, entries in self.memories.items():
            for entry in entries:
                if entry.id == memory_id:
                    entry.mark_accessed()
                    return entry
        return None
    
    def add_association(self, memory_id1: str, memory_id2: str) -> None:
        """添加记忆关联"""
        if memory_id1 not in self.association_graph:
            self.association_graph[memory_id1] = []
        
        if memory_id2 not in self.association_graph[memory_id1]:
            self.association_graph[memory_id1].append(memory_id2)
    
    def get_related_memories(self, memory_id: str, depth: int = 1) -> List[MemoryEntry]:
        """获取相关记忆"""
        if memory_id not in self.association_graph:
            return []
        
        related_ids = self.association_graph[memory_id]
        related_memories = []
        
        for related_id in related_ids:
            entry = self.find_memory_by_id(related_id)
            if entry:
                related_memories.append(entry)
        
        return related_memories
    
    # -----------------------------------------------------------------------
    # 技能管理API
    # -----------------------------------------------------------------------
    
    def register_skill(self, skill: SkillDefinition) -> None:
        """注册技能"""
        self.skills[skill.name] = skill
        self._save_skills()
    
    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """获取技能"""
        return self.skills.get(name)
    
    def list_skills(self) -> List[SkillDefinition]:
        """列出所有已注册的技能"""
        return list(self.skills.values())
    
    def get_skill_dependencies(self, skill_name: str) -> List[SkillDefinition]:
        """获取技能依赖"""
        skill = self.get_skill(skill_name)
        if not skill:
            return []
        
        dependencies = []
        for dep_name in skill.dependencies:
            dep_skill = self.get_skill(dep_name)
            if dep_skill:
                dependencies.append(dep_skill)
        
        return dependencies
    
    def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """执行技能（简化版本）"""
        skill = self.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")
        
        # 记录技能使用
        skill.usage_count += 1
        skill.updated_at = time.time()
        self._save_skills()
        
        # 这里应该调用实际的技能执行逻辑
        # 目前只返回模拟结果
        return {
            "skill": skill_name,
            "status": "executed",
            "timestamp": time.time(),
            "parameters": kwargs,
        }
    
    # -----------------------------------------------------------------------
    # 术语治理API
    # -----------------------------------------------------------------------
    
    def define_term(self, term: str, definition: str, **kwargs) -> TerminologyEntry:
        """定义术语"""
        entry = TerminologyEntry(term=term, definition=definition, **kwargs)
        self.terminology[term] = entry
        self._save_terminology()
        return entry
    
    def get_term(self, term: str) -> Optional[TerminologyEntry]:
        """获取术语定义"""
        entry = self.terminology.get(term)
        if entry:
            entry.usage_count += 1
            entry.updated_at = time.time()
            self._save_terminology()
        return entry
    
    def search_terms(self, query: str) -> List[TerminologyEntry]:
        """搜索术语"""
        query_lower = query.lower()
        results = []
        
        for entry in self.terminology.values():
            if (query_lower in entry.term.lower() or
                query_lower in entry.definition.lower() or
                any(query_lower in alias.lower() for alias in entry.aliases)):
                
                entry.usage_count += 1
                results.append(entry)
        
        # 按使用次数排序
        results.sort(key=lambda e: -e.usage_count)
        return results
    
    def resolve_term(self, text: str) -> Dict[str, Any]:
        """解析文本中的术语"""
        resolved = {}
        
        for term, entry in self.terminology.items():
            if term in text:
                resolved[term] = {
                    "definition": entry.definition,
                    "category": entry.category,
                    "examples": entry.examples,
                }
        
        return resolved
    
    # -----------------------------------------------------------------------
    # 辅助方法
    # -----------------------------------------------------------------------
    
    def _generate_context_hash(self, content: str) -> str:
        """生成上下文哈希"""
        # 使用简化的哈希算法
        import hashlib
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化版本）"""
        # 这里可以实现更复杂的关键词提取算法
        # 目前使用简单的分词
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        
        # 过滤停用词
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        return list(set(keywords))  # 去重
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "memory_stats": {
                scope.value: {
                    "count": len(entries),
                    "types": list(set(e.type.value for e in entries)),
                    "total_usage": sum(e.usage_count for e in entries),
                }
                for scope, entries in self.memories.items()
            },
            "skill_stats": {
                "total_skills": len(self.skills),
                "categories": list(set(s.category for s in self.skills.values())),
                "total_usage": sum(s.usage_count for s in self.skills.values()),
            },
            "terminology_stats": {
                "total_terms": len(self.terminology),
                "categories": list(set(t.category for t in self.terminology.values())),
                "total_usage": sum(t.usage_count for t in self.terminology.values()),
            },
        }
    
    def store_memory(
        self,
        content: str,
        scope: MemoryScope = MemoryScope.PROJECT,
        memory_type: MemoryType = MemoryType.CONTEXT,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        tags: List[str] = None,
        source: str = "",
    ) -> str:
        """便捷方法：存储记忆并返回ID"""
        entry = self.add_memory(
            scope=scope,
            type=memory_type,
            content=content,
            tags=tags,
            priority=priority,
            source=source,
        )
        return entry.id

    def list_memories(
        self,
        scope: MemoryScope = None,
        memory_type: MemoryType = None,
    ) -> List[MemoryEntry]:
        """列出记忆，支持按范围和类型过滤"""
        if scope and memory_type:
            return [e for e in self.memories.get(scope, [])
                    if e.type == memory_type]
        elif scope:
            return list(self.memories.get(scope, []))
        elif memory_type:
            return [e for scope_entries in self.memories.values()
                    for e in scope_entries if e.type == memory_type]
        else:
            return [e for entries in self.memories.values() for e in entries]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息（兼容接口）"""
        stats = self.get_stats()
        # 添加汇总字段
        total_memories = sum(
            len(entries) for entries in self.memories.values()
        )
        stats["total_memories"] = total_memories
        stats["total_skills"] = len(self.skills)
        stats["total_terminologies"] = len(self.terminology)
        return stats

    def apply_memory_decay(self, decay_factor: float = 0.95, min_priority: MemoryPriority = MemoryPriority.LOW) -> int:
        """智能记忆衰减：基于时间和访问频率调整优先级。
        
        策略：
        - 长时间未访问的记忆优先级递减
        - 高频访问的记忆保持高优先级
        - 最低优先级的记忆在下次清理时移除
        
        Returns: 衰减的记忆条数
        """
        import time as _time
        current_time = _time.time()
        decayed_count = 0
        
        for scope, entries in self.memories.items():
            for entry in entries:
                # 计算时间衰减（每7天衰减一次）
                age_days = (current_time - entry.updated_at) / 86400
                access_bonus = min(entry.usage_count * 0.02, 0.3)  # 访问频率加分
                
                # 越老越少访问的记忆衰减越多
                if age_days > 7:
                    decay_amount = decay_factor * (1 - access_bonus)
                    new_priority_val = max(
                        min_priority.value,
                        int(entry.priority.value * decay_amount)
                    )
                    if new_priority_val != entry.priority.value:
                        entry.priority = MemoryPriority(new_priority_val)
                        decayed_count += 1
            
            # 移除极低优先级且很久没访问的记忆
            original_count = len(entries)
            self.memories[scope] = [
                e for e in entries
                if not (e.priority == MemoryPriority.LOW and 
                       (current_time - e.accessed_at) > 30 * 86400)  # 30天未访问
            ]
            removed = original_count - len(self.memories[scope])
            if removed > 0:
                decayed_count += removed
                self._save_scope(scope)
        
        return decayed_count

    def get_relevant_memories_for_context(
        self,
        current_query: str = "",
        max_tokens: int = 3000,
    ) -> List[MemoryEntry]:
        """上下文感知记忆检索：根据当前对话自动推送相关记忆。
        
        策略：
        1. 基于关键词匹配
        2. 基于标签匹配
        3. 基于优先级排序
        4. 基于访问频率
        5. Token 预算限制
        """
        from astrid.context_manager import estimate_tokens
        
        if not current_query:
            # 无查询时返回高优先级记忆
            all_entries = []
            for entries in self.memories.values():
                all_entries.extend(entries)
            all_entries.sort(key=lambda e: (e.priority.value, e.usage_count), reverse=True)
            return all_entries[:20]
        
        # 提取查询关键词
        query_keywords = set(self._extract_keywords(current_query))
        query_lower = current_query.lower()
        
        # 计算每条记忆的相关性分数
        scored_entries = []
        for entries in self.memories.values():
            for entry in entries:
                score = 0.0
                
                # 关键词匹配
                entry_keywords = set(self._extract_keywords(entry.content))
                keyword_overlap = query_keywords & entry_keywords
                if keyword_overlap:
                    score += len(keyword_overlap) * 2.0
                
                # 直接文本匹配
                if query_lower in entry.content.lower():
                    score += 5.0
                
                # 标签匹配
                for tag in entry.tags:
                    if tag.lower() in query_lower:
                        score += 3.0
                
                # 优先级加权
                score += entry.priority.value * 0.5
                
                # 访问频率加权
                score += min(entry.usage_count * 0.1, 2.0)
                
                # 时间衰减（越近越相关）
                import time as _time
                age_hours = (_time.time() - entry.updated_at) / 3600
                if age_hours < 1:
                    score += 3.0  # 1小时内
                elif age_hours < 24:
                    score += 1.5  # 1天内
                elif age_hours < 168:  # 7天
                    score += 0.5
                
                if score > 0:
                    scored_entries.append((score, entry))
        
        # 按分数排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        
        # 应用 token 预算
        result = []
        used_tokens = 0
        for score, entry in scored_entries:
            entry_tokens = estimate_tokens(entry.content)
            if used_tokens + entry_tokens <= max_tokens:
                result.append(entry)
                used_tokens += entry_tokens
                entry.mark_accessed()  # 标记为已访问
        
        return result

    def format_context_for_prompt(self, max_tokens: int = 4000) -> str:
        """格式化记忆上下文用于系统提示"""
        from astrid.context_manager import estimate_tokens
        
        context_parts = []
        total_tokens = 0
        
        # 添加术语定义
        if self.terminology:
            terms_section = "## Terminology Definitions\n\n"
            for term, entry in list(self.terminology.items())[:10]:  # 最多10个术语
                term_text = f"**{term}**: {entry.definition}"
                if entry.examples:
                    term_text += f"\n  Example: {entry.examples[0]}"
                terms_section += f"- {term_text}\n"
            
            tokens = estimate_tokens(terms_section)
            if total_tokens + tokens <= max_tokens:
                context_parts.append(terms_section)
                total_tokens += tokens
        
        # 添加相关记忆（使用上下文感知检索）
        relevant_memories = self.get_relevant_memories_for_context(
            max_tokens=int(max_tokens * 0.5),  # 分配50%预算给记忆
        )
        if relevant_memories:
            memories_section = "## Relevant Memories\n\n"
            for entry in relevant_memories[:15]:
                memories_section += f"- [{entry.scope.value}/{entry.type.value}] {entry.content[:150]}\n"
                if entry.tags:
                    memories_section += f"  Tags: {', '.join(entry.tags[:3])}\n"
            
            tokens = estimate_tokens(memories_section)
            if total_tokens + tokens <= max_tokens:
                context_parts.append(memories_section)
                total_tokens += tokens
        
        # 添加技能信息
        if self.skills:
            skills_section = "## Available Skills\n\n"
            for skill in list(self.skills.values())[:5]:  # 最多5个技能
                skills_section += f"- **{skill.name}**: {skill.description}\n"
                if skill.capabilities:
                    skills_section += f"  Capabilities: {', '.join(skill.capabilities[:3])}\n"
            
            tokens = estimate_tokens(skills_section)
            if total_tokens + tokens <= max_tokens:
                context_parts.append(skills_section)
                total_tokens += tokens
        
        return "\n".join(context_parts) if context_parts else ""


# ---------------------------------------------------------------------------
# 系统集成
# ---------------------------------------------------------------------------

def create_memory_integration(
    workspace: str | Path | None = None,
) -> AdvancedMemoryManager:
    """创建记忆管理器集成。

    保留 ``workspace`` 参数兼容性，方便测试和需要隔离存储的调用方
    指定独立工作目录。
    """
    return AdvancedMemoryManager(workspace=workspace)

def inject_advanced_memory_context(
    system_prompt: str,
    memory_manager: AdvancedMemoryManager,
    current_context: str = "",
    max_tokens: int = 5000,
) -> str:
    """注入增强的记忆上下文到系统提示"""
    memory_context = memory_manager.format_context_for_prompt(max_tokens)
    
    if not memory_context:
        return system_prompt
    
    # 如果有当前上下文，添加相关记忆
    if current_context:
        contextual_memories = memory_manager.get_contextual_memories(current_context, max_entries=5)
        if contextual_memories:
            context_section = "## Contextual Memories\n\n"
            for memory in contextual_memories:
                context_section += f"- **{memory.type.value.title()}**: {memory.content}\n"
            
            memory_context = context_section + "\n" + memory_context
    
    return f"""{system_prompt}

## Advanced Memory Context

The following information is available from the memory system:

{memory_context}

Use this context to inform your decisions, maintain consistency with established patterns,
and leverage available skills effectively."""

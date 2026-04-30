"""技能执行引擎。

基于参考仓库的技能架构，实现技能的管理、执行和组合功能。
支持技能依赖解析、执行生命周期管理和结果缓存。
"""

from __future__ import annotations

import time
import inspect
import asyncio
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union, Set
from pathlib import Path
from functools import wraps

from astrid.state.advanced_memory import AdvancedMemoryManager, SkillDefinition, MemoryEntry, MemoryScope, MemoryType


# ---------------------------------------------------------------------------
# 技能执行状态
# ---------------------------------------------------------------------------

class SkillStatus(str, Enum):
    """技能执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SkillResultType(str, Enum):
    """技能结果类型"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    CACHED = "cached"


# ---------------------------------------------------------------------------
# 技能执行结果
# ---------------------------------------------------------------------------

@dataclass
class SkillExecutionResult:
    """技能执行结果"""
    skill_name: str
    status: SkillStatus
    result_type: SkillResultType
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    # 元数据
    cache_hit: bool = False
    dependencies_executed: List[str] = field(default_factory=list)
    memory_entries_created: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skill_name": self.skill_name,
            "status": self.status.value,
            "result_type": self.result_type.value,
            "output": str(self.output) if not isinstance(self.output, (dict, list, str, int, float, bool, type(None))) else self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp,
            "cache_hit": self.cache_hit,
            "dependencies_executed": self.dependencies_executed,
            "memory_entries_created": self.memory_entries_created,
        }
    
    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == SkillStatus.COMPLETED and self.result_type in [SkillResultType.SUCCESS, SkillResultType.CACHED]
    
    def get_output_summary(self) -> str:
        """获取输出摘要"""
        if isinstance(self.output, str):
            return self.output[:200] + "..." if len(self.output) > 200 else self.output
        elif isinstance(self.output, (dict, list)):
            return str(self.output)[:200] + "..." if len(str(self.output)) > 200 else str(self.output)
        else:
            return str(self.output)


# ---------------------------------------------------------------------------
# 技能执行上下文
# ---------------------------------------------------------------------------

@dataclass
class SkillExecutionContext:
    """技能执行上下文"""
    skill_name: str
    parameters: Dict[str, Any]
    memory_manager: AdvancedMemoryManager
    parent_execution_id: Optional[str] = None
    
    # 执行状态
    execution_id: str = field(default_factory=lambda: f"exec-{int(time.time())}-{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}")
    start_time: float = field(default_factory=time.time)
    
    # 结果缓存
    cache_key: Optional[str] = None
    use_cache: bool = True
    
    def get_cache_key(self) -> str:
        """获取缓存键"""
        if self.cache_key:
            return self.cache_key
        
        # 基于技能名和参数生成缓存键
        param_str = json.dumps(self.parameters, sort_keys=True) if hasattr(self, 'json') else str(sorted(self.parameters.items()))
        return hashlib.md5(f"{self.skill_name}:{param_str}".encode()).hexdigest()
    
    def create_memory_entry(self, content: str, **kwargs) -> MemoryEntry:
        """创建记忆条目"""
        return self.memory_manager.add_memory(
            scope=MemoryScope.SESSION,
            type=MemoryType.CONTEXT,
            content=content,
            source=f"skill:{self.skill_name}",
            **kwargs
        )


# ---------------------------------------------------------------------------
# 技能装饰器
# ---------------------------------------------------------------------------

class SkillDecorator:
    """技能装饰器，用于注册技能函数"""
    
    def __init__(self, memory_manager: Optional[AdvancedMemoryManager] = None):
        self.memory_manager = memory_manager
        self.registered_skills: Dict[str, RegisteredSkill] = {}
        self.skill_engine: Optional[SkillEngine] = None
    
    def skill(
        self,
        name: str,
        description: str,
        dependencies: List[str] = None,
        category: str = "general",
        capabilities: List[str] = None,
        version: str = "1.0.0",
    ):
        """技能装饰器"""
        def decorator(func: Callable):
            # 创建技能定义
            skill_def = SkillDefinition(
                name=name,
                description=description,
                version=version,
                category=category,
                dependencies=dependencies or [],
                capabilities=capabilities or [],
                entry_point=f"{func.__module__}.{func.__name__}",
            )
            
            # 注册技能
            registered_skill = RegisteredSkill(
                definition=skill_def,
                function=func,
                is_async=inspect.iscoroutinefunction(func),
            )
            
            self.registered_skills[name] = registered_skill
            
            # 如果存在记忆管理器，注册技能
            if self.memory_manager:
                self.memory_manager.register_skill(skill_def)
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 如果技能引擎已设置，使用引擎执行
                if self.skill_engine:
                    context = SkillExecutionContext(
                        skill_name=name,
                        parameters=kwargs,
                        memory_manager=self.memory_manager or AdvancedMemoryManager(),
                    )
                    return self.skill_engine.execute_skill(context)
                else:
                    # 直接执行函数
                    return func(*args, **kwargs)
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 如果技能引擎已设置，使用引擎执行
                if self.skill_engine:
                    context = SkillExecutionContext(
                        skill_name=name,
                        parameters=kwargs,
                        memory_manager=self.memory_manager or AdvancedMemoryManager(),
                    )
                    return await self.skill_engine.execute_skill_async(context)
                else:
                    # 直接执行异步函数
                    return await func(*args, **kwargs)
            
            return async_wrapper if registered_skill.is_async else wrapper
        
        return decorator


# ---------------------------------------------------------------------------
# 注册的技能
# ---------------------------------------------------------------------------

@dataclass
class RegisteredSkill:
    """注册的技能"""
    definition: SkillDefinition
    function: Callable
    is_async: bool
    
    def execute(self, context: SkillExecutionContext) -> SkillExecutionResult:
        """执行技能"""
        start_time = time.time()
        
        try:
            if self.is_async:
                # 对于异步函数，需要特殊的处理
                # 这里简化处理，在实际应用中应该使用异步执行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    output = loop.run_until_complete(self.function(**context.parameters))
                finally:
                    loop.close()
            else:
                output = self.function(**context.parameters)
            
            execution_time = time.time() - start_time
            
            # 创建执行结果
            return SkillExecutionResult(
                skill_name=self.definition.name,
                status=SkillStatus.COMPLETED,
                result_type=SkillResultType.SUCCESS,
                output=output,
                execution_time=execution_time,
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            return SkillExecutionResult(
                skill_name=self.definition.name,
                status=SkillStatus.FAILED,
                result_type=SkillResultType.FAILURE,
                output=None,
                error=str(e),
                execution_time=execution_time,
            )


# ---------------------------------------------------------------------------
# 技能引擎
# ---------------------------------------------------------------------------

class SkillEngine:
    """技能执行引擎"""
    
    def __init__(self, memory_manager: AdvancedMemoryManager):
        self.memory_manager = memory_manager
        self.skill_decorator = SkillDecorator(memory_manager)
        self.skill_decorator.skill_engine = self
        self.skill_cache: Dict[str, SkillExecutionResult] = {}
        self.execution_history: List[SkillExecutionResult] = []
        
    def register_skill(self, skill_def: SkillDefinition, func: Callable) -> None:
        """注册技能"""
        registered_skill = RegisteredSkill(
            definition=skill_def,
            function=func,
            is_async=inspect.iscoroutinefunction(func),
        )
        
        self.skill_decorator.registered_skills[skill_def.name] = registered_skill
        self.memory_manager.register_skill(skill_def)
    
    def get_skill(self, name: str) -> Optional[RegisteredSkill]:
        """获取技能"""
        return self.skill_decorator.registered_skills.get(name)
    
    def resolve_dependencies(self, skill_name: str) -> List[str]:
        """解析技能依赖"""
        skill = self.get_skill(skill_name)
        if not skill:
            return []
        
        # 递归解析依赖
        resolved: Set[str] = set()
        
        def resolve(name: str):
            dep_skill = self.get_skill(name)
            if not dep_skill:
                return
            
            for dep in dep_skill.definition.dependencies:
                if dep not in resolved:
                    resolve(dep)
            
            resolved.add(name)
        
        # 解析当前技能的依赖
        for dep in skill.definition.dependencies:
            resolve(dep)
        
        # 最后添加当前技能
        resolve(skill_name)
        
        return list(resolved)
    
    def execute_skill(self, context: SkillExecutionContext) -> SkillExecutionResult:
        """执行技能（同步）"""
        return self._execute_skill_internal(context)
    
    async def execute_skill_async(self, context: SkillExecutionContext) -> SkillExecutionResult:
        """执行技能（异步）"""
        # 简化处理：在协程中运行同步执行
        return self._execute_skill_internal(context)
    
    def _execute_skill_internal(self, context: SkillExecutionContext) -> SkillExecutionResult:
        """内部执行逻辑"""
        skill = self.get_skill(context.skill_name)
        if not skill:
            return SkillExecutionResult(
                skill_name=context.skill_name,
                status=SkillStatus.FAILED,
                result_type=SkillResultType.FAILURE,
                output=None,
                error=f"Skill not found: {context.skill_name}",
            )
        
        # 检查缓存
        cache_key = context.get_cache_key()
        if context.use_cache and cache_key in self.skill_cache:
            cached_result = self.skill_cache[cache_key]
            cached_result.cache_hit = True
            return cached_result
        
        # 解析并执行依赖
        dependency_order = self.resolve_dependencies(context.skill_name)
        dependencies_executed = []
        
        for dep_name in dependency_order:
            if dep_name == context.skill_name:
                continue
            
            # 为依赖创建执行上下文
            dep_context = SkillExecutionContext(
                skill_name=dep_name,
                parameters={},  # 依赖可能需要参数，这里简化
                memory_manager=context.memory_manager,
                parent_execution_id=context.execution_id,
            )
            
            # 执行依赖
            dep_result = self.execute_skill(dep_context)
            if dep_result.is_success():
                dependencies_executed.append(dep_name)
            else:
                # 依赖执行失败，整个技能执行失败
                return SkillExecutionResult(
                    skill_name=context.skill_name,
                    status=SkillStatus.FAILED,
                    result_type=SkillResultType.FAILURE,
                    output=None,
                    error=f"Dependency failed: {dep_name}: {dep_result.error}",
                    dependencies_executed=dependencies_executed,
                )
        
        # 执行主技能
        start_time = time.time()
        result = skill.execute(context)
        execution_time = time.time() - start_time
        
        # 更新执行时间
        result.execution_time = execution_time
        result.dependencies_executed = dependencies_executed
        
        # 缓存结果
        if context.use_cache:
            self.skill_cache[cache_key] = result
        
        # 记录执行历史
        self.execution_history.append(result)
        
        # 限制历史记录大小
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
        
        return result
    
    def execute_skill_chain(
        self,
        skill_chain: List[Dict[str, Any]],
        memory_manager: Optional[AdvancedMemoryManager] = None,
    ) -> List[SkillExecutionResult]:
        """执行技能链"""
        results = []
        mgr = memory_manager or self.memory_manager
        
        for skill_spec in skill_chain:
            skill_name = skill_spec.get("skill")
            parameters = skill_spec.get("parameters", {})
            
            context = SkillExecutionContext(
                skill_name=skill_name,
                parameters=parameters,
                memory_manager=mgr,
            )
            
            result = self.execute_skill(context)
            results.append(result)
            
            # 如果技能执行失败，可以停止链式执行
            if not result.is_success() and skill_spec.get("stop_on_failure", True):
                break
        
        return results
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        successful = [r for r in self.execution_history if r.is_success()]
        failed = [r for r in self.execution_history if not r.is_success()]
        
        if not self.execution_history:
            return {}
        
        total_execution_time = sum(r.execution_time for r in self.execution_history)
        
        return {
            "total_executions": len(self.execution_history),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self.execution_history) if self.execution_history else 0,
            "avg_execution_time": total_execution_time / len(self.execution_history),
            "cache_hits": sum(1 for r in self.execution_history if r.cache_hit),
            "cache_hit_rate": sum(1 for r in self.execution_history if r.cache_hit) / len(self.execution_history) if self.execution_history else 0,
        }
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self.skill_cache.clear()
    
    def get_available_skills(self) -> List[SkillDefinition]:
        """获取可用技能"""
        return [skill.definition for skill in self.skill_decorator.registered_skills.values()]


# ---------------------------------------------------------------------------
# 内置技能实现
# ---------------------------------------------------------------------------

def create_default_skill_engine(memory_manager: AdvancedMemoryManager) -> SkillEngine:
    """创建默认技能引擎，包含内置技能"""
    engine = SkillEngine(memory_manager)
    
    # 创建技能装饰器
    decorator = engine.skill_decorator
    
    # 定义内置技能
    
    @decorator.skill(
        name="terminology-lookup",
        description="查找术语定义",
        category="terminology",
        capabilities=["术语查询", "定义检索"],
    )
    def terminology_lookup(term: str) -> Dict[str, Any]:
        """查找术语定义"""
        term_entry = memory_manager.get_term(term)
        if term_entry:
            return {
                "term": term,
                "definition": term_entry.definition,
                "category": term_entry.category,
                "examples": term_entry.examples,
                "related_terms": term_entry.related_terms,
            }
        else:
            # 尝试搜索相似术语
            similar = memory_manager.search_terms(term)
            return {
                "term": term,
                "found": False,
                "similar_terms": [t.term for t in similar[:3]],
            }
    
    @decorator.skill(
        name="memory-search",
        description="搜索记忆条目",
        category="memory",
        capabilities=["记忆搜索", "上下文检索"],
    )
    def memory_search(query: str, scope: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        if scope:
            memory_scope = MemoryScope(scope)
            results = memory_manager.search_memories(query, scope=memory_scope, limit=limit)
        else:
            results = memory_manager.search_memories(query, limit=limit)
        
        return [
            {
                "id": r.id,
                "type": r.type.value,
                "content": r.content,
                "confidence": r.confidence,
                "usage_count": r.usage_count,
            }
            for r in results
        ]
    
    @decorator.skill(
        name="context-builder",
        description="构建当前会话的上下文",
        category="context",
        dependencies=["memory-search"],
        capabilities=["上下文构建", "记忆整合"],
    )
    def context_builder(current_text: str, max_memories: int = 5) -> Dict[str, Any]:
        """构建上下文"""
        # 搜索相关记忆
        memories = memory_manager.get_contextual_memories(current_text, max_entries=max_memories)
        
        # 提取关键词
        keywords = memory_manager._extract_keywords(current_text)
        
        return {
            "context_text": current_text,
            "relevant_memories": [
                {
                    "id": m.id,
                    "type": m.type.value,
                    "content": m.content[:100] + "..." if len(m.content) > 100 else m.content,
                    "confidence": m.confidence,
                }
                for m in memories
            ],
            "keywords": keywords,
            "memory_count": len(memories),
        }
    
    @decorator.skill(
        name="pattern-recognizer",
        description="识别代码或文本模式",
        category="analysis",
        capabilities=["模式识别", "规律发现"],
    )
    def pattern_recognizer(text: str, pattern_type: str = "code") -> Dict[str, Any]:
        """识别模式"""
        # 简化版本：在实际应用中应该实现更复杂的模式识别算法
        if pattern_type == "code":
            # 识别常见的代码模式
            patterns = []
            
            # 检查函数定义
            import re
            function_patterns = re.findall(r'def\s+\w+\s*\([^)]*\)', text)
            if function_patterns:
                patterns.append({
                    "type": "function_definition",
                    "count": len(function_patterns),
                    "examples": function_patterns[:2],
                })
            
            # 检查类定义
            class_patterns = re.findall(r'class\s+\w+', text)
            if class_patterns:
                patterns.append({
                    "type": "class_definition",
                    "count": len(class_patterns),
                    "examples": class_patterns[:2],
                })
            
            return {
                "pattern_type": pattern_type,
                "patterns_found": patterns,
                "total_patterns": len(patterns),
            }
        
        elif pattern_type == "text":
            # 识别文本模式
            lines = text.split('\n')
            return {
                "pattern_type": pattern_type,
                "line_count": len(lines),
                "avg_line_length": sum(len(line) for line in lines) / max(len(lines), 1),
                "unique_words": len(set(text.lower().split())),
            }
        
        else:
            return {
                "pattern_type": pattern_type,
                "error": f"Unsupported pattern type: {pattern_type}",
            }
    
    @decorator.skill(
        name="decision-recorder",
        description="记录重要决策",
        category="memory",
        capabilities=["决策记录", "历史追踪"],
    )
    def decision_recorder(decision: str, rationale: str, impact: str = "") -> Dict[str, Any]:
        """记录决策"""
        # 创建决策记忆
        memory_entry = memory_manager.add_memory(
            scope=MemoryScope.PROJECT,
            type=MemoryType.DECISION,
            content=f"Decision: {decision}\nRationale: {rationale}\nImpact: {impact}",
            tags=["decision", "record"],
            categories=["project-management"],
            priority=MemoryPriority.HIGH,
            source="skill:decision-recorder",
        )
        
        return {
            "decision": decision,
            "memory_id": memory_entry.id,
            "recorded_at": time.time(),
        }
    
    return engine


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

import json

def create_skill_from_function(
    func: Callable,
    name: str,
    description: str,
    dependencies: List[str] = None,
    category: str = "general",
    capabilities: List[str] = None,
    version: str = "1.0.0",
) -> RegisteredSkill:
    """从函数创建技能"""
    # 分析函数签名
    params = inspect.signature(func).parameters
    
    # 创建技能定义
    skill_def = SkillDefinition(
        name=name,
        description=description,
        version=version,
        category=category,
        dependencies=dependencies or [],
        capabilities=capabilities or [],
        entry_point=f"{func.__module__}.{func.__name__}",
    )
    
    return RegisteredSkill(
        definition=skill_def,
        function=func,
        is_async=inspect.iscoroutinefunction(func),
    )


def execute_skill_workflow(
    workflow: List[Dict[str, Any]],
    memory_manager: AdvancedMemoryManager,
) -> Dict[str, Any]:
    """执行技能工作流"""
    engine = SkillEngine(memory_manager)
    
    results = engine.execute_skill_chain(workflow, memory_manager)
    
    # 汇总结果
    successful = [r for r in results if r.is_success()]
    failed = [r for r in results if not r.is_success()]
    
    return {
        "total_skills": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "results": [r.to_dict() for r in results],
        "overall_status": "success" if not failed else "partial" if successful else "failure",
        "execution_time": sum(r.execution_time for r in results),
    }

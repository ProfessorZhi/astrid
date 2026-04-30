"""自举(self-bootstrapping)系统。

基于参考仓库 https://github.com/Ydy4HYW7ExA/agent 的自举理论，
实现系统自我改进、技能生成、知识扩展和元学习能力。

核心概念：
1. 自我改进：分析性能，识别瓶颈，优化执行
2. 技能生成：从经验中提炼模式，创建新技能
3. 知识扩展：主动学习和扩展知识库
4. 依赖优化：优化技能依赖和执行顺序
5. 元学习：学习如何更好地学习
"""

from __future__ import annotations

import json
import time
import uuid
import hashlib
import inspect
import asyncio
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Union
from pathlib import Path
from datetime import datetime, timedelta

from astrid.state.advanced_memory import (
    AdvancedMemoryManager, MemoryEntry, MemoryScope, MemoryType, MemoryPriority,
    SkillDefinition, TerminologyEntry
)
from astrid.integrations.skill_engine import SkillEngine, SkillExecutionResult, SkillExecutionContext
from astrid.integrations.terminology_governance import TerminologyGovernanceSystem


# ---------------------------------------------------------------------------
# 自举状态和类型
# ---------------------------------------------------------------------------

class BootstrapPhase(str, Enum):
    """自举阶段"""
    INITIALIZATION = "initialization"
    OBSERVATION = "observation"
    ANALYSIS = "analysis" 
    GENERATION = "generation"
    INTEGRATION = "integration"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"

class ImprovementType(str, Enum):
    """改进类型"""
    PERFORMANCE = "performance"
    MEMORY = "memory"
    SKILL = "skill"
    TERMINOLOGY = "terminology"
    WORKFLOW = "workflow"
    ARCHITECTURE = "architecture"

class LearningSource(str, Enum):
    """学习来源"""
    USER_INTERACTION = "user_interaction"
    TOOL_EXECUTION = "tool_execution"
    CODE_ANALYSIS = "code_analysis"
    DOCUMENTATION = "documentation"
    ERROR_ANALYSIS = "error_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"


# ---------------------------------------------------------------------------
# 自举记录
# ---------------------------------------------------------------------------

@dataclass
class BootstrapRecord:
    """自举过程记录"""
    id: str
    phase: BootstrapPhase
    improvement_type: ImprovementType
    description: str
    timestamp: float = field(default_factory=time.time)
    
    # 输入数据
    input_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    
    # 处理结果
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    generated_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    integration_results: Dict[str, Any] = field(default_factory=dict)
    
    # 评估指标
    metrics: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error_message: str = ""
    
    # 元数据
    learning_source: LearningSource = LearningSource.USER_INTERACTION
    confidence: float = 0.0  # 0.0-1.0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "phase": self.phase.value,
            "improvement_type": self.improvement_type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "input_data": self.input_data,
            "context": self.context,
            "analysis_results": self.analysis_results,
            "generated_artifacts": self.generated_artifacts,
            "integration_results": self.integration_results,
            "metrics": self.metrics,
            "success": self.success,
            "error_message": self.error_message,
            "learning_source": self.learning_source.value,
            "confidence": self.confidence,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BootstrapRecord":
        """从字典创建"""
        return cls(
            id=data["id"],
            phase=BootstrapPhase(data["phase"]),
            improvement_type=ImprovementType(data["improvement_type"]),
            description=data["description"],
            timestamp=data.get("timestamp", time.time()),
            input_data=data.get("input_data", {}),
            context=data.get("context", {}),
            analysis_results=data.get("analysis_results", {}),
            generated_artifacts=data.get("generated_artifacts", []),
            integration_results=data.get("integration_results", {}),
            metrics=data.get("metrics", {}),
            success=data.get("success", False),
            error_message=data.get("error_message", ""),
            learning_source=LearningSource(data.get("learning_source", "user_interaction")),
            confidence=data.get("confidence", 0.0),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# 性能分析器
# ---------------------------------------------------------------------------

class PerformanceAnalyzer:
    """性能分析器，用于识别优化机会"""
    
    def __init__(self, memory_manager: AdvancedMemoryManager):
        self.memory_manager = memory_manager
        self.performance_history: List[Dict[str, Any]] = []
        self.bottlenecks: List[Dict[str, Any]] = []
        
    def analyze_skill_performance(self, skill_engine: SkillEngine) -> Dict[str, Any]:
        """分析技能性能"""
        stats = skill_engine.get_execution_stats()
        
        analysis = {
            "timestamp": time.time(),
            "total_executions": stats.get("total_executions", 0),
            "success_rate": stats.get("success_rate", 0),
            "avg_execution_time": stats.get("avg_execution_time", 0),
            "cache_hit_rate": stats.get("cache_hit_rate", 0),
        }
        
        # 识别性能问题
        issues = []
        
        if stats.get("success_rate", 1.0) < 0.8:
            issues.append({
                "type": "low_success_rate",
                "severity": "high",
                "description": f"技能执行成功率较低: {stats.get('success_rate', 0):.2%}",
                "suggestions": [
                    "检查技能依赖关系",
                    "优化错误处理逻辑",
                    "增加技能验证",
                ]
            })
        
        if stats.get("avg_execution_time", 0) > 5.0:  # 超过5秒
            issues.append({
                "type": "high_execution_time",
                "severity": "medium",
                "description": f"平均执行时间较高: {stats.get('avg_execution_time', 0):.2f}秒",
                "suggestions": [
                    "优化技能算法",
                    "添加结果缓存",
                    "并行执行独立任务",
                ]
            })
        
        if stats.get("cache_hit_rate", 0) < 0.3:
            issues.append({
                "type": "low_cache_utilization",
                "severity": "low",
                "description": f"缓存命中率较低: {stats.get('cache_hit_rate', 0):.2%}",
                "suggestions": [
                    "优化缓存键生成",
                    "增加缓存过期时间",
                    "检查缓存有效性",
                ]
            })
        
        analysis["issues"] = issues
        self.performance_history.append(analysis)
        
        # 限制历史记录大小
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
        
        return analysis
    
    def analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用情况"""
        stats = self.memory_manager.get_stats()
        
        analysis = {
            "timestamp": time.time(),
            "memory_stats": stats.get("memory_stats", {}),
            "skill_stats": stats.get("skill_stats", {}),
            "terminology_stats": stats.get("terminology_stats", {}),
        }
        
        # 识别内存使用问题
        issues = []
        
        # 检查记忆使用分布
        for scope, scope_stats in stats.get("memory_stats", {}).items():
            count = scope_stats.get("count", 0)
            usage = scope_stats.get("total_usage", 0)
            
            if count > 0 and usage == 0:
                issues.append({
                    "type": "unused_memory",
                    "scope": scope,
                    "severity": "low",
                    "description": f"{scope}范围的记忆条目未被使用",
                    "suggestions": [
                        "清理未使用的记忆",
                        "优化记忆关联",
                        "增加记忆访问",
                    ]
                })
        
        # 检查技能使用情况
        total_skills = stats.get("skill_stats", {}).get("total_skills", 0)
        total_skill_usage = stats.get("skill_stats", {}).get("total_usage", 0)
        
        if total_skills > 0:
            avg_usage = total_skill_usage / total_skills
            if avg_usage < 1.0:
                issues.append({
                    "type": "underutilized_skills",
                    "severity": "medium",
                    "description": f"技能平均使用次数较低: {avg_usage:.2f}",
                    "suggestions": [
                        "优化技能发现机制",
                        "增加技能推荐",
                        "合并相似技能",
                    ]
                })
        
        analysis["issues"] = issues
        return analysis
    
    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """识别性能瓶颈"""
        bottlenecks = []
        
        # 分析技能执行历史
        for perf_record in self.performance_history[-10:]:  # 最近10次记录
            for issue in perf_record.get("issues", []):
                if issue["severity"] in ["high", "medium"]:
                    bottlenecks.append({
                        "type": issue["type"],
                        "severity": issue["severity"],
                        "description": issue["description"],
                        "first_detected": perf_record["timestamp"],
                        "last_detected": time.time(),
                        "suggestions": issue["suggestions"],
                    })
        
        self.bottlenecks = bottlenecks
        return bottlenecks
    
    def generate_optimization_plan(self) -> Dict[str, Any]:
        """生成优化计划"""
        bottlenecks = self.identify_bottlenecks()
        
        plan = {
            "timestamp": time.time(),
            "total_bottlenecks": len(bottlenecks),
            "by_severity": {},
            "optimization_tasks": [],
        }
        
        # 按严重程度分组
        for bottleneck in bottlenecks:
            severity = bottleneck["severity"]
            if severity not in plan["by_severity"]:
                plan["by_severity"][severity] = 0
            plan["by_severity"][severity] += 1
        
        # 生成优化任务
        for bottleneck in bottlenecks:
            task = {
                "id": f"opt-{uuid.uuid4().hex[:8]}",
                "bottleneck_type": bottleneck["type"],
                "severity": bottleneck["severity"],
                "description": f"优化: {bottleneck['description']}",
                "suggestions": bottleneck["suggestions"],
                "priority": 1 if bottleneck["severity"] == "high" else 2 if bottleneck["severity"] == "medium" else 3,
                "estimated_effort": "high" if bottleneck["severity"] == "high" else "medium",
            }
            plan["optimization_tasks"].append(task)
        
        # 按优先级排序
        plan["optimization_tasks"].sort(key=lambda x: x["priority"])
        
        return plan


# ---------------------------------------------------------------------------
# 技能生成器
# ---------------------------------------------------------------------------

class SkillGenerator:
    """技能生成器，从经验中创建新技能"""
    
    def __init__(self, memory_manager: AdvancedMemoryManager, skill_engine: SkillEngine):
        self.memory_manager = memory_manager
        self.skill_engine = skill_engine
        self.generated_skills: List[Dict[str, Any]] = []
        
    def analyze_patterns_for_skill_creation(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """分析模式以创建新技能"""
        patterns = []
        
        # 1. 分析频繁执行的代码模式
        execution_history = self.skill_engine.execution_history
        if len(execution_history) < min_occurrences:
            return patterns
        
        # 按技能分组
        skill_groups: Dict[str, List[SkillExecutionResult]] = {}
        for result in execution_history:
            if result.is_success():
                skill_name = result.skill_name
                if skill_name not in skill_groups:
                    skill_groups[skill_name] = []
                skill_groups[skill_name].append(result)
        
        # 2. 识别频繁组合的技能
        skill_sequences = self._extract_skill_sequences(execution_history)
        frequent_sequences = self._find_frequent_sequences(skill_sequences, min_occurrences)
        
        for seq in frequent_sequences:
            patterns.append({
                "type": "skill_sequence",
                "sequence": seq["sequence"],
                "frequency": seq["frequency"],
                "avg_success_rate": seq.get("avg_success_rate", 0),
                "suggestion": f"创建组合技能: {' -> '.join(seq['sequence'])}",
            })
        
        # 3. 分析相似工具调用模式
        tool_patterns = self._analyze_tool_patterns()
        patterns.extend(tool_patterns)
        
        return patterns
    
    def _extract_skill_sequences(self, history: List[SkillExecutionResult], window_size: int = 5) -> List[List[str]]:
        """提取技能序列"""
        sequences = []
        
        for i in range(len(history) - window_size + 1):
            window = history[i:i + window_size]
            sequence = [result.skill_name for result in window if result.is_success()]
            if len(sequence) >= 2:  # 至少2个技能
                sequences.append(sequence)
        
        return sequences
    
    def _find_frequent_sequences(self, sequences: List[List[str]], min_freq: int) -> List[Dict[str, Any]]:
        """查找频繁序列"""
        sequence_counts: Dict[str, Dict[str, Any]] = {}
        
        for seq in sequences:
            seq_key = "->".join(seq)
            if seq_key not in sequence_counts:
                sequence_counts[seq_key] = {
                    "sequence": seq,
                    "count": 0,
                    "success_count": 0,
                }
            sequence_counts[seq_key]["count"] += 1
        
        # 过滤并计算成功率
        frequent_sequences = []
        for seq_data in sequence_counts.values():
            if seq_data["count"] >= min_freq:
                # 这里简化处理，实际应用中需要计算实际成功率
                seq_data["frequency"] = seq_data["count"]
                seq_data["avg_success_rate"] = 0.8  # 假设的成功率
                frequent_sequences.append(seq_data)
        
        return frequent_sequences
    
    def _analyze_tool_patterns(self) -> List[Dict[str, Any]]:
        """分析工具调用模式"""
        # 从记忆系统中搜索工具使用模式
        tool_memories = self.memory_manager.search_memories(
            query="tool",
            type=MemoryType.PATTERN,
            limit=20
        )
        
        patterns = []
        for memory in tool_memories:
            # 分析工具使用模式
            if "tool" in memory.content.lower() or "execute" in memory.content.lower():
                patterns.append({
                    "type": "tool_usage",
                    "memory_id": memory.id,
                    "content": memory.content[:100],
                    "usage_count": memory.usage_count,
                    "suggestion": f"从工具使用模式创建技能: {memory.content[:50]}...",
                })
        
        return patterns
    
    def generate_skill_from_pattern(self, pattern: Dict[str, Any]) -> Optional[SkillDefinition]:
        """从模式生成技能"""
        pattern_type = pattern.get("type")
        
        if pattern_type == "skill_sequence":
            sequence = pattern.get("sequence", [])
            if len(sequence) >= 2:
                # 创建组合技能
                skill_name = f"composite-{'-'.join(sequence[:3])}"
                description = f"组合技能: {' -> '.join(sequence)}"
                
                # 分析依赖关系
                dependencies = []
                for i in range(len(sequence) - 1):
                    # 检查技能是否存在
                    if self.skill_engine.get_skill(sequence[i]):
                        dependencies.append(sequence[i])
                
                skill_def = SkillDefinition(
                    name=skill_name,
                    description=description,
                    category="composite",
                    dependencies=dependencies,
                    capabilities=["组合执行", "流程优化", "结果聚合"],
                    version="1.0.0",
                )
                
                return skill_def
        
        elif pattern_type == "tool_usage":
            # 从工具使用模式创建技能
            content = pattern.get("content", "")
            skill_name = f"tool-pattern-{hashlib.md5(content.encode()).hexdigest()[:8]}"
            
            skill_def = SkillDefinition(
                name=skill_name,
                description=f"工具使用模式: {content[:50]}...",
                category="tool",
                capabilities=["工具调用", "模式匹配", "自动化"],
                version="1.0.0",
            )
            
            return skill_def
        
        return None
    
    def create_skill_implementation(self, skill_def: SkillDefinition) -> Optional[Callable]:
        """创建技能实现"""
        # 这是一个简化版本，实际应用中需要生成实际的Python代码
        # 这里返回一个模拟函数
        
        def generated_skill(**kwargs):
            """生成的技能函数"""
            return {
                "skill": skill_def.name,
                "status": "generated",
                "timestamp": time.time(),
                "parameters": kwargs,
                "message": "This is an auto-generated skill implementation.",
            }
        
        return generated_skill


# ---------------------------------------------------------------------------
# 知识扩展器
# ---------------------------------------------------------------------------

class KnowledgeExpander:
    """知识扩展器，主动学习和扩展知识库"""
    
    def __init__(self, memory_manager: AdvancedMemoryManager):
        self.memory_manager = memory_manager
        self.learning_sessions: List[Dict[str, Any]] = []
        
    def extract_knowledge_from_interaction(self, interaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从交互中提取知识"""
        knowledge_items = []
        
        # 提取用户查询中的知识
        user_query = interaction.get("user_query", "")
        if user_query:
            # 提取潜在术语
            potential_terms = self._extract_potential_terms(user_query)
            for term in potential_terms:
                knowledge_items.append({
                    "type": "potential_term",
                    "content": term,
                    "context": user_query,
                    "confidence": 0.7,
                })
            
            # 提取任务模式
            task_patterns = self._extract_task_patterns(user_query)
            knowledge_items.extend(task_patterns)
        
        # 提取系统响应中的知识
        system_response = interaction.get("system_response", "")
        if system_response:
            # 提取解决方案模式
            solution_patterns = self._extract_solution_patterns(system_response)
            knowledge_items.extend(solution_patterns)
            
            # 提取代码模式
            code_patterns = self._extract_code_patterns(system_response)
            knowledge_items.extend(code_patterns)
        
        # 提取工具执行结果中的知识
        tool_results = interaction.get("tool_results", [])
        for result in tool_results:
            # 提取工具使用模式
            tool_patterns = self._extract_tool_patterns(result)
            knowledge_items.extend(tool_patterns)
        
        return knowledge_items
    
    def _extract_potential_terms(self, text: str) -> List[str]:
        """提取潜在术语"""
        import re
        
        # 提取首字母大写的单词（技术术语常见模式）
        potential_terms = re.findall(r'\b[A-Z][a-zA-Z0-9]+\b', text)
        
        # 提取带连字符的术语
        hyphen_terms = re.findall(r'\b[a-zA-Z]+-[a-zA-Z]+\b', text)
        potential_terms.extend(hyphen_terms)
        
        # 提取带下划线的术语
        underscore_terms = re.findall(r'\b[a-zA-Z]+_[a-zA-Z]+\b', text)
        potential_terms.extend(underscore_terms)
        
        return list(set(potential_terms))
    
    def _extract_task_patterns(self, text: str) -> List[Dict[str, Any]]:
        """提取任务模式"""
        patterns = []
        
        # 常见任务关键词
        task_keywords = ["create", "implement", "add", "remove", "update", "fix", 
                        "optimize", "refactor", "test", "deploy", "analyze"]
        
        for keyword in task_keywords:
            if keyword in text.lower():
                # 提取任务描述
                import re
                task_match = re.search(rf'{keyword}\s+([^,.!?]+)', text, re.IGNORECASE)
                if task_match:
                    task_desc = task_match.group(1).strip()
                    patterns.append({
                        "type": "task_pattern",
                        "keyword": keyword,
                        "description": task_desc,
                        "context": text,
                    })
        
        return patterns
    
    def _extract_solution_patterns(self, text: str) -> List[Dict[str, Any]]:
        """提取解决方案模式"""
        patterns = []
        
        # 解决方案模式关键词
        solution_patterns = [
            ("step", r"step\s+\d+[:.]?\s*(.+)", "步骤模式"),
            ("approach", r"approach[:.]?\s*(.+)", "方法模式"),
            ("solution", r"solution[:.]?\s*(.+)", "解决方案模式"),
            ("implementation", r"implementation[:.]?\s*(.+)", "实现模式"),
        ]
        
        for pattern_name, pattern_re, description in solution_patterns:
            import re
            matches = re.findall(pattern_re, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match_text = match[0]
                else:
                    match_text = match
                
                patterns.append({
                    "type": "solution_pattern",
                    "pattern": pattern_name,
                    "content": match_text.strip(),
                    "description": description,
                })
        
        return patterns
    
    def _extract_code_patterns(self, text: str) -> List[Dict[str, Any]]:
        """提取代码模式"""
        patterns = []
        
        # 检测代码块
        import re
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', text, re.DOTALL)
        
        for i, code_block in enumerate(code_blocks):
            # 分析代码结构
            lines = code_block.strip().split('\n')
            if len(lines) >= 3:  # 有意义的代码块
                # 提取函数定义
                function_defs = re.findall(r'def\s+(\w+)\s*\([^)]*\)', code_block)
                for func in function_defs:
                    patterns.append({
                        "type": "code_pattern",
                        "subtype": "function_definition",
                        "name": func,
                        "line_count": len(lines),
                        "context": f"代码块 {i+1}",
                    })
                
                # 提取类定义
                class_defs = re.findall(r'class\s+(\w+)', code_block)
                for cls in class_defs:
                    patterns.append({
                        "type": "code_pattern",
                        "subtype": "class_definition",
                        "name": cls,
                        "line_count": len(lines),
                        "context": f"代码块 {i+1}",
                    })
        
        return patterns
    
    def _extract_tool_patterns(self, tool_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取工具模式"""
        patterns = []
        
        tool_name = tool_result.get("tool", "")
        success = tool_result.get("success", False)
        
        if success:
            # 成功的工具使用模式
            patterns.append({
                "type": "tool_success_pattern",
                "tool": tool_name,
                "context": str(tool_result.get("result", ""))[:100],
                "confidence": 0.8,
            })
        else:
            # 失败的工具使用模式（学习如何避免）
            error = tool_result.get("error", "")
            patterns.append({
                "type": "tool_error_pattern",
                "tool": tool_name,
                "error": error[:100],
                "confidence": 0.9,
            })
        
        return patterns
    
    def integrate_knowledge(self, knowledge_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """集成知识到记忆系统"""
        integrated = {
            "terms_added": 0,
            "memories_added": 0,
            "patterns_recorded": 0,
            "errors": [],
        }
        
        for item in knowledge_items:
            item_type = item.get("type")
            
            try:
                if item_type == "potential_term":
                    # 添加到术语系统
                    term = item.get("content", "")
                    if term and len(term) > 2:  # 有意义的术语
                        context = item.get("context", "")
                        self.memory_manager.add_memory(
                            scope=MemoryScope.PROJECT,
                            type=MemoryType.TERMINOLOGY,
                            content=f"潜在术语: {term}\n上下文: {context}",
                            tags=["potential_term", "auto_extracted"],
                            priority=MemoryPriority.LOW,
                            source="knowledge_expander",
                        )
                        integrated["terms_added"] += 1
                
                elif item_type in ["task_pattern", "solution_pattern"]:
                    # 添加到记忆系统
                    content = f"{item.get('description', '')}: {item.get('content', '')}"
                    self.memory_manager.add_memory(
                        scope=MemoryScope.PROJECT,
                        type=MemoryType.PATTERN,
                        content=content,
                        tags=["pattern", "auto_extracted", item_type],
                        categories=["knowledge_extraction"],
                        priority=MemoryPriority.MEDIUM,
                        source="knowledge_expander",
                    )
                    integrated["patterns_recorded"] += 1
                
                elif item_type == "code_pattern":
                    # 记录代码模式
                    subtype = item.get("subtype", "")
                    name = item.get("name", "")
                    content = f"{subtype}: {name} ({item.get('line_count', 0)} lines)"
                    
                    self.memory_manager.add_memory(
                        scope=MemoryScope.PROJECT,
                        type=MemoryType.PATTERN,
                        content=content,
                        tags=["code_pattern", subtype, "auto_extracted"],
                        categories=["code_analysis"],
                        priority=MemoryPriority.MEDIUM,
                        source="knowledge_expander",
                    )
                    integrated["memories_added"] += 1
                
                elif item_type in ["tool_success_pattern", "tool_error_pattern"]:
                    # 记录工具使用模式
                    tool = item.get("tool", "")
                    pattern_type = "success" if "success" in item_type else "error"
                    content = f"工具使用模式 ({pattern_type}): {tool}"
                    
                    if pattern_type == "error":
                        content += f"\n错误: {item.get('error', '')}"
                    
                    self.memory_manager.add_memory(
                        scope=MemoryScope.PROJECT,
                        type=MemoryType.PATTERN,
                        content=content,
                        tags=["tool_pattern", pattern_type, "auto_extracted"],
                        categories=["tool_usage"],
                        priority=MemoryPriority.HIGH if pattern_type == "error" else MemoryPriority.MEDIUM,
                        source="knowledge_expander",
                    )
                    integrated["patterns_recorded"] += 1
            
            except Exception as e:
                integrated["errors"].append({
                    "item_type": item_type,
                    "error": str(e),
                })
        
        # 记录学习会话
        self.learning_sessions.append({
            "timestamp": time.time(),
            "knowledge_items_processed": len(knowledge_items),
            "integration_results": integrated,
        })
        
        # 限制会话记录大小
        if len(self.learning_sessions) > 50:
            self.learning_sessions = self.learning_sessions[-50:]
        
        return integrated


# ---------------------------------------------------------------------------
# 元学习协调器
# ---------------------------------------------------------------------------

class MetaLearningCoordinator:
    """元学习协调器，学习如何更好地学习"""
    
    def __init__(
        self,
        memory_manager: AdvancedMemoryManager,
        skill_engine: SkillEngine,
        performance_analyzer: PerformanceAnalyzer,
        skill_generator: SkillGenerator,
        knowledge_expander: KnowledgeExpander,
    ):
        self.memory_manager = memory_manager
        self.skill_engine = skill_engine
        self.performance_analyzer = performance_analyzer
        self.skill_generator = skill_generator
        self.knowledge_expander = knowledge_expander
        
        self.learning_cycles: List[Dict[str, Any]] = []
        self.learning_strategies: Dict[str, Dict[str, Any]] = {}
        
        # 初始化学习策略
        self._initialize_learning_strategies()
    
    def _initialize_learning_strategies(self) -> None:
        """初始化学习策略"""
        self.learning_strategies = {
            "performance_optimization": {
                "name": "性能优化学习",
                "description": "通过分析性能数据来优化系统",
                "trigger_conditions": ["low_success_rate", "high_execution_time"],
                "actions": ["analyze_performance", "generate_optimizations"],
                "priority": 1,
                "effectiveness": 0.8,
                "usage_count": 0,
            },
            "skill_generation": {
                "name": "技能生成学习",
                "description": "从频繁模式中生成新技能",
                "trigger_conditions": ["frequent_patterns", "repetitive_tasks"],
                "actions": ["analyze_patterns", "generate_skills"],
                "priority": 2,
                "effectiveness": 0.7,
                "usage_count": 0,
            },
            "knowledge_extraction": {
                "name": "知识提取学习",
                "description": "从交互中提取和整合知识",
                "trigger_conditions": ["user_interaction", "tool_execution"],
                "actions": ["extract_knowledge", "integrate_knowledge"],
                "priority": 3,
                "effectiveness": 0.9,
                "usage_count": 0,
            },
            "terminology_learning": {
                "name": "术语学习",
                "description": "学习和标准化术语",
                "trigger_conditions": ["new_terminology", "inconsistent_terms"],
                "actions": ["extract_terms", "standardize_terminology"],
                "priority": 2,
                "effectiveness": 0.85,
                "usage_count": 0,
            },
        }
    
    def monitor_and_learn(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """监控环境并触发学习"""
        # 分析当前状态
        current_state = self._analyze_current_state(context)
        
        # 确定需要的学习策略
        applicable_strategies = self._determine_applicable_strategies(current_state)
        
        # 执行学习策略
        learning_results = []
        for strategy_name in applicable_strategies:
            result = self._execute_learning_strategy(strategy_name, current_state)
            learning_results.append(result)
            
            # 更新策略效果
            self._update_strategy_effectiveness(strategy_name, result)
        
        # 记录学习周期
        learning_cycle = {
            "timestamp": time.time(),
            "context": context,
            "current_state": current_state,
            "applied_strategies": applicable_strategies,
            "results": learning_results,
        }
        
        self.learning_cycles.append(learning_cycle)
        
        # 限制记录大小
        if len(self.learning_cycles) > 100:
            self.learning_cycles = self.learning_cycles[-100:]
        
        return {
            "learning_cycle_id": f"lc-{int(time.time())}",
            "strategies_applied": len(applicable_strategies),
            "results_summary": [r.get("summary", "") for r in learning_results],
            "total_learning_cycles": len(self.learning_cycles),
        }
    
    def _analyze_current_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析当前状态"""
        state = {
            "timestamp": time.time(),
            "context_keys": list(context.keys()),
        }
        
        # 分析性能状态
        try:
            perf_analysis = self.performance_analyzer.analyze_skill_performance(self.skill_engine)
            state["performance_issues"] = len(perf_analysis.get("issues", []))
            state["success_rate"] = perf_analysis.get("success_rate", 0)
        except:
            state["performance_issues"] = 0
            state["success_rate"] = 0
        
        # 分析记忆状态
        try:
            memory_stats = self.memory_manager.get_stats()
            state["memory_entries"] = sum(
                scope_stats.get("count", 0)
                for scope_stats in memory_stats.get("memory_stats", {}).values()
            )
            state["total_skills"] = memory_stats.get("skill_stats", {}).get("total_skills", 0)
        except:
            state["memory_entries"] = 0
            state["total_skills"] = 0
        
        # 分析交互上下文
        if "user_query" in context:
            state["has_user_interaction"] = True
            state["query_length"] = len(context["user_query"])
        else:
            state["has_user_interaction"] = False
        
        if "tool_results" in context:
            state["has_tool_execution"] = True
            state["tool_count"] = len(context["tool_results"])
        else:
            state["has_tool_execution"] = False
        
        return state
    
    def _determine_applicable_strategies(self, state: Dict[str, Any]) -> List[str]:
        """确定适用的学习策略"""
        applicable = []
        
        # 检查每个策略的触发条件
        for strategy_name, strategy in self.learning_strategies.items():
            should_trigger = False
            
            for condition in strategy.get("trigger_conditions", []):
                if self._check_trigger_condition(condition, state):
                    should_trigger = True
                    break
            
            if should_trigger:
                applicable.append(strategy_name)
        
        # 按优先级排序
        applicable.sort(key=lambda s: self.learning_strategies[s].get("priority", 99))
        
        return applicable
    
    def _check_trigger_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        """检查触发条件"""
        if condition == "low_success_rate":
            return state.get("success_rate", 1.0) < 0.8
        
        elif condition == "high_execution_time":
            # 这里简化处理，实际需要更复杂的检查
            return state.get("performance_issues", 0) > 0
        
        elif condition == "frequent_patterns":
            # 检查是否有频繁模式
            return state.get("memory_entries", 0) > 50
        
        elif condition == "repetitive_tasks":
            # 检查是否有重复任务
            return state.get("has_user_interaction", False) and state.get("query_length", 0) > 20
        
        elif condition == "user_interaction":
            return state.get("has_user_interaction", False)
        
        elif condition == "tool_execution":
            return state.get("has_tool_execution", False)
        
        elif condition == "new_terminology":
            # 检查是否有新术语
            return state.get("has_user_interaction", False) and state.get("query_length", 0) > 10
        
        elif condition == "inconsistent_terms":
            # 这里简化处理
            return False
        
        return False
    
    def _execute_learning_strategy(self, strategy_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行学习策略"""
        strategy = self.learning_strategies[strategy_name]
        strategy["usage_count"] = strategy.get("usage_count", 0) + 1
        
        result = {
            "strategy": strategy_name,
            "timestamp": time.time(),
            "actions_executed": [],
            "results": {},
            "success": True,
        }
        
        try:
            if strategy_name == "performance_optimization":
                # 执行性能优化
                perf_analysis = self.performance_analyzer.analyze_skill_performance(self.skill_engine)
                optimization_plan = self.performance_analyzer.generate_optimization_plan()
                
                result["actions_executed"].append("analyze_performance")
                result["actions_executed"].append("generate_optimizations")
                result["results"]["performance_analysis"] = perf_analysis
                result["results"]["optimization_plan"] = optimization_plan
                result["summary"] = f"性能分析完成，发现{len(optimization_plan.get('optimization_tasks', []))}个优化任务"
            
            elif strategy_name == "skill_generation":
                # 执行技能生成
                patterns = self.skill_generator.analyze_patterns_for_skill_creation(min_occurrences=2)
                
                generated_skills = []
                for pattern in patterns[:3]:  # 最多处理3个模式
                    skill_def = self.skill_generator.generate_skill_from_pattern(pattern)
                    if skill_def:
                        generated_skills.append({
                            "pattern": pattern.get("type"),
                            "skill_name": skill_def.name,
                            "description": skill_def.description,
                        })
                
                result["actions_executed"].append("analyze_patterns")
                result["actions_executed"].append("generate_skills")
                result["results"]["patterns_found"] = len(patterns)
                result["results"]["skills_generated"] = generated_skills
                result["summary"] = f"发现{len(patterns)}个模式，生成{len(generated_skills)}个技能"
            
            elif strategy_name == "knowledge_extraction":
                # 执行知识提取
                # 这里需要实际的交互数据，使用模拟数据
                mock_interaction = {
                    "user_query": "如何创建一个新的技能？",
                    "system_response": "要创建新技能，需要定义技能名称、描述和实现函数。",
                    "tool_results": [],
                }
                
                knowledge_items = self.knowledge_expander.extract_knowledge_from_interaction(mock_interaction)
                integration_result = self.knowledge_expander.integrate_knowledge(knowledge_items)
                
                result["actions_executed"].append("extract_knowledge")
                result["actions_executed"].append("integrate_knowledge")
                result["results"]["knowledge_items"] = len(knowledge_items)
                result["results"]["integration_result"] = integration_result
                result["summary"] = f"提取{len(knowledge_items)}个知识项，集成{integration_result.get('memories_added', 0)}个记忆"
            
            elif strategy_name == "terminology_learning":
                # 执行术语学习
                # 这里简化处理
                result["actions_executed"].append("extract_terms")
                result["actions_executed"].append("standardize_terminology")
                result["summary"] = "术语学习策略执行完成"
        
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["summary"] = f"策略执行失败: {str(e)}"
        
        return result
    
    def _update_strategy_effectiveness(self, strategy_name: str, result: Dict[str, Any]) -> None:
        """更新策略效果评估"""
        if strategy_name not in self.learning_strategies:
            return
        
        strategy = self.learning_strategies[strategy_name]
        
        # 根据执行结果调整效果评分
        if result.get("success", False):
            # 成功执行，稍微提高效果评分
            current_effectiveness = strategy.get("effectiveness", 0.5)
            new_effectiveness = min(1.0, current_effectiveness + 0.01)
            strategy["effectiveness"] = new_effectiveness
        else:
            # 执行失败，稍微降低效果评分
            current_effectiveness = strategy.get("effectiveness", 0.5)
            new_effectiveness = max(0.0, current_effectiveness - 0.02)
            strategy["effectiveness"] = new_effectiveness
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """获取学习洞察"""
        if not self.learning_cycles:
            return {"message": "No learning cycles recorded yet."}
        
        # 分析学习效果
        successful_cycles = [c for c in self.learning_cycles if any(
            r.get("success", False) for r in c.get("results", [])
        )]
        
        # 分析策略使用情况
        strategy_usage = {}
        for strategy_name, strategy in self.learning_strategies.items():
            strategy_usage[strategy_name] = {
                "usage_count": strategy.get("usage_count", 0),
                "effectiveness": strategy.get("effectiveness", 0),
                "priority": strategy.get("priority", 99),
            }
        
        # 提取学习趋势
        recent_cycles = self.learning_cycles[-10:] if len(self.learning_cycles) >= 10 else self.learning_cycles
        recent_success_rate = len([
            c for c in recent_cycles if any(
                r.get("success", False) for r in c.get("results", [])
            )
        ]) / max(len(recent_cycles), 1)
        
        return {
            "total_learning_cycles": len(self.learning_cycles),
            "successful_cycles": len(successful_cycles),
            "overall_success_rate": len(successful_cycles) / max(len(self.learning_cycles), 1),
            "recent_success_rate": recent_success_rate,
            "strategy_usage": strategy_usage,
            "most_used_strategy": max(
                strategy_usage.items(),
                key=lambda x: x[1]["usage_count"],
                default=("none", {"usage_count": 0})
            )[0],
            "most_effective_strategy": max(
                strategy_usage.items(),
                key=lambda x: x[1]["effectiveness"],
                default=("none", {"effectiveness": 0})
            )[0],
        }


# ---------------------------------------------------------------------------
# 自举系统主类
# ---------------------------------------------------------------------------

class BootstrapSystem:
    """自举系统主类"""
    
    def __init__(
        self,
        memory_manager: AdvancedMemoryManager,
        skill_engine: SkillEngine,
        terminology_governance: Optional[TerminologyGovernanceSystem] = None,
    ):
        self.memory_manager = memory_manager
        self.skill_engine = skill_engine
        self.terminology_governance = terminology_governance
        
        # 初始化各个组件
        self.performance_analyzer = PerformanceAnalyzer(memory_manager)
        self.skill_generator = SkillGenerator(memory_manager, skill_engine)
        self.knowledge_expander = KnowledgeExpander(memory_manager)
        self.meta_learning_coordinator = MetaLearningCoordinator(
            memory_manager,
            skill_engine,
            self.performance_analyzer,
            self.skill_generator,
            self.knowledge_expander,
        )
        
        # 自举记录
        self.bootstrap_records: List[BootstrapRecord] = []
        self._load_bootstrap_records()
    
    def _load_bootstrap_records(self) -> None:
        """加载自举记录"""
        records_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "bootstrap_records.json"
        
        if not records_file.exists():
            return
        
        try:
            data = json.loads(records_file.read_text(encoding="utf-8"))
            for record_data in data.get("records", []):
                record = BootstrapRecord.from_dict(record_data)
                self.bootstrap_records.append(record)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading bootstrap records: {e}")
    
    def _save_bootstrap_records(self) -> None:
        """保存自举记录"""
        records_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "bootstrap_records.json"
        records_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "last_updated": time.time(),
            "total_records": len(self.bootstrap_records),
            "records": [record.to_dict() for record in self.bootstrap_records[-100:]],  # 保存最近100条
        }
        
        records_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def execute_bootstrap_cycle(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行自举周期"""
        context = context or {}
        
        # 创建自举记录
        record_id = f"boot-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        record = BootstrapRecord(
            id=record_id,
            phase=BootstrapPhase.INITIALIZATION,
            improvement_type=ImprovementType.PERFORMANCE,
            description="执行自举周期",
            input_data=context,
            timestamp=time.time(),
        )
        
        try:
            # 阶段1: 观察和分析
            record.phase = BootstrapPhase.OBSERVATION
            
            # 分析当前状态
            perf_analysis = self.performance_analyzer.analyze_skill_performance(self.skill_engine)
            memory_analysis = self.performance_analyzer.analyze_memory_usage()
            
            record.analysis_results = {
                "performance_analysis": perf_analysis,
                "memory_analysis": memory_analysis,
            }
            
            # 阶段2: 生成改进
            record.phase = BootstrapPhase.GENERATION
            
            # 生成优化计划
            optimization_plan = self.performance_analyzer.generate_optimization_plan()
            
            # 分析模式以生成新技能
            patterns = self.skill_generator.analyze_patterns_for_skill_creation(min_occurrences=2)
            
            record.generated_artifacts = [
                {
                    "type": "optimization_plan",
                    "content": optimization_plan,
                },
                {
                    "type": "skill_patterns",
                    "content": {"patterns_found": len(patterns)},
                },
            ]
            
            # 阶段3: 集成和验证
            record.phase = BootstrapPhase.INTEGRATION
            
            # 执行元学习
            learning_result = self.meta_learning_coordinator.monitor_and_learn(context)
            
            record.integration_results = {
                "meta_learning": learning_result,
            }
            
            # 阶段4: 评估
            record.phase = BootstrapPhase.VALIDATION
            
            # 计算指标
            record.metrics = {
                "performance_issues": len(perf_analysis.get("issues", [])),
                "optimization_tasks": len(optimization_plan.get("optimization_tasks", [])),
                "patterns_found": len(patterns),
                "learning_strategies_applied": learning_result.get("strategies_applied", 0),
            }
            
            record.success = True
            record.confidence = 0.8
            
            # 添加记录
            self.bootstrap_records.append(record)
            
            # 保存记录
            self._save_bootstrap_records()
            
            return {
                "status": "success",
                "bootstrap_id": record_id,
                "phases_completed": ["observation", "generation", "integration", "validation"],
                "metrics": record.metrics,
                "record_id": record_id,
            }
        
        except Exception as e:
            record.phase = BootstrapPhase.VALIDATION
            record.success = False
            record.error_message = str(e)
            record.confidence = 0.0
            
            # 添加失败的记录
            self.bootstrap_records.append(record)
            self._save_bootstrap_records()
            
            return {
                "status": "error",
                "bootstrap_id": record_id,
                "error": str(e),
                "record_id": record_id,
            }
    
    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """获取自举统计信息"""
        if not self.bootstrap_records:
            return {"message": "No bootstrap records available."}
        
        successful = [r for r in self.bootstrap_records if r.success]
        failed = [r for r in self.bootstrap_records if not r.success]
        
        # 按改进类型统计
        by_improvement_type = {}
        for record in self.bootstrap_records:
            imp_type = record.improvement_type.value
            if imp_type not in by_improvement_type:
                by_improvement_type[imp_type] = 0
            by_improvement_type[imp_type] += 1
        
        # 按阶段统计
        by_phase = {}
        for record in self.bootstrap_records:
            phase = record.phase.value
            if phase not in by_phase:
                by_phase[phase] = 0
            by_phase[phase] += 1
        
        # 计算平均置信度
        avg_confidence = statistics.mean([r.confidence for r in self.bootstrap_records]) if self.bootstrap_records else 0
        
        return {
            "total_records": len(self.bootstrap_records),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / max(len(self.bootstrap_records), 1),
            "by_improvement_type": by_improvement_type,
            "by_phase": by_phase,
            "avg_confidence": avg_confidence,
            "most_recent": self.bootstrap_records[-1].to_dict() if self.bootstrap_records else None,
        }
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """获取学习洞察"""
        return self.meta_learning_coordinator.get_learning_insights()
    
    def generate_bootstrap_report(self) -> str:
        """生成自举报告"""
        stats = self.get_bootstrap_stats()
        learning_insights = self.get_learning_insights()
        
        report_lines = [
            "# Bootstrap System Report",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Overview",
            f"- Total bootstrap cycles: {stats.get('total_records', 0)}",
            f"- Success rate: {stats.get('success_rate', 0):.1%}",
            f"- Average confidence: {stats.get('avg_confidence', 0):.1%}",
            "",
            "## By Improvement Type",
        ]
        
        for imp_type, count in stats.get("by_improvement_type", {}).items():
            report_lines.append(f"- {imp_type}: {count}")
        
        report_lines.extend([
            "",
            "## Learning Insights",
            f"- Total learning cycles: {learning_insights.get('total_learning_cycles', 0)}",
            f"- Overall success rate: {learning_insights.get('overall_success_rate', 0):.1%}",
            f"- Recent success rate: {learning_insights.get('recent_success_rate', 0):.1%}",
            f"- Most used strategy: {learning_insights.get('most_used_strategy', 'none')}",
            f"- Most effective strategy: {learning_insights.get('most_effective_strategy', 'none')}",
            "",
            "## Recommendations",
        ])
        
        # 基于分析生成建议
        if stats.get("success_rate", 0) < 0.7:
            report_lines.append("- Focus on improving bootstrap success rate by addressing common failure points")
        
        if learning_insights.get("recent_success_rate", 0) < 0.5:
            report_lines.append("- Recent learning effectiveness has decreased, consider adjusting learning strategies")
        
        # 添加优化建议
        report_lines.extend([
            "- Continue regular bootstrap cycles to maintain system improvement",
            "- Monitor performance metrics to identify new optimization opportunities",
            "- Expand knowledge extraction from user interactions",
        ])
        
        return "\n".join(report_lines)


# ---------------------------------------------------------------------------
# 集成函数
# ---------------------------------------------------------------------------

def create_bootstrap_system(
    memory_manager: AdvancedMemoryManager,
    skill_engine: SkillEngine,
    terminology_governance: Optional[TerminologyGovernanceSystem] = None,
) -> BootstrapSystem:
    """创建自举系统"""
    return BootstrapSystem(memory_manager, skill_engine, terminology_governance)

def integrate_bootstrap_with_main_loop(
    bootstrap_system: BootstrapSystem,
    interval_minutes: int = 60,
) -> Dict[str, Any]:
    """将自举系统集成到主循环中（模拟）"""
    # 这里返回模拟的集成结果
    # 实际应用中，应该创建一个定时任务来定期执行自举周期
    
    return {
        "status": "integrated",
        "interval_minutes": interval_minutes,
        "next_scheduled": time.time() + (interval_minutes * 60),
        "message": f"Bootstrap system scheduled to run every {interval_minutes} minutes",
    }

def execute_manual_bootstrap(
    memory_manager: AdvancedMemoryManager,
    skill_engine: SkillEngine,
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """手动执行自举"""
    bootstrap_system = BootstrapSystem(memory_manager, skill_engine)
    return bootstrap_system.execute_bootstrap_cycle(context)
"""术语治理系统。

基于参考仓库的terminology-governance技能，实现术语的定义、管理、
一致性检查和标准化功能。
"""

from __future__ import annotations

import re
import json
import time
import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

from astrid.advanced_memory import AdvancedMemoryManager, TerminologyEntry, MemoryScope, MemoryType


# ---------------------------------------------------------------------------
# 术语治理状态
# ---------------------------------------------------------------------------

class TerminologyStatus(str, Enum):
    """术语状态"""
    DRAFT = "draft"          # 草案
    REVIEW = "review"        # 审核中
    APPROVED = "approved"    # 已批准
    DEPRECATED = "deprecated"  # 已弃用
    ARCHIVED = "archived"    # 已归档

class ConsistencyLevel(str, Enum):
    """一致性级别"""
    STRICT = "strict"        # 严格一致性
    MODERATE = "moderate"    # 适度一致性
    FLEXIBLE = "flexible"    # 灵活一致性


# ---------------------------------------------------------------------------
# 术语版本
# ---------------------------------------------------------------------------

@dataclass
class TerminologyVersion:
    """术语版本"""
    version: str
    term: str
    definition: str
    author: str
    created_at: float = field(default_factory=time.time)
    change_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "term": self.term,
            "definition": self.definition,
            "author": self.author,
            "created_at": self.created_at,
            "change_reason": self.change_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerminologyVersion":
        """从字典创建"""
        return cls(
            version=data["version"],
            term=data["term"],
            definition=data["definition"],
            author=data.get("author", ""),
            created_at=data.get("created_at", time.time()),
            change_reason=data.get("change_reason", ""),
        )


# ---------------------------------------------------------------------------
# 治理策略
# ---------------------------------------------------------------------------

@dataclass
class GovernancePolicy:
    """治理策略"""
    name: str
    description: str
    
    # 一致性规则
    consistency_level: ConsistencyLevel = ConsistencyLevel.MODERATE
    require_approval: bool = True
    min_reviewers: int = 1
    version_control: bool = True
    
    # 命名规则
    naming_patterns: List[str] = field(default_factory=list)
    prohibited_terms: List[str] = field(default_factory=list)
    
    # 生命周期
    review_period_days: int = 7
    archive_after_days: int = 365
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "consistency_level": self.consistency_level.value,
            "require_approval": self.require_approval,
            "min_reviewers": self.min_reviewers,
            "version_control": self.version_control,
            "naming_patterns": self.naming_patterns,
            "prohibited_terms": self.prohibited_terms,
            "review_period_days": self.review_period_days,
            "archive_after_days": self.archive_after_days,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GovernancePolicy":
        """从字典创建"""
        return cls(
            name=data["name"],
            description=data["description"],
            consistency_level=ConsistencyLevel(data.get("consistency_level", "moderate")),
            require_approval=data.get("require_approval", True),
            min_reviewers=data.get("min_reviewers", 1),
            version_control=data.get("version_control", True),
            naming_patterns=data.get("naming_patterns", []),
            prohibited_terms=data.get("prohibited_terms", []),
            review_period_days=data.get("review_period_days", 7),
            archive_after_days=data.get("archive_after_days", 365),
        )


# ---------------------------------------------------------------------------
# 一致性检查结果
# ---------------------------------------------------------------------------

@dataclass
class ConsistencyCheckResult:
    """一致性检查结果"""
    term: str
    checks: List[Dict[str, Any]]
    passed: bool
    score: float  # 0.0-1.0
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "term": self.term,
            "checks": self.checks,
            "passed": self.passed,
            "score": self.score,
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# 术语治理系统
# ---------------------------------------------------------------------------

class TerminologyGovernanceSystem:
    """术语治理系统"""
    
    def __init__(self, memory_manager: AdvancedMemoryManager):
        self.memory_manager = memory_manager
        self.policies: Dict[str, GovernancePolicy] = {}
        self.term_versions: Dict[str, List[TerminologyVersion]] = {}
        self.term_status: Dict[str, TerminologyStatus] = {}
        self.review_records: Dict[str, List[Dict[str, Any]]] = {}
        
        # 加载默认策略
        self._load_default_policies()
        self._load_existing_data()
    
    def _load_default_policies(self) -> None:
        """加载默认策略"""
        default_policies = [
            GovernancePolicy(
                name="technical-terminology",
                description="技术术语治理策略",
                consistency_level=ConsistencyLevel.STRICT,
                naming_patterns=[
                    r"^[a-z][a-z0-9]*([A-Z][a-z0-9]*)*$",  # camelCase
                    r"^[A-Z][a-z0-9]*([A-Z][a-z0-9]*)*$",  # PascalCase
                ],
                prohibited_terms=["tmp", "temp", "test", "dummy"],
            ),
            GovernancePolicy(
                name="business-terminology",
                description="业务术语治理策略",
                consistency_level=ConsistencyLevel.MODERATE,
                naming_patterns=[
                    r"^[A-Za-z\s]+$",  # 允许空格
                ],
            ),
            GovernancePolicy(
                name="general-terminology",
                description="通用术语治理策略",
                consistency_level=ConsistencyLevel.FLEXIBLE,
                require_approval=False,
            ),
        ]
        
        for policy in default_policies:
            self.policies[policy.name] = policy
    
    def _load_existing_data(self) -> None:
        """加载现有数据"""
        # 加载术语版本
        versions_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "term_versions.json"
        if versions_file.exists():
            try:
                data = json.loads(versions_file.read_text(encoding="utf-8"))
                for term, version_list in data.get("versions", {}).items():
                    self.term_versions[term] = [
                        TerminologyVersion.from_dict(v) for v in version_list
                    ]
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 加载术语状态
        status_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "term_status.json"
        if status_file.exists():
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
                for term, status_str in data.get("status", {}).items():
                    self.term_status[term] = TerminologyStatus(status_str)
            except (json.JSONDecodeError, KeyError):
                pass
    
    def _save_data(self) -> None:
        """保存数据"""
        # 保存术语版本
        versions_data = {
            "last_updated": time.time(),
            "versions": {
                term: [v.to_dict() for v in versions]
                for term, versions in self.term_versions.items()
            },
        }
        
        versions_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "term_versions.json"
        versions_file.parent.mkdir(parents=True, exist_ok=True)
        versions_file.write_text(
            json.dumps(versions_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        
        # 保存术语状态
        status_data = {
            "last_updated": time.time(),
            "status": {
                term: status.value
                for term, status in self.term_status.items()
            },
        }
        
        status_file = self.memory_manager._get_scope_path(MemoryScope.SYSTEM) / "term_status.json"
        status_file.write_text(
            json.dumps(status_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    # -----------------------------------------------------------------------
    # 策略管理
    # -----------------------------------------------------------------------
    
    def create_policy(self, policy: GovernancePolicy) -> None:
        """创建策略"""
        self.policies[policy.name] = policy
    
    def get_policy(self, name: str) -> Optional[GovernancePolicy]:
        """获取策略"""
        return self.policies.get(name)
    
    def get_applicable_policy(self, term: str, category: str = "general") -> GovernancePolicy:
        """获取适用的策略"""
        # 根据类别选择策略
        if category in self.policies:
            return self.policies[category]
        
        # 根据术语特征选择策略
        if re.match(r'^[A-Z]', term) and not ' ' in term:
            return self.policies.get("technical-terminology", self.policies["general-terminology"])
        elif ' ' in term:
            return self.policies.get("business-terminology", self.policies["general-terminology"])
        else:
            return self.policies["general-terminology"]
    
    # -----------------------------------------------------------------------
    # 术语生命周期管理
    # -----------------------------------------------------------------------
    
    def propose_term(
        self,
        term: str,
        definition: str,
        category: str = "general",
        author: str = "",
        aliases: List[str] = None,
        examples: List[str] = None,
        policy_name: str = None,
    ) -> Dict[str, Any]:
        """提议新术语"""
        # 获取适用策略
        policy = self.get_policy(policy_name) if policy_name else self.get_applicable_policy(term, category)
        
        # 检查术语是否已存在
        existing_term = self.memory_manager.get_term(term)
        if existing_term:
            return {
                "status": "exists",
                "term": term,
                "existing_definition": existing_term.definition,
                "message": "Term already exists",
            }
        
        # 执行一致性检查
        check_result = self.check_consistency(term, definition, policy)
        
        # 创建初始版本
        version = TerminologyVersion(
            version="1.0.0",
            term=term,
            definition=definition,
            author=author,
            change_reason="Initial proposal",
        )
        
        # 存储版本历史
        if term not in self.term_versions:
            self.term_versions[term] = []
        self.term_versions[term].append(version)
        
        # 设置初始状态
        if policy.require_approval:
            self.term_status[term] = TerminologyStatus.REVIEW
        else:
            self.term_status[term] = TerminologyStatus.APPROVED
            
            # 如果不需要审核，直接添加到记忆管理器
            self.memory_manager.define_term(
                term=term,
                definition=definition,
                category=category,
                aliases=aliases or [],
                examples=examples or [],
            )
        
        # 保存数据
        self._save_data()
        
        return {
            "status": "proposed",
            "term": term,
            "version": "1.0.0",
            "policy": policy.name,
            "requires_approval": policy.require_approval,
            "consistency_check": check_result.to_dict(),
            "current_status": self.term_status[term].value,
        }
    
    def approve_term(
        self,
        term: str,
        reviewer: str,
        comments: str = "",
        version: str = None,
    ) -> Dict[str, Any]:
        """批准术语"""
        if term not in self.term_status:
            return {
                "status": "error",
                "term": term,
                "message": "Term not found",
            }
        
        current_status = self.term_status[term]
        if current_status != TerminologyStatus.REVIEW:
            return {
                "status": "error",
                "term": term,
                "current_status": current_status.value,
                "message": f"Term is not in review status: {current_status.value}",
            }
        
        # 更新状态
        self.term_status[term] = TerminologyStatus.APPROVED
        
        # 记录审核
        if term not in self.review_records:
            self.review_records[term] = []
        
        self.review_records[term].append({
            "reviewer": reviewer,
            "action": "approve",
            "comments": comments,
            "timestamp": time.time(),
            "version": version or self._get_latest_version(term),
        })
        
        # 获取最新版本并添加到记忆管理器
        latest_version = self._get_latest_version_data(term)
        if latest_version:
            # 查找术语的完整信息（可能需要从其他地方获取）
            # 这里简化处理，实际应用中需要更完整的数据
            term_entry = TerminologyEntry(
                term=term,
                definition=latest_version["definition"],
                category="general",  # 需要从其他地方获取
                created_at=latest_version["created_at"],
            )
            self.memory_manager.terminology[term] = term_entry
            self.memory_manager._save_terminology()
        
        # 保存数据
        self._save_data()
        
        return {
            "status": "approved",
            "term": term,
            "reviewer": reviewer,
            "new_status": TerminologyStatus.APPROVED.value,
        }
    
    def update_term(
        self,
        term: str,
        new_definition: str,
        author: str,
        change_reason: str,
        version_increment: str = "minor",  # "major", "minor", "patch"
    ) -> Dict[str, Any]:
        """更新术语"""
        if term not in self.term_status:
            return {
                "status": "error",
                "term": term,
                "message": "Term not found",
            }
        
        # 获取当前版本
        current_versions = self.term_versions.get(term, [])
        if not current_versions:
            return {
                "status": "error",
                "term": term,
                "message": "No version history found",
            }
        
        latest_version = current_versions[-1]
        
        # 计算新版本号
        new_version = self._increment_version(
            latest_version.version,
            version_increment
        )
        
        # 创建新版本
        new_version_obj = TerminologyVersion(
            version=new_version,
            term=term,
            definition=new_definition,
            author=author,
            created_at=time.time(),
            change_reason=change_reason,
        )
        
        # 添加到版本历史
        self.term_versions[term].append(new_version_obj)
        
        # 更新状态为需要审核（如果之前是已批准）
        if self.term_status[term] == TerminologyStatus.APPROVED:
            self.term_status[term] = TerminologyStatus.REVIEW
        
        # 保存数据
        self._save_data()
        
        return {
            "status": "updated",
            "term": term,
            "old_version": latest_version.version,
            "new_version": new_version,
            "new_status": self.term_status[term].value,
            "change_reason": change_reason,
        }
    
    def deprecate_term(self, term: str, reason: str, deprecated_by: str) -> Dict[str, Any]:
        """弃用术语"""
        if term not in self.term_status:
            return {
                "status": "error",
                "term": term,
                "message": "Term not found",
            }
        
        # 更新状态
        self.term_status[term] = TerminologyStatus.DEPRECATED
        
        # 记录弃用原因
        if term not in self.review_records:
            self.review_records[term] = []
        
        self.review_records[term].append({
            "reviewer": deprecated_by,
            "action": "deprecate",
            "comments": reason,
            "timestamp": time.time(),
        })
        
        # 保存数据
        self._save_data()
        
        return {
            "status": "deprecated",
            "term": term,
            "reason": reason,
            "deprecated_by": deprecated_by,
            "new_status": TerminologyStatus.DEPRECATED.value,
        }
    
    # -----------------------------------------------------------------------
    # 一致性检查
    # -----------------------------------------------------------------------
    
    def check_consistency(
        self,
        term: str,
        definition: str,
        policy: GovernancePolicy,
    ) -> ConsistencyCheckResult:
        """检查一致性"""
        checks = []
        passed_checks = 0
        total_checks = 0
        
        # 1. 命名模式检查
        if policy.naming_patterns:
            total_checks += 1
            naming_passed = False
            for pattern in policy.naming_patterns:
                if re.match(pattern, term):
                    naming_passed = True
                    break
            
            checks.append({
                "check": "naming_pattern",
                "passed": naming_passed,
                "patterns": policy.naming_patterns,
            })
            
            if naming_passed:
                passed_checks += 1
        
        # 2. 禁止术语检查
        if policy.prohibited_terms:
            total_checks += 1
            prohibited_passed = True
            prohibited_found = []
            
            for prohibited in policy.prohibited_terms:
                if prohibited.lower() in term.lower():
                    prohibited_passed = False
                    prohibited_found.append(prohibited)
            
            checks.append({
                "check": "prohibited_terms",
                "passed": prohibited_passed,
                "found": prohibited_found,
            })
            
            if prohibited_passed:
                passed_checks += 1
        
        # 3. 定义长度检查
        total_checks += 1
        definition_length = len(definition.strip())
        length_passed = 10 <= definition_length <= 1000
        
        checks.append({
            "check": "definition_length",
            "passed": length_passed,
            "length": definition_length,
            "min": 10,
            "max": 1000,
        })
        
        if length_passed:
            passed_checks += 1
        
        # 4. 术语唯一性检查（简化）
        total_checks += 1
        uniqueness_passed = True
        
        # 检查相似术语
        similar_terms = self.find_similar_terms(term, threshold=0.7)
        if similar_terms:
            uniqueness_passed = False
        
        checks.append({
            "check": "term_uniqueness",
            "passed": uniqueness_passed,
            "similar_terms": similar_terms,
        })
        
        if uniqueness_passed:
            passed_checks += 1
        
        # 计算得分
        score = passed_checks / total_checks if total_checks > 0 else 1.0
        passed = score >= self._get_passing_threshold(policy.consistency_level)
        
        # 生成建议
        recommendations = self._generate_recommendations(checks, policy)
        
        return ConsistencyCheckResult(
            term=term,
            checks=checks,
            passed=passed,
            score=score,
            recommendations=recommendations,
        )
    
    def find_similar_terms(self, term: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """查找相似术语"""
        similar = []
        
        for existing_term in self.memory_manager.terminology.keys():
            similarity = difflib.SequenceMatcher(
                None,
                term.lower(),
                existing_term.lower()
            ).ratio()
            
            if similarity >= threshold and term.lower() != existing_term.lower():
                similar.append({
                    "term": existing_term,
                    "similarity": similarity,
                    "definition": self.memory_manager.terminology[existing_term].definition[:100],
                })
        
        # 按相似度排序
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similar[:5]  # 返回前5个最相似的
    
    # -----------------------------------------------------------------------
    # 查询和分析
    # -----------------------------------------------------------------------
    
    def get_term_history(self, term: str) -> List[TerminologyVersion]:
        """获取术语历史"""
        return self.term_versions.get(term, [])
    
    def get_term_status(self, term: str) -> Optional[TerminologyStatus]:
        """获取术语状态"""
        return self.term_status.get(term)
    
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """获取待审核的术语"""
        pending = []
        
        for term, status in self.term_status.items():
            if status == TerminologyStatus.REVIEW:
                versions = self.term_versions.get(term, [])
                latest_version = versions[-1] if versions else None
                
                pending.append({
                    "term": term,
                    "status": status.value,
                    "latest_version": latest_version.version if latest_version else "unknown",
                    "definition": latest_version.definition if latest_version else "",
                    "proposed_by": latest_version.author if latest_version else "",
                    "proposed_at": latest_version.created_at if latest_version else 0,
                })
        
        # 按提议时间排序
        pending.sort(key=lambda x: x["proposed_at"], reverse=True)
        
        return pending
    
    def get_deprecated_terms(self) -> List[Dict[str, Any]]:
        """获取已弃用的术语"""
        deprecated = []
        
        for term, status in self.term_status.items():
            if status == TerminologyStatus.DEPRECATED:
                versions = self.term_versions.get(term, [])
                latest_version = versions[-1] if versions else None
                
                deprecated.append({
                    "term": term,
                    "status": status.value,
                    "latest_version": latest_version.version if latest_version else "unknown",
                    "definition": latest_version.definition if latest_version else "",
                    "last_updated": latest_version.created_at if latest_version else 0,
                })
        
        return deprecated
    
    def get_consistency_report(self) -> Dict[str, Any]:
        """获取一致性报告"""
        all_terms = list(self.memory_manager.terminology.keys())
        report = {
            "total_terms": len(all_terms),
            "by_status": {},
            "by_category": {},
            "consistency_scores": [],
        }
        
        # 按状态统计
        for term in all_terms:
            status = self.term_status.get(term, TerminologyStatus.APPROVED)
            status_key = status.value
            
            if status_key not in report["by_status"]:
                report["by_status"][status_key] = 0
            report["by_status"][status_key] += 1
        
        # 按类别统计
        for term, entry in self.memory_manager.terminology.items():
            category = entry.category or "unknown"
            
            if category not in report["by_category"]:
                report["by_category"][category] = 0
            report["by_category"][category] += 1
        
        # 计算一致性得分（简化）
        if all_terms:
            # 检查命名一致性
            naming_consistent = 0
            for term in all_terms:
                if re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', term):
                    naming_consistent += 1
            
            report["naming_consistency"] = naming_consistent / len(all_terms)
        
        return report
    
    # -----------------------------------------------------------------------
    # 辅助方法
    # -----------------------------------------------------------------------
    
    def _get_latest_version(self, term: str) -> Optional[str]:
        """获取最新版本号"""
        versions = self.term_versions.get(term, [])
        return versions[-1].version if versions else None
    
    def _get_latest_version_data(self, term: str) -> Optional[Dict[str, Any]]:
        """获取最新版本数据"""
        versions = self.term_versions.get(term, [])
        return versions[-1].to_dict() if versions else None
    
    def _increment_version(self, current_version: str, increment_type: str) -> str:
        """递增版本号"""
        try:
            major, minor, patch = map(int, current_version.split('.'))
            
            if increment_type == "major":
                return f"{major + 1}.0.0"
            elif increment_type == "minor":
                return f"{major}.{minor + 1}.0"
            else:  # patch
                return f"{major}.{minor}.{patch + 1}"
        except (ValueError, AttributeError):
            # 如果版本号格式不正确，返回初始版本
            return "1.0.0"
    
    def _get_passing_threshold(self, consistency_level: ConsistencyLevel) -> float:
        """获取通过阈值"""
        thresholds = {
            ConsistencyLevel.STRICT: 0.9,
            ConsistencyLevel.MODERATE: 0.7,
            ConsistencyLevel.FLEXIBLE: 0.5,
        }
        return thresholds.get(consistency_level, 0.7)
    
    def _generate_recommendations(
        self,
        checks: List[Dict[str, Any]],
        policy: GovernancePolicy,
    ) -> List[str]:
        """生成建议"""
        recommendations = []
        
        for check in checks:
            if not check["passed"]:
                check_name = check["check"]
                
                if check_name == "naming_pattern":
                    recommendations.append(
                        f"术语命名不符合模式要求。请参考以下模式：{', '.join(check['patterns'])}"
                    )
                
                elif check_name == "prohibited_terms":
                    recommendations.append(
                        f"术语包含禁止的词汇：{', '.join(check['found'])}"
                    )
                
                elif check_name == "definition_length":
                    length = check["length"]
                    if length < check["min"]:
                        recommendations.append(
                            f"定义太短（{length}字符）。建议至少{check['min']}字符。"
                        )
                    else:
                        recommendations.append(
                            f"定义太长（{length}字符）。建议不超过{check['max']}字符。"
                        )
                
                elif check_name == "term_uniqueness":
                    similar = check["similar_terms"]
                    if similar:
                        recommendations.append(
                            f"存在相似术语：{', '.join(s['term'] for s in similar[:3])}"
                        )
        
        # 根据策略级别添加额外建议
        if policy.consistency_level == ConsistencyLevel.STRICT:
            recommendations.append("严格一致性模式下，请确保所有检查都通过。")
        
        return recommendations


# ---------------------------------------------------------------------------
# 集成函数
# ---------------------------------------------------------------------------

def create_terminology_governance_system(
    memory_manager: AdvancedMemoryManager,
) -> TerminologyGovernanceSystem:
    """创建术语治理系统"""
    return TerminologyGovernanceSystem(memory_manager)

def check_and_resolve_terminology(
    text: str,
    governance_system: TerminologyGovernanceSystem,
    memory_manager: AdvancedMemoryManager,
) -> Dict[str, Any]:
    """检查并解析文本中的术语"""
    # 提取潜在的术语
    words = re.findall(r'\b[A-Z][a-zA-Z0-9]+\b', text)  # 首字母大写的单词
    potential_terms = list(set(words))
    
    resolved = {}
    unresolved = []
    
    for term in potential_terms:
        # 尝试获取术语定义
        term_entry = memory_manager.get_term(term)
        
        if term_entry:
            # 术语已定义
            resolved[term] = {
                "definition": term_entry.definition,
                "status": governance_system.get_term_status(term) or TerminologyStatus.APPROVED,
                "category": term_entry.category,
            }
        else:
            # 术语未定义
            unresolved.append(term)
    
    # 检查未定义术语的相似性
    suggestions = {}
    for term in unresolved:
        similar = governance_system.find_similar_terms(term, threshold=0.6)
        if similar:
            suggestions[term] = similar[:3]
    
    return {
        "text_length": len(text),
        "potential_terms_found": len(potential_terms),
        "resolved_terms": len(resolved),
        "unresolved_terms": len(unresolved),
        "resolved": resolved,
        "unresolved": unresolved,
        "suggestions": suggestions,
    }

def export_terminology_glossary(
    governance_system: TerminologyGovernanceSystem,
    memory_manager: AdvancedMemoryManager,
    include_status: bool = True,
    include_history: bool = False,
) -> str:
    """导出术语表"""
    lines = ["# Terminology Glossary", ""]
    
    # 按类别分组
    by_category: Dict[str, List[Tuple[str, TerminologyEntry]]] = {}
    
    for term, entry in memory_manager.terminology.items():
        category = entry.category or "uncategorized"
        
        if category not in by_category:
            by_category[category] = []
        
        by_category[category].append((term, entry))
    
    # 生成术语表
    for category, terms in sorted(by_category.items()):
        lines.append(f"## {category.title()}")
        lines.append("")
        
        for term, entry in sorted(terms, key=lambda x: x[0].lower()):
            status = governance_system.get_term_status(term)
            
            line = f"**{term}**: {entry.definition}"
            
            if include_status and status:
                line += f" *({status.value})*"
            
            lines.append(f"- {line}")
            
            if include_history:
                history = governance_system.get_term_history(term)
                if history:
                    latest = history[-1]
                    lines.append(f"  - Latest version: {latest.version} by {latest.author}")
        
        lines.append("")
    
    return "\n".join(lines)

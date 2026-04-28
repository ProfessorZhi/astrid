#!/usr/bin/env python3
"""测试自举(self-bootstrapping)系统功能。

验证自举系统的各个组件：性能分析、技能生成、知识扩展和元学习。
"""

import sys
import os
import tempfile
import time
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from astrid.advanced_memory import create_memory_integration, AdvancedMemoryManager
from astrid.skill_engine import create_default_skill_engine, SkillEngine
from astrid.terminology_governance import create_terminology_governance_system
from astrid.bootstrap_system import (
    create_bootstrap_system,
    BootstrapSystem,
    PerformanceAnalyzer,
    SkillGenerator,
    KnowledgeExpander,
    MetaLearningCoordinator,
)


def test_performance_analyzer():
    """测试性能分析器"""
    print("=== 测试性能分析器 ===")
    
    # 创建内存管理器
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_mgr = create_memory_integration(workspace=tmpdir)
        
        # 创建技能引擎
        skill_engine = create_default_skill_engine(memory_mgr)
        
        # 创建性能分析器
        analyzer = PerformanceAnalyzer(memory_mgr)
        
        # 分析技能性能
        perf_analysis = analyzer.analyze_skill_performance(skill_engine)
        print(f"性能分析结果: {perf_analysis.get('total_executions', 0)} 次执行")
        print(f"成功率: {perf_analysis.get('success_rate', 0):.1%}")
        
        # 分析内存使用
        memory_analysis = analyzer.analyze_memory_usage()
        print(f"内存分析完成，发现 {len(memory_analysis.get('issues', []))} 个问题")
        
        # 识别瓶颈
        bottlenecks = analyzer.identify_bottlenecks()
        print(f"识别到 {len(bottlenecks)} 个性能瓶颈")
        
        # 生成优化计划
        optimization_plan = analyzer.generate_optimization_plan()
        print(f"生成优化计划，包含 {len(optimization_plan.get('optimization_tasks', []))} 个任务")
        
        # 验证数据结构
        assert isinstance(perf_analysis, dict)
        assert isinstance(memory_analysis, dict)
        assert isinstance(bottlenecks, list)
        assert isinstance(optimization_plan, dict)
        
        print("✅ 性能分析器测试通过\n")


def test_skill_generator():
    """测试技能生成器"""
    print("=== 测试技能生成器 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_mgr = create_memory_integration(workspace=tmpdir)
        skill_engine = create_default_skill_engine(memory_mgr)
        
        # 创建技能生成器
        generator = SkillGenerator(memory_mgr, skill_engine)
        
        # 分析模式以创建技能
        patterns = generator.analyze_patterns_for_skill_creation(min_occurrences=1)
        print(f"分析到 {len(patterns)} 个潜在技能模式")
        
        # 从模式生成技能
        generated_skills = []
        for pattern in patterns[:2]:  # 测试前2个模式
            skill_def = generator.generate_skill_from_pattern(pattern)
            if skill_def:
                generated_skills.append(skill_def)
                print(f"生成技能: {skill_def.name} - {skill_def.description}")
        
        # 验证技能生成
        if generated_skills:
            for skill_def in generated_skills:
                assert skill_def.name, "技能必须有名称"
                assert skill_def.description, "技能必须有描述"
                assert isinstance(skill_def.dependencies, list)
                assert isinstance(skill_def.capabilities, list)
        
        print(f"✅ 技能生成器测试通过，生成 {len(generated_skills)} 个技能\n")


def test_knowledge_expander():
    """测试知识扩展器"""
    print("=== 测试知识扩展器 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_mgr = create_memory_integration(workspace=tmpdir)
        
        # 创建知识扩展器
        expander = KnowledgeExpander(memory_mgr)
        
        # 模拟交互数据
        mock_interaction = {
            "user_query": "如何实现一个自举(self-bootstrapping)系统？需要哪些组件？",
            "system_response": "自举系统需要性能分析器、技能生成器、知识扩展器和元学习协调器。",
            "tool_results": [
                {
                    "tool": "code_analysis",
                    "success": True,
                    "result": "分析完成，发现3个优化点",
                }
            ],
        }
        
        # 提取知识
        knowledge_items = expander.extract_knowledge_from_interaction(mock_interaction)
        print(f"从交互中提取到 {len(knowledge_items)} 个知识项")
        
        # 显示提取的知识
        for i, item in enumerate(knowledge_items[:3], 1):
            print(f"  知识项 {i}: {item.get('type')} - {item.get('content', '')[:50]}...")
        
        # 集成知识
        integration_result = expander.integrate_knowledge(knowledge_items)
        print(f"知识集成结果: {integration_result.get('memories_added', 0)} 个记忆添加")
        
        # 验证数据结构
        assert isinstance(knowledge_items, list)
        assert isinstance(integration_result, dict)
        assert "memories_added" in integration_result
        
        print("✅ 知识扩展器测试通过\n")


def test_meta_learning_coordinator():
    """测试元学习协调器"""
    print("=== 测试元学习协调器 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_mgr = create_memory_integration(workspace=tmpdir)
        skill_engine = create_default_skill_engine(memory_mgr)
        
        # 创建其他组件
        analyzer = PerformanceAnalyzer(memory_mgr)
        generator = SkillGenerator(memory_mgr, skill_engine)
        expander = KnowledgeExpander(memory_mgr)
        
        # 创建元学习协调器
        coordinator = MetaLearningCoordinator(
            memory_mgr, skill_engine, analyzer, generator, expander
        )
        
        # 模拟上下文
        context = {
            "user_query": "测试自举系统功能",
            "timestamp": time.time(),
            "test_mode": True,
        }
        
        # 监控和学习
        learning_result = coordinator.monitor_and_learn(context)
        print(f"元学习结果: {learning_result.get('strategies_applied', 0)} 个策略应用")
        
        # 获取学习洞察
        insights = coordinator.get_learning_insights()
        print(f"学习洞察: {insights.get('total_learning_cycles', 0)} 个学习周期")
        
        # 验证数据结构
        assert isinstance(learning_result, dict)
        assert isinstance(insights, dict)
        assert "total_learning_cycles" in insights
        
        # 检查学习策略
        strategies = coordinator.learning_strategies
        print(f"可用学习策略: {len(strategies)} 个")
        for name, strategy in list(strategies.items())[:3]:
            print(f"  策略: {name} (优先级: {strategy.get('priority', 0)})")
        
        print("✅ 元学习协调器测试通过\n")


def test_bootstrap_system_integration():
    """测试自举系统集成"""
    print("=== 测试自举系统集成 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建所有组件
        memory_mgr = create_memory_integration(workspace=tmpdir)
        skill_engine = create_default_skill_engine(memory_mgr)
        terminology_governance = create_terminology_governance_system(memory_mgr)
        
        # 创建自举系统
        bootstrap_system = create_bootstrap_system(
            memory_mgr, skill_engine, terminology_governance
        )
        
        # 执行自举周期
        context = {
            "test_name": "bootstrap_integration_test",
            "timestamp": time.time(),
            "workspace": tmpdir,
        }
        
        result = bootstrap_system.execute_bootstrap_cycle(context)
        print(f"自举周期执行结果: {result.get('status', 'unknown')}")
        print(f"完成阶段: {', '.join(result.get('phases_completed', []))}")
        
        # 获取统计信息
        stats = bootstrap_system.get_bootstrap_stats()
        print(f"自举统计: {stats.get('total_records', 0)} 条记录")
        print(f"成功率: {stats.get('success_rate', 0):.1%}")
        
        # 获取学习洞察
        learning_insights = bootstrap_system.get_learning_insights()
        print(f"学习洞察: {learning_insights.get('overall_success_rate', 0):.1%} 总体成功率")
        
        # 生成报告
        report = bootstrap_system.generate_bootstrap_report()
        print(f"生成报告长度: {len(report)} 字符")
        
        # 验证结果
        assert result["status"] in ["success", "error"], "状态必须是success或error"
        assert isinstance(stats, dict)
        assert isinstance(learning_insights, dict)
        assert isinstance(report, str)
        assert len(report) > 100, "报告应该有一定长度"
        
        # 检查记录保存
        assert len(bootstrap_system.bootstrap_records) > 0, "应该有自举记录"
        
        print("✅ 自举系统集成测试通过\n")


def test_bootstrap_persistence():
    """测试自举系统持久化"""
    print("=== 测试自举系统持久化 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 第一次运行
        memory_mgr1 = create_memory_integration(workspace=tmpdir)
        skill_engine1 = create_default_skill_engine(memory_mgr1)
        bootstrap_system1 = create_bootstrap_system(memory_mgr1, skill_engine1)
        
        # 执行几次自举周期
        for i in range(3):
            context = {"cycle": i, "timestamp": time.time()}
            bootstrap_system1.execute_bootstrap_cycle(context)
        
        records_count1 = len(bootstrap_system1.bootstrap_records)
        print(f"第一次运行后记录数: {records_count1}")
        
        # 重新创建系统（模拟重启）
        memory_mgr2 = create_memory_integration(workspace=tmpdir)
        skill_engine2 = create_default_skill_engine(memory_mgr2)
        bootstrap_system2 = create_bootstrap_system(memory_mgr2, skill_engine2)
        
        records_count2 = len(bootstrap_system2.bootstrap_records)
        print(f"重新启动后记录数: {records_count2}")
        
        # 验证持久化（系统只保留最近100条记录）
        assert records_count2 >= min(records_count1, 100), "重新启动后应该加载之前保留下来的记录"
        
        # 检查记录完整性
        if bootstrap_system2.bootstrap_records:
            latest_record = bootstrap_system2.bootstrap_records[-1]
            assert latest_record.id, "记录必须有ID"
            assert latest_record.phase, "记录必须有阶段"
            assert latest_record.timestamp > 0, "记录必须有时间戳"
        
        print("✅ 自举系统持久化测试通过\n")


def test_comprehensive_bootstrap_workflow():
    """测试完整的自举工作流"""
    print("=== 测试完整的自举工作流 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 初始化所有组件
        memory_mgr = create_memory_integration(workspace=tmpdir)
        skill_engine = create_default_skill_engine(memory_mgr)
        terminology_governance = create_terminology_governance_system(memory_mgr)
        bootstrap_system = create_bootstrap_system(
            memory_mgr, skill_engine, terminology_governance
        )
        
        # 模拟多个交互周期
        test_scenarios = [
            {
                "name": "初始分析",
                "context": {"phase": "initial", "action": "system_analysis"},
            },
            {
                "name": "技能优化", 
                "context": {"phase": "optimization", "action": "skill_improvement"},
            },
            {
                "name": "知识整合",
                "context": {"phase": "integration", "action": "knowledge_consolidation"},
            },
        ]
        
        results = []
        for scenario in test_scenarios:
            print(f"执行场景: {scenario['name']}")
            result = bootstrap_system.execute_bootstrap_cycle(scenario["context"])
            results.append(result)
            print(f"  结果: {result.get('status')}")
            time.sleep(0.1)  # 短暂延迟
        
        # 验证总体结果
        successful = sum(1 for r in results if r.get("status") == "success")
        print(f"总体成功率: {successful}/{len(results)}")
        
        # 检查系统状态
        stats = bootstrap_system.get_bootstrap_stats()
        insights = bootstrap_system.get_learning_insights()
        
        print(f"最终统计: {stats.get('total_records', 0)} 条记录")
        print(f"学习洞察: {insights.get('recent_success_rate', 0):.1%} 近期成功率")
        
        # 验证系统改进
        assert stats["total_records"] >= len(test_scenarios), "应该有足够的记录"
        assert successful > 0, "至少应该有一些成功的周期"
        
        print("✅ 完整自举工作流测试通过\n")


def main():
    """运行所有测试"""
    print("开始测试自举(self-bootstrapping)系统...\n")
    
    tests = [
        ("性能分析器", test_performance_analyzer),
        ("技能生成器", test_skill_generator),
        ("知识扩展器", test_knowledge_expander),
        ("元学习协调器", test_meta_learning_coordinator),
        ("自举系统集成", test_bootstrap_system_integration),
        ("持久化测试", test_bootstrap_persistence),
        ("完整工作流", test_comprehensive_bootstrap_workflow),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            success = True
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 总结结果
    print("\n" + "="*60)
    print("测试结果总结:")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:20} {status}")
    
    print("="*60)
    print(f"总体结果: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！自举系统功能完整。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

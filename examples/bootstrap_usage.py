#!/usr/bin/env python3
"""自举(self-bootstrapping)系统使用示例。

展示如何使用自举系统的各个功能组件。
"""

import sys
import os
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from astrid.state.advanced_memory import create_memory_integration
from astrid.skill_engine import create_default_skill_engine
from astrid.terminology_governance import create_terminology_governance_system
from astrid.bootstrap_system import (
    create_bootstrap_system,
    execute_manual_bootstrap,
    integrate_bootstrap_with_main_loop,
)


def example_basic_usage():
    """基本使用示例"""
    print("=== 自举系统基本使用示例 ===\n")
    
    # 1. 创建临时工作区
    with tempfile.TemporaryDirectory() as workspace:
        print(f"工作区: {workspace}")
        
        # 2. 初始化内存管理器
        print("1. 初始化内存管理器...")
        memory_mgr = create_memory_integration(workspace=workspace)
        
        # 3. 初始化技能引擎
        print("2. 初始化技能引擎...")
        skill_engine = create_default_skill_engine(memory_mgr)
        
        # 4. 初始化术语治理系统
        print("3. 初始化术语治理系统...")
        terminology_governance = create_terminology_governance_system(memory_mgr)
        
        # 5. 创建自举系统
        print("4. 创建自举系统...")
        bootstrap_system = create_bootstrap_system(
            memory_mgr, 
            skill_engine, 
            terminology_governance
        )
        
        print("✅ 系统初始化完成\n")
        return bootstrap_system


def example_execute_bootstrap_cycle(bootstrap_system):
    """执行自举周期示例"""
    print("=== 执行自举周期示例 ===\n")
    
    # 1. 执行自举周期
    print("1. 执行自举周期...")
    context = {
        "user_query": "如何优化系统性能？",
        "session_id": "example_session_001",
        "timestamp": time.time(),
    }
    
    result = bootstrap_system.execute_bootstrap_cycle(context)
    print(f"   结果: {result.get('status')}")
    print(f"   自举ID: {result.get('bootstrap_id')}")
    print(f"   完成阶段: {', '.join(result.get('phases_completed', []))}")
    
    # 2. 查看统计信息
    print("\n2. 查看统计信息...")
    stats = bootstrap_system.get_bootstrap_stats()
    print(f"   总记录数: {stats.get('total_records', 0)}")
    print(f"   成功率: {stats.get('success_rate', 0):.1%}")
    print(f"   平均置信度: {stats.get('avg_confidence', 0):.1%}")
    
    # 3. 查看改进类型分布
    print("\n3. 改进类型分布:")
    for imp_type, count in stats.get("by_improvement_type", {}).items():
        print(f"   {imp_type}: {count}")
    
    print("\n✅ 自举周期执行完成\n")


def example_manual_bootstrap():
    """手动执行自举示例"""
    print("=== 手动执行自举示例 ===\n")
    
    with tempfile.TemporaryDirectory() as workspace:
        # 使用便捷函数手动执行自举
        print("1. 使用便捷函数执行自举...")
        memory_mgr = create_memory_integration(workspace=workspace)
        skill_engine = create_default_skill_engine(memory_mgr)
        
        context = {
            "action": "manual_bootstrap_example",
            "description": "手动执行自举测试",
        }
        
        result = execute_manual_bootstrap(memory_mgr, skill_engine, context)
        print(f"   结果: {result.get('status')}")
        print(f"   自举ID: {result.get('bootstrap_id')}")
        
        print("\n✅ 手动自举执行完成\n")


def example_learning_insights(bootstrap_system):
    """学习洞察示例"""
    print("=== 学习洞察示例 ===\n")
    
    # 1. 获取学习洞察
    print("1. 获取学习洞察...")
    insights = bootstrap_system.get_learning_insights()
    
    print(f"   总学习周期: {insights.get('total_learning_cycles', 0)}")
    print(f"   总体成功率: {insights.get('overall_success_rate', 0):.1%}")
    print(f"   近期成功率: {insights.get('recent_success_rate', 0):.1%}")
    
    # 2. 查看策略使用情况
    print("\n2. 学习策略使用情况:")
    strategy_usage = insights.get("strategy_usage", {})
    for strategy_name, usage_info in strategy_usage.items():
        print(f"   {strategy_name}:")
        print(f"     使用次数: {usage_info.get('usage_count', 0)}")
        print(f"     效果评分: {usage_info.get('effectiveness', 0):.1%}")
    
    # 3. 最常用策略
    print(f"\n3. 最常用策略: {insights.get('most_used_strategy', 'none')}")
    print(f"   最有效策略: {insights.get('most_effective_strategy', 'none')}")
    
    print("\n✅ 学习洞察获取完成\n")


def example_generate_report(bootstrap_system):
    """生成报告示例"""
    print("=== 生成自举报告示例 ===\n")
    
    # 1. 生成报告
    print("1. 生成自举报告...")
    report = bootstrap_system.generate_bootstrap_report()
    
    # 显示报告摘要
    lines = report.split('\n')
    print("   报告摘要:")
    for line in lines[:20]:  # 显示前20行
        print(f"   {line}")
    
    if len(lines) > 20:
        print(f"   ... (总共 {len(lines)} 行)")
    
    # 2. 保存报告到文件
    print("\n2. 保存报告到文件...")
    report_file = Path("bootstrap_report.md")
    report_file.write_text(report, encoding="utf-8")
    print(f"   报告已保存到: {report_file.absolute()}")
    
    print("\n✅ 报告生成完成\n")


def example_integration_with_main_loop():
    """与主循环集成示例"""
    print("=== 与主循环集成示例 ===\n")
    
    # 1. 模拟集成到主循环
    print("1. 模拟集成到主循环...")
    integration_result = integrate_bootstrap_with_main_loop(
        bootstrap_system=None,  # 实际使用时传入真实的bootstrap_system
        interval_minutes=30
    )
    
    print(f"   集成状态: {integration_result.get('status')}")
    print(f"   执行间隔: {integration_result.get('interval_minutes')} 分钟")
    print(f"   下次执行: {time.ctime(integration_result.get('next_scheduled', 0))}")
    print(f"   消息: {integration_result.get('message')}")
    
    print("\n2. 集成说明:")
    print("""
   在实际应用中，应该将自举系统集成到主程序循环中：
   
   1. 在程序启动时初始化自举系统
   2. 定期执行自举周期（例如每30分钟）
   3. 根据自举结果优化系统行为
   4. 保存学习记录用于持续改进
   
   集成方式：
   - 使用 threading.Timer 定时执行
   - 在关键事件后触发自举（如完成重要任务）
   - 根据系统负载动态调整自举频率
   """)
    
    print("\n✅ 集成示例完成\n")


def example_advanced_usage_scenarios():
    """高级使用场景示例"""
    print("=== 高级使用场景示例 ===\n")
    
    print("1. 性能优化场景:")
    print("""
   当系统性能下降时，自举系统可以：
   - 分析技能执行性能数据
   - 识别瓶颈（高延迟、低成功率）
   - 生成优化建议（缓存、并行化）
   - 自动执行优化任务
   """)
    
    print("\n2. 技能生成场景:")
    print("""
   当发现重复模式时，自举系统可以：
   - 分析用户交互和工具使用模式
   - 识别频繁执行的技能序列
   - 自动生成新的组合技能
   - 验证新技能的有效性
   """)
    
    print("\n3. 知识扩展场景:")
    print("""
   在处理新领域时，自举系统可以：
   - 提取用户查询中的关键术语
   - 学习新的解决方案模式
   - 建立知识关联网络
   - 丰富系统知识库
   """)
    
    print("\n4. 元学习场景:")
    print("""
   在长期运行中，自举系统可以：
   - 评估不同学习策略的效果
   - 调整学习参数和频率
   - 发现最佳实践模式
   - 适应不同用户和任务类型
   """)
    
    print("\n✅ 高级场景示例完成\n")


def main():
    """运行所有示例"""
    print("🚀 自举(self-bootstrapping)系统使用示例\n")
    print("="*60 + "\n")
    
    try:
        # 示例1: 基本使用
        bootstrap_system = example_basic_usage()
        
        # 示例2: 执行自举周期
        example_execute_bootstrap_cycle(bootstrap_system)
        
        # 示例3: 手动执行自举
        example_manual_bootstrap()
        
        # 示例4: 学习洞察
        example_learning_insights(bootstrap_system)
        
        # 示例5: 生成报告
        example_generate_report(bootstrap_system)
        
        # 示例6: 与主循环集成
        example_integration_with_main_loop()
        
        # 示例7: 高级使用场景
        example_advanced_usage_scenarios()
        
        print("="*60)
        print("\n🎉 所有示例执行完成！")
        print("\n📋 总结:")
        print("""
        自举系统提供了以下核心功能：
        
        1. **自我改进**: 持续分析性能并优化
        2. **技能生成**: 从模式中创建新技能  
        3. **知识扩展**: 学习和整合新知识
        4. **元学习**: 优化学习策略本身
        5. **报告生成**: 提供改进洞察和建议
        
        集成到 Astrid 后，系统能够：
        - 自动适应不同项目和任务
        - 从使用经验中学习改进
        - 持续优化执行效率
        - 提供智能建议和自动化
        
        这使得 Astrid 成为一个真正能够自我改进的AI编程助手！
        """)
        
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
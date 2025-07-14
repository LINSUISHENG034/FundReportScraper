#!/usr/bin/env python3
"""
Celery Windows兼容性修复验证脚本

用途:
- 快速验证Celery在Windows环境下是否正常工作
- 检查Solo池配置是否有效
- 验证任务分发和执行功能
- 生成简要的健康检查报告

使用方法:
    python scripts/verification/verify_celery_windows_fix.py

作者: AI Assistant
创建时间: 2025-07-14
"""

import sys
import os
import time
import platform
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.core.celery_app import app
    from src.tasks.download_tasks import test_celery_task
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保在项目根目录下运行此脚本")
    sys.exit(1)

def print_header():
    """打印测试头部信息"""
    print("=" * 60)
    print("🔧 Celery Windows兼容性修复验证")
    print("=" * 60)
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 操作系统: {platform.system()} {platform.release()}")
    print(f"🐍 Python版本: {platform.python_version()}")
    print(f"📁 项目路径: {project_root}")
    print()

def check_environment():
    """检查环境配置"""
    print("🔍 环境检查")
    print("-" * 30)
    
    # 检查操作系统
    if platform.system() != 'Windows':
        print("⚠️  警告: 当前不是Windows环境")
    else:
        print("✅ Windows环境确认")
    
    # 检查Celery应用配置
    try:
        broker_url = app.conf.broker_url
        result_backend = app.conf.result_backend
        print(f"✅ Broker URL: {broker_url}")
        print(f"✅ Result Backend: {result_backend}")
    except Exception as e:
        print(f"❌ Celery配置错误: {e}")
        return False
    
    # 检查任务注册
    if 'src.tasks.download_tasks.test_celery_task' in app.tasks:
        print("✅ 测试任务已注册")
    else:
        print("❌ 测试任务未找到")
        return False
    
    print()
    return True

def test_task_execution():
    """测试任务执行"""
    print("🚀 任务执行测试")
    print("-" * 30)
    
    try:
        # 发送测试任务
        print("📤 发送测试任务...")
        start_time = time.time()
        result = test_celery_task.delay()
        print(f"✅ 任务已发送，ID: {result.id}")
        
        # 等待任务完成
        print("⏳ 等待任务完成...")
        task_result = result.get(timeout=30)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"✅ 任务执行成功!")
        print(f"⏱️  执行时间: {execution_time:.2f}秒")
        print(f"📋 任务结果: {task_result}")
        
        return True, execution_time, task_result
        
    except Exception as e:
        print(f"❌ 任务执行失败: {str(e)}")
        return False, 0, None

def test_multiple_tasks():
    """测试多任务并发"""
    print("\n🔄 多任务测试")
    print("-" * 30)
    
    task_count = 3
    results = []
    
    try:
        print(f"📤 发送 {task_count} 个并发任务...")
        start_time = time.time()
        
        # 发送多个任务
        async_results = []
        for i in range(task_count):
            result = test_celery_task.delay()
            async_results.append(result)
            print(f"  任务 {i+1}: {result.id}")
        
        # 等待所有任务完成
        print("⏳ 等待所有任务完成...")
        for i, result in enumerate(async_results):
            task_result = result.get(timeout=30)
            results.append(task_result)
            print(f"  ✅ 任务 {i+1} 完成")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"✅ 所有任务执行成功!")
        print(f"⏱️  总执行时间: {total_time:.2f}秒")
        print(f"📊 平均每任务: {total_time/task_count:.2f}秒")
        
        return True, total_time, results
        
    except Exception as e:
        print(f"❌ 多任务测试失败: {str(e)}")
        return False, 0, []

def check_worker_status():
    """检查Worker状态"""
    print("\n👷 Worker状态检查")
    print("-" * 30)
    
    try:
        # 检查活跃的workers
        inspect = app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            print("✅ 发现活跃的Workers:")
            for worker_name, worker_stats in stats.items():
                print(f"  📍 Worker: {worker_name}")
                print(f"    - 池类型: {worker_stats.get('pool', {}).get('implementation', 'unknown')}")
                print(f"    - 进程数: {worker_stats.get('pool', {}).get('processes', 'unknown')}")
                print(f"    - 最大并发: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')}")
            return True
        else:
            print("⚠️  未发现活跃的Workers")
            print("💡 提示: 请使用以下命令启动Worker:")
            print("   celery -A src.core.celery_app worker --pool=solo -l info")
            return False
            
    except Exception as e:
        print(f"❌ Worker状态检查失败: {str(e)}")
        return False

def generate_report(env_ok, task_ok, task_time, task_result, multi_ok, multi_time, multi_results, worker_ok):
    """生成测试报告"""
    print("\n📊 测试报告")
    print("=" * 60)
    
    # 计算总体状态
    total_tests = 4
    passed_tests = sum([env_ok, task_ok, multi_ok, worker_ok])
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"📈 总体状态: {passed_tests}/{total_tests} 通过 ({success_rate:.1f}%)")
    print()
    
    # 详细结果
    print("📋 详细结果:")
    print(f"  {'✅' if env_ok else '❌'} 环境检查: {'通过' if env_ok else '失败'}")
    print(f"  {'✅' if task_ok else '❌'} 单任务测试: {'通过' if task_ok else '失败'}")
    if task_ok:
        print(f"    ⏱️  执行时间: {task_time:.2f}秒")
    print(f"  {'✅' if multi_ok else '❌'} 多任务测试: {'通过' if multi_ok else '失败'}")
    if multi_ok:
        print(f"    ⏱️  总时间: {multi_time:.2f}秒")
        print(f"    📊 任务数: {len(multi_results)}")
    print(f"  {'✅' if worker_ok else '❌'} Worker状态: {'正常' if worker_ok else '异常'}")
    print()
    
    # 建议
    if success_rate == 100:
        print("🎉 恭喜! Celery Windows兼容性修复完全有效!")
        print("💡 建议: 继续使用当前配置")
    elif success_rate >= 75:
        print("⚠️  大部分功能正常，但存在一些问题")
        print("💡 建议: 检查失败的测试项并进行修复")
    else:
        print("❌ 存在严重问题，需要立即修复")
        print("💡 建议: 检查Celery配置和Worker状态")
    
    print()
    print("📚 相关文档:")
    print("  - docs/technical/celery_windows_compatibility_fix.md")
    print("  - docs/technical/celery_windows_fix_test_report.md")
    
    return success_rate

def main():
    """主函数"""
    print_header()
    
    # 环境检查
    env_ok = check_environment()
    if not env_ok:
        print("❌ 环境检查失败，无法继续测试")
        return 1
    
    # 单任务测试
    task_ok, task_time, task_result = test_task_execution()
    
    # 多任务测试
    multi_ok, multi_time, multi_results = test_multiple_tasks()
    
    # Worker状态检查
    worker_ok = check_worker_status()
    
    # 生成报告
    success_rate = generate_report(
        env_ok, task_ok, task_time, task_result, 
        multi_ok, multi_time, multi_results, worker_ok
    )
    
    # 返回适当的退出码
    return 0 if success_rate >= 75 else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生未预期的错误: {e}")
        sys.exit(1)
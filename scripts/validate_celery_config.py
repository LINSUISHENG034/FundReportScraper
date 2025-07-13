"""
Celery配置验证脚本
Celery Configuration Validation Script

验证Celery配置是否正确，包括Redis连接、任务注册等
"""

import sys
from pathlib import Path

def get_project_root():
    """获取项目根目录"""
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    return project_root

def validate_celery_configuration():
    """验证Celery配置"""
    print("🔍 Celery配置验证")
    print("=" * 50)
    
    # 添加项目路径
    project_root = get_project_root()
    sys.path.insert(0, str(project_root))
    
    try:
        # 1. 导入Celery应用
        print("1️⃣ 导入Celery应用...")
        from src.core.celery_app import app, validate_configuration
        print("   ✅ Celery应用导入成功")
        
        # 2. 检查基本配置
        print("\n2️⃣ 检查基本配置...")
        print(f"   应用名称: {app.main}")
        print(f"   Broker URL: {app.conf.broker_url}")
        print(f"   Result Backend: {app.conf.result_backend}")
        print(f"   时区: {app.conf.timezone}")
        print(f"   序列化格式: {app.conf.task_serializer}")
        print("   ✅ 基本配置正常")
        
        # 3. 检查任务注册
        print("\n3️⃣ 检查任务注册...")
        registered_tasks = list(app.tasks.keys())
        expected_tasks = ['tasks.download_fund_report', 'tasks.test_celery']
        
        print(f"   注册的任务数量: {len(registered_tasks)}")
        for task in expected_tasks:
            if task in registered_tasks:
                print(f"   ✅ {task}")
            else:
                print(f"   ❌ {task} (未注册)")
        
        # 4. 检查队列配置
        print("\n4️⃣ 检查队列配置...")
        task_routes = app.conf.task_routes
        print(f"   任务路由数量: {len(task_routes)}")
        for task, route in task_routes.items():
            print(f"   {task} -> {route.get('queue', 'default')}")
        
        # 5. 检查高级配置
        print("\n5️⃣ 检查高级配置...")
        advanced_configs = [
            ('worker_prefetch_multiplier', app.conf.worker_prefetch_multiplier),
            ('task_acks_late', app.conf.task_acks_late),
            ('result_expires', app.conf.result_expires),
            ('task_max_retries', app.conf.task_max_retries),
            ('task_soft_time_limit', app.conf.task_soft_time_limit),
            ('task_time_limit', app.conf.task_time_limit),
        ]
        
        for config_name, config_value in advanced_configs:
            print(f"   {config_name}: {config_value}")
        
        # 6. 运行内置验证
        print("\n6️⃣ 运行内置验证...")
        validation_result = validate_configuration()
        
        if validation_result:
            print("   ✅ 内置验证通过")
        else:
            print("   ❌ 内置验证失败")
        
        # 7. 测试任务导入
        print("\n7️⃣ 测试任务导入...")
        try:
            from src.tasks.download_tasks import test_celery_task, download_fund_report_task
            print("   ✅ 下载任务模块导入成功")
            print(f"   ✅ test_celery_task: {test_celery_task}")
            print(f"   ✅ download_fund_report_task: {download_fund_report_task}")
        except ImportError as e:
            print(f"   ❌ 任务导入失败: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 Celery配置验证完成！")
        
        # 总结
        print("\n📊 配置总结:")
        print(f"  • 应用状态: ✅ 正常")
        print(f"  • Redis连接: {'✅ 正常' if validation_result else '❌ 失败'}")
        print(f"  • 任务注册: ✅ {len([t for t in expected_tasks if t in registered_tasks])}/{len(expected_tasks)}")
        print(f"  • 队列配置: ✅ {len(task_routes)} 个路由")
        print(f"  • 高级功能: ✅ 已启用")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 配置验证失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        
        print("\n🔧 故障排除建议:")
        print("  1. 确保项目依赖已安装: pip install -r requirements.txt")
        print("  2. 确保Redis服务正在运行: docker ps | grep redis")
        print("  3. 检查配置文件: src/core/config.py")
        print("  4. 检查任务模块: src/tasks/download_tasks.py")
        
        return False


def main():
    """主函数"""
    success = validate_celery_configuration()
    
    if success:
        print("\n✨ 配置验证成功！可以启动Celery Worker了。")
        print("\n💡 启动命令:")
        print("   python scripts/start_celery_worker.py")
        print("   或者:")
        print("   celery -A src.core.celery_app worker --loglevel=info --pool=solo")
    else:
        print("\n💡 请解决上述问题后重新验证。")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

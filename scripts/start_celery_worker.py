"""
Celery Worker启动脚本
Celery Worker Startup Script

用于启动Celery Worker的便捷脚本，自动选择合适的执行池
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def get_project_root():
    """获取项目根目录"""
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    return project_root

def check_redis_connection():
    """检查Redis连接"""
    try:
        import redis
        sys.path.insert(0, str(get_project_root()))
        from src.core.config import settings
        
        redis_client = redis.from_url(settings.redis.url)
        redis_client.ping()
        print(f"✅ Redis连接正常: {settings.redis.url}")
        return True
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        print("请确保Redis服务正在运行:")
        print("  docker run -d -p 6379:6379 --name fund-redis redis:latest")
        return False

def start_celery_worker(pool_type="solo", concurrency=1, log_level="info", queues=None):
    """启动Celery Worker"""
    project_root = get_project_root()

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    # 构建命令
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "src.core.celery_app",
        "worker",
        f"--loglevel={log_level}",
        f"--pool={pool_type}"
    ]

    if pool_type != "solo":
        cmd.extend([f"--concurrency={concurrency}"])

    # 添加队列配置
    if queues:
        cmd.extend(["-Q", ",".join(queues)])
    else:
        # 默认监听所有队列
        cmd.extend(["-Q", "default,download"])

    print(f"🚀 启动Celery Worker...")
    print(f"   执行池: {pool_type}")
    print(f"   并发数: {concurrency if pool_type != 'solo' else '1 (solo模式)'}")
    print(f"   日志级别: {log_level}")
    print(f"   监听队列: {queues or ['default', 'download']}")
    print(f"   工作目录: {project_root}")
    print(f"   命令: {' '.join(cmd)}")
    print("-" * 60)

    try:
        # 启动Worker
        subprocess.run(cmd, cwd=project_root, env=env)
    except KeyboardInterrupt:
        print("\n🛑 Celery Worker已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def main():
    """主函数"""
    print("🔧 Celery Worker启动器")
    print("=" * 60)
    
    # 检查Redis连接
    if not check_redis_connection():
        return 1
    
    # 根据平台选择合适的执行池
    system = platform.system()
    print(f"🖥️  检测到系统: {system}")
    
    if system == "Windows":
        print("💡 Windows系统建议使用solo或threads执行池")
        pool_type = "solo"  # Windows上最稳定
    else:
        print("💡 Unix系统可以使用prefork执行池")
        pool_type = "prefork"
    
    # 询问用户选择
    print(f"\n📋 可用的执行池选项:")
    print("  1. solo - 单进程模式 (Windows推荐)")
    print("  2. threads - 线程模式")
    print("  3. prefork - 多进程模式 (Unix推荐)")
    
    try:
        choice = input(f"\n请选择执行池 (默认: {pool_type}): ").strip()
        
        if choice == "1" or choice.lower() == "solo":
            pool_type = "solo"
        elif choice == "2" or choice.lower() == "threads":
            pool_type = "threads"
        elif choice == "3" or choice.lower() == "prefork":
            pool_type = "prefork"
        elif choice == "":
            pass  # 使用默认值
        else:
            print(f"使用默认执行池: {pool_type}")
        
        # 设置并发数
        concurrency = 1
        if pool_type != "solo":
            try:
                concurrency_input = input("请输入并发数 (默认: 2): ").strip()
                if concurrency_input:
                    concurrency = int(concurrency_input)
                else:
                    concurrency = 2
            except ValueError:
                concurrency = 2
        
        # 启动Worker
        start_celery_worker(pool_type, concurrency)
        
    except KeyboardInterrupt:
        print("\n👋 已取消启动")
        return 0
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
环境验证脚本
Environment verification script
"""

import sys

def verify_environment():
    """验证环境配置"""
    print("🔍 环境验证")
    print("=" * 50)
    
    print(f"Python版本: {sys.version}")
    print(f"虚拟环境: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    
    # 测试核心依赖导入
    dependencies = [
        'fastapi',
        'sqlalchemy', 
        'pandas',
        'openpyxl',
        'structlog',
        'celery',
        'pydantic',
        'httpx',
        'lxml',
        'bs4'
    ]
    
    print("\n📦 依赖验证:")
    failed_imports = []
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"  ✅ {dep}")
        except ImportError as e:
            print(f"  ❌ {dep}: {e}")
            failed_imports.append(dep)
    
    if failed_imports:
        print(f"\n❌ 失败的导入: {failed_imports}")
        return False
    else:
        print("\n🎉 所有依赖验证成功！")
        return True

if __name__ == "__main__":
    success = verify_environment()
    sys.exit(0 if success else 1)
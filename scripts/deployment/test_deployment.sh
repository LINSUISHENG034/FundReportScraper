#!/bin/bash
# 部署测试和诊断脚本

echo "🔍 开始部署诊断..."

# 添加用户本地bin到PATH
export PATH="$HOME/.local/bin:$PATH"

# 检查Python环境
echo "🐍 检查Python环境:"
python3 --version
echo "Python路径: $(which python3)"

# 检查关键模块
echo ""
echo "📦 检查关键Python模块:"
for module in fastapi uvicorn pydantic sqlalchemy; do
    if python3 -c "import $module; print('✅ $module:', getattr($module, '__version__', 'unknown version'))" 2>/dev/null; then
        continue
    else
        echo "❌ $module 不可用"
        echo "   尝试安装: python3 -m pip install $module"
    fi
done

echo ""
echo "📁 检查项目结构:"
# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ls -la src/api/ 2>/dev/null || echo "❌ src/api/ 目录不存在"

if [ -f "src/api/main.py" ]; then
    echo "✅ API主文件存在"
    echo "   检查导入:"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # 检查具体的导入错误
    echo "   导入详细测试："
    if python3 -c "import fastapi" 2>/dev/null; then
        echo "   ✅ FastAPI 导入成功"
    else
        echo "   ❌ FastAPI 导入失败"
    fi
    
    if python3 -c "import src" 2>/dev/null; then
        echo "   ✅ src 包导入成功"
    else
        echo "   ❌ src 包导入失败"
    fi
    
    if python3 -c "import src.api" 2>/dev/null; then
        echo "   ✅ src.api 包导入成功"
    else
        echo "   ❌ src.api 包导入失败"
    fi
    
    if python3 -c "import src.api.main" 2>/dev/null; then
        echo "   ✅ API模块导入成功"
    else
        echo "   ❌ API模块导入失败:"
        python3 -c "import src.api.main" 2>&1 | head -3
    fi
else
    echo "❌ API主文件不存在"
fi

echo ""
echo "🔧 建议的修复步骤:"
echo "1. 更新PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "2. 安装必要依赖: python3 -m pip install fastapi uvicorn pydantic sqlalchemy alembic"
echo "3. 检查项目结构是否完整"
echo "4. 确保所有Python模块都能正确导入"
echo "5. 重新运行: ./setup_platform.sh --mode demo"
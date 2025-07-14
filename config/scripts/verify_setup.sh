#!/bin/bash
# 快速验证脚本 - 验证项目配置和模块导入

echo "🔍 项目配置验证"
echo "=================="

# 1. 检查当前目录
echo ""
echo "📂 当前工作目录:"
pwd

# 2. 检查项目结构
echo ""
echo "📁 项目结构检查:"
for dir in src src/api src/core src/services frontend/user frontend/admin; do
    if [ -d "$dir" ]; then
        echo "✅ $dir 目录存在"
    else
        echo "❌ $dir 目录缺失"
    fi
done

# 3. 检查关键文件
echo ""
echo "📄 关键文件检查:"
for file in src/api/main.py src/core/config.py setup.sh pyproject.toml; do
    if [ -f "$file" ]; then
        echo "✅ $file 文件存在"
    else
        echo "❌ $file 文件缺失"
    fi
done

# 4. 检查Python环境
echo ""
echo "🐍 Python环境:"
python3 --version
which python3

# 5. 检查模块导入
echo ""
echo "📦 模块导入测试:"
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 测试基础模块
if python3 -c "import fastapi; print('✅ FastAPI:', fastapi.__version__)" 2>/dev/null; then
    true
else
    echo "❌ FastAPI 不可用"
fi

if python3 -c "import uvicorn; print('✅ Uvicorn:', uvicorn.__version__)" 2>/dev/null; then
    true
else
    echo "❌ Uvicorn 不可用"
fi

# 测试项目模块
if python3 -c "import src; print('✅ src 包导入成功')" 2>/dev/null; then
    true
else
    echo "❌ src 包导入失败"
fi

if python3 -c "import src.api.main; print('✅ API模块导入成功')" 2>/dev/null; then
    true
else
    echo "❌ API模块导入失败"
    echo "   详细错误:"
    python3 -c "import src.api.main" 2>&1 | head -3 | sed 's/^/   /'
fi

# 6. 检查前端文件
echo ""
echo "🌐 前端文件检查:"
for file in frontend/user/index.html frontend/admin/index.html frontend/user/js/api.js; do
    if [ -f "$file" ]; then
        echo "✅ $file 存在"
    else
        echo "❌ $file 缺失"
    fi
done

# 7. 检查端口占用
echo ""
echo "🔌 端口状态检查:"
if lsof -i :8000 >/dev/null 2>&1; then
    echo "⚠️  端口 8000 已被占用"
    echo "   占用进程:"
    lsof -i :8000 | tail -n +2 | sed 's/^/   /'
else
    echo "✅ 端口 8000 可用"
fi

if lsof -i :8001 >/dev/null 2>&1; then
    echo "⚠️  端口 8001 已被占用"
    echo "   占用进程:"
    lsof -i :8001 | tail -n +2 | sed 's/^/   /'
else
    echo "✅ 端口 8001 可用"
fi

echo ""
echo "🎯 验证完成"
echo "=============="
echo ""

# 8. 提供快速启动建议
echo "💡 快速启动建议:"
echo "   1. 启动后端API: python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo "   2. 访问用户界面: file://$(pwd)/frontend/user/index.html"
echo "   3. 访问管理后台: file://$(pwd)/frontend/admin/index.html"
echo "   4. API文档: http://localhost:8000/docs"
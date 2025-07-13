#!/bin/bash
# 简化的部署测试脚本

echo "🔍 基金报告平台部署修复测试"

# 设置环境
export PATH="$HOME/.local/bin:$PATH"
# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

echo "✅ 当前目录: $(pwd)"
echo "✅ PYTHONPATH: $PYTHONPATH"

# 测试Python模块导入
echo ""
echo "🧪 测试Python模块导入:"
if python3 -c "import src.api.main; print('API模块导入成功!')"; then
    echo "✅ 所有模块导入正常"
else
    echo "❌ 模块导入失败"
    exit 1
fi

# 创建配置文件
echo ""
echo "⚙️ 创建演示配置:"
cat > .env.demo << EOF
# 演示模式配置
API_PORT=8000
DB_TYPE=sqlite
LOG_LEVEL=INFO
ENABLE_DEBUG=false
DEMO_MODE=true
PRELOAD_SAMPLE_DATA=true
EOF

echo "✅ 配置文件创建完成"

# 创建日志目录
mkdir -p logs

# 启动API服务
echo ""
echo "🚀 启动API服务:"
cat > start_api.sh << 'EOF'
#!/bin/bash
# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
EOF

chmod +x start_api.sh

echo "启动API服务..."
nohup ./start_api.sh > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > logs/api.pid

echo "✅ API服务已启动，PID: $API_PID"

# 等待服务启动
echo ""
echo "⏳ 等待API服务启动..."
sleep 5

# 检查服务状态
for i in {1..6}; do
    echo "检查API服务状态 ($i/6)..."
    
    if kill -0 $API_PID 2>/dev/null; then
        echo "✅ API进程运行正常"
        
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            echo "🎉 API服务启动成功！"
            echo ""
            echo "📊 访问地址:"
            echo "   - API文档: http://localhost:8000/docs"
            echo "   - 健康检查: http://localhost:8000/health"
            echo ""
            echo "🛠️ 管理命令:"
            echo "   - 查看日志: tail -f logs/api.log"
            echo "   - 停止服务: kill $API_PID"
            echo ""
            echo "✅ 部署完成！基金报告平台已成功启动"
            exit 0
        else
            echo "⏳ API服务启动中..."
        fi
    else
        echo "❌ API进程异常退出"
        break
    fi
    
    sleep 5
done

echo "❌ API服务启动失败"
echo "📋 错误诊断:"
echo "   - 检查日志: tail logs/api.log"
echo "   - 检查进程: ps aux | grep uvicorn"

if [ -f logs/api.log ]; then
    echo ""
    echo "🔍 API启动日志:"
    tail -10 logs/api.log
fi
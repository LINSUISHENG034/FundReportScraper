#!/bin/bash
# 基金报告平台 - 主入口脚本
# Fund Report Platform - Main Entry Script

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 显示欢迎信息
show_welcome() {
    clear
    echo -e "${BLUE}"
    cat << "EOF"
╔══════════════════════════════════════════════════════════════════════════════╗
║                    基金报告自动化采集与分析平台                                ║
║              Fund Report Automated Collection & Analysis Platform           ║
║                                                                              ║
║                           🚀 快速部署入口 🚀                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo
}

# 显示菜单
show_menu() {
    echo -e "${GREEN}选择要执行的操作：${NC}"
    echo
    echo "📦 部署相关："
    echo "  1) 🚀 完整引导式部署 (推荐新用户)"
    echo "  2) ⚡ 快速部署 (适合开发测试)"
    echo "  3) 🧪 部署测试"
    echo
    echo "🎯 演示相关："
    echo "  4) 📺 查看双界面设计展示"
    echo "  5) 💡 查看用户体验改进展示"
    echo
    echo "🛠️ 管理相关："
    echo "  6) 🏥 系统健康检查"
    echo "  7) 📊 启动Web管理界面"
    echo "  8) 📖 查看使用文档"
    echo
    echo "  9) 🚪 退出"
    echo
}

# 执行选择
execute_choice() {
    local choice=$1
    
    case $choice in
        1)
            echo -e "${BLUE}启动完整引导式部署...${NC}"
            bash scripts/deployment/setup_platform.sh
            ;;
        2)
            echo -e "${BLUE}启动快速部署...${NC}"
            bash scripts/deployment/deploy_simple.sh
            ;;
        3)
            echo -e "${BLUE}运行部署测试...${NC}"
            bash scripts/deployment/test_deployment.sh
            ;;
        4)
            echo -e "${BLUE}显示双界面设计展示...${NC}"
            bash scripts/demo/show_dual_interface.sh
            ;;
        5)
            echo -e "${BLUE}显示用户体验改进展示...${NC}"
            bash scripts/demo/show_improvements.sh
            ;;
        6)
            echo -e "${BLUE}检查系统健康状态...${NC}"
            if command -v curl &> /dev/null; then
                curl -f http://localhost:8000/health 2>/dev/null && echo -e "${GREEN}✅ 系统运行正常${NC}" || echo -e "${RED}❌ 系统未运行或异常${NC}"
            else
                echo -e "${YELLOW}❌ curl命令不可用，无法检查健康状态${NC}"
            fi
            ;;
        7)
            echo -e "${BLUE}启动Web管理界面...${NC}"
            if command -v streamlit &> /dev/null; then
                streamlit run gui/web_admin.py
            else
                echo -e "${YELLOW}请先安装streamlit: pip install streamlit${NC}"
                echo "然后运行: streamlit run gui/web_admin.py"
            fi
            ;;
        8)
            echo -e "${BLUE}查看使用文档...${NC}"
            if [ -f "docs/user-guide.md" ]; then
                echo "📖 用户指南: docs/user-guide.md"
            fi
            if [ -f "README.md" ]; then
                echo "📋 项目说明: README.md"
            fi
            if [ -f "docs/operations/运维手册.md" ]; then
                echo "🔧 运维手册: docs/operations/运维手册.md"
            fi
            echo
            echo "💡 在线文档："
            echo "   API文档: http://localhost:8000/docs"
            echo "   用户界面: http://localhost:8000/"
            echo "   管理后台: http://localhost:8000/admin"
            ;;
        9)
            echo -e "${GREEN}感谢使用基金报告平台！${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}无效选择，请输入 1-9${NC}"
            ;;
    esac
}

# 主函数
main() {
    # 检查是否在项目根目录
    if [ ! -f "pyproject.toml" ] && [ ! -f "src/api/main.py" ]; then
        echo -e "${RED}错误：请在项目根目录运行此脚本${NC}"
        exit 1
    fi
    
    show_welcome
    
    while true; do
        show_menu
        read -p "请选择 [1-9]: " -r choice
        echo
        
        execute_choice "$choice"
        
        echo
        echo -e "${YELLOW}按回车键返回主菜单...${NC}"
        read -r
        clear
    done
}

# 命令行参数处理
case "${1:-}" in
    --deploy)
        bash scripts/deployment/setup_platform.sh
        ;;
    --quick)
        bash scripts/deployment/deploy_simple.sh
        ;;
    --test)
        bash scripts/deployment/test_deployment.sh
        ;;
    --health)
        curl -f http://localhost:8000/health 2>/dev/null && echo "✅ 系统运行正常" || echo "❌ 系统未运行或异常"
        ;;
    --help|-h)
        echo "基金报告平台 - 快速启动脚本"
        echo
        echo "用法:"
        echo "  $0                交互式菜单"
        echo "  $0 --deploy       完整引导式部署"
        echo "  $0 --quick        快速部署"
        echo "  $0 --test         部署测试"
        echo "  $0 --health       健康检查"
        echo "  $0 --help         显示帮助"
        ;;
    "")
        main
        ;;
    *)
        echo "未知参数: $1"
        echo "使用 $0 --help 查看帮助"
        exit 1
        ;;
esac
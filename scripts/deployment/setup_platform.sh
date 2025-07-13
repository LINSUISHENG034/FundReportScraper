#!/bin/bash
# 引导式一键部署脚本
# Guided One-Click Deployment Script
# 基金报告自动化采集与分析平台

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 全局变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_MODE=""
CONFIG_FILE=""
LOG_FILE="$PROJECT_ROOT/logs/deployment_$(date +%Y%m%d_%H%M%S).log"

# 创建日志目录
mkdir -p "$PROJECT_ROOT/logs"

# 日志函数
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO")
            echo -e "${BLUE}[INFO]${NC} $message" | tee -a "$LOG_FILE"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} $message" | tee -a "$LOG_FILE"
            ;;
        "WARNING")
            echo -e "${YELLOW}[WARNING]${NC} $message" | tee -a "$LOG_FILE"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE"
            ;;
        "STEP")
            echo -e "${PURPLE}[STEP]${NC} $message" | tee -a "$LOG_FILE"
            ;;
    esac
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# 显示欢迎信息
show_welcome() {
    clear
    echo -e "${PURPLE}"
    cat << "EOF"
╔══════════════════════════════════════════════════════════════════════════════╗
║                    基金报告自动化采集与分析平台                                ║
║              Fund Report Automated Collection & Analysis Platform           ║
║                                                                              ║
║                           🚀 引导式一键部署向导 🚀                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    echo
    echo -e "${CYAN}欢迎使用基金报告平台部署向导！${NC}"
    echo
    echo "本向导将帮助您："
    echo "  🔧 检查系统环境和依赖"
    echo "  ⚙️  配置部署参数"
    echo "  🚀 自动部署和启动服务"
    echo "  ✅ 验证系统功能"
    echo
    echo -e "${YELLOW}注意：部署过程需要sudo权限来安装依赖和配置服务${NC}"
    echo
    
    read -p "按回车键继续..." -r
}

# 检查系统环境
check_system_requirements() {
    log "STEP" "检查系统环境和依赖..."
    
    local requirements_met=true
    
    # 检查操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log "SUCCESS" "操作系统: Linux (支持)"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log "SUCCESS" "操作系统: macOS (支持)"
    else
        log "WARNING" "操作系统: $OSTYPE (可能不完全支持)"
    fi
    
    # 检查必需的命令
    local required_commands=("docker" "python3" "curl" "git")
    
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            local version
            case $cmd in
                "docker")
                    version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
                    log "SUCCESS" "$cmd 已安装 (版本: $version)"
                    ;;
                "python3")
                    version=$(python3 --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
                    log "SUCCESS" "$cmd 已安装 (版本: $version)"
                    ;;
                *)
                    log "SUCCESS" "$cmd 已安装"
                    ;;
            esac
        else
            log "ERROR" "$cmd 未安装"
            requirements_met=false
        fi
    done
    
    # 检查docker-compose (可选，因为新版Docker包含compose)
    if command -v docker-compose &> /dev/null; then
        local compose_version=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "SUCCESS" "docker-compose 已安装 (版本: $compose_version)"
    elif docker compose version &> /dev/null; then
        local compose_version=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "SUCCESS" "docker compose 已安装 (版本: $compose_version)"
    else
        log "ERROR" "docker-compose 或 docker compose 未安装"
        requirements_met=false
    fi
    
    # 检查系统资源
    log "INFO" "检查系统资源..."
    
    # 检查内存
    if command -v free &> /dev/null; then
        local memory_gb=$(free -g | awk '/^Mem:/{print $2}')
        if [ "$memory_gb" -ge 4 ]; then
            log "SUCCESS" "系统内存: ${memory_gb}GB (充足)"
        else
            log "WARNING" "系统内存: ${memory_gb}GB (建议至少4GB)"
        fi
    fi
    
    # 检查磁盘空间
    local disk_space_gb=$(df -BG . | awk 'NR==2{gsub(/G/,"",$4); print $4}')
    if [ "$disk_space_gb" -ge 20 ]; then
        log "SUCCESS" "可用磁盘空间: ${disk_space_gb}GB (充足)"
    else
        log "WARNING" "可用磁盘空间: ${disk_space_gb}GB (建议至少20GB)"
    fi
    
    # 检查端口占用
    log "INFO" "检查端口占用情况..."
    local ports_to_check=(8000 5432 6379 9000 9001)
    
    for port in "${ports_to_check[@]}"; do
        if command -v ss &> /dev/null && ss -tlnp 2>/dev/null | grep -q ":$port "; then
            log "WARNING" "端口 $port 已被占用"
        elif command -v netstat &> /dev/null && netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            log "WARNING" "端口 $port 已被占用"
        else
            log "SUCCESS" "端口 $port 可用"
        fi
    done
    
    if [ "$requirements_met" = false ]; then
        log "ERROR" "系统环境检查失败，请安装缺失的依赖"
        
        echo
        echo -e "${YELLOW}自动安装依赖？${NC}"
        echo "1) 是，自动安装缺失的依赖"
        echo "2) 否，我稍后手动安装"
        echo "3) 显示安装指南"
        
        read -p "请选择 [1-3]: " -r install_choice
        
        case $install_choice in
            1)
                install_dependencies
                ;;
            2)
                log "INFO" "请手动安装缺失的依赖后重新运行脚本"
                exit 1
                ;;
            3)
                show_installation_guide
                exit 1
                ;;
            *)
                log "ERROR" "无效选择"
                exit 1
                ;;
        esac
    else
        log "SUCCESS" "系统环境检查通过"
    fi
}

# 自动安装依赖
install_dependencies() {
    log "STEP" "自动安装系统依赖..."
    
    # 检测包管理器
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        log "INFO" "检测到 apt 包管理器，安装依赖..."
        
        sudo apt-get update
        sudo apt-get install -y curl git python3 python3-pip
        
        # 安装Docker
        if ! command -v docker &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
        fi
        
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        log "INFO" "检测到 yum 包管理器，安装依赖..."
        
        sudo yum update -y
        sudo yum install -y curl git python3 python3-pip
        
        # 安装Docker
        if ! command -v docker &> /dev/null; then
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
        fi
        
    elif command -v brew &> /dev/null; then
        # macOS
        log "INFO" "检测到 Homebrew，安装依赖..."
        
        brew install docker python3 git curl
        
    else
        log "ERROR" "未检测到支持的包管理器，请手动安装依赖"
        show_installation_guide
        exit 1
    fi
    
    log "SUCCESS" "依赖安装完成"
    
    # 如果安装了Docker，提示重新登录
    if groups $USER | grep -q docker; then
        log "WARNING" "Docker已安装，您可能需要重新登录以使用Docker命令"
        log "INFO" "或者运行: newgrp docker"
    fi
}

# 显示安装指南
show_installation_guide() {
    echo
    echo -e "${CYAN}=== 手动安装指南 ===${NC}"
    echo
    echo "请根据您的操作系统手动安装以下依赖："
    echo
    echo -e "${YELLOW}Ubuntu/Debian:${NC}"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y docker.io python3 python3-pip git curl"
    echo "  sudo usermod -aG docker \$USER"
    echo
    echo -e "${YELLOW}CentOS/RHEL:${NC}"
    echo "  sudo yum install -y docker python3 python3-pip git curl"
    echo "  sudo systemctl start docker && sudo systemctl enable docker"
    echo "  sudo usermod -aG docker \$USER"
    echo
    echo -e "${YELLOW}macOS:${NC}"
    echo "  brew install docker python3 git curl"
    echo "  # 或下载 Docker Desktop for Mac"
    echo
    echo -e "${YELLOW}安装完成后，请重新运行此脚本${NC}"
}

# 选择部署模式
choose_deployment_mode() {
    echo
    log "STEP" "选择部署模式..."
    
    echo
    echo -e "${CYAN}请选择部署模式：${NC}"
    echo
    echo "1) 🧪 开发环境 (Development)"
    echo "   - 适合学习和测试"
    echo "   - 使用SQLite数据库"
    echo "   - 单机部署，快速启动"
    echo "   - 包含调试功能"
    echo
    echo "2) 🚀 生产环境 (Production)"
    echo "   - 适合正式使用"
    echo "   - 使用PostgreSQL数据库"
    echo "   - Docker容器化部署"
    echo "   - 完整监控和日志"
    echo
    echo "3) 🔧 自定义配置 (Custom)"
    echo "   - 高级用户选项"
    echo "   - 自定义所有配置参数"
    echo "   - 适合特殊部署需求"
    echo
    echo "4) 📱 演示模式 (Demo)"
    echo "   - 快速演示功能"
    echo "   - 预置示例数据"
    echo "   - 最小化资源使用"
    echo
    
    while true; do
        read -p "请选择部署模式 [1-4]: " -r mode_choice
        
        case $mode_choice in
            1)
                DEPLOYMENT_MODE="development"
                log "INFO" "选择部署模式: 开发环境"
                break
                ;;
            2)
                DEPLOYMENT_MODE="production"
                log "INFO" "选择部署模式: 生产环境"
                break
                ;;
            3)
                DEPLOYMENT_MODE="custom"
                log "INFO" "选择部署模式: 自定义配置"
                break
                ;;
            4)
                DEPLOYMENT_MODE="demo"
                log "INFO" "选择部署模式: 演示模式"
                break
                ;;
            *)
                echo -e "${RED}无效选择，请输入1-4${NC}"
                ;;
        esac
    done
}

# 配置部署参数
configure_deployment() {
    log "STEP" "配置部署参数..."
    
    case $DEPLOYMENT_MODE in
        "development")
            configure_development
            ;;
        "production")
            configure_production
            ;;
        "custom")
            configure_custom
            ;;
        "demo")
            configure_demo
            ;;
    esac
    
    # 生成配置文件
    generate_config_file
}

# 配置开发环境
configure_development() {
    echo
    echo -e "${CYAN}=== 开发环境配置 ===${NC}"
    
    # API端口
    read -p "API服务端口 [8000]: " -r api_port
    api_port=${api_port:-8000}
    
    # 数据库选择
    echo
    echo "数据库选择："
    echo "1) SQLite (推荐，无需额外配置)"
    echo "2) PostgreSQL (需要Docker)"
    
    read -p "请选择 [1-2]: " -r db_choice
    
    if [ "$db_choice" = "2" ]; then
        DB_TYPE="postgresql"
        read -p "数据库密码 [dev123456]: " -r db_password
        db_password=${db_password:-dev123456}
    else
        DB_TYPE="sqlite"
        db_password=""
    fi
    
    # 保存配置
    cat > "$PROJECT_ROOT/.env.dev" << EOF
# 开发环境配置
API_PORT=$api_port
DB_TYPE=$DB_TYPE
DB_PASSWORD=$db_password
LOG_LEVEL=DEBUG
ENABLE_DEBUG=true
EOF

    log "SUCCESS" "开发环境配置完成"
}

# 配置生产环境
configure_production() {
    echo
    echo -e "${CYAN}=== 生产环境配置 ===${NC}"
    
    # 基本配置
    read -p "API服务端口 [8000]: " -r api_port
    api_port=${api_port:-8000}
    
    read -p "域名（可选）: " -r domain_name
    
    # 安全配置
    echo
    echo -e "${YELLOW}安全配置：${NC}"
    
    read -p "数据库密码（留空自动生成）: " -s -r db_password
    echo
    if [ -z "$db_password" ]; then
        db_password=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        log "INFO" "已自动生成数据库密码"
    fi
    
    read -p "Redis密码（留空自动生成）: " -s -r redis_password
    echo
    if [ -z "$redis_password" ]; then
        redis_password=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        log "INFO" "已自动生成Redis密码"
    fi
    
    # SSL配置
    echo
    read -p "启用SSL证书？[y/N]: " -r enable_ssl
    
    if [[ $enable_ssl =~ ^[Yy]$ ]]; then
        read -p "SSL证书路径: " -r ssl_cert_path
        read -p "SSL私钥路径: " -r ssl_key_path
    else
        ssl_cert_path=""
        ssl_key_path=""
    fi
    
    # 监控配置
    echo
    read -p "启用监控告警？[Y/n]: " -r enable_monitoring
    if [[ ! $enable_monitoring =~ ^[Nn]$ ]]; then
        read -p "告警邮箱: " -r alert_email
        read -p "SMTP服务器: " -r smtp_server
        read -p "SMTP端口 [587]: " -r smtp_port
        smtp_port=${smtp_port:-587}
    else
        alert_email=""
        smtp_server=""
        smtp_port=""
    fi
    
    # 保存生产配置
    cat > "$PROJECT_ROOT/.env.prod" << EOF
# 生产环境配置
API_PORT=$api_port
DOMAIN_NAME=$domain_name

# 数据库配置
POSTGRES_PASSWORD=$db_password
REDIS_PASSWORD=$redis_password

# SSL配置
ENABLE_SSL=$([[ $enable_ssl =~ ^[Yy]$ ]] && echo "true" || echo "false")
SSL_CERT_PATH=$ssl_cert_path
SSL_KEY_PATH=$ssl_key_path

# 监控配置
ENABLE_MONITORING=$([[ ! $enable_monitoring =~ ^[Nn]$ ]] && echo "true" || echo "false")
ALERT_EMAIL=$alert_email
SMTP_SERVER=$smtp_server
SMTP_PORT=$smtp_port

# 安全配置
SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
LOG_LEVEL=INFO
ENABLE_DEBUG=false
EOF

    log "SUCCESS" "生产环境配置完成"
    
    # 显示重要信息
    echo
    echo -e "${YELLOW}=== 重要信息，请妥善保存 ===${NC}"
    echo "数据库密码: $db_password"
    echo "Redis密码: $redis_password"
    echo -e "${YELLOW}=================================${NC}"
}

# 配置自定义模式
configure_custom() {
    echo
    echo -e "${CYAN}=== 自定义配置模式 ===${NC}"
    echo "请参考生产环境配置，根据需要自定义参数"
    
    configure_production
}

# 配置演示模式
configure_demo() {
    echo
    echo -e "${CYAN}=== 演示模式配置 ===${NC}"
    
    # 演示模式使用默认配置
    cat > "$PROJECT_ROOT/.env.demo" << EOF
# 演示模式配置
API_PORT=8000
DB_TYPE=sqlite
LOG_LEVEL=INFO
ENABLE_DEBUG=false
DEMO_MODE=true
PRELOAD_SAMPLE_DATA=true
EOF

    log "SUCCESS" "演示模式配置完成"
}

# 生成配置文件
generate_config_file() {
    CONFIG_FILE="$PROJECT_ROOT/.env.$DEPLOYMENT_MODE"
    log "INFO" "配置文件已生成: $CONFIG_FILE"
}

# 执行部署
deploy_system() {
    log "STEP" "开始部署系统..."
    
    cd "$PROJECT_ROOT"
    
    case $DEPLOYMENT_MODE in
        "development")
            deploy_development
            ;;
        "production")
            deploy_production
            ;;
        "custom")
            deploy_production  # 自定义模式使用生产部署
            ;;
        "demo")
            deploy_demo
            ;;
    esac
}

# 部署开发环境
deploy_development() {
    log "INFO" "部署开发环境..."
    
    # 设置PATH以包含用户本地bin目录
    export PATH="$HOME/.local/bin:$PATH"
    
    # 设置Python路径
    cd "$PROJECT_ROOT"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # 检查Python环境
    log "INFO" "检查Python环境..."
    if ! python3 -c "import sys; print(sys.version)" >/dev/null 2>&1; then
        log "ERROR" "Python3环境异常"
        return 1
    fi
    
    # 安装Python依赖
    log "INFO" "安装Python依赖..."
    if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
        log "INFO" "使用pyproject.toml安装依赖..."
        if ! python3 -m pip install -e . 2>"$LOG_FILE"; then
            log "WARNING" "pyproject.toml安装失败，尝试手动安装基础依赖"
            python3 -m pip install fastapi uvicorn pydantic sqlalchemy alembic psycopg2-binary redis celery structlog requests pydantic-settings 2>"$LOG_FILE" || log "WARNING" "基础依赖安装失败"
        fi
    elif [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        log "INFO" "使用requirements.txt安装依赖..."
        python3 -m pip install -r requirements.txt 2>"$LOG_FILE" || log "WARNING" "requirements.txt安装失败"
    else
        log "INFO" "安装基础依赖..."
        python3 -m pip install fastapi uvicorn pydantic sqlalchemy alembic psycopg2-binary redis celery structlog requests pydantic-settings 2>"$LOG_FILE" || log "WARNING" "基础依赖安装失败"
    fi
    
    # 检查关键模块
    log "INFO" "验证关键Python模块..."
    for module in fastapi uvicorn pydantic; do
        if ! python3 -c "import $module" 2>/dev/null; then
            log "ERROR" "关键模块 $module 不可用"
            return 1
        fi
    done
    
    # 验证API模块可以导入
    log "INFO" "验证API模块导入..."
    
    # 创建临时错误文件用于调试
    local temp_error_file="$PROJECT_ROOT/logs/api_import_error.log"
    local temp_test_script="$PROJECT_ROOT/logs/test_import.py"
    
    # 创建临时测试脚本
    cat > "$temp_test_script" << EOF
import sys
import os
# 确保项目根目录在Python路径中
project_root = "$PROJECT_ROOT"
sys.path.insert(0, project_root)
os.chdir(project_root)
import src.api.main
print("API模块导入成功")
EOF
    
    if ! python3 "$temp_test_script" 2>"$temp_error_file"; then
        log "ERROR" "API模块导入失败"
        if [ -f "$temp_error_file" ]; then
            log "ERROR" "错误详情："
            while read line; do
                log "ERROR" "  $line"
            done < "$temp_error_file"
        fi
        rm -f "$temp_test_script" "$temp_error_file" 2>/dev/null
        return 1
    else
        log "SUCCESS" "API模块导入成功"
        rm -f "$temp_test_script" "$temp_error_file" 2>/dev/null
    fi
    
    # 启动服务
    local db_type="sqlite"
    if [ -f "$PROJECT_ROOT/.env.dev" ]; then
        db_type=$(grep "DB_TYPE" "$PROJECT_ROOT/.env.dev" | cut -d'=' -f2 2>/dev/null || echo "sqlite")
    fi
    
    if [ "$db_type" = "postgresql" ]; then
        log "INFO" "启动PostgreSQL容器..."
        
        # 使用docker或docker-compose
        if command -v docker-compose &> /dev/null; then
            if [ -f "$PROJECT_ROOT/docker-compose.dev.yml" ]; then
                docker-compose -f docker-compose.dev.yml up -d postgres redis 2>"$LOG_FILE" || log "WARNING" "Docker服务启动失败"
            else
                log "WARNING" "docker-compose.dev.yml文件不存在，跳过PostgreSQL启动"
            fi
        elif docker compose version &> /dev/null; then
            if [ -f "$PROJECT_ROOT/docker-compose.dev.yml" ]; then
                docker compose -f docker-compose.dev.yml up -d postgres redis 2>"$LOG_FILE" || log "WARNING" "Docker服务启动失败"
            else
                log "WARNING" "docker-compose.dev.yml文件不存在，跳过PostgreSQL启动"
            fi
        fi
        
        # 等待数据库启动
        log "INFO" "等待数据库启动..."
        sleep 10
    else
        log "INFO" "使用SQLite数据库，无需启动额外服务"
    fi
    
    # 初始化数据库
    log "INFO" "初始化数据库..."
    if [ -f "$PROJECT_ROOT/alembic.ini" ]; then
        python3 -m alembic upgrade head 2>"$LOG_FILE" || log "WARNING" "数据库迁移失败，可能需要手动处理"
    else
        log "INFO" "未找到alembic.ini，跳过数据库迁移"
    fi
    
    # 启动API服务
    log "INFO" "启动API服务..."
    
    # 创建启动脚本
    cat > "$PROJECT_ROOT/start_api.sh" << EOF
#!/bin/bash
cd "$(dirname "\$0")"
export PATH="\$HOME/.local/bin:\$PATH"
export PYTHONPATH="\$(pwd):\$PYTHONPATH"
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
EOF
    chmod +x "$PROJECT_ROOT/start_api.sh"
    
    # 后台启动API服务
    nohup bash "$PROJECT_ROOT/start_api.sh" > "$PROJECT_ROOT/logs/api.log" 2>&1 &
    local api_pid=$!
    
    log "INFO" "API服务已启动，PID: $api_pid"
    echo "$api_pid" > "$PROJECT_ROOT/logs/api.pid"
    
    log "SUCCESS" "开发环境部署完成"
}

# 部署生产环境
deploy_production() {
    log "INFO" "部署生产环境..."
    
    # 构建生产镜像
    log "INFO" "构建生产Docker镜像..."
    
    # 使用docker-compose或docker compose
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.prod.yml build 2>/dev/null || log "WARNING" "Docker镜像构建失败"
        
        # 启动服务
        log "INFO" "启动生产环境服务..."
        docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d 2>/dev/null || log "WARNING" "Docker服务启动失败"
        
    elif docker compose version &> /dev/null; then
        docker compose -f docker-compose.prod.yml build 2>/dev/null || log "WARNING" "Docker镜像构建失败"
        
        # 启动服务
        log "INFO" "启动生产环境服务..."
        docker compose -f docker-compose.prod.yml --env-file .env.prod up -d 2>/dev/null || log "WARNING" "Docker服务启动失败"
    else
        log "ERROR" "未找到docker-compose或docker compose命令"
        return 1
    fi
    
    # 等待服务启动
    log "INFO" "等待服务启动..."
    sleep 30
    
    # 初始化数据库
    log "INFO" "初始化数据库..."
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head 2>/dev/null || log "WARNING" "数据库初始化失败"
    elif docker compose version &> /dev/null; then
        docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head 2>/dev/null || log "WARNING" "数据库初始化失败"
    fi
    
    log "SUCCESS" "生产环境部署完成"
}

# 部署演示模式
deploy_demo() {
    log "INFO" "部署演示模式..."
    
    # 使用开发配置但加载示例数据
    deploy_development
    
    # 加载示例数据
    log "INFO" "加载示例数据..."
    if [ -f "$PROJECT_ROOT/scripts/demos/load_sample_data.py" ]; then
        python3 scripts/demos/load_sample_data.py 2>/dev/null || log "WARNING" "示例数据加载失败"
    fi
    
    log "SUCCESS" "演示模式部署完成"
}

# 验证部署
verify_deployment() {
    log "STEP" "验证部署结果..."
    
    local api_port=8000
    if [ -f "$CONFIG_FILE" ]; then
        api_port=$(grep "API_PORT" "$CONFIG_FILE" | cut -d'=' -f2 2>/dev/null || echo "8000")
    fi
    
    # 等待服务完全启动
    log "INFO" "等待服务完全启动..."
    sleep 5
    
    # 检查API健康状态
    local max_attempts=12  # 减少到12次，每次5秒
    local attempt=1
    local api_started=false
    
    while [ $attempt -le $max_attempts ]; do
        log "INFO" "等待API服务启动... ($attempt/$max_attempts)"
        
        # 检查API进程是否存在
        if [ -f "$PROJECT_ROOT/logs/api.pid" ]; then
            local api_pid=$(cat "$PROJECT_ROOT/logs/api.pid" 2>/dev/null)
            if [ -n "$api_pid" ] && kill -0 "$api_pid" 2>/dev/null; then
                log "INFO" "API进程 $api_pid 正在运行"
                
                # 检查HTTP响应
                if curl -f "http://localhost:$api_port/health" >/dev/null 2>&1; then
                    log "SUCCESS" "API服务健康检查通过"
                    api_started=true
                    break
                elif curl -f "http://localhost:$api_port/" >/dev/null 2>&1; then
                    log "SUCCESS" "API服务响应正常"
                    api_started=true
                    break
                else
                    log "INFO" "API服务启动中，等待响应..."
                fi
            else
                log "WARNING" "API进程可能已停止，检查日志..."
                if [ -f "$PROJECT_ROOT/logs/api.log" ]; then
                    tail -5 "$PROJECT_ROOT/logs/api.log" >> "$LOG_FILE"
                fi
            fi
        else
            log "INFO" "等待API进程创建PID文件..."
        fi
        
        sleep 5
        ((attempt++))
    done
    
    if [ "$api_started" != "true" ]; then
        log "ERROR" "API服务启动失败或超时"
        
        # 显示错误诊断信息
        log "INFO" "开始故障诊断..."
        
        # 检查端口占用
        if command -v ss &> /dev/null; then
            local port_check=$(ss -tlnp | grep ":$api_port " 2>/dev/null)
            if [ -n "$port_check" ]; then
                log "INFO" "端口 $api_port 已被占用: $port_check"
            else
                log "WARNING" "端口 $api_port 没有被监听"
            fi
        fi
        
        # 检查API日志
        if [ -f "$PROJECT_ROOT/logs/api.log" ]; then
            log "INFO" "API启动日志内容："
            tail -20 "$PROJECT_ROOT/logs/api.log" | while read line; do
                log "INFO" "API日志: $line"
            done
        else
            log "WARNING" "API日志文件不存在"
        fi
        
        # 检查Python模块
        log "INFO" "检查Python模块导入..."
        cd "$PROJECT_ROOT"
        export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
        
        if python3 -c "import src.api.main" 2>/dev/null; then
            log "SUCCESS" "API模块导入成功"
        else
            log "ERROR" "API模块导入失败"
            python3 -c "import src.api.main" 2>&1 | head -10 | while read line; do
                log "ERROR" "导入错误: $line"
            done
        fi
        
        return 1
    fi
    
    # 测试主要端点
    local endpoints=("/health" "/docs" "/")
    
    for endpoint in "${endpoints[@]}"; do
        if curl -f "http://localhost:$api_port$endpoint" >/dev/null 2>&1; then
            log "SUCCESS" "端点 $endpoint 响应正常"
        else
            log "WARNING" "端点 $endpoint 响应异常"
        fi
    done
    
    # 检查Docker服务（如果是容器化部署）
    if [ "$DEPLOYMENT_MODE" = "production" ] || [ "$DEPLOYMENT_MODE" = "custom" ]; then
        log "INFO" "检查Docker服务状态..."
        
        if command -v docker-compose &> /dev/null; then
            local services=$(docker-compose -f docker-compose.prod.yml ps --services 2>/dev/null)
        elif docker compose version &> /dev/null; then
            local services=$(docker compose -f docker-compose.prod.yml ps --services 2>/dev/null)
        fi
        
        if [ -n "$services" ]; then
            for service in $services; do
                if command -v docker-compose &> /dev/null; then
                    if docker-compose -f docker-compose.prod.yml ps "$service" 2>/dev/null | grep -q "Up"; then
                        log "SUCCESS" "服务 $service 运行正常"
                    else
                        log "WARNING" "服务 $service 状态异常"
                    fi
                elif docker compose version &> /dev/null; then
                    if docker compose -f docker-compose.prod.yml ps "$service" 2>/dev/null | grep -q "Up"; then
                        log "SUCCESS" "服务 $service 运行正常"
                    else
                        log "WARNING" "服务 $service 状态异常"
                    fi
                fi
            done
        fi
    fi
    
    log "SUCCESS" "部署验证完成"
}

# 显示部署结果
show_deployment_summary() {
    local api_port=8000
    if [ -f "$CONFIG_FILE" ]; then
        api_port=$(grep "API_PORT" "$CONFIG_FILE" | cut -d'=' -f2 2>/dev/null || echo "8000")
    fi
    
    echo
    echo -e "${GREEN}"
    cat << "EOF"
╔══════════════════════════════════════════════════════════════════════════════╗
║                            🎉 部署成功！🎉                                    ║
║                      Fund Platform Deployment Complete                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    echo
    echo -e "${CYAN}=== 访问地址 ===${NC}"
    echo "🌐 API文档:      http://localhost:$api_port/docs"
    echo "❤️  健康检查:    http://localhost:$api_port/health"
    echo "📊 Web管理界面:  streamlit run gui/web_admin.py"
    
    if [ "$DEPLOYMENT_MODE" = "production" ] || [ "$DEPLOYMENT_MODE" = "custom" ]; then
        echo "🗄️  MinIO控制台: http://localhost:9001"
    fi
    
    echo
    echo -e "${CYAN}=== 管理命令 ===${NC}"
    
    if [ "$DEPLOYMENT_MODE" = "production" ] || [ "$DEPLOYMENT_MODE" = "custom" ]; then
        if command -v docker-compose &> /dev/null; then
            echo "查看服务状态: docker-compose -f docker-compose.prod.yml ps"
            echo "查看日志:     docker-compose -f docker-compose.prod.yml logs -f"
            echo "重启服务:     docker-compose -f docker-compose.prod.yml restart"
            echo "停止服务:     docker-compose -f docker-compose.prod.yml down"
        elif docker compose version &> /dev/null; then
            echo "查看服务状态: docker compose -f docker-compose.prod.yml ps"
            echo "查看日志:     docker compose -f docker-compose.prod.yml logs -f"
            echo "重启服务:     docker compose -f docker-compose.prod.yml restart"
            echo "停止服务:     docker compose -f docker-compose.prod.yml down"
        fi
    else
        echo "查看API日志:   tail -f logs/api.log"
        echo "停止服务:     pkill -f uvicorn"
    fi
    
    echo "监控系统:     python scripts/monitor_production.py --single"
    echo "运行测试:     python scripts/run_uat_tests.py"
    
    echo
    echo -e "${CYAN}=== 下一步操作 ===${NC}"
    echo "1. 🔍 访问 http://localhost:$api_port/docs 查看API文档"
    echo "2. 📊 运行 'streamlit run gui/web_admin.py' 启动Web管理界面"
    echo "3. ⚙️  创建数据采集任务开始使用系统"
    echo "4. 📖 查看 docs/ 目录下的详细文档"
    
    echo
    echo -e "${YELLOW}=== 重要文件位置 ===${NC}"
    echo "配置文件:     $CONFIG_FILE"
    echo "部署日志:     $LOG_FILE"
    echo "运维手册:     docs/operations/运维手册.md"
    echo "脚本工具:     scripts/"
    
    if [ "$DEPLOYMENT_MODE" = "production" ] && [ -f "$PROJECT_ROOT/.env.prod" ]; then
        echo
        echo -e "${RED}=== 安全提醒 ===${NC}"
        echo "🔐 请妥善保管 .env.prod 文件中的密码信息"
        echo "🔐 建议定期更换密码和密钥"
        echo "🔐 生产环境请配置防火墙和SSL证书"
    fi
    
    echo
    echo -e "${GREEN}基金报告平台已成功部署并运行！${NC}"
    echo -e "${CYAN}感谢使用我们的平台，如有问题请查看文档或联系技术支持。${NC}"
}

# 错误处理
handle_error() {
    local exit_code=$?
    local line_number=$1
    
    log "ERROR" "部署过程中发生错误 (退出码: $exit_code, 行号: $line_number)"
    
    echo
    echo -e "${RED}=== 部署失败 ===${NC}"
    echo
    echo "故障排查建议："
    echo "1. 查看详细日志: $LOG_FILE"
    echo "2. 检查系统资源: free -h && df -h"
    echo "3. 检查端口占用: ss -tlnp"
    echo "4. 重新运行脚本"
    echo
    echo "如需技术支持，请提供以下信息："
    echo "- 操作系统版本: $(uname -a)"
    echo "- 部署模式: $DEPLOYMENT_MODE"
    echo "- 错误日志: $LOG_FILE"
    
    exit $exit_code
}

# 主函数
main() {
    # 设置错误处理
    trap 'handle_error $LINENO' ERR
    
    # 检查是否在项目根目录
    if [ ! -f "pyproject.toml" ] && [ ! -f "src/api/main.py" ]; then
        log "ERROR" "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 如果没有指定模式，显示欢迎信息
    if [ -z "$DEPLOYMENT_MODE" ]; then
        show_welcome
    fi
    
    # 检查系统环境
    check_system_requirements
    
    # 选择部署模式（如果未指定）
    if [ -z "$DEPLOYMENT_MODE" ]; then
        choose_deployment_mode
    fi
    
    # 配置部署参数
    configure_deployment
    
    # 执行部署
    deploy_system
    
    # 验证部署
    verify_deployment
    
    # 显示部署结果
    show_deployment_summary
}

# 命令行参数处理
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            DEPLOYMENT_MODE="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo
            echo "选项:"
            echo "  --mode MODE     指定部署模式 (development|production|demo|custom)"
            echo "  --config FILE   指定配置文件路径"
            echo "  --help, -h      显示此帮助信息"
            echo
            echo "示例:"
            echo "  $0                    # 交互式部署"
            echo "  $0 --mode production  # 直接指定生产模式"
            exit 0
            ;;
        *)
            log "ERROR" "未知选项: $1"
            exit 1
            ;;
    esac
done

# 运行主函数
main "$@"
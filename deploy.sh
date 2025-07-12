#!/bin/bash
# 一键部署脚本 - 基金报告自动化采集与分析平台
# One-click deployment script for Fund Report Platform

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 命令未找到，请先安装 $1"
        exit 1
    fi
}

# 检查端口是否被占用
check_port() {
    if ss -tlnp | grep -q ":$1 "; then
        log_warning "端口 $1 已被占用，请检查或修改配置"
        read -p "是否继续部署？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 生成随机密码
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# 显示欢迎信息
show_welcome() {
    echo "=================================================="
    echo "基金报告自动化采集与分析平台 - 一键部署脚本"
    echo "Fund Report Platform - One-Click Deployment"
    echo "=================================================="
    echo
}

# 检查系统要求
check_requirements() {
    log_info "检查系统要求..."
    
    # 检查操作系统
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        log_warning "建议在Linux系统上运行此脚本"
    fi
    
    # 检查必要命令
    check_command docker
    check_command docker-compose
    check_command curl
    check_command openssl
    
    # 检查Docker版本
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log_info "Docker版本: $DOCKER_VERSION"
    
    # 检查Docker Compose版本
    COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log_info "Docker Compose版本: $COMPOSE_VERSION"
    
    # 检查系统资源
    MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    if [ $MEMORY_GB -lt 4 ]; then
        log_warning "系统内存少于4GB，建议至少4GB内存"
    fi
    
    DISK_SPACE_GB=$(df -BG . | awk 'NR==2{gsub(/G/,"",$4); print $4}')
    if [ $DISK_SPACE_GB -lt 50 ]; then
        log_warning "可用磁盘空间少于50GB，建议至少50GB空间"
    fi
    
    log_success "系统要求检查完成"
}

# 检查端口占用
check_ports() {
    log_info "检查端口占用情况..."
    
    PORTS=(8000 5432 6379 9000 9001 80 443)
    for port in "${PORTS[@]}"; do
        check_port $port
    done
    
    log_success "端口检查完成"
}

# 配置环境变量
configure_environment() {
    log_info "配置环境变量..."
    
    ENV_FILE=".env.prod"
    
    if [ -f "$ENV_FILE" ]; then
        log_warning "发现现有的环境配置文件 $ENV_FILE"
        read -p "是否使用现有配置？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "使用现有配置文件"
            return
        fi
    fi
    
    log_info "生成新的环境配置..."
    
    # 生成密码
    POSTGRES_PASSWORD=$(generate_password)
    REDIS_PASSWORD=$(generate_password)
    MINIO_ACCESS_KEY="fundadmin"
    MINIO_SECRET_KEY=$(generate_password)
    SECRET_KEY=$(generate_password)
    
    # 创建环境配置文件
    cat > $ENV_FILE << EOF
# 生产环境配置
# 由部署脚本自动生成于 $(date)

# =================
# 数据库配置
# =================
POSTGRES_DB=fundreport_prod
POSTGRES_USER=funduser_prod
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_PORT=5432

# =================
# Redis配置
# =================
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_PORT=6379

# =================
# MinIO配置
# =================
MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY
MINIO_SECRET_KEY=$MINIO_SECRET_KEY
MINIO_BUCKET_NAME=fund-reports-prod
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001

# =================
# 应用配置
# =================
SECRET_KEY=$SECRET_KEY
API_PORT=8000
LOG_LEVEL=INFO

# =================
# Nginx配置
# =================
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
EOF
    
    log_success "环境配置文件已生成: $ENV_FILE"
    
    # 显示生成的密码
    echo
    log_info "重要信息 - 请妥善保存以下凭据:"
    echo "----------------------------------------"
    echo "PostgreSQL 密码: $POSTGRES_PASSWORD"
    echo "Redis 密码: $REDIS_PASSWORD"
    echo "MinIO Access Key: $MINIO_ACCESS_KEY"
    echo "MinIO Secret Key: $MINIO_SECRET_KEY"
    echo "应用密钥: $SECRET_KEY"
    echo "----------------------------------------"
    echo
    
    read -p "请确认已记录上述信息，按回车继续..."
}

# 下载和构建镜像
build_images() {
    log_info "构建Docker镜像..."
    
    # 构建生产镜像
    docker-compose -f docker-compose.prod.yml build --no-cache
    
    log_success "Docker镜像构建完成"
}

# 初始化数据卷
initialize_volumes() {
    log_info "初始化数据卷..."
    
    # 创建必要的目录
    mkdir -p logs data exports reports
    mkdir -p deploy/nginx/ssl
    
    # 设置权限
    chmod 755 logs data exports reports
    
    log_success "数据卷初始化完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    # 启动数据库和Redis
    docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d postgres redis minio
    
    # 等待数据库启动
    log_info "等待数据库启动..."
    for i in {1..30}; do
        if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U $POSTGRES_USER 2>/dev/null; then
            break
        fi
        sleep 2
    done
    
    # 等待Redis启动
    log_info "等待Redis启动..."
    for i in {1..30}; do
        if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
            break
        fi
        sleep 2
    done
    
    # 等待MinIO启动
    log_info "等待MinIO启动..."
    for i in {1..30}; do
        if curl -f http://localhost:9000/minio/health/live 2>/dev/null; then
            break
        fi
        sleep 2
    done
    
    # 启动应用服务
    docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
    
    log_success "所有服务已启动"
}

# 初始化数据库
initialize_database() {
    log_info "初始化数据库..."
    
    # 等待API服务启动
    sleep 10
    
    # 运行数据库迁移
    docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head
    
    log_success "数据库初始化完成"
}

# 验证部署
verify_deployment() {
    log_info "验证部署状态..."
    
    # 检查服务状态
    SERVICES=(postgres redis minio api celery_worker celery_beat)
    for service in "${SERVICES[@]}"; do
        if docker-compose -f docker-compose.prod.yml ps $service | grep -q "Up"; then
            log_success "$service 服务运行正常"
        else
            log_error "$service 服务启动失败"
            docker-compose -f docker-compose.prod.yml logs $service
        fi
    done
    
    # 测试API健康检查
    log_info "测试API健康检查..."
    sleep 5
    
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        log_success "API健康检查通过"
    else
        log_error "API健康检查失败"
        docker-compose -f docker-compose.prod.yml logs api
    fi
    
    # 测试API文档
    if curl -f http://localhost:8000/docs >/dev/null 2>&1; then
        log_success "API文档可访问"
    else
        log_warning "API文档访问失败"
    fi
}

# 显示部署结果
show_deployment_summary() {
    echo
    echo "=================================================="
    echo "部署完成！"
    echo "=================================================="
    echo
    echo "服务访问地址:"
    echo "  • API文档: http://localhost:8000/docs"
    echo "  • API健康检查: http://localhost:8000/health"
    echo "  • MinIO控制台: http://localhost:9001"
    echo
    echo "管理命令:"
    echo "  • 查看服务状态: docker-compose -f docker-compose.prod.yml ps"
    echo "  • 查看日志: docker-compose -f docker-compose.prod.yml logs -f"
    echo "  • 停止服务: docker-compose -f docker-compose.prod.yml stop"
    echo "  • 重启服务: docker-compose -f docker-compose.prod.yml restart"
    echo
    echo "配置文件位置:"
    echo "  • 环境配置: .env.prod"
    echo "  • Docker配置: docker-compose.prod.yml"
    echo "  • 运维手册: docs/operations/运维手册.md"
    echo
    log_success "基金报告自动化采集与分析平台部署成功！"
}

# 错误处理
handle_error() {
    log_error "部署过程中发生错误！"
    echo
    echo "故障排查建议:"
    echo "1. 查看错误日志: docker-compose -f docker-compose.prod.yml logs"
    echo "2. 检查系统资源: free -h && df -h"
    echo "3. 检查端口占用: ss -tlnp"
    echo "4. 重新运行部署脚本"
    echo
    echo "如需技术支持，请联系开发团队。"
    exit 1
}

# 主函数
main() {
    # 设置错误处理
    trap 'handle_error' ERR
    
    # 显示欢迎信息
    show_welcome
    
    # 检查是否在项目根目录
    if [ ! -f "docker-compose.prod.yml" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 确认部署
    echo "此脚本将在当前服务器上部署基金报告自动化采集与分析平台。"
    echo "部署过程将安装和配置以下组件："
    echo "  • PostgreSQL 数据库"
    echo "  • Redis 缓存和消息队列"
    echo "  • MinIO 对象存储"
    echo "  • FastAPI Web服务"
    echo "  • Celery 异步任务处理"
    echo
    read -p "是否继续部署？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "部署已取消"
        exit 0
    fi
    
    # 执行部署步骤
    check_requirements
    check_ports
    configure_environment
    build_images
    initialize_volumes
    start_services
    initialize_database
    verify_deployment
    show_deployment_summary
}

# 如果直接运行脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
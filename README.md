# 公募基金报告自动化采集与分析平台

[![CI/CD Pipeline](https://github.com/user/FundReportScraper/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/user/FundReportScraper/actions)
[![codecov](https://codecov.io/gh/user/FundReportScraper/branch/main/graph/badge.svg)](https://codecov.io/gh/user/FundReportScraper)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

一个自动化采集、解析和分析中国公募基金定期报告的平台，基于 Python 3.10+ 开发，采用现代化微服务架构。

## 🎯 项目特性

- **自动化采集**: 从证监会信息披露平台自动采集基金报告
- **多格式支持**: 支持 XBRL、PDF、HTML 等多种报告格式
- **分布式架构**: 基于 Celery + Redis 的任务队列系统
- **数据持久化**: PostgreSQL 存储结构化数据，MinIO 存储原始文件
- **高质量代码**: 80%+ 测试覆盖率，结构化日志，完整的CI/CD流程
- **RESTful API**: FastAPI 提供高性能的数据查询接口

## 🏗️ 技术架构

### 核心技术栈
- **后端框架**: FastAPI (Python 3.10+)
- **数据库**: PostgreSQL 14+ with SQLAlchemy 2.0
- **任务队列**: Celery + Redis
- **对象存储**: MinIO (S3兼容)
- **HTTP客户端**: httpx (异步支持)
- **数据解析**: arelle (XBRL), lxml, BeautifulSoup4
- **日志系统**: Structlog (结构化JSON日志)
- **测试框架**: Pytest (包含异步测试)
- **容器化**: Docker + Docker Compose

### 系统架构图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  Celery Beat    │    │  Celery Worker  │
│   (API Layer)   │    │  (Scheduler)    │    │  (Task Executor)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │     MinIO       │
│ (Structured DB) │    │ (Message Queue) │    │ (File Storage)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- Poetry (推荐) 或 pip

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd FundReportScraper
```

2. **一键环境设置**
```bash
# 执行自动化设置脚本
./setup_dev.sh
```

3. **手动设置 (可选)**
```bash
# 安装依赖
poetry install

# 复制环境配置
cp .env.example .env

# 启动基础服务
docker-compose -f docker-compose.dev.yml up -d

# 运行数据库迁移
poetry run alembic upgrade head
```

4. **启动应用**
```bash
# 启动FastAPI应用
poetry run uvicorn src.main:app --reload

# 或使用Docker (完整服务)
docker-compose up
```

### 验证安装

```bash
# 运行测试
./run_tests.sh

# 检查API状态
curl http://localhost:8000/health

# 查看API文档
open http://localhost:8000/docs
```

## 📖 使用说明

### API接口

访问 `http://localhost:8000/docs` 查看完整的API文档。

主要接口：
- `GET /health` - 健康检查
- `POST /tasks/scraping` - 创建爬取任务
- `GET /tasks/{task_id}` - 查询任务状态
- `GET /reports` - 查询基金报告
- `GET /funds` - 查询基金列表

### 创建爬取任务示例

```bash
curl -X POST "http://localhost:8000/tasks/scraping" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "2023年年报爬取",
    "target_year": 2023,
    "report_type": "ANNUAL"
  }'
```

### 查询报告数据

```bash
# 查询指定基金的报告
curl "http://localhost:8000/reports?fund_code=000001&year=2023"

# 查询基金列表
curl "http://localhost:8000/funds?search=华夏"
```

## 🛠️ 开发指南

### 代码规范

项目强制执行以下规范：

- **日志记录**: 必须使用 Structlog，禁止 `print()` 语句
- **测试覆盖率**: 核心业务模块不低于 80%
- **代码格式**: Black + isort + Flake8
- **类型检查**: MyPy (建议)

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行特定测试
poetry run pytest tests/unit/test_fund_scraper.py

# 生成覆盖率报告
poetry run pytest --cov=src --cov-report=html
```

### 代码检查

```bash
# 格式化代码
poetry run black src tests

# 排序导入
poetry run isort src tests

# 代码检查
poetry run flake8 src tests

# 类型检查
poetry run mypy src
```

### 数据库迁移

```bash
# 创建新迁移
poetry run alembic revision --autogenerate -m "描述变更"

# 应用迁移
poetry run alembic upgrade head

# 回滚迁移
poetry run alembic downgrade -1
```

## 📊 项目状态

### 开发进度

- ✅ **阶段一 (W1-W3)**: 基础架构与核心爬取功能
  - ✅ 环境搭建和项目初始化
  - ✅ 数据库模型设计
  - ✅ 核心爬虫实现
  - ✅ 文件存储功能
  - ✅ 单元测试 (80%+ 覆盖率)

- 🚧 **阶段二 (W4-W6)**: 数据解析与入库 (计划中)
- 🚧 **阶段三 (W7-W8)**: 任务调度与健壮性 (计划中)
- 🚧 **阶段四 (W9-W10)**: 部署与API (计划中)
- 🚧 **阶段五 (W11-W12)**: 验收与上线 (计划中)

### 当前功能

- ✅ 结构化日志记录
- ✅ HTTP客户端与错误处理
- ✅ 请求频率限制
- ✅ 基金报告列表获取
- ✅ 文件下载与存储
- ✅ RESTful API接口
- ✅ 数据库连接与ORM
- ✅ Docker容器化部署

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交变更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### Pull Request 要求

- 所有测试必须通过
- 代码覆盖率不得降低
- 遵循项目代码规范
- 包含必要的文档更新

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持与联系

- 问题反馈: [GitHub Issues](https://github.com/user/FundReportScraper/issues)
- 技术文档: [项目Wiki](https://github.com/user/FundReportScraper/wiki)
- 邮件联系: dev@example.com

## 🔄 更新日志

### v0.1.0 (2025-07-12)
- ✨ 项目初始化和基础架构搭建
- ✨ 核心爬虫功能实现
- ✨ 数据库模型设计
- ✨ MinIO文件存储集成
- ✨ FastAPI REST接口
- ✨ 完整的测试套件
- ✨ CI/CD流程配置

---

**注意**: 本项目仅用于学习和研究目的，请遵守相关网站的robots.txt和使用条款。
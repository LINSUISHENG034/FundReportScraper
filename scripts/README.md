# 脚本目录说明
## Scripts Directory Overview

本目录包含基金报告自动化采集与分析平台的所有脚本工具，按功能分类组织。

---

## 📁 目录结构

```
scripts/
├── 📁 deployment/          # 部署相关脚本
│   ├── setup_platform.sh   # 🚀 完整引导式部署脚本（主要部署工具）
│   ├── deploy_simple.sh    # ⚡ 简化快速部署脚本
│   ├── test_deployment.sh  # 🧪 部署测试脚本
│   └── start_api.sh        # 🔄 API服务启动脚本
├── 📁 demo/                # 功能演示脚本  
│   ├── show_dual_interface.sh    # 📺 双界面设计展示
│   └── show_improvements.sh      # 💡 用户体验改进展示
├── 📁 analysis/            # 数据分析脚本
├── 📁 demos/               # 功能演示脚本
├── 📁 verification/        # 验证测试脚本
├── 📁 legacy/              # 历史脚本
└── README.md              # 本说明文件
```

### 🚀 部署脚本 (deployment/)

| 脚本文件 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `setup_platform.sh` | 🌟 完整引导式部署脚本 | **主要部署工具**，支持所有模式 |
| `deploy_simple.sh` | ⚡ 简化快速部署脚本 | 开发测试环境快速部署 |
| `test_deployment.sh` | 🧪 部署验证测试 | 验证部署结果和功能 |
| `start_api.sh` | 🔄 API服务启动脚本 | 由部署脚本自动生成 |

### 🎭 演示脚本 (demo/)

| 脚本文件 | 功能说明 | 展示内容 |
|---------|---------|---------|
| `show_dual_interface.sh` | 📺 双界面设计展示 | 用户界面 + 管理后台设计 |
| `show_improvements.sh` | 💡 用户体验改进展示 | 改进前后对比展示 |

### 🔧 核心运维脚本

| 脚本文件 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `run_uat_tests.py` | UAT用户验收测试自动化脚本 | 第五阶段验收测试 |
| `historical_backfill.py` | 历史数据回补脚本 | 数据回补和初始化 |
| `production_deploy.py` | 生产环境部署脚本 | 生产环境部署 |
| `monitor_production.py` | 生产环境监控脚本 | 持续监控和运维 |

### 📊 里程碑验证脚本

| 脚本文件 | 功能说明 | 对应阶段 |
|---------|---------|---------|
| `verify_stage4_milestone.py` | 第四阶段里程碑验证 | 部署与API |
| `verify_stage5_milestone.py` | 第五阶段里程碑验证 | 验收与上线 |

### 📈 分析脚本目录 (`analysis/`)

| 脚本文件 | 功能说明 | 数据来源 |
|---------|---------|---------|
| `collect_pingan_2025_data.py` | 收集平安基金2025年数据 | 官方API |
| `collect_comparable_funds.py` | 收集同类基金对比数据 | 多数据源 |
| `collect_complete_fund_data.py` | 收集完整基金数据 | 综合数据源 |
| `collect_comprehensive_pingan_data.py` | 收集平安基金综合数据 | 官方+第三方 |
| `parse_pingan_html_data.py` | 解析平安基金HTML数据 | 网页数据 |
| `export_to_excel.py` | 数据导出Excel工具 | 数据库 |
| `generate_analysis_report.py` | 生成分析报告 | 处理后数据 |
| `run_automated_analysis.py` | 自动化分析流程 | 全流程 |

### 🎯 演示脚本目录 (`demos/`)

| 脚本文件 | 功能说明 | 演示内容 |
|---------|---------|---------|
| `demonstrate_pingan_fund.py` | 平安基金演示 | 单个基金公司分析 |
| `demonstrate_complete_report.py` | 完整报告演示 | 全面功能展示 |
| `demonstrate_phase3_achievements.py` | 第三阶段成果演示 | 阶段性成果 |

### ✅ 验证脚本目录 (`verification/`)

| 脚本文件 | 功能说明 | 验证范围 |
|---------|---------|---------|
| `verify_phase1.py` | 第一阶段验证 | 基础架构 |
| `verify_phase2_milestone.py` | 第二阶段里程碑验证 | 数据解析 |
| `verify_phase2_structure.py` | 第二阶段结构验证 | 代码结构 |
| `verify_phase3_milestone.py` | 第三阶段里程碑验证 | 任务调度 |
| `verify_phase3_structure.py` | 第三阶段结构验证 | 架构完整性 |
| `test_core_functionality.py` | 核心功能测试 | 关键功能 |

### 📦 历史脚本目录 (`legacy/`)

| 脚本文件 | 功能说明 | 状态 |
|---------|---------|------|
| `run_comprehensive_analysis.py` | 旧版综合分析脚本 | 已弃用 |
| `run_demo_analysis.py` | 旧版演示分析脚本 | 已弃用 |
| `run_ultimate_analysis.py` | 旧版终极分析脚本 | 已弃用 |
| `verify_environment.py` | 环境验证脚本 | 已弃用 |
| `get-pip.py` | pip安装脚本 | 已弃用 |

---

## 🚀 快速使用指南

### 生产环境部署
```bash
# 一键部署生产环境
python scripts/production_deploy.py

# 或者使用shell脚本
./deploy.sh
```

### 用户验收测试
```bash
# 运行完整UAT测试
python scripts/run_uat_tests.py

# 只运行单次检查
python scripts/run_uat_tests.py --single
```

### 历史数据回补
```bash
# 测试模式（只处理前5只基金）
python scripts/historical_backfill.py --test-mode

# 完整回补（2020-2024年）
python scripts/historical_backfill.py

# 指定年份范围
python scripts/historical_backfill.py --start-year 2022 --end-year 2024
```

### 生产环境监控
```bash
# 单次监控检查
python scripts/monitor_production.py --single

# 持续监控（每5分钟）
python scripts/monitor_production.py --interval 300

# 持续监控（限时1小时）
python scripts/monitor_production.py --duration 3600
```

### 里程碑验证
```bash
# 验证第四阶段里程碑
python scripts/verify_stage4_milestone.py

# 验证第五阶段里程碑
python scripts/verify_stage5_milestone.py
```

---

## 🔧 高级用法

### 自定义分析
```bash
# 分析特定基金公司
python scripts/analysis/collect_pingan_2025_data.py

# 生成Excel报告
python scripts/analysis/export_to_excel.py

# 自动化分析流程
python scripts/analysis/run_automated_analysis.py
```

### 功能演示
```bash
# 演示平安基金功能
python scripts/demos/demonstrate_pingan_fund.py

# 演示完整报告功能
python scripts/demos/demonstrate_complete_report.py
```

### 系统验证
```bash
# 核心功能测试
python scripts/verification/test_core_functionality.py

# 阶段性验证
python scripts/verification/verify_phase3_milestone.py
```

---

## 📋 脚本执行顺序建议

### 首次部署流程
1. `production_deploy.py` - 部署生产环境
2. `verify_stage4_milestone.py` - 验证部署成功
3. `historical_backfill.py --test-mode` - 测试数据回补
4. `run_uat_tests.py` - 执行验收测试
5. `verify_stage5_milestone.py` - 验证项目上线

### 日常运维流程
1. `monitor_production.py --single` - 每日健康检查
2. `historical_backfill.py` - 定期数据回补
3. `run_uat_tests.py` - 定期功能验证

### 问题排查流程
1. `monitor_production.py --single` - 检查系统状态
2. `verification/test_core_functionality.py` - 测试核心功能
3. `run_uat_tests.py` - 验证功能完整性

---

## 🛠️ 开发者工具

### 环境设置
- `init_db.sql` - 数据库初始化脚本
- `../setup_dev.sh` - 开发环境设置
- `../run_tests.sh` - 测试执行脚本

### 配置文件
- `../alembic.ini` - 数据库迁移配置
- `../pyproject.toml` - 项目依赖配置
- `../docker-compose.*.yml` - 容器编排配置

---

## 📞 技术支持

如果在使用脚本过程中遇到问题，请：

1. 查看脚本的 `--help` 参数获取详细用法
2. 检查相关日志文件（通常在 `logs/` 目录）
3. 参考 `docs/operations/运维手册.md`
4. 联系技术支持团队

---

**最后更新**: 2025年07月12日  
**维护团队**: 基金报告平台开发组
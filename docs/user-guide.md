# 🎯 用户使用指南
# User Guide

> **5分钟快速上手基金报告自动化采集与分析平台**

---

## 📋 目录

- [🚀 快速开始](#-快速开始)
- [🎮 Web管理界面](#-web管理界面)
- [🔍 数据查询操作](#-数据查询操作)
- [⚙️ 任务管理](#️-任务管理)
- [📊 数据分析](#-数据分析)
- [🛠️ 系统管理](#️-系统管理)
- [❓ 常见问题](#-常见问题)

---

## 🚀 快速开始

### 第一步：系统部署

#### 🎯 选择部署方式

<table>
<tr>
<td width="50%">

**🧪 体验模式（推荐新手）**
```bash
# 一键部署体验版
./setup_platform.sh --mode demo

# 特点：
# ✅ 5分钟快速部署
# ✅ 预装示例数据
# ✅ 资源占用最小
# ✅ 适合功能体验
```

</td>
<td width="50%">

**🚀 正式使用**
```bash
# 完整生产环境
./setup_platform.sh --mode production

# 特点：
# ✅ 完整功能支持
# ✅ 高性能配置
# ✅ 数据持久化
# ✅ 适合正式使用
```

</td>
</tr>
</table>

#### 🔧 部署步骤详解

1. **环境检查**
   ```bash
   # 检查系统要求
   docker --version    # 需要 20.10+
   docker-compose --version  # 需要 2.0+
   python3 --version   # 需要 3.10+
   ```

2. **执行部署**
   ```bash
   # 克隆项目
   git clone <项目地址>
   cd fund-report-platform
   
   # 运行引导式部署
   ./setup_platform.sh
   ```

3. **验证部署**
   ```bash
   # 检查API服务
   curl http://localhost:8000/health
   
   # 输出应该是：
   # {"status": "healthy", "timestamp": "..."}
   ```

### 第二步：访问系统

部署完成后，您可以通过以下方式访问系统：

| 服务 | 地址 | 用途 |
|------|------|------|
| **🌐 API文档** | http://localhost:8000/docs | 查看和测试API接口 |
| **❤️ 健康检查** | http://localhost:8000/health | 系统状态监控 |
| **📊 Web管理界面** | `streamlit run gui/web_admin.py` | 图形化管理界面 |

---

## 🎮 Web管理界面

### 启动Web界面

```bash
# 安装依赖
pip install streamlit plotly pandas

# 启动Web界面
streamlit run gui/web_admin.py

# 访问地址
open http://localhost:8501
```

### 界面功能导览

#### 📊 系统概览页面

<table>
<tr>
<td width="50%">

**🎯 主要信息**
- 系统运行状态
- 基金和报告数量统计
- 任务执行情况
- 系统架构图
- 最近活动记录

</td>
<td width="50%">

**🔍 快速操作**
- 一键健康检查
- 刷新系统数据
- 查看服务状态
- 系统性能监控

</td>
</tr>
</table>

#### 🔍 数据查询页面

**基金信息查询**
1. 选择查询类型：基金信息查询
2. 输入查询条件：
   - 基金代码（可选）
   - 基金类型（全部/股票型/混合型/债券型/货币型）
   - 每页显示数量
3. 点击"🔍 查询基金"
4. 查看结果表格和图表

**报告信息查询**
1. 选择查询类型：报告信息查询
2. 设置筛选条件
3. 查看报告列表和详细信息

#### ⚙️ 任务管理页面

**创建新任务**
1. 切换到"创建任务"标签
2. 填写任务信息：
   ```
   任务类型: collect_reports
   目标基金代码: 
   000001
   000300
   110022
   
   开始日期: 2024-01-01
   结束日期: 2024-12-31
   优先级: high
   任务描述: 年度报告采集任务
   ```
3. 点击"🚀 创建任务"
4. 记录返回的任务ID

**监控任务状态**
1. 切换到"任务列表"标签
2. 查看所有任务的执行状态
3. 点击任务ID查看详细信息

#### 📋 部署向导页面

**新系统部署**
1. 选择部署模式：
   - 🧪 开发环境：学习和测试
   - 🚀 生产环境：正式使用
   - 🔧 自定义配置：高级选项

2. 配置系统参数：
   - 数据库密码
   - API端口
   - SSL证书（生产环境）

3. 执行一键部署

4. 查看部署进度和结果

---

## 🔍 数据查询操作

### API接口查询

#### 🏥 系统健康检查

```bash
# 检查系统状态
curl http://localhost:8000/health

# 响应示例
{
  "status": "healthy",
  "timestamp": "2025-07-12T20:30:00",
  "version": "1.0.0",
  "uptime": "2 hours 15 minutes"
}
```

#### 📊 基金信息查询

**获取基金列表**
```bash
# 基础查询
curl "http://localhost:8000/api/v1/funds/"

# 带筛选条件
curl "http://localhost:8000/api/v1/funds/" \
  -G \
  -d "fund_type=股票型" \
  -d "page=1" \
  -d "page_size=20"

# 搜索特定基金
curl "http://localhost:8000/api/v1/funds/" \
  -G \
  -d "fund_code=000001"
```

**查询基金详细信息**
```bash
# 获取基金详情
curl "http://localhost:8000/api/v1/funds/000001"

# 响应示例
{
  "success": true,
  "data": {
    "fund_code": "000001",
    "fund_name": "华夏成长混合",
    "fund_type": "混合型",
    "management_company": "华夏基金管理有限公司",
    "fund_manager": "张三",
    "establish_date": "2001-12-18",
    "total_asset": 12500000000,
    "nav_info": {
      "latest_nav": 1.2345,
      "nav_date": "2025-07-11",
      "accumulated_nav": 2.3456
    }
  }
}
```

**获取净值历史**
```bash
# 查询净值历史
curl "http://localhost:8000/api/v1/funds/000001/nav-history" \
  -G \
  -d "start_date=2024-01-01" \
  -d "end_date=2024-12-31"
```

#### 📄 报告信息查询

**获取报告列表**
```bash
# 基础查询
curl "http://localhost:8000/api/v1/reports/"

# 按基金筛选
curl "http://localhost:8000/api/v1/reports/" \
  -G \
  -d "fund_code=000001" \
  -d "report_year=2024"
```

**获取最新报告**
```bash
# 获取基金最新报告
curl "http://localhost:8000/api/v1/reports/fund/000001/latest"
```

**获取重仓股信息**
```bash
# 查询重仓股历史
curl "http://localhost:8000/api/v1/reports/fund/000001/holdings" \
  -G \
  -d "report_type=quarterly"
```

### Python脚本查询

```python
import requests

# API基础地址
BASE_URL = "http://localhost:8000"

# 查询基金信息
def get_fund_info(fund_code):
    url = f"{BASE_URL}/api/v1/funds/{fund_code}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data['success']:
            return data['data']
    return None

# 使用示例
fund_info = get_fund_info("000001")
if fund_info:
    print(f"基金名称: {fund_info['fund_name']}")
    print(f"基金类型: {fund_info['fund_type']}")
    print(f"最新净值: {fund_info['nav_info']['latest_nav']}")
```

---

## ⚙️ 任务管理

### 创建数据采集任务

#### 📥 单只基金采集

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "collect_reports",
    "target_fund_codes": ["000001"],
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    },
    "priority": "high",
    "description": "华夏成长混合年度报告采集"
  }'
```

#### 📥 批量基金采集

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "collect_reports",
    "target_fund_codes": ["000001", "000300", "110022"],
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    },
    "priority": "medium",
    "description": "热门基金批量采集任务"
  }'
```

#### 📊 净值更新任务

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "update_nav",
    "target_fund_codes": ["000001"],
    "priority": "high",
    "description": "净值数据实时更新"
  }'
```

### 任务状态监控

#### 📋 查询任务列表

```bash
# 获取所有任务
curl "http://localhost:8000/api/v1/tasks/"

# 按状态筛选
curl "http://localhost:8000/api/v1/tasks/" \
  -G \
  -d "status=running"
```

#### 🔍 查询特定任务

```bash
# 查询任务详情
curl "http://localhost:8000/api/v1/tasks/{task_id}"

# 响应示例
{
  "success": true,
  "data": {
    "task_id": "task_12345",
    "task_type": "collect_reports",
    "status": "completed",
    "progress": 100,
    "created_at": "2025-07-12T10:00:00",
    "started_at": "2025-07-12T10:01:00",
    "completed_at": "2025-07-12T10:15:00",
    "result": {
      "total_funds": 3,
      "successful_funds": 3,
      "failed_funds": 0,
      "total_reports": 12,
      "execution_time": "14 minutes"
    }
  }
}
```

#### ⏹️ 任务控制操作

```bash
# 取消任务
curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/cancel"

# 删除任务
curl -X DELETE "http://localhost:8000/api/v1/tasks/{task_id}"
```

### 定时任务配置

定时任务通过Celery Beat自动管理，默认配置：

| 任务类型 | 执行频率 | 说明 |
|---------|---------|------|
| **净值更新** | 每日 09:00 | 更新所有基金净值 |
| **报告检查** | 每周一 02:00 | 检查新发布报告 |
| **数据清理** | 每月1日 01:00 | 清理过期临时数据 |
| **健康检查** | 每小时 | 系统健康状态检查 |

---

## 📊 数据分析

### 基金业绩分析

#### 📈 净值趋势分析

```bash
# 获取净值历史数据
curl "http://localhost:8000/api/v1/funds/000001/nav-history" \
  -G \
  -d "start_date=2024-01-01" \
  -d "end_date=2024-12-31"

# 分析数据示例
{
  "success": true,
  "data": {
    "fund_code": "000001",
    "nav_data": [
      {
        "nav_date": "2024-01-01",
        "nav": 1.2000,
        "accumulated_nav": 2.3000
      },
      {
        "nav_date": "2024-01-02", 
        "nav": 1.2050,
        "accumulated_nav": 2.3050
      }
    ],
    "statistics": {
      "return_ytd": 0.125,    // 年初至今收益率
      "return_1m": 0.025,     // 近1月收益率
      "return_3m": 0.045,     // 近3月收益率
      "volatility": 0.156,    // 波动率
      "max_drawdown": -0.089  // 最大回撤
    }
  }
}
```

#### 🏢 持仓分析

```bash
# 获取重仓股信息
curl "http://localhost:8000/api/v1/reports/fund/000001/holdings"

# 响应数据
{
  "success": true,
  "data": {
    "report_date": "2024-12-31",
    "top_holdings": [
      {
        "stock_code": "000858",
        "stock_name": "五粮液",
        "holding_ratio": 8.52,
        "holding_shares": 12500000,
        "market_value": 2125000000
      }
    ],
    "industry_allocation": [
      {
        "industry_name": "食品饮料",
        "allocation_ratio": 25.6
      }
    ]
  }
}
```

### 对比分析

#### 📊 同类基金对比

```python
import requests
import pandas as pd

def compare_funds(fund_codes):
    """对比多只基金的业绩"""
    results = []
    
    for code in fund_codes:
        url = f"http://localhost:8000/api/v1/funds/{code}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()['data']
            results.append({
                'fund_code': code,
                'fund_name': data['fund_name'],
                'latest_nav': data['nav_info']['latest_nav'],
                'fund_type': data['fund_type']
            })
    
    return pd.DataFrame(results)

# 使用示例
fund_comparison = compare_funds(['000001', '000300', '110022'])
print(fund_comparison)
```

### 数据导出

#### 📥 Excel报告导出

```bash
# 导出基金数据到Excel
python scripts/analysis/export_to_excel.py \
  --fund_codes 000001,000300 \
  --output reports/fund_analysis.xlsx
```

#### 📊 生成分析报告

```bash
# 生成完整分析报告
python scripts/analysis/generate_analysis_report.py \
  --fund_code 000001 \
  --report_type comprehensive
```

---

## 🛠️ 系统管理

### 系统监控

#### 📊 监控命令

```bash
# 单次系统检查
python scripts/monitor_production.py --single

# 持续监控（每5分钟）
python scripts/monitor_production.py --interval 300

# 查看监控报告
ls reports/监控报告_*
```

#### 🔍 系统状态检查

```bash
# 检查Docker服务
docker-compose -f docker-compose.prod.yml ps

# 查看服务日志
docker-compose -f docker-compose.prod.yml logs -f api

# 检查数据库连接
docker-compose -f docker-compose.prod.yml exec postgres psql -U funduser_prod -d fundreport_prod -c "SELECT COUNT(*) FROM funds;"
```

### 数据备份

#### 💾 数据库备份

```bash
# 备份数据库
docker-compose -f docker-compose.prod.yml exec postgres pg_dump \
  -U funduser_prod -d fundreport_prod > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker-compose -f docker-compose.prod.yml exec -T postgres psql \
  -U funduser_prod -d fundreport_prod < backup_20250712.sql
```

#### 📁 文件备份

```bash
# 备份MinIO数据
docker-compose -f docker-compose.prod.yml exec minio mc mirror \
  /data/fund-reports backup/minio/

# 备份配置文件
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  .env.prod docker-compose.prod.yml
```

### 系统更新

#### 🔄 代码更新

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose -f docker-compose.prod.yml build

# 重启服务
docker-compose -f docker-compose.prod.yml up -d
```

#### 📊 数据库迁移

```bash
# 运行数据库迁移
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# 检查迁移状态
docker-compose -f docker-compose.prod.yml exec api alembic current
```

---

## ❓ 常见问题

### 🚨 部署问题

**Q: 部署脚本执行失败怎么办？**

A: 按以下步骤排查：
```bash
# 1. 检查系统要求
docker --version
docker-compose --version
python3 --version

# 2. 检查端口占用
ss -tlnp | grep -E ":(8000|5432|6379|9000)"

# 3. 查看详细错误日志
tail -f logs/deployment_*.log

# 4. 清理并重试
docker-compose down
docker system prune -a
./setup_platform.sh
```

**Q: API服务无法访问？**

A: 检查以下项目：
```bash
# 检查服务状态
curl http://localhost:8000/health

# 查看API日志
docker-compose logs api

# 检查防火墙设置
sudo ufw status

# 重启API服务
docker-compose restart api
```

### 📊 数据问题

**Q: 基金数据为空？**

A: 可能原因和解决方案：
```bash
# 1. 检查数据库连接
docker-compose exec postgres psql -U funduser_prod -c "\dt"

# 2. 运行数据采集任务
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{"task_type": "collect_reports", "target_fund_codes": ["000001"]}'

# 3. 加载示例数据（测试用）
python scripts/demos/load_sample_data.py
```

**Q: 数据更新不及时？**

A: 检查定时任务：
```bash
# 查看Celery Beat状态
docker-compose logs celery_beat

# 手动触发更新
curl -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{"task_type": "update_nav", "priority": "high"}'
```

### 🔧 性能问题

**Q: API响应很慢？**

A: 性能优化建议：
```bash
# 1. 检查系统资源
free -h
df -h
top

# 2. 优化数据库查询
docker-compose exec postgres psql -U funduser_prod -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;"

# 3. 启用Redis缓存
# 在.env.prod中添加：
# ENABLE_CACHE=true
# CACHE_TTL=3600
```

### 🛡️ 安全问题

**Q: 如何修改默认密码？**

A: 修改配置文件：
```bash
# 1. 生成新密码
openssl rand -base64 32 | tr -d "=+/" | cut -c1-25

# 2. 更新.env.prod文件
nano .env.prod

# 3. 重启服务
docker-compose down
docker-compose up -d
```

**Q: 如何启用SSL？**

A: SSL配置步骤：
```bash
# 1. 获取SSL证书
# 使用Let's Encrypt或购买证书

# 2. 配置Nginx
# 编辑deploy/nginx/nginx.conf

# 3. 更新环境变量
ENABLE_SSL=true
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem

# 4. 重启服务
docker-compose up -d
```

### 🆘 获取更多帮助

| 问题类型 | 联系方式 |
|---------|---------|
| **📚 查看文档** | [docs/](../docs/) 目录 |
| **🐛 报告Bug** | [GitHub Issues](https://github.com/your-org/fund-report-platform/issues) |
| **💬 社区讨论** | [GitHub Discussions](https://github.com/your-org/fund-report-platform/discussions) |
| **📧 技术支持** | tech-support@example.com |

---

<div align="center">

## 🎉 恭喜！您已经掌握了基金报告平台的使用方法

**下一步建议：**
- 🚀 开始创建您的第一个数据采集任务
- 📊 探索数据分析和可视化功能
- 🔧 根据需要调整系统配置
- 📚 深入阅读技术文档

**📞 需要帮助？** 查看 [FAQ](../docs/faq.md) 或联系技术支持

---

*最后更新: 2025年07月12日*  
*版本: v1.0.0*

</div>
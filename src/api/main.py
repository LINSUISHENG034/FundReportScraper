"""
FastAPI application main entry point.
基金报告数据查询API主入口。
"""

from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn

from src.core.config import get_settings
from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.api.routes import funds, reports, tasks
from src.api.schemas import FundResponse, ReportResponse, HealthResponse

logger = get_logger(__name__)
settings = get_settings()

# 创建FastAPI应用实例
app = FastAPI(
    title="基金报告自动化采集与分析平台 API",
    description="Fund Report Automated Collection and Analysis Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(funds.router, prefix="/api/v1/funds", tags=["基金信息"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告数据"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])


@app.get("/health", response_model=HealthResponse, tags=["系统健康"])
async def health_check():
    """
    系统健康检查接口
    Health check endpoint
    """
    try:
        # 检查数据库连接
        db = next(get_db_session())
        db.execute("SELECT 1")
        db_status = "healthy"
        
    except Exception as e:
        logger.error("health_check.database_error", error=str(e))
        db_status = "unhealthy"
    
    status = "healthy" if db_status == "healthy" else "unhealthy"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.version,
        services={
            "database": db_status,
            "api": "healthy"
        }
    )


@app.get("/", response_class=HTMLResponse, tags=["根路径"])
async def root():
    """
    用户主界面 - 基金报告查询和分析平台
    User-friendly interface for fund report queries and analysis
    """
    
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>基金报告查询平台 - 让投资更智能</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 1rem;
            }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 2rem;
                padding: 2rem 0;
            }
            .header h1 {
                font-size: 2.8rem;
                margin-bottom: 0.5rem;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .header p {
                font-size: 1.3rem;
                opacity: 0.9;
                margin-bottom: 1rem;
            }
            .header .subtitle {
                font-size: 1rem;
                opacity: 0.8;
            }
            .main-content {
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.1);
                overflow: hidden;
                margin-bottom: 2rem;
            }
            .nav-tabs {
                display: flex;
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            .nav-tab {
                flex: 1;
                padding: 1rem 2rem;
                text-align: center;
                cursor: pointer;
                border: none;
                background: transparent;
                font-size: 1.1rem;
                font-weight: 500;
                color: #666;
                transition: all 0.3s ease;
            }
            .nav-tab.active {
                background: white;
                color: #667eea;
                border-bottom: 3px solid #667eea;
            }
            .nav-tab:hover {
                background: #e9ecef;
                color: #495057;
            }
            .tab-content {
                padding: 2rem;
                min-height: 500px;
            }
            .tab-pane {
                display: none;
            }
            .tab-pane.active {
                display: block;
            }
            .search-section {
                background: #f8f9fa;
                border-radius: 10px;
                padding: 2rem;
                margin-bottom: 2rem;
            }
            .search-form {
                display: grid;
                grid-template-columns: 1fr 1fr auto;
                gap: 1rem;
                align-items: end;
            }
            .form-group {
                display: flex;
                flex-direction: column;
            }
            .form-group label {
                margin-bottom: 0.5rem;
                font-weight: 500;
                color: #495057;
            }
            .form-control {
                padding: 0.8rem;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                font-size: 1rem;
                transition: border-color 0.3s ease;
            }
            .form-control:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            .btn {
                padding: 0.8rem 2rem;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1rem;
                font-weight: 500;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .btn-secondary {
                background: #6c757d;
            }
            .btn-success {
                background: #28a745;
            }
            .results-section {
                margin-top: 2rem;
            }
            .fund-card {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 1.5rem;
                margin-bottom: 1rem;
                transition: all 0.3s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .fund-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                border-color: #667eea;
            }
            .fund-header {
                display: flex;
                justify-content: between;
                align-items: center;
                margin-bottom: 1rem;
            }
            .fund-name {
                font-size: 1.3rem;
                font-weight: 600;
                color: #333;
                margin-bottom: 0.5rem;
            }
            .fund-code {
                font-size: 1rem;
                color: #666;
                background: #f8f9fa;
                padding: 0.2rem 0.8rem;
                border-radius: 15px;
                display: inline-block;
            }
            .fund-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin: 1rem 0;
            }
            .fund-detail {
                text-align: center;
                padding: 1rem;
                background: #f8f9fa;
                border-radius: 8px;
            }
            .detail-label {
                font-size: 0.9rem;
                color: #666;
                margin-bottom: 0.5rem;
            }
            .detail-value {
                font-size: 1.2rem;
                font-weight: 600;
                color: #333;
            }
            .fund-actions {
                display: flex;
                gap: 1rem;
                margin-top: 1rem;
            }
            .loading {
                text-align: center;
                padding: 3rem;
                color: #666;
            }
            .spinner {
                display: inline-block;
                width: 40px;
                height: 40px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 1rem;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .quick-actions {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 1rem;
                margin-bottom: 2rem;
            }
            .quick-action {
                background: white;
                border-radius: 10px;
                padding: 1.5rem;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
                cursor: pointer;
            }
            .quick-action:hover {
                transform: translateY(-3px);
            }
            .quick-action .icon {
                font-size: 2.5rem;
                margin-bottom: 1rem;
            }
            .admin-link {
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 0.8rem 1.5rem;
                border-radius: 25px;
                text-decoration: none;
                font-size: 0.9rem;
                transition: all 0.3s ease;
                z-index: 1000;
            }
            .admin-link:hover {
                background: rgba(0,0,0,0.9);
                transform: translateY(-2px);
            }
            @media (max-width: 768px) {
                .search-form {
                    grid-template-columns: 1fr;
                }
                .fund-details {
                    grid-template-columns: 1fr 1fr;
                }
                .fund-actions {
                    flex-direction: column;
                }
                .header h1 { font-size: 2rem; }
                .container { padding: 0.5rem; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 基金报告查询平台</h1>
                <p>专业的基金数据分析工具</p>
                <div class="subtitle">让每一次投资决策都有数据支撑</div>
            </div>
            
            <div class="main-content">
                <div class="nav-tabs">
                    <button class="nav-tab active" onclick="showTab('search')">🔍 基金搜索</button>
                    <button class="nav-tab" onclick="showTab('reports')">📊 报告分析</button>
                    <button class="nav-tab" onclick="showTab('tasks')">⚙️ 数据采集</button>
                    <button class="nav-tab" onclick="showTab('tools')">🛠️ 实用工具</button>
                </div>
                
                <!-- 基金搜索标签页 -->
                <div id="search-tab" class="tab-pane active">
                    <div class="search-section">
                        <h3 style="margin-bottom: 1rem;">🎯 智能基金搜索</h3>
                        <div class="search-form">
                            <div class="form-group">
                                <label for="fundCode">基金代码/名称</label>
                                <input type="text" id="fundCode" class="form-control" placeholder="输入基金代码或名称，如：000001">
                            </div>
                            <div class="form-group">
                                <label for="fundType">基金类型</label>
                                <select id="fundType" class="form-control">
                                    <option value="">全部类型</option>
                                    <option value="股票型">股票型</option>
                                    <option value="混合型">混合型</option>
                                    <option value="债券型">债券型</option>
                                    <option value="货币型">货币型</option>
                                    <option value="指数型">指数型</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <button class="btn" onclick="searchFunds()">🔍 搜索基金</button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="quick-actions">
                        <div class="quick-action" onclick="quickSearch('热门基金')">
                            <div class="icon">🔥</div>
                            <h4>热门基金</h4>
                            <p>查看当前最受关注的基金</p>
                        </div>
                        <div class="quick-action" onclick="quickSearch('新发基金')">
                            <div class="icon">✨</div>
                            <h4>新发基金</h4>
                            <p>最新成立的基金产品</p>
                        </div>
                        <div class="quick-action" onclick="quickSearch('高分红基金')">
                            <div class="icon">💰</div>
                            <h4>高分红基金</h4>
                            <p>分红收益较高的基金</p>
                        </div>
                    </div>
                    
                    <div id="searchResults" class="results-section">
                        <div style="text-align: center; padding: 3rem; color: #666;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                            <h3>开始搜索基金</h3>
                            <p>输入基金代码或名称，获取详细的基金信息和报告分析</p>
                        </div>
                    </div>
                </div>
                
                <!-- 报告分析标签页 -->
                <div id="reports-tab" class="tab-pane">
                    <h3>📊 基金报告分析</h3>
                    <div class="search-section">
                        <h4>选择基金获取报告</h4>
                        <div class="search-form">
                            <div class="form-group">
                                <label for="reportFundCode">基金代码</label>
                                <input type="text" id="reportFundCode" class="form-control" placeholder="输入基金代码">
                            </div>
                            <div class="form-group">
                                <label for="reportType">报告类型</label>
                                <select id="reportType" class="form-control">
                                    <option value="all">全部报告</option>
                                    <option value="annual">年度报告</option>
                                    <option value="quarterly">季度报告</option>
                                    <option value="interim">中期报告</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <button class="btn" onclick="getReports()">📄 获取报告</button>
                            </div>
                        </div>
                    </div>
                    <div id="reportsResults"></div>
                </div>
                
                <!-- 数据采集标签页 -->
                <div id="tasks-tab" class="tab-pane">
                    <h3>⚙️ 数据采集任务</h3>
                    <div class="search-section">
                        <h4>创建数据采集任务</h4>
                        <div class="form-group" style="margin-bottom: 1rem;">
                            <label for="taskFundCodes">目标基金代码（每行一个）</label>
                            <textarea id="taskFundCodes" class="form-control" rows="4" placeholder="000001&#10;000300&#10;110022"></textarea>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 1rem;">
                            <div class="form-group">
                                <label for="startDate">开始日期</label>
                                <input type="date" id="startDate" class="form-control">
                            </div>
                            <div class="form-group">
                                <label for="endDate">结束日期</label>
                                <input type="date" id="endDate" class="form-control">
                            </div>
                            <div class="form-group">
                                <label for="priority">优先级</label>
                                <select id="priority" class="form-control">
                                    <option value="medium">普通</option>
                                    <option value="high">高</option>
                                    <option value="low">低</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <button class="btn btn-success" onclick="createTask()">🚀 开始采集</button>
                            </div>
                        </div>
                    </div>
                    <div id="taskResults"></div>
                </div>
                
                <!-- 实用工具标签页 -->
                <div id="tools-tab" class="tab-pane">
                    <h3>🛠️ 实用工具</h3>
                    <div class="quick-actions">
                        <div class="quick-action" onclick="checkSystemHealth()">
                            <div class="icon">🏥</div>
                            <h4>系统健康检查</h4>
                            <p>检查平台运行状态</p>
                        </div>
                        <div class="quick-action" onclick="window.open('/docs')">
                            <div class="icon">📖</div>
                            <h4>API文档</h4>
                            <p>查看完整的接口文档</p>
                        </div>
                        <div class="quick-action" onclick="downloadSample()">
                            <div class="icon">📥</div>
                            <h4>示例数据</h4>
                            <p>下载示例基金数据</p>
                        </div>
                        <div class="quick-action" onclick="openWebAdmin()">
                            <div class="icon">🎮</div>
                            <h4>Web管理界面</h4>
                            <p>启动Streamlit管理界面</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <a href="/admin" class="admin-link">🛠️ 管理后台</a>
        
        <script>
            // 标签页切换
            function showTab(tabName) {
                // 隐藏所有标签页
                document.querySelectorAll('.tab-pane').forEach(pane => {
                    pane.classList.remove('active');
                });
                document.querySelectorAll('.nav-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // 显示目标标签页
                document.getElementById(tabName + '-tab').classList.add('active');
                event.target.classList.add('active');
            }
            
            // 基金搜索
            async function searchFunds() {
                const fundCode = document.getElementById('fundCode').value;
                const fundType = document.getElementById('fundType').value;
                const resultsDiv = document.getElementById('searchResults');
                
                resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>正在搜索基金...</p></div>';
                
                try {
                    let url = '/api/v1/funds/?';
                    if (fundCode) url += `fund_code=${fundCode}&`;
                    if (fundType) url += `fund_type=${fundType}&`;
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    if (data.success && data.data.items && data.data.items.length > 0) {
                        displayFunds(data.data.items);
                    } else {
                        resultsDiv.innerHTML = '<div style="text-align: center; padding: 3rem;"><h3>未找到相关基金</h3><p>请尝试调整搜索条件</p></div>';
                    }
                } catch (error) {
                    resultsDiv.innerHTML = '<div style="text-align: center; padding: 3rem; color: red;"><h3>搜索失败</h3><p>请检查网络连接或稍后重试</p></div>';
                }
            }
            
            // 显示基金列表
            function displayFunds(funds) {
                const resultsDiv = document.getElementById('searchResults');
                let html = '<h3>搜索结果</h3>';
                
                funds.forEach(fund => {
                    html += `
                        <div class="fund-card">
                            <div class="fund-header">
                                <div>
                                    <div class="fund-name">${fund.fund_name || '未知基金'}</div>
                                    <span class="fund-code">${fund.fund_code}</span>
                                </div>
                            </div>
                            <div class="fund-details">
                                <div class="fund-detail">
                                    <div class="detail-label">基金类型</div>
                                    <div class="detail-value">${fund.fund_type || '-'}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">管理公司</div>
                                    <div class="detail-value">${fund.management_company || '-'}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">基金经理</div>
                                    <div class="detail-value">${fund.fund_manager || '-'}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">成立日期</div>
                                    <div class="detail-value">${fund.establish_date || '-'}</div>
                                </div>
                            </div>
                            <div class="fund-actions">
                                <button class="btn" onclick="getFundDetails('${fund.fund_code}')">📊 详细信息</button>
                                <button class="btn btn-secondary" onclick="getFundReports('${fund.fund_code}')">📄 获取报告</button>
                                <button class="btn btn-success" onclick="addToTask('${fund.fund_code}')">➕ 添加到采集</button>
                            </div>
                        </div>
                    `;
                });
                
                resultsDiv.innerHTML = html;
            }
            
            // 快速搜索
            function quickSearch(type) {
                document.getElementById('fundCode').value = '';
                if (type === '热门基金') {
                    document.getElementById('fundType').value = '股票型';
                } else if (type === '新发基金') {
                    document.getElementById('fundType').value = '';
                } else if (type === '高分红基金') {
                    document.getElementById('fundType').value = '混合型';
                }
                searchFunds();
            }
            
            // 其他功能
            function getFundDetails(fundCode) {
                alert(`正在获取基金 ${fundCode} 的详细信息...\\n\\n功能开发中，敬请期待！`);
            }
            
            function getFundReports(fundCode) {
                document.getElementById('reportFundCode').value = fundCode;
                showTab('reports');
            }
            
            function addToTask(fundCode) {
                const textarea = document.getElementById('taskFundCodes');
                const currentValue = textarea.value;
                const newValue = currentValue ? currentValue + '\\n' + fundCode : fundCode;
                textarea.value = newValue;
                showTab('tasks');
            }
            
            function getReports() {
                alert('报告获取功能开发中，敬请期待！');
            }
            
            function createTask() {
                alert('数据采集任务创建功能开发中，敬请期待！');
            }
            
            function checkSystemHealth() {
                window.open('/health', '_blank');
            }
            
            function downloadSample() {
                alert('示例数据下载功能开发中，敬请期待！');
            }
            
            function openWebAdmin() {
                alert('请运行以下命令启动Web管理界面:\\n\\nstreamlit run gui/web_admin.py\\n\\n然后访问: http://localhost:8501');
            }
            
            // 设置默认日期
            document.addEventListener('DOMContentLoaded', function() {
                const today = new Date();
                const lastYear = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
                
                document.getElementById('startDate').value = lastYear.toISOString().split('T')[0];
                document.getElementById('endDate').value = today.toISOString().split('T')[0];
            });
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@app.get("/admin", response_class=HTMLResponse, tags=["管理后台"])
async def admin():
    """
    管理后台界面 - 面向开发者和系统管理员
    Admin dashboard for developers and system administrators
    """
    
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管理后台 - 基金报告平台</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 3rem;
            }
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .header p {
                font-size: 1.2rem;
                opacity: 0.9;
            }
            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 2rem;
                margin-bottom: 2rem;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 2rem;
                text-align: center;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 12px 40px rgba(0,0,0,0.2);
            }
            .card .icon {
                font-size: 3rem;
                margin-bottom: 1rem;
            }
            .card h3 {
                color: #333;
                margin-bottom: 1rem;
                font-size: 1.5rem;
            }
            .card p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 1.5rem;
            }
            .btn {
                display: inline-block;
                padding: 0.8rem 2rem;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                text-decoration: none;
                border-radius: 25px;
                transition: all 0.3s ease;
                font-weight: 500;
                border: none;
                cursor: pointer;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .user-link {
                position: fixed;
                bottom: 2rem;
                left: 2rem;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 0.8rem 1.5rem;
                border-radius: 25px;
                text-decoration: none;
                font-size: 0.9rem;
                transition: all 0.3s ease;
                z-index: 1000;
            }
            .user-link:hover {
                background: rgba(0,0,0,0.9);
                transform: translateY(-2px);
            }
            .status {
                background: rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                text-align: center;
                margin-top: 2rem;
            }
            .status-item {
                display: inline-block;
                margin: 0 1rem;
                padding: 0.5rem 1rem;
                background: rgba(255,255,255,0.2);
                border-radius: 20px;
                font-size: 0.9rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛠️ 系统管理后台</h1>
                <p>Fund Report Platform - Admin Dashboard</p>
            </div>
            
            <div class="cards">
                <div class="card">
                    <div class="icon">📖</div>
                    <h3>API 文档</h3>
                    <p>完整的REST API接口文档，支持在线测试和调试。查看所有可用的端点和参数。</p>
                    <a href="/docs" class="btn">查看文档</a>
                </div>
                
                <div class="card">
                    <div class="icon">🏥</div>
                    <h3>系统健康</h3>
                    <p>实时查看系统运行状态，包括数据库连接、API服务和各项系统指标。</p>
                    <a href="/health" class="btn">健康检查</a>
                </div>
                
                <div class="card">
                    <div class="icon">📊</div>
                    <h3>基金数据</h3>
                    <p>管理基金信息、净值历史、持仓数据等。支持批量操作和数据导入导出。</p>
                    <a href="/docs#/基金信息" class="btn">数据管理</a>
                </div>
                
                <div class="card">
                    <div class="icon">📄</div>
                    <h3>报告管理</h3>
                    <p>管理基金定期报告、年报、季报等数据，监控数据质量和完整性。</p>
                    <a href="/docs#/报告数据" class="btn">报告管理</a>
                </div>
                
                <div class="card">
                    <div class="icon">⚙️</div>
                    <h3>任务调度</h3>
                    <p>管理数据采集任务，监控任务执行状态，配置定时任务和优先级。</p>
                    <a href="/docs#/任务管理" class="btn">任务管理</a>
                </div>
                
                <div class="card">
                    <div class="icon">🎮</div>
                    <h3>Web 管理</h3>
                    <p>启动Streamlit管理界面，提供图形化的系统管理和数据分析功能。</p>
                    <a href="#" onclick="openWebAdmin()" class="btn">启动界面</a>
                </div>
            </div>
            
            <div class="status">
                <h3>🚀 系统状态</h3>
                <div style="margin-top: 1rem;">
                    <span class="status-item">✅ API 服务运行中</span>
                    <span class="status-item">📅 最后更新: <span id="timestamp"></span></span>
                    <span class="status-item">🔄 版本: v1.0.0</span>
                </div>
            </div>
        </div>
        
        <a href="/" class="user-link">👤 用户界面</a>
        
        <script>
            // 更新时间戳
            document.getElementById('timestamp').textContent = new Date().toLocaleString('zh-CN');
            
            // Web管理界面提示
            function openWebAdmin() {
                alert('请运行以下命令启动Web管理界面:\\n\\nstreamlit run gui/web_admin.py\\n\\n然后访问: http://localhost:8501');
            }
            
            // 定期检查API状态
            setInterval(async () => {
                try {
                    const response = await fetch('/health');
                    const data = await response.json();
                    document.getElementById('timestamp').textContent = new Date().toLocaleString('zh-CN');
                } catch (error) {
                    console.log('健康检查失败:', error);
                }
            }, 30000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """
    404错误处理器
    404 error handler
    """
    return JSONResponse(
        status_code=404,
        content={
            "detail": "请求的资源不存在",
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """
    500错误处理器
    500 error handler
    """
    logger.error("internal_server_error", 
                path=str(request.url.path), 
                error=str(exc))
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# 启动事件
@app.on_event("startup")
async def startup_event():
    """
    应用启动事件
    Application startup event
    """
    logger.info("fastapi_app.startup", 
               app_name=settings.name,
               version=settings.version,
               debug=settings.debug)


# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """
    应用关闭事件
    Application shutdown event
    """
    logger.info("fastapi_app.shutdown")


if __name__ == "__main__":
    # 开发环境直接运行
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
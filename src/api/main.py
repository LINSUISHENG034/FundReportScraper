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
            .modal {
                display: none;
                position: fixed;
                z-index: 2000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
            }
            .modal-content {
                background-color: #fefefe;
                margin: 5% auto;
                padding: 0;
                border-radius: 15px;
                width: 90%;
                max-width: 800px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            .modal-header {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 1.5rem 2rem;
                border-radius: 15px 15px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .modal-body {
                padding: 2rem;
            }
            .close {
                color: white;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
                opacity: 0.8;
                transition: opacity 0.3s ease;
            }
            .close:hover {
                opacity: 1;
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
                    <button class="nav-tab" onclick="showTab('data')">📊 数据中心</button>
                    <button class="nav-tab" onclick="showTab('reports')">📄 报告分析</button>
                    <button class="nav-tab" onclick="showTab('tasks')">⚙️ 数据采集</button>
                    <button class="nav-tab" onclick="showTab('tools')">🛠️ 实用工具</button>
                </div>
                
                <!-- 基金搜索标签页 -->
                <div id="search-tab" class="tab-pane active">
                    <div class="search-section">
                        <h3 style="margin-bottom: 1rem;">🎯 智能基金搜索</h3>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div class="form-group">
                                <label for="fundCode">基金代码</label>
                                <input type="text" id="fundCode" class="form-control" placeholder="输入基金代码，如：000001">
                            </div>
                            <div class="form-group">
                                <label for="fundName">基金名称</label>
                                <input type="text" id="fundName" class="form-control" placeholder="输入基金名称，支持模糊搜索">
                            </div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 1rem;">
                            <div class="form-group">
                                <label for="fundCompany">基金公司</label>
                                <input type="text" id="fundCompany" class="form-control" placeholder="输入基金公司名称">
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
                                    <option value="QDII">QDII</option>
                                    <option value="FOF">FOF</option>
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
                
                <!-- 数据中心标签页 -->
                <div id="data-tab" class="tab-pane">
                    <h3>📊 数据中心</h3>
                    <div class="search-section">
                        <h4>已采集数据概览</h4>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                            <div class="fund-detail" style="cursor: pointer;" onclick="loadDataStats()">
                                <div class="detail-label">总基金数量</div>
                                <div class="detail-value" id="totalFunds">加载中...</div>
                            </div>
                            <div class="fund-detail" style="cursor: pointer;" onclick="loadDataStats()">
                                <div class="detail-label">总报告数量</div>
                                <div class="detail-value" id="totalReports">加载中...</div>
                            </div>
                            <div class="fund-detail" style="cursor: pointer;" onclick="loadTaskStats()">
                                <div class="detail-label">成功任务</div>
                                <div class="detail-value" id="successTasks">加载中...</div>
                            </div>
                            <div class="fund-detail" style="cursor: pointer;" onclick="loadTaskStats()">
                                <div class="detail-label">最新数据日期</div>
                                <div class="detail-value" id="latestData">加载中...</div>
                            </div>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 1rem; margin-bottom: 2rem;">
                            <div class="form-group">
                                <label for="dataFundCode">基金代码筛选</label>
                                <input type="text" id="dataFundCode" class="form-control" placeholder="输入基金代码查看其数据">
                            </div>
                            <div class="form-group">
                                <label for="dataDateFrom">数据日期从</label>
                                <input type="date" id="dataDateFrom" class="form-control">
                            </div>
                            <div class="form-group">
                                <label for="dataDateTo">数据日期到</label>
                                <input type="date" id="dataDateTo" class="form-control">
                            </div>
                            <div class="form-group">
                                <button class="btn" onclick="loadMyData()">📊 查看我的数据</button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="quick-actions">
                        <div class="quick-action" onclick="downloadAllData()">
                            <div class="icon">📥</div>
                            <h4>下载全部数据</h4>
                            <p>导出所有采集的基金数据为Excel文件</p>
                        </div>
                        <div class="quick-action" onclick="downloadRecentData()">
                            <div class="icon">📊</div>
                            <h4>下载最新数据</h4>
                            <p>导出最近30天的基金数据</p>
                        </div>
                        <div class="quick-action" onclick="downloadCustomData()">
                            <div class="icon">🎯</div>
                            <h4>自定义导出</h4>
                            <p>根据筛选条件导出特定数据</p>
                        </div>
                        <div class="quick-action" onclick="generateReport()">
                            <div class="icon">📈</div>
                            <h4>生成分析报告</h4>
                            <p>基于采集数据生成投资分析报告</p>
                        </div>
                    </div>
                    
                    <div id="dataResults" class="results-section">
                        <div style="text-align: center; padding: 3rem; color: #666;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                            <h3>欢迎使用数据中心</h3>
                            <p>这里展示您采集的所有基金数据，支持查看、筛选和下载</p>
                            <div style="margin-top: 1rem;">
                                <button class="btn" onclick="loadMyData()">🔄 刷新数据</button>
                            </div>
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
        
        <!-- 模态弹窗 -->
        <div id="modalDialog" class="modal" role="dialog" aria-labelledby="modalTitle" aria-hidden="true">
            <div class="modal-content" role="document">
                <div class="modal-header">
                    <h2 id="modalTitle">标题</h2>
                    <span class="close" onclick="closeModal()" aria-label="关闭对话框" tabindex="0" onkeydown="handleCloseKeydown(event)">&times;</span>
                </div>
                <div class="modal-body" id="modalBody" tabindex="-1">
                    内容
                </div>
            </div>
        </div>
        
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
                const fundCode = document.getElementById('fundCode').value.trim();
                const fundName = document.getElementById('fundName').value.trim();
                const fundCompany = document.getElementById('fundCompany').value.trim();
                const fundType = document.getElementById('fundType').value;
                const resultsDiv = document.getElementById('searchResults');
                
                // 显示加载状态
                resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>正在搜索基金...</p></div>';
                
                try {
                    // 构建查询URL
                    let url = '/api/v1/funds/?page=1&size=20';
                    if (fundCode) url += `&fund_code=${encodeURIComponent(fundCode)}`;
                    if (fundName) url += `&fund_name=${encodeURIComponent(fundName)}`;
                    if (fundCompany) url += `&fund_company=${encodeURIComponent(fundCompany)}`;
                    if (fundType) url += `&fund_type=${encodeURIComponent(fundType)}`;
                    
                    console.log('Searching funds with URL:', url);
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    console.log('Search response:', data);
                    
                    if (data.success && data.data && data.data.length > 0) {
                        // Sanitize data before display
                        const sanitizedData = data.data.map(fund => sanitizeFundData(fund));
                        displayFunds(sanitizedData, data.total || data.data.length);
                    } else {
                        resultsDiv.innerHTML = `
                            <div style="text-align: center; padding: 3rem;">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                                <h3>未找到相关基金</h3>
                                <p>请尝试调整搜索条件或检查输入的基金代码</p>
                                <div style="margin-top: 1rem; color: #666;">
                                    <small>提示：可以只输入基金名称的一部分进行模糊搜索</small>
                                </div>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.error('Search error:', error);
                    resultsDiv.innerHTML = `
                        <div style="text-align: center; padding: 3rem; color: red;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">❌</div>
                            <h3>搜索失败</h3>
                            <p>网络连接异常或服务暂时不可用</p>
                            <div style="margin-top: 1rem;">
                                <button class="btn" onclick="searchFunds()">重试</button>
                            </div>
                        </div>
                    `;
                }
            }
            
            // 显示基金列表
            function displayFunds(funds, total = 0) {
                const resultsDiv = document.getElementById('searchResults');
                let html = `<h3>搜索结果 (${total} 条)</h3>`;
                
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
                                    <div class="detail-value">${fund.fund_company || '-'}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">成立日期</div>
                                    <div class="detail-value">${fund.establishment_date ? formatDate(fund.establishment_date) : '-'}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">基金经理</div>
                                    <div class="detail-value">${fund.fund_manager || '-'}</div>
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
            
            // 格式化日期
            function formatDate(dateString) {
                if (!dateString) return '-';
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('zh-CN');
                } catch (e) {
                    return dateString;
                }
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
            
            // 获取基金详细信息
            async function getFundDetails(fundCode) {
                try {
                    const response = await fetch(`/api/v1/funds/${fundCode}`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const fund = data.data;
                        const navInfo = data.nav_info;
                        
                        let detailHtml = `
                            <div style="background: white; border-radius: 10px; padding: 2rem; margin: 1rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                                <h3 style="color: #667eea; margin-bottom: 1rem;">📊 ${fund.fund_name} (${fund.fund_code})</h3>
                                
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                                    <div class="fund-detail">
                                        <div class="detail-label">基金类型</div>
                                        <div class="detail-value">${fund.fund_type || '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">管理公司</div>
                                        <div class="detail-value">${fund.fund_company || '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">成立日期</div>
                                        <div class="detail-value">${fund.establishment_date ? formatDate(fund.establishment_date) : '-'}</div>
                                    </div>
                                </div>
                        `;
                        
                        if (navInfo) {
                            detailHtml += `
                                <h4 style="color: #28a745; margin-bottom: 1rem;">💰 最新净值信息</h4>
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                                    <div class="fund-detail">
                                        <div class="detail-label">单位净值</div>
                                        <div class="detail-value">${navInfo.unit_nav || '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">累计净值</div>
                                        <div class="detail-value">${navInfo.cumulative_nav || '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">净值日期</div>
                                        <div class="detail-value">${navInfo.nav_date ? formatDate(navInfo.nav_date) : '-'}</div>
                                    </div>
                                </div>
                            `;
                        }
                        
                        detailHtml += `
                                <div style="text-align: center; margin-top: 2rem;">
                                    <button class="btn" onclick="getFundNavHistory('${fundCode}')">📈 查看净值历史</button>
                                    <button class="btn btn-secondary" onclick="getFundReports('${fundCode}')">📄 获取报告</button>
                                    <button class="btn btn-success" onclick="addToTask('${fundCode}')">➕ 添加到采集</button>
                                </div>
                            </div>
                        `;
                        
                        // 显示在弹窗或者结果区域
                        showModal('基金详细信息', detailHtml);
                        
                    } else {
                        alert(`无法获取基金 ${fundCode} 的详细信息\\n\\n${data.message || '数据不存在'}`);
                    }
                } catch (error) {
                    console.error('Get fund details error:', error);
                    alert(`获取基金详细信息失败\\n\\n请检查网络连接或稍后重试`);
                }
            }
            
            // 获取基金净值历史
            async function getFundNavHistory(fundCode) {
                try {
                    const response = await fetch(`/api/v1/funds/${fundCode}/nav-history?limit=30`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const navHistory = data.data;
                        
                        let historyHtml = `
                            <div style="background: white; border-radius: 10px; padding: 2rem;">
                                <h3 style="color: #667eea; margin-bottom: 1rem;">📈 ${fundCode} 净值历史</h3>
                                <div style="max-height: 400px; overflow-y: auto;">
                                    <table style="width: 100%; border-collapse: collapse;">
                                        <thead>
                                            <tr style="background: #f8f9fa;">
                                                <th style="padding: 0.8rem; border: 1px solid #dee2e6;">日期</th>
                                                <th style="padding: 0.8rem; border: 1px solid #dee2e6;">单位净值</th>
                                                <th style="padding: 0.8rem; border: 1px solid #dee2e6;">累计净值</th>
                                                <th style="padding: 0.8rem; border: 1px solid #dee2e6;">报告类型</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                        `;
                        
                        navHistory.forEach(nav => {
                            historyHtml += `
                                <tr>
                                    <td style="padding: 0.8rem; border: 1px solid #dee2e6;">${formatDate(nav.date)}</td>
                                    <td style="padding: 0.8rem; border: 1px solid #dee2e6;">${nav.unit_nav || '-'}</td>
                                    <td style="padding: 0.8rem; border: 1px solid #dee2e6;">${nav.cumulative_nav || '-'}</td>
                                    <td style="padding: 0.8rem; border: 1px solid #dee2e6;">${nav.report_type || '-'}</td>
                                </tr>
                            `;
                        });
                        
                        historyHtml += `
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        `;
                        
                        showModal('净值历史', historyHtml);
                        
                    } else {
                        alert(`无法获取基金 ${fundCode} 的净值历史\\n\\n${data.message || '数据不存在'}`);
                    }
                } catch (error) {
                    console.error('Get nav history error:', error);
                    alert(`获取净值历史失败\\n\\n请检查网络连接或稍后重试`);
                }
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
                const fundCode = document.getElementById('reportFundCode').value.trim();
                const reportType = document.getElementById('reportType').value;
                
                if (!fundCode) {
                    alert('请输入基金代码');
                    return;
                }
                
                fetchFundReports(fundCode, reportType);
            }
            
            // 获取基金报告
            async function fetchFundReports(fundCode, reportType = '') {
                try {
                    let url = `/api/v1/reports/?fund_code=${fundCode}&page=1&size=10`;
                    if (reportType && reportType !== 'all') {
                        url += `&report_type=${reportType}`;
                    }
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    if (data.success && data.data && data.data.length > 0) {
                        displayReports(data.data, fundCode);
                    } else {
                        document.getElementById('reportsResults').innerHTML = `
                            <div style="text-align: center; padding: 3rem;">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">📄</div>
                                <h3>暂无报告数据</h3>
                                <p>基金 ${fundCode} 暂无${reportType && reportType !== 'all' ? reportType : ''}报告数据</p>
                                <div style="margin-top: 1rem;">
                                    <button class="btn" onclick="createReportTask('${fundCode}')">🚀 创建采集任务</button>
                                </div>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.error('Fetch reports error:', error);
                    document.getElementById('reportsResults').innerHTML = `
                        <div style="text-align: center; padding: 3rem; color: red;">
                            <h3>获取报告失败</h3>
                            <p>请检查网络连接或稍后重试</p>
                        </div>
                    `;
                }
            }
            
            // 显示报告列表
            function displayReports(reports, fundCode) {
                let html = `<h3>${fundCode} 的报告列表 (${reports.length} 条)</h3>`;
                
                reports.forEach(report => {
                    html += `
                        <div class="fund-card">
                            <div class="fund-header">
                                <div>
                                    <div class="fund-name">${report.fund_name || fundCode}</div>
                                    <span class="fund-code">${report.report_type}</span>
                                </div>
                            </div>
                            <div class="fund-details">
                                <div class="fund-detail">
                                    <div class="detail-label">报告日期</div>
                                    <div class="detail-value">${formatDate(report.report_date)}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">报告类型</div>
                                    <div class="detail-value">${report.report_type}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">创建时间</div>
                                    <div class="detail-value">${formatDate(report.created_at)}</div>
                                </div>
                                <div class="fund-detail">
                                    <div class="detail-label">文件路径</div>
                                    <div class="detail-value">${report.file_path ? '已存储' : '未存储'}</div>
                                </div>
                            </div>
                            <div class="fund-actions">
                                <button class="btn" onclick="getReportDetail('${report.report_id}')">📊 查看详情</button>
                                <button class="btn btn-secondary" onclick="downloadReport('${report.report_id}')">📥 下载报告</button>
                            </div>
                        </div>
                    `;
                });
                
                document.getElementById('reportsResults').innerHTML = html;
            }
            
            // 获取报告详情
            async function getReportDetail(reportId) {
                try {
                    const response = await fetch(`/api/v1/reports/${reportId}`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const report = data.data;
                        
                        let detailHtml = `
                            <div style="background: white; border-radius: 10px; padding: 2rem;">
                                <h3 style="color: #667eea; margin-bottom: 1rem;">📊 ${report.fund_name} - ${report.report_type}</h3>
                                <p><strong>报告日期:</strong> ${formatDate(report.report_date)}</p>
                        `;
                        
                        if (report.asset_allocation) {
                            const asset = report.asset_allocation;
                            detailHtml += `
                                <h4 style="color: #28a745; margin: 1.5rem 0 1rem;">💰 资产配置</h4>
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem;">
                                    <div class="fund-detail">
                                        <div class="detail-label">股票比例</div>
                                        <div class="detail-value">${asset.stock_ratio ? (asset.stock_ratio * 100).toFixed(2) + '%' : '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">债券比例</div>
                                        <div class="detail-value">${asset.bond_ratio ? (asset.bond_ratio * 100).toFixed(2) + '%' : '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">现金比例</div>
                                        <div class="detail-value">${asset.cash_ratio ? (asset.cash_ratio * 100).toFixed(2) + '%' : '-'}</div>
                                    </div>
                                    <div class="fund-detail">
                                        <div class="detail-label">总资产</div>
                                        <div class="detail-value">${asset.total_assets || '-'}</div>
                                    </div>
                                </div>
                            `;
                        }
                        
                        if (report.top_holdings && report.top_holdings.length > 0) {
                            detailHtml += `
                                <h4 style="color: #dc3545; margin: 1.5rem 0 1rem;">🏢 前十大重仓股</h4>
                                <div style="max-height: 300px; overflow-y: auto;">
                                    <table style="width: 100%; border-collapse: collapse;">
                                        <thead>
                                            <tr style="background: #f8f9fa;">
                                                <th style="padding: 0.5rem; border: 1px solid #dee2e6;">股票代码</th>
                                                <th style="padding: 0.5rem; border: 1px solid #dee2e6;">股票名称</th>
                                                <th style="padding: 0.5rem; border: 1px solid #dee2e6;">持仓比例</th>
                                                <th style="padding: 0.5rem; border: 1px solid #dee2e6;">市值(万元)</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                            `;
                            
                            report.top_holdings.forEach(holding => {
                                detailHtml += `
                                    <tr>
                                        <td style="padding: 0.5rem; border: 1px solid #dee2e6;">${holding.stock_code}</td>
                                        <td style="padding: 0.5rem; border: 1px solid #dee2e6;">${holding.stock_name}</td>
                                        <td style="padding: 0.5rem; border: 1px solid #dee2e6;">${holding.holding_ratio ? (holding.holding_ratio * 100).toFixed(2) + '%' : '-'}</td>
                                        <td style="padding: 0.5rem; border: 1px solid #dee2e6;">${holding.market_value || '-'}</td>
                                    </tr>
                                `;
                            });
                            
                            detailHtml += `
                                        </tbody>
                                    </table>
                                </div>
                            `;
                        }
                        
                        detailHtml += '</div>';
                        showModal('报告详情', detailHtml);
                        
                    } else {
                        alert(`无法获取报告详情\\n\\n${data.message || '数据不存在'}`);
                    }
                } catch (error) {
                    console.error('Get report detail error:', error);
                    alert('获取报告详情失败\\n\\n请检查网络连接或稍后重试');
                }
            }
            
            function createTask() {
                const fundCodes = document.getElementById('taskFundCodes').value.trim();
                const startDate = document.getElementById('startDate').value;
                const endDate = document.getElementById('endDate').value;
                const priority = document.getElementById('priority').value;
                
                if (!fundCodes) {
                    alert('请输入至少一个基金代码');
                    return;
                }
                
                const codes = fundCodes.split('\\n').filter(code => code.trim());
                createDataCollectionTask(codes, startDate, endDate, priority);
            }
            
            // 创建数据采集任务
            async function createDataCollectionTask(fundCodes, startDate, endDate, priority = 'medium') {
                try {
                    const taskData = {
                        task_type: 'fund_scraping',
                        description: `批量采集基金数据: ${fundCodes.slice(0, 3).join(', ')}${fundCodes.length > 3 ? ` 等${fundCodes.length}只基金` : ''}`,
                        parameters: {
                            fund_codes: fundCodes,
                            start_date: startDate,
                            end_date: endDate,
                            priority: priority,
                            count: fundCodes.length
                        }
                    };
                    
                    const response = await fetch('/api/v1/tasks/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(taskData)
                    });
                    
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const task = data.data;
                        const resultHtml = `
                            <div style="text-align: center; padding: 2rem;">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">✅</div>
                                <h3>任务创建成功！</h3>
                                <p><strong>任务ID:</strong> ${task.task_id}</p>
                                <p><strong>任务名称:</strong> ${task.task_name}</p>
                                <p><strong>状态:</strong> ${task.status}</p>
                                <div style="margin-top: 2rem;">
                                    <button class="btn" onclick="trackTask('${task.task_id}')">📊 跟踪任务进度</button>
                                    <button class="btn btn-secondary" onclick="showTab('tasks')">📋 查看所有任务</button>
                                </div>
                            </div>
                        `;
                        document.getElementById('taskResults').innerHTML = resultHtml;
                        
                        // 开始跟踪任务进度
                        setTimeout(() => trackTask(task.task_id), 2000);
                        
                    } else {
                        alert(`任务创建失败\\n\\n${data.message || '未知错误'}`);
                    }
                } catch (error) {
                    console.error('Create task error:', error);
                    alert('创建任务失败\\n\\n请检查网络连接或稍后重试');
                }
            }
            
            // 跟踪任务进度
            async function trackTask(taskId) {
                try {
                    const response = await fetch(`/api/v1/tasks/${taskId}`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const task = data.data;
                        updateTaskProgress(task);
                        
                        // 如果任务还在运行，继续跟踪
                        if (task.status === 'running' || task.status === 'pending') {
                            setTimeout(() => trackTask(taskId), 3000);
                        }
                    }
                } catch (error) {
                    console.error('Track task error:', error);
                }
            }
            
            // 更新任务进度显示
            function updateTaskProgress(task) {
                const resultHtml = `
                    <div style="text-align: center; padding: 2rem;">
                        <h3>📊 任务进度跟踪</h3>
                        <p><strong>任务ID:</strong> ${task.task_id}</p>
                        <p><strong>任务名称:</strong> ${task.task_name}</p>
                        <p><strong>状态:</strong> <span style="color: ${getStatusColor(task.status)}">${getStatusText(task.status)}</span></p>
                        <div style="margin: 1rem 0;">
                            <div style="background: #f0f0f0; border-radius: 10px; overflow: hidden;">
                                <div style="background: linear-gradient(90deg, #667eea, #764ba2); height: 20px; width: ${task.progress}%; transition: width 0.3s ease;"></div>
                            </div>
                            <p style="margin-top: 0.5rem;">${task.progress}% 完成</p>
                        </div>
                        ${task.error_message ? `<p style="color: red;"><strong>错误:</strong> ${task.error_message}</p>` : ''}
                        ${task.result ? `<p style="color: green;"><strong>结果:</strong> ${JSON.stringify(task.result)}</p>` : ''}
                    </div>
                `;
                document.getElementById('taskResults').innerHTML = resultHtml;
            }
            
            function getStatusColor(status) {
                switch(status) {
                    case 'success': return 'green';
                    case 'failed': return 'red';
                    case 'running': return 'blue';
                    default: return 'orange';
                }
            }
            
            function getStatusText(status) {
                switch(status) {
                    case 'pending': return '等待中';
                    case 'running': return '运行中';
                    case 'success': return '已完成';
                    case 'failed': return '失败';
                    default: return status;
                }
            }
            
            // ========== 数据中心相关功能 ==========
            
            // 加载数据统计信息
            async function loadDataStats() {
                try {
                    // 获取基金统计
                    const fundsResponse = await fetch('/api/v1/funds/stats/summary');
                    const fundsData = await fundsResponse.json();
                    
                    if (fundsData.success && fundsData.data) {
                        document.getElementById('totalFunds').textContent = fundsData.data.total_funds || '0';
                    }
                    
                    // 获取报告统计
                    const reportsResponse = await fetch('/api/v1/reports/stats/summary');
                    const reportsData = await reportsResponse.json();
                    
                    if (reportsData.success && reportsData.data) {
                        document.getElementById('totalReports').textContent = reportsData.data.total_reports || '0';
                        document.getElementById('latestData').textContent = reportsData.data.latest_report_date ? 
                            formatDate(reportsData.data.latest_report_date) : '暂无数据';
                    }
                    
                } catch (error) {
                    console.error('Load data stats error:', error);
                }
            }
            
            // 加载任务统计信息
            async function loadTaskStats() {
                try {
                    const response = await fetch('/api/v1/tasks/stats/summary');
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const successCount = data.data.by_status?.success || 0;
                        document.getElementById('successTasks').textContent = successCount;
                    }
                    
                } catch (error) {
                    console.error('Load task stats error:', error);
                    document.getElementById('successTasks').textContent = '0';
                }
            }
            
            // 加载我的数据
            async function loadMyData() {
                const fundCode = document.getElementById('dataFundCode').value.trim();
                const dateFrom = document.getElementById('dataDateFrom').value;
                const dateTo = document.getElementById('dataDateTo').value;
                const resultsDiv = document.getElementById('dataResults');
                
                // 显示加载状态
                resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>正在加载数据...</p></div>';
                
                try {
                    // 构建查询URL
                    let url = '/api/v1/reports/?page=1&size=50';
                    if (fundCode) url += `&fund_code=${encodeURIComponent(fundCode)}`;
                    if (dateFrom) url += `&start_date=${dateFrom}`;
                    if (dateTo) url += `&end_date=${dateTo}`;
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    if (data.success && data.data && data.data.length > 0) {
                        displayMyData(data.data, data.total || data.data.length);
                    } else {
                        resultsDiv.innerHTML = \`
                            <div style="text-align: center; padding: 3rem;">
                                <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                                <h3>暂无符合条件的数据</h3>
                                <p>请尝试调整筛选条件或先进行数据采集</p>
                                <div style="margin-top: 1rem;">
                                    <button class="btn" onclick="showTab('tasks')">🚀 开始采集数据</button>
                                </div>
                            </div>
                        \`;
                    }
                } catch (error) {
                    console.error('Load my data error:', error);
                    resultsDiv.innerHTML = \`
                        <div style="text-align: center; padding: 3rem; color: red;">
                            <h3>加载失败</h3>
                            <p>请检查网络连接或稍后重试</p>
                            <button class="btn" onclick="loadMyData()">重试</button>
                        </div>
                    \`;
                }
            }
            
            // 显示我的数据
            function displayMyData(reports, total) {
                const resultsDiv = document.getElementById('dataResults');
                let html = \`
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                        <h3>📊 已采集数据 (${total} 条)</h3>
                        <div>
                            <button class="btn btn-secondary" onclick="exportCurrentData()">📥 导出当前数据</button>
                        </div>
                    </div>
                \`;
                
                // 按基金代码分组显示
                const groupedReports = {};
                reports.forEach(report => {
                    if (!groupedReports[report.fund_code]) {
                        groupedReports[report.fund_code] = [];
                    }
                    groupedReports[report.fund_code].push(report);
                });
                
                for (const [fundCode, fundReports] of Object.entries(groupedReports)) {
                    const fundName = fundReports[0].fund_name || '未知基金';
                    
                    html += \`
                        <div class="fund-card">
                            <div class="fund-header">
                                <div>
                                    <div class="fund-name">${fundName}</div>
                                    <span class="fund-code">${fundCode}</span>
                                </div>
                                <div>
                                    <span style="background: #28a745; color: white; padding: 0.2rem 0.8rem; border-radius: 15px;">
                                        ${fundReports.length} 个报告
                                    </span>
                                </div>
                            </div>
                            <div class="fund-details">
                    \`;
                    
                    // 显示报告类型统计
                    const typeStats = {};
                    fundReports.forEach(report => {
                        const type = report.report_type;
                        typeStats[type] = (typeStats[type] || 0) + 1;
                    });
                    
                    for (const [type, count] of Object.entries(typeStats)) {
                        html += \`
                            <div class="fund-detail">
                                <div class="detail-label">${type}</div>
                                <div class="detail-value">${count} 个</div>
                            </div>
                        \`;
                    }
                    
                    // 最新报告日期
                    const latestReport = fundReports.sort((a, b) => new Date(b.report_date) - new Date(a.report_date))[0];
                    html += \`
                        <div class="fund-detail">
                            <div class="detail-label">最新报告日期</div>
                            <div class="detail-value">${formatDate(latestReport.report_date)}</div>
                        </div>
                    \`;
                    
                    html += \`
                            </div>
                            <div class="fund-actions">
                                <button class="btn" onclick="viewFundReports('${fundCode}')">📊 查看详细报告</button>
                                <button class="btn btn-secondary" onclick="downloadFundData('${fundCode}')">📥 下载数据</button>
                                <button class="btn btn-success" onclick="generateFundReport('${fundCode}')">📈 生成分析</button>
                            </div>
                        </div>
                    \`;
                }
                
                resultsDiv.innerHTML = html;
            }
            
            // 查看基金报告详情
            function viewFundReports(fundCode) {
                document.getElementById('reportFundCode').value = fundCode;
                showTab('reports');
            }
            
            // 下载基金数据
            async function downloadFundData(fundCode) {
                try {
                    showLoadingToast('正在准备下载数据...');
                    
                    // 生成下载数据
                    const response = await fetch(\`/api/v1/reports/?fund_code=\${fundCode}&size=1000\`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const exportData = {
                            fund_code: fundCode,
                            export_time: new Date().toISOString(),
                            total_reports: data.data.length,
                            reports: data.data
                        };
                        
                        const dataStr = JSON.stringify(exportData, null, 2);
                        const dataBlob = new Blob([dataStr], {type: 'application/json'});
                        const url = URL.createObjectURL(dataBlob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = \`基金\${fundCode}_数据_\${new Date().toISOString().split('T')[0]}.json\`;
                        link.click();
                        URL.revokeObjectURL(url);
                        
                        showSuccessToast(\`基金 \${fundCode} 数据下载完成！\`);
                    } else {
                        alert('下载失败：无法获取数据');
                    }
                } catch (error) {
                    console.error('Download fund data error:', error);
                    alert('下载失败：网络异常');
                }
            }
            
            // 下载全部数据
            async function downloadAllData() {
                if (!confirm('确定要下载所有数据吗？这可能需要一些时间。')) return;
                
                try {
                    showLoadingToast('正在准备全部数据下载...');
                    
                    const response = await fetch('/api/v1/reports/?size=5000');
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const exportData = {
                            platform: '基金报告自动化采集与分析平台',
                            export_time: new Date().toISOString(),
                            total_reports: data.data.length,
                            reports: data.data
                        };
                        
                        const dataStr = JSON.stringify(exportData, null, 2);
                        const dataBlob = new Blob([dataStr], {type: 'application/json'});
                        const url = URL.createObjectURL(dataBlob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = \`全部基金数据_\${new Date().toISOString().split('T')[0]}.json\`;
                        link.click();
                        URL.revokeObjectURL(url);
                        
                        showSuccessToast(\`全部数据下载完成！共 \${data.data.length} 条记录\`);
                    } else {
                        alert('下载失败：无法获取数据');
                    }
                } catch (error) {
                    console.error('Download all data error:', error);
                    alert('下载失败：网络异常');
                }
            }
            
            // 下载最新数据
            async function downloadRecentData() {
                const endDate = new Date().toISOString().split('T')[0];
                const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                
                try {
                    showLoadingToast('正在准备最新数据下载...');
                    
                    const response = await fetch(\`/api/v1/reports/?start_date=\${startDate}&end_date=\${endDate}&size=1000\`);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const exportData = {
                            platform: '基金报告自动化采集与分析平台',
                            export_time: new Date().toISOString(),
                            date_range: { start_date: startDate, end_date: endDate },
                            total_reports: data.data.length,
                            reports: data.data
                        };
                        
                        const dataStr = JSON.stringify(exportData, null, 2);
                        const dataBlob = new Blob([dataStr], {type: 'application/json'});
                        const url = URL.createObjectURL(dataBlob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = \`最新30天基金数据_\${endDate}.json\`;
                        link.click();
                        URL.revokeObjectURL(url);
                        
                        showSuccessToast(\`最新数据下载完成！共 \${data.data.length} 条记录\`);
                    } else {
                        alert('下载失败：无法获取数据');
                    }
                } catch (error) {
                    console.error('Download recent data error:', error);
                    alert('下载失败：网络异常');
                }
            }
            
            // 自定义导出
            function downloadCustomData() {
                const fundCode = document.getElementById('dataFundCode').value.trim();
                const dateFrom = document.getElementById('dataDateFrom').value;
                const dateTo = document.getElementById('dataDateTo').value;
                
                if (!fundCode && !dateFrom && !dateTo) {
                    alert('请至少设置一个筛选条件');
                    return;
                }
                
                // 使用当前筛选条件下载
                downloadFilteredData(fundCode, dateFrom, dateTo);
            }
            
            // 下载筛选后的数据
            async function downloadFilteredData(fundCode, dateFrom, dateTo) {
                try {
                    showLoadingToast('正在准备自定义数据下载...');
                    
                    let url = '/api/v1/reports/?size=1000';
                    if (fundCode) url += \`&fund_code=\${encodeURIComponent(fundCode)}\`;
                    if (dateFrom) url += \`&start_date=\${dateFrom}\`;
                    if (dateTo) url += \`&end_date=\${dateTo}\`;
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    if (data.success && data.data) {
                        const exportData = {
                            platform: '基金报告自动化采集与分析平台',
                            export_time: new Date().toISOString(),
                            filters: { fund_code: fundCode, date_from: dateFrom, date_to: dateTo },
                            total_reports: data.data.length,
                            reports: data.data
                        };
                        
                        const dataStr = JSON.stringify(exportData, null, 2);
                        const dataBlob = new Blob([dataStr], {type: 'application/json'});
                        const url = URL.createObjectURL(dataBlob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = \`自定义基金数据_\${new Date().toISOString().split('T')[0]}.json\`;
                        link.click();
                        URL.revokeObjectURL(url);
                        
                        showSuccessToast(\`自定义数据下载完成！共 \${data.data.length} 条记录\`);
                    } else {
                        alert('下载失败：无符合条件的数据');
                    }
                } catch (error) {
                    console.error('Download filtered data error:', error);
                    alert('下载失败：网络异常');
                }
            }
            
            // 生成分析报告
            function generateReport() {
                alert('分析报告生成功能开发中\\n\\n将支持：\\n- 基金业绩分析\\n- 风险评估\\n- 投资建议\\n- 行业配置分析\\n\\n敬请期待！');
            }
            
            // 生成基金分析报告
            function generateFundReport(fundCode) {
                alert(\`基金 \${fundCode} 专项分析报告生成功能开发中\\n\\n将包含：\\n- 历史业绩分析\\n- 持仓变化趋势\\n- 风险收益特征\\n- 投资价值评估\\n\\n敬请期待！\`);
            }
            
            // 导出当前数据
            function exportCurrentData() {
                const fundCode = document.getElementById('dataFundCode').value.trim();
                const dateFrom = document.getElementById('dataDateFrom').value;
                const dateTo = document.getElementById('dataDateTo').value;
                
                downloadFilteredData(fundCode, dateFrom, dateTo);
            }
            
            // 消息提示函数
            function showLoadingToast(message) {
                // 简单的加载提示
                console.log('Loading:', message);
            }
            
            function showSuccessToast(message) {
                // 简单的成功提示
                console.log('Success:', message);
                alert(message);
            }
            
            // 页面加载时自动加载统计数据
            document.addEventListener('DOMContentLoaded', function() {
                loadDataStats();
                loadTaskStats();
                
                // 设置默认日期
                const today = new Date();
                const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
                const lastYear = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
                
                document.getElementById('startDate').value = lastYear.toISOString().split('T')[0];
                document.getElementById('endDate').value = today.toISOString().split('T')[0];
                
                document.getElementById('dataDateFrom').value = lastMonth.toISOString().split('T')[0];
                document.getElementById('dataDateTo').value = today.toISOString().split('T')[0];
            });
            
            // ========== 数据中心功能结束 ==========
            
            function checkSystemHealth() {
                window.open('/health', '_blank');
            }
            
            function openWebAdmin() {
                alert('请运行以下命令启动Web管理界面:\\n\\nstreamlit run gui/web_admin.py\\n\\n然后访问: http://localhost:8501');
            }
            
            // 模态弹窗功能 (保持向后兼容)
            function showModal(title, content) {
                openModal(title, content);
            }
            
            function closeModal() {
                const modal = document.getElementById('modalDialog');
                modal.style.display = 'none';
                modal.setAttribute('aria-hidden', 'true');
                document.body.style.overflow = 'auto';
                // 恢复焦点到触发元素
                if (window.modalTriggerElement) {
                    window.modalTriggerElement.focus();
                    window.modalTriggerElement = null;
                }
            }
            
            function openModal(title, content, triggerElement = null) {
                const modal = document.getElementById('modalDialog');
                const modalTitle = document.getElementById('modalTitle');
                const modalBody = document.getElementById('modalBody');
                
                // 保存触发元素引用
                window.modalTriggerElement = triggerElement || document.activeElement;
                
                modalTitle.textContent = title;
                modalBody.innerHTML = content;
                modal.style.display = 'block';
                modal.setAttribute('aria-hidden', 'false');
                document.body.style.overflow = 'hidden';
                
                // 设置焦点到模态框内容
                modalBody.focus();
            }
            
            function handleCloseKeydown(event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    closeModal();
                }
            }
            
            // 点击模态框外部关闭
            window.onclick = function(event) {
                const modal = document.getElementById('modalDialog');
                if (event.target === modal) {
                    closeModal();
                }
            }
            
            // 按ESC键关闭模态框
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    const modal = document.getElementById('modalDialog');
                    if (modal.style.display === 'block') {
                        closeModal();
                    }
                }
            });
            
            // 其他辅助功能
            function downloadReport(reportId) {
                alert(`报告下载功能开发中\\n\\n报告ID: ${reportId}\\n\\n此功能需要配置文件存储服务`);
            }
            
            function downloadSample() {
                // 生成示例数据并下载
                const sampleData = {
                    platform: "基金报告自动化采集与分析平台",
                    description: "示例基金数据",
                    funds: [
                        { fund_code: "000001", fund_name: "华夏成长混合", fund_type: "混合型", fund_company: "华夏基金" },
                        { fund_code: "000300", fund_name: "沪深300ETF", fund_type: "指数型", fund_company: "华泰柏瑞基金" },
                        { fund_code: "110022", fund_name: "易方达消费行业股票", fund_type: "股票型", fund_company: "易方达基金" }
                    ],
                    timestamp: new Date().toISOString()
                };
                
                const dataStr = JSON.stringify(sampleData, null, 2);
                const dataBlob = new Blob([dataStr], {type: 'application/json'});
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `sample_fund_data_${new Date().toISOString().split('T')[0]}.json`;
                link.click();
                URL.revokeObjectURL(url);
            }
            
            // 创建针对特定基金的报告采集任务
            function createReportTask(fundCode) {
                const currentDate = new Date().toISOString().split('T')[0];
                const lastYear = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                
                createDataCollectionTask([fundCode], lastYear, currentDate, 'high');
            }
            
            // 数据清理函数
            function sanitizeFundData(fund) {
                const sanitized = {};
                for (const [key, value] of Object.entries(fund)) {
                    if (typeof value === 'string') {
                        // 基本的HTML转义
                        sanitized[key] = value
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/"/g, '&quot;')
                            .replace(/'/g, '&#x27;');
                    } else {
                        sanitized[key] = value;
                    }
                }
                return sanitized;
            }

            // 常量定义
            const DEFAULT_PROGRESS = 50;
            const RETRY_DELAY = 1000;
            const MAX_RETRIES = 3;

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
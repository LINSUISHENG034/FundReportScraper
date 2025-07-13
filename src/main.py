"""
Main FastAPI application entry point.
基金报告自动化采集与分析平台 - 统一应用入口
"""

import httpx
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.logging import configure_logging, get_logger
from src.models import get_db_session, init_database
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService

# Configure logging
configure_logging(
    log_level=settings.log_level,
    json_logs=not settings.debug
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("application.startup")
    
    # Create httpx client
    app.state.http_client = httpx.AsyncClient()
    logger.info("application.http_client.created")

    # Create services
    app.state.download_task_service = DownloadTaskService()
    logger.info("application.services.created")
    
    yield
    
    # Close httpx client
    await app.state.http_client.aclose()
    logger.info("application.http_client.closed")
    logger.info("application.shutdown")


# Create FastAPI application
app = FastAPI(
    title="基金报告自动化采集与分析平台 API",
    description="Fund Report Automated Collection and Analysis Platform API",
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for scraper
def get_scraper(request: Request) -> CSRCFundReportScraper:
    """
    Dependency to get a CSRCFundReportScraper instance.
    """
    return CSRCFundReportScraper(session=request.app.state.http_client)


# 导入路由模块
try:
    from src.api.routes import fund_reports
    from src.api.routes import reports_v2, downloads  # V2 API路由
    from src.api.schemas import HealthResponse

    # 注册V1路由（向后兼容）
    app.include_router(fund_reports.router, tags=["基金报告(V1)"])  # 旧版路由

    # 注册V2路由（新的RESTful设计）
    app.include_router(reports_v2.router, tags=["报告搜索(V2)"])  # 新的报告搜索API
    app.include_router(downloads.router, tags=["下载任务(V2)"])   # 新的下载任务API

    ROUTES_AVAILABLE = True
except ImportError as e:
    logger.warning("api.routes.import_failed", error=str(e))
    ROUTES_AVAILABLE = False

    # 创建基本的响应模型
    class HealthResponse(BaseModel):
        status: str
        timestamp: datetime
        version: str
        services: Dict[str, str]


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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """
    根路径，返回API文档链接
    Root path with API documentation links
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>基金报告自动化采集与分析平台</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 40px; }
            .links { display: flex; justify-content: center; gap: 20px; }
            .link { padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
            .link:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏦 基金报告自动化采集与分析平台</h1>
                <p>Fund Report Automated Collection and Analysis Platform</p>
            </div>
            <div class="links">
                <a href="/docs" class="link">📚 API文档 (Swagger)</a>
                <a href="/redoc" class="link">📖 API文档 (ReDoc)</a>
                <a href="/health" class="link">💚 健康检查</a>
            </div>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "application.starting",
        host="0.0.0.0",
        port=8000,
        debug=settings.debug
    )
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=None  # Use our custom logging
    )

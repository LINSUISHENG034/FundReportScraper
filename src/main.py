"""
Main FastAPI application entry point.
基金报告自动化采集与分析平台 - 统一应用入口
"""

import aiohttp
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text

from src.core.config import settings
from src.core.logging import configure_logging, get_logger

from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper

from src.services.fund_report_service import FundReportService

# Configure logging
configure_logging()

logger = get_logger(__name__)


def create_app(http_client: aiohttp.ClientSession = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan management."""
        logger.info("application.startup")
        
        # Create aiohttp client
        # 关键修复：在Session级别添加User-Agent，与Celery任务保持一致
        app.state.http_client = http_client or aiohttp.ClientSession(
            headers={'User-Agent': settings.scraper.user_agent}
        )
        logger.info("application.http_client.created")

        # Create services
        scraper = CSRCFundReportScraper(session=app.state.http_client)
        from src.services.downloader import Downloader
        downloader = Downloader()  # Downloader creates its own session
        app.state.fund_report_service = FundReportService(scraper=scraper, downloader=downloader)

        logger.info("application.services.created")
        
        yield
        
        # Close aiohttp client
        await app.state.http_client.close()
        logger.info("application.http_client.closed")
        logger.info("application.shutdown")
    """Create and configure the FastAPI application."""
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

    # 导入路由模块
    from src.api.routes import reports, downloads

    app.include_router(reports.router, tags=["报告搜索"])
    app.include_router(downloads.router, tags=["下载任务"])

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
        db_status = "healthy"  # Placeholder

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
            <meta charset=\"utf-8\">
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
            <div class=\"container\">
                <div class=\"header\">
                    <h1>🏦 基金报告自动化采集与分析平台</h1>
                    <p>Fund Report Automated Collection and Analysis Platform</p>
                </div>
                <div class=\"links\">
                    <a href=\"/docs\" class=\"link\">📚 API文档 (Swagger)</a>
                    <a href=\"/redoc\" class=\"link\">📖 API文档 (ReDoc)</a>
                    <a href=\"/health\" class=\"link\">💚 健康检查</a>
                </div>
            </div>
        </body>
        </html>
        """
    return app

app = create_app()

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

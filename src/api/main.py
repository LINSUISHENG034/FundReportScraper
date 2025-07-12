"""
FastAPI application main entry point.
基金报告数据查询API主入口。
"""

from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.get("/", tags=["根路径"])
async def root():
    """
    API根路径
    API root endpoint
    """
    return {
        "message": "基金报告自动化采集与分析平台 API",
        "version": settings.version,
        "docs_url": "/docs",
        "health_url": "/health"
    }


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
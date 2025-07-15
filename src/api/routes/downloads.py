
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.services.fund_report_service import FundReportService


from src.parsers.xbrl_parser import XBRLParser

from src.tasks.download_tasks import start_download_pipeline  # Phase 3重构版本
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter(prefix="/api/downloads", tags=["下载任务"])

# Pydantic Models
class DownloadTaskCreateRequest(BaseModel):
    reports: List[Dict[str, Any]] = Field(..., description="从搜索接口获得的报告对象列表")
    save_dir: Optional[str] = Field("data/downloads", description="文件保存目录")

class DownloadTaskCreateResponse(BaseModel):
    success: bool
    message: str
    task_id: str

class ProgressInfo(BaseModel):
    total: int
    completed: int
    failed: int
    percentage: float

class TaskResults(BaseModel):
    completed_ids: List[str]
    failed_ids: List[dict]

class TaskStatusInfo(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: ProgressInfo
    results: TaskResults
    error_message: Optional[str] = None

class DownloadTaskStatusResponse(BaseModel):
    success: bool
    task_status: TaskStatusInfo


# Dependency Injection

def get_fund_report_service(request: Request) -> FundReportService:
    """获取共享的基金报告服务实例"""
    return request.app.state.fund_report_service

@router.post("", response_model=DownloadTaskCreateResponse, status_code=202)
async def create_download_task(
    request: DownloadTaskCreateRequest
) -> DownloadTaskCreateResponse:
    task_id = str(uuid.uuid4())
    
    # Phase 4.5: 直接将报告列表和保存路径传递给Celery任务
    celery_task = start_download_pipeline.delay(
        task_id=task_id,
        reports_to_process=request.reports,
        save_dir=request.save_dir
    )

    logger.info(
        "downloads.create_task.celery_dispatched",
        task_id=task_id,
        celery_task_id=celery_task.id,
        report_count=len(request.reports)
    )

    return DownloadTaskCreateResponse(
        success=True,
        message="下载任务已创建并分发到Celery队列",
        task_id=task_id
    )

@router.get("/{task_id}", response_model=DownloadTaskStatusResponse)
async def get_download_task_status(
    task_id: str
) -> DownloadTaskStatusResponse:
    # TODO: 实现基于Celery任务状态的查询
    # 目前返回占位符响应
    raise HTTPException(
        status_code=501, 
        detail="任务状态查询功能正在重构中，请使用Celery监控工具查看任务状态"
    )


# Phase 5: execute_download_task 函数已迁移到 src/tasks/download_tasks.py
# 作为 download_fund_report_task Celery任务

@router.post("/test-celery", tags=["测试"])
async def test_celery():
    """
    测试Celery是否正常工作
    Test if Celery is working properly
    """
    from src.tasks.download_tasks import test_celery_task

    bound_logger = logger.bind(component="test_celery")
    bound_logger.info("downloads.test_celery.start")

    try:
        # 分发测试任务到Celery
        celery_task = test_celery_task.delay()

        bound_logger.info(
            "downloads.test_celery.dispatched",
            celery_task_id=celery_task.id
        )

        return {
            "success": True,
            "message": "Celery测试任务已分发",
            "celery_task_id": celery_task.id
        }

    except Exception as e:
        bound_logger.error(
            "downloads.test_celery.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Celery测试失败: {str(e)}"
        )

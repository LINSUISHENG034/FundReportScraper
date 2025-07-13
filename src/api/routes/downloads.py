
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.main import get_scraper
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService, DownloadTask, TaskStatus
from src.models import get_db_session
from src.parsers.xbrl_parser import XBRLParser
from src.services.fund_data_service import FundDataService
from src.tasks.download_tasks import download_fund_report_task  # Phase 5新增
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/downloads", tags=["下载任务"])

# Pydantic Models
class DownloadTaskCreateRequest(BaseModel):
    report_ids: List[int] = Field(..., min_items=1)
    save_dir: Optional[str] = "data/downloads"

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
def get_download_task_service(request: Request) -> DownloadTaskService:
    return request.app.state.download_task_service

def get_fund_report_service(scraper: CSRCFundReportScraper = Depends(get_scraper)) -> FundReportService:
    return FundReportService(scraper)

@router.post("", response_model=DownloadTaskCreateResponse, status_code=202)
async def create_download_task(
    request: DownloadTaskCreateRequest,
    task_service: DownloadTaskService = Depends(get_download_task_service)
) -> DownloadTaskCreateResponse:
    task_id = str(uuid.uuid4())
    task = DownloadTask(
        task_id=task_id,
        report_ids=request.report_ids,
        save_dir=request.save_dir,
        max_concurrent=3, # Hardcoded for now
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow(),
        total_count=len(request.report_ids)
    )
    await task_service.create_task(task)

    # Phase 5: 使用Celery任务替代BackgroundTasks
    celery_task = download_fund_report_task.delay(task_id)

    bound_logger.info(
        "downloads.create_task.celery_dispatched",
        task_id=task_id,
        celery_task_id=celery_task.id,
        report_count=len(request.report_ids)
    )

    return DownloadTaskCreateResponse(
        success=True,
        message="下载任务已创建并分发到Celery队列",
        task_id=task_id
    )

@router.get("/{task_id}", response_model=DownloadTaskStatusResponse)
async def get_download_task_status(
    task_id: str,
    task_service: DownloadTaskService = Depends(get_download_task_service)
) -> DownloadTaskStatusResponse:
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    progress = ProgressInfo(
        total=task.total_count,
        completed=task.completed_count,
        failed=task.failed_count,
        percentage=round((task.completed_count / task.total_count) * 100, 2) if task.total_count > 0 else 0.0
    )
    results = TaskResults(
        completed_ids=task.completed_ids or [],
        failed_ids=task.failed_results or []
    )
    task_status = TaskStatusInfo(
        task_id=task.task_id,
        status=task.status.value,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        progress=progress,
        results=results,
        error_message=task.error_message
    )
    return DownloadTaskStatusResponse(success=True, task_status=task_status)


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

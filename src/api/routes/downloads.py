"""
下载任务管理API路由 (V2)
Download Task Management API Routes (V2)

基于异步任务模式的下载管理接口
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.main import get_scraper
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService, DownloadTask, TaskStatus

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/downloads", tags=["下载任务"])

# 全局任务服务实例（在生产环境中应该使用数据库持久化）
_global_task_service = None


# Pydantic 请求模型
class DownloadTaskCreateRequest(BaseModel):
    """创建下载任务请求"""
    report_ids: List[int] = Field(..., description="报告ID列表 (upload_info_id)", min_items=1)
    save_dir: Optional[str] = Field("data/downloads", description="保存目录")
    max_concurrent: Optional[int] = Field(3, ge=1, le=10, description="最大并发数")


# Pydantic 响应模型
class DownloadTaskCreateResponse(BaseModel):
    """创建下载任务响应"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    task_id: str = Field(..., description="任务ID")


class ProgressInfo(BaseModel):
    """进度信息"""
    total: int = Field(..., description="总数量")
    completed: int = Field(..., description="已完成数量")
    failed: int = Field(..., description="失败数量")
    percentage: float = Field(..., description="完成百分比")


class TaskResults(BaseModel):
    """任务结果"""
    completed_ids: List[str] = Field(..., description="成功完成的ID列表")
    failed_ids: List[dict] = Field(..., description="失败的ID和错误信息")


class TaskStatusInfo(BaseModel):
    """任务状态信息"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    progress: ProgressInfo = Field(..., description="进度信息")
    results: TaskResults = Field(..., description="任务结果")
    error_message: Optional[str] = Field(None, description="错误消息")


class DownloadTaskStatusResponse(BaseModel):
    """下载任务状态响应"""
    success: bool = Field(..., description="请求是否成功")
    task_status: TaskStatusInfo = Field(..., description="任务状态详情")


def get_scraper() -> CSRCFundReportScraper:
    """获取爬虫实例"""
    from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
    import httpx

    # 为测试环境创建独立的HTTP客户端
    session = httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    )

    return CSRCFundReportScraper(session=session)


def get_fund_report_service(scraper: CSRCFundReportScraper = Depends(get_scraper)) -> FundReportService:
    """获取基金报告服务实例"""
    return FundReportService(scraper)


def get_download_task_service() -> DownloadTaskService:
    """获取下载任务服务实例（单例模式）"""
    global _global_task_service
    if _global_task_service is None:
        _global_task_service = DownloadTaskService()
    return _global_task_service


@router.post("", response_model=DownloadTaskCreateResponse, status_code=202)
async def create_download_task(
    request: DownloadTaskCreateRequest,
    background_tasks: BackgroundTasks,
    task_service: DownloadTaskService = Depends(get_download_task_service),
    fund_service: FundReportService = Depends(get_fund_report_service)
) -> DownloadTaskCreateResponse:
    """
    创建批量下载任务
    
    创建一个后台批量下载任务，立即返回任务ID。
    任务将在后台异步执行，可通过任务ID查询状态和进度。
    """
    bound_logger = logger.bind(
        report_count=len(request.report_ids),
        save_dir=request.save_dir,
        max_concurrent=request.max_concurrent
    )
    
    bound_logger.info("api.downloads.create_task.start")
    
    try:
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = DownloadTask(
            task_id=task_id,
            report_ids=request.report_ids,
            save_dir=request.save_dir,
            max_concurrent=request.max_concurrent,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            total_count=len(request.report_ids)
        )
        
        # 保存任务到服务
        await task_service.create_task(task)
        
        # 添加后台任务执行下载
        background_tasks.add_task(
            execute_download_task,
            task_id,
            task_service,
            fund_service
        )
        
        bound_logger.info(
            "api.downloads.create_task.success",
            task_id=task_id,
            report_count=len(request.report_ids)
        )
        
        return DownloadTaskCreateResponse(
            success=True,
            message="下载任务已创建",
            task_id=task_id
        )
        
    except Exception as e:
        bound_logger.error(
            "api.downloads.create_task.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"创建下载任务失败: {str(e)}")


@router.get("/{task_id}", response_model=DownloadTaskStatusResponse)
async def get_download_task_status(
    task_id: str,
    task_service: DownloadTaskService = Depends(get_download_task_service)
) -> DownloadTaskStatusResponse:
    """
    查询下载任务状态
    
    根据任务ID获取特定下载任务的当前状态和进度。
    """
    bound_logger = logger.bind(task_id=task_id)
    bound_logger.info("api.downloads.get_status.start")
    
    try:
        # 获取任务状态
        task = await task_service.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"任务不存在: {task_id}"
            )
        
        # 构建进度信息
        progress = ProgressInfo(
            total=task.total_count,
            completed=task.completed_count,
            failed=task.failed_count,
            percentage=round((task.completed_count / task.total_count) * 100, 2) if task.total_count > 0 else 0.0
        )
        
        # 构建结果信息
        results = TaskResults(
            completed_ids=task.completed_ids or [],
            failed_ids=task.failed_results or []
        )
        
        # 构建任务状态信息
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
        
        response = DownloadTaskStatusResponse(
            success=True,
            task_status=task_status
        )
        
        bound_logger.info(
            "api.downloads.get_status.success",
            status=task.status.value,
            progress_percentage=progress.percentage
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.downloads.get_status.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.get("", tags=["任务列表"])
async def list_download_tasks(
    status: Optional[str] = None,
    limit: int = 20,
    task_service: DownloadTaskService = Depends(get_download_task_service)
):
    """
    获取下载任务列表
    
    可选择按状态筛选任务。
    """
    bound_logger = logger.bind(status=status, limit=limit)
    bound_logger.info("api.downloads.list_tasks.start")
    
    try:
        # 验证状态参数
        status_filter = None
        if status:
            try:
                status_filter = TaskStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的任务状态: {status}. 有效值: {[s.value for s in TaskStatus]}"
                )
        
        # 获取任务列表
        tasks = await task_service.list_tasks(status=status_filter, limit=limit)
        
        # 转换为响应格式
        task_list = []
        for task in tasks:
            progress_percentage = round((task.completed_count / task.total_count) * 100, 2) if task.total_count > 0 else 0.0
            
            task_info = {
                "task_id": task.task_id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "total_count": task.total_count,
                "completed_count": task.completed_count,
                "failed_count": task.failed_count,
                "progress_percentage": progress_percentage
            }
            task_list.append(task_info)
        
        bound_logger.info(
            "api.downloads.list_tasks.success",
            task_count=len(task_list)
        )
        
        return {
            "success": True,
            "data": task_list,
            "total": len(task_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.downloads.list_tasks.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


async def execute_download_task(
    task_id: str,
    task_service: DownloadTaskService,
    fund_service: FundReportService
):
    """
    执行下载任务的后台函数
    Background function to execute download task
    """
    bound_logger = logger.bind(task_id=task_id)
    bound_logger.info("downloads.execute_task.start")
    
    try:
        # 获取任务
        task = await task_service.get_task(task_id)
        if not task:
            bound_logger.error("downloads.execute_task.task_not_found")
            return
        
        # 更新任务状态为进行中
        await task_service.update_task_status(task_id, TaskStatus.IN_PROGRESS, started_at=datetime.utcnow())
        
        # 执行下载
        from pathlib import Path
        save_dir = Path(task.save_dir)

        # 根据report_ids获取完整的报告信息
        # 注意：report_ids实际上是upload_info_id列表
        reports = []
        failed_to_get = []

        for upload_info_id in task.report_ids:
            try:
                # 尝试获取报告的完整信息
                report = await fund_service.get_report_by_upload_id(upload_info_id)
                if report:
                    reports.append(report)
                else:
                    failed_to_get.append(upload_info_id)
                    bound_logger.warning(
                        "downloads.execute_task.report_not_found",
                        upload_info_id=upload_info_id
                    )
            except Exception as e:
                failed_to_get.append(upload_info_id)
                bound_logger.error(
                    "downloads.execute_task.get_report_error",
                    upload_info_id=upload_info_id,
                    error=str(e)
                )

        bound_logger.info(
            "downloads.execute_task.reports_prepared",
            total_requested=len(task.report_ids),
            reports_found=len(reports),
            failed_to_get=len(failed_to_get),
            upload_info_ids=task.report_ids[:3]  # 只记录前3个ID
        )

        # 如果没有找到任何报告，标记任务失败
        if not reports:
            await task_service.update_task_status(
                task_id,
                TaskStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message="无法获取任何报告信息"
            )
            bound_logger.error("downloads.execute_task.no_reports_found")
            return

        # 执行批量下载
        download_result = await fund_service.batch_download(
            reports, save_dir, task.max_concurrent
        )
        
        # 更新任务结果
        if download_result["success"]:
            completed_ids = [r.get("upload_info_id", "") for r in download_result.get("results", []) if r.get("success")]
            failed_results = [
                {"id": r.get("upload_info_id", ""), "error": r.get("error", "")}
                for r in download_result.get("results", []) if not r.get("success")
            ]
            
            await task_service.update_task_progress(
                task_id,
                completed_count=len(completed_ids),
                failed_count=len(failed_results),
                completed_ids=completed_ids,
                failed_results=failed_results
            )
            
            # 标记任务完成
            await task_service.update_task_status(task_id, TaskStatus.COMPLETED, completed_at=datetime.utcnow())
            
            bound_logger.info(
                "downloads.execute_task.success",
                completed=len(completed_ids),
                failed=len(failed_results)
            )
        else:
            # 标记任务失败
            await task_service.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                completed_at=datetime.utcnow(),
                error_message=download_result.get("error", "Unknown error")
            )
            
            bound_logger.error(
                "downloads.execute_task.failed",
                error=download_result.get("error", "Unknown error")
            )
    
    except Exception as e:
        bound_logger.error(
            "downloads.execute_task.error",
            error=str(e),
            error_type=type(e).__name__
        )
        
        # 标记任务失败
        try:
            await task_service.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )
        except Exception as update_error:
            bound_logger.error(
                "downloads.execute_task.update_status_error",
                error=str(update_error)
            )

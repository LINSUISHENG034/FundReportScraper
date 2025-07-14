"""
下载任务 (Celery)
Download Tasks (Celery)

将下载和解析逻辑封装为Celery任务，实现真正的异步处理
"""

import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

from src.core.celery_app import app as celery_app
from src.core.config import settings
from src.core.logging import get_logger
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService, TaskStatus
from src.parsers.xbrl_parser import XBRLParser
from src.services.fund_data_service import FundDataService

logger = get_logger(__name__)


@celery_app.task(bind=True)
def test_celery_task(self):
    """
    测试Celery是否正常工作的简单任务
    Simple task to test if Celery is working properly
    """
    print("Test task executed successfully!")
    print(f"Task ID: {self.request.id}")

    return {
        "success": True,
        "message": "Celery is working!",
        "timestamp": datetime.now().isoformat(),
        "task_id": self.request.id
    }


def _validate_and_prepare_task(task_service: DownloadTaskService, task_id: str, celery_request, bound_logger) -> tuple:
    """
    验证任务状态并准备执行
    Validate task status and prepare for execution
    """
    # 获取任务信息
    task = task_service.get_task_sync(task_id)
    if not task:
        error_msg = f"Task {task_id} not found in database"
        bound_logger.error("celery.download_task.task_not_found_in_db", task_id=task_id)
        return None, {"success": False, "error": error_msg}

    # 验证任务状态
    if task.status == TaskStatus.COMPLETED:
        bound_logger.warning("celery.download_task.already_completed", task_id=task_id)
        return None, {"success": True, "message": "Task already completed"}
    
    if task.status == TaskStatus.FAILED and celery_request.retries == 0:
        bound_logger.info("celery.download_task.retry_failed_task", task_id=task_id)

    # 更新任务状态为进行中
    task_service.update_task_status_sync(
        task_id,
        TaskStatus.IN_PROGRESS,
        started_at=datetime.utcnow()
    )
    
    # 更新Celery任务ID到数据库
    try:
        success = task_service.update_task_celery_id_sync(task_id, celery_request.id)
        if success:
            bound_logger.info("celery.download_task.celery_id_updated", celery_task_id=celery_request.id)
        else:
            bound_logger.warning("celery.download_task.celery_id_update_failed")
    except Exception as e:
        bound_logger.warning("celery.download_task.celery_id_update_error", error=str(e))

    bound_logger.info(
        "celery.download_task.task_started",
        report_count=len(task.report_ids),
        save_dir=task.save_dir
    )
    
    return task, None


def _get_reports_to_download(fund_service: FundReportService, task, task_service: DownloadTaskService, task_id: str, bound_logger) -> tuple:
    """
    获取要下载的报告信息
    Get reports information for download
    """
    reports_to_download = fund_service.get_reports_by_ids_sync(task.report_ids)

    if not reports_to_download:
        error_msg = "无法获取任何报告信息"
        task_service.update_task_status_sync(
            task_id,
            TaskStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=error_msg
        )
        bound_logger.error("celery.download_task.no_reports_found")
        return None, {"success": False, "error": error_msg}
    
    return reports_to_download, None


def _execute_batch_download(fund_service: FundReportService, reports_to_download: List[Dict], task, bound_logger) -> Dict:
    """
    执行批量下载
    Execute batch download
    """
    save_dir = Path(task.save_dir)
    download_result = fund_service.batch_download_sync(
        reports_to_download,
        save_dir,
        task.max_concurrent
    )

    # 处理下载结果
    completed_downloads = [
        r for r in download_result.get("results", [])
        if r.get("success")
    ]
    failed_downloads = [
        r for r in download_result.get("results", [])
        if not r.get("success")
    ]

    bound_logger.info(
        "celery.download_task.download_completed",
        completed=len(completed_downloads),
        failed=len(failed_downloads)
    )
    
    return {
        "completed_downloads": completed_downloads,
        "failed_downloads": failed_downloads
    }


def _parse_single_download(download: Dict, fund_data_service: FundDataService, bound_logger) -> tuple:
    """
    解析单个下载文件
    Parse single downloaded file
    """
    try:
        file_path = Path(download["file_path"])
        if not file_path.exists():
            return None, {
                "upload_info_id": download.get("upload_info_id", "unknown"),
                "error": f"Downloaded file not found: {download['file_path']}"
            }

        # 解析XBRL文件
        parser = XBRLParser()
        parsed_data = parser.parse_file(file_path)

        if not parsed_data:
            return None, {
                "upload_info_id": download.get("upload_info_id", "unknown"),
                "error": "Failed to parse XBRL file"
            }

        # 保存解析后的数据
        upload_info_id = download.get("upload_info_id", "unknown")
        report_id = fund_data_service.save_fund_report(
            parsed_data,
            upload_info_id,
            file_path
        )

        if not report_id:
            return None, {
                "upload_info_id": upload_info_id,
                "error": "Failed to save parsed data"
            }

        bound_logger.info(
            "celery.download_task.parsing_success",
            upload_info_id=upload_info_id,
            report_id=report_id
        )
        
        return {
            "upload_info_id": upload_info_id,
            "report_id": report_id,
            "file_path": str(file_path)
        }, None

    except Exception as e:
        upload_info_id = download.get("upload_info_id", "unknown")
        error_msg = f"Parsing error: {str(e)}"
        bound_logger.error(
            "celery.download_task.parsing_error",
            upload_info_id=upload_info_id,
            error=str(e),
            error_type=type(e).__name__
        )
        return None, {
            "upload_info_id": upload_info_id,
            "error": error_msg
        }


def _process_parsing_results(completed_downloads: List[Dict], fund_data_service: FundDataService, bound_logger) -> tuple:
    """
    处理解析结果
    Process parsing results
    """
    parsing_failures = []
    successfully_parsed = []

    for download in completed_downloads:
        success_result, failure_result = _parse_single_download(download, fund_data_service, bound_logger)
        
        if success_result:
            successfully_parsed.append(success_result)
        elif failure_result:
            parsing_failures.append(failure_result)
    
    return successfully_parsed, parsing_failures


def _update_task_results(task_service: DownloadTaskService, task_id: str, task, 
                        successfully_parsed: List[Dict], failed_downloads: List[Dict], 
                        parsing_failures: List[Dict], bound_logger) -> Dict:
    """
    更新任务结果
    Update task results
    """
    # 更新任务进度
    total_failed = len(failed_downloads) + len(parsing_failures)
    completed_ids = [str(r["upload_info_id"]) for r in successfully_parsed]
    failed_results = []

    # 添加下载失败的结果
    for failed in failed_downloads:
        failed_results.append({
            "id": str(failed.get("upload_info_id", "unknown")),
            "error": failed.get("error", "Download failed")
        })

    # 添加解析失败的结果
    for failed in parsing_failures:
        failed_results.append({
            "id": str(failed["upload_info_id"]),
            "error": failed["error"]
        })

    task_service.update_task_progress_sync(
        task_id,
        completed_count=len(successfully_parsed),
        failed_count=total_failed,
        completed_ids=completed_ids,
        failed_results=failed_results
    )

    # 标记任务完成
    task_service.update_task_status_sync(
        task_id,
        TaskStatus.COMPLETED,
        completed_at=datetime.utcnow()
    )

    bound_logger.info(
        "celery.download_task.success",
        total_reports=len(task.report_ids),
        successfully_parsed=len(successfully_parsed),
        total_failed=total_failed
    )

    return {
        "success": True,
        "task_id": task_id,
        "total_reports": len(task.report_ids),
        "successfully_parsed": len(successfully_parsed),
        "total_failed": total_failed,
        "completed_ids": completed_ids,
        "failed_results": failed_results
    }


def _handle_task_retry(task_service: DownloadTaskService, task_id: str, celery_task, 
                      error: Exception, error_msg: str, bound_logger) -> Dict:
    """
    处理任务重试逻辑
    Handle task retry logic
    """
    max_retries = 3
    if celery_task.request.retries < max_retries:
        # 计算重试延迟（指数退避）
        retry_delay = 60 * (2 ** celery_task.request.retries)  # 60s, 120s, 240s
        bound_logger.info(
            "celery.download_task.retry_scheduled",
            retry_count=celery_task.request.retries + 1,
            max_retries=max_retries,
            retry_delay=retry_delay,
            task_id=task_id
        )
        
        # 更新任务状态为重试中
        try:
            task_service.update_task_status_sync(
                task_id,
                TaskStatus.PENDING,  # 重置为PENDING状态
                error_message=f"Retry {celery_task.request.retries + 1}/{max_retries}: {error_msg}"
            )
        except Exception as update_error:
            bound_logger.error(
                "celery.download_task.update_retry_status_error",
                error=str(update_error)
            )
        
        # 抛出重试异常
        raise celery_task.retry(countdown=retry_delay, exc=error)

    # 达到最大重试次数，标记任务失败
    try:
        task_service.update_task_status_sync(
            task_id,
            TaskStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=f"Failed after {max_retries} retries: {error_msg}"
        )
    except Exception as update_error:
        bound_logger.error(
            "celery.download_task.update_status_error",
            error=str(update_error)
        )

    return {
        "success": False,
        "task_id": task_id,
        "error": f"Failed after {max_retries} retries: {error_msg}",
        "retries": celery_task.request.retries
    }


@celery_app.task(bind=True)
def download_fund_report_task(self, task_id: str):
    """
    下载并处理基金报告的 Celery 任务 (重构版本)
    Download and process fund report Celery task (refactored version)
    
    重构后的版本将复杂逻辑拆分为多个小函数，提高可读性和可维护性
    """
    bound_logger = logger.bind(
        task_id=task_id,
        celery_task_id=self.request.id,
        component="celery_download_task"
    )

    bound_logger.info("celery.download_task.start", 
                     celery_task_id=self.request.id,
                     retries=self.request.retries)

    # 获取数据库URL
    db_url = settings.database.url

    # 在Celery任务中，所有服务都应该使用独立的数据库会话
    task_service = DownloadTaskService(db_url=db_url)
    fund_data_service = FundDataService(db_url=db_url)

    try:
        # 创建HTTP客户端和相关服务
        with httpx.Client(follow_redirects=True, timeout=30.0) as http_client:
            scraper = CSRCFundReportScraper(session=http_client)
            fund_service = FundReportService(scraper)

            # 步骤1: 验证和准备任务
            task, early_return = _validate_and_prepare_task(task_service, task_id, self.request, bound_logger)
            if early_return:
                return early_return

            # 步骤2: 获取要下载的报告信息
            reports_to_download, error_return = _get_reports_to_download(fund_service, task, task_service, task_id, bound_logger)
            if error_return:
                return error_return

            # 步骤3: 执行批量下载
            download_results = _execute_batch_download(fund_service, reports_to_download, task, bound_logger)
            
            # 步骤4: 处理解析结果
            successfully_parsed, parsing_failures = _process_parsing_results(
                download_results["completed_downloads"], fund_data_service, bound_logger
            )
            
            # 步骤5: 更新任务结果
            return _update_task_results(
                task_service, task_id, task, successfully_parsed, 
                download_results["failed_downloads"], parsing_failures, bound_logger
            )

    except Exception as e:
        error_msg = f"Task execution failed: {str(e)}"
        bound_logger.error(
            "celery.download_task.error",
            error=str(e),
            error_type=type(e).__name__,
            task_id=task_id,
            celery_task_id=self.request.id,
            retries=self.request.retries
        )

        # 处理重试逻辑
        return _handle_task_retry(task_service, task_id, self, e, error_msg, bound_logger)

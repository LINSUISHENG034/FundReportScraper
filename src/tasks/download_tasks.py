"""
下载任务 (Celery)
Download Tasks (Celery)

将下载和解析逻辑封装为Celery任务，实现真正的异步处理
"""

import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from src.core.celery_app import app as celery_app
from src.core.config import settings
from src.core.logging import get_logger
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService, TaskStatus
from src.parsers.xbrl_parser import XBRLParser
from src.services.fund_data_service import FundDataService

logger = get_logger(__name__)


@celery_app.task(name="tasks.test_celery")
def test_celery_task():
    """
    测试Celery是否正常工作的简单任务
    Simple task to test if Celery is working properly
    """
    print("Test task executed successfully!")

    return {
        "success": True,
        "message": "Celery is working!",
        "timestamp": datetime.now().isoformat()
    }


@celery_app.task(name="tasks.download_fund_report")
def download_fund_report_task(task_id: str):
    """
    下载并处理基金报告的 Celery 任务 (完整版本)
    Download and process fund report Celery task (full version)

    这是从 execute_download_task 迁移过来的完整逻辑
    """
    bound_logger = logger.bind(
        task_id=task_id,
        component="celery_download_task"
    )

    bound_logger.info("celery.download_task.start")

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

            # 获取任务信息
            # 注意：这里需要同步版本的get_task，因为Celery任务是同步的
            task = task_service.get_task_sync(task_id)
            if not task:
                bound_logger.error("celery.download_task.task_not_found_in_db")
                return {"success": False, "error": "Task not found in database"}

            # 更新任务状态为进行中
            task_service.update_task_status_sync(
                task_id,
                TaskStatus.IN_PROGRESS,
                started_at=datetime.utcnow()
            )

            bound_logger.info(
                "celery.download_task.task_started",
                report_count=len(task.report_ids),
                save_dir=task.save_dir
            )

            # 获取要下载的报告信息
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
                return {"success": False, "error": error_msg}

            # 执行批量下载
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

            # 解析下载成功的文件
            parsing_failures = []
            successfully_parsed = []

            for download in completed_downloads:
                try:
                    file_path = Path(download["file_path"])
                    if file_path.exists():
                        # 解析XBRL文件
                        parser = XBRLParser()
                        parsed_data = parser.parse_file(file_path)

                        if parsed_data:
                            # 保存解析后的数据
                            upload_info_id = download.get("upload_info_id", "unknown")
                            report_id = fund_data_service.save_fund_report(
                                parsed_data,
                                upload_info_id,
                                file_path
                            )

                            if report_id:
                                successfully_parsed.append({
                                    "upload_info_id": upload_info_id,
                                    "report_id": report_id,
                                    "file_path": str(file_path)
                                })
                                bound_logger.info(
                                    "celery.download_task.parsing_success",
                                    upload_info_id=upload_info_id,
                                    report_id=report_id
                                )
                            else:
                                parsing_failures.append({
                                    "upload_info_id": upload_info_id,
                                    "error": "Failed to save parsed data"
                                })
                        else:
                            parsing_failures.append({
                                "upload_info_id": download.get("upload_info_id", "unknown"),
                                "error": "Failed to parse XBRL file"
                            })
                    else:
                        parsing_failures.append({
                            "upload_info_id": download.get("upload_info_id", "unknown"),
                            "error": f"Downloaded file not found: {download['file_path']}"
                        })

                except Exception as e:
                    upload_info_id = download.get("upload_info_id", "unknown")
                    error_msg = f"Parsing error: {str(e)}"
                    parsing_failures.append({
                        "upload_info_id": upload_info_id,
                        "error": error_msg
                    })
                    bound_logger.error(
                        "celery.download_task.parsing_error",
                        upload_info_id=upload_info_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )

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

    except Exception as e:
        error_msg = f"Task execution failed: {str(e)}"
        bound_logger.error(
            "celery.download_task.error",
            error=str(e),
            error_type=type(e).__name__
        )

        # 标记任务失败
        try:
            task_service.update_task_status_sync(
                task_id,
                TaskStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message=error_msg
            )
        except Exception as update_error:
            bound_logger.error(
                "celery.download_task.update_status_error",
                error=str(update_error)
            )

        return {
            "success": False,
            "task_id": task_id,
            "error": error_msg
        }

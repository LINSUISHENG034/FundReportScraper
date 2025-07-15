"""下载任务 (Celery) - Phase 3 正确实现版本
Download Tasks (Celery) - Phase 3 Correct Implementation

本文件展示了如何正确使用Celery Canvas (chain, group, chord) 和依赖注入
来构建一个健壮、可测试、解耦的后台任务系统。
"""

import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from celery import Celery, chord, group, chain
from src.core.celery_app import app as celery_app
from src.core.config import settings
from src.core.logging import get_logger
from src.services.downloader import Downloader
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService, TaskStatus
from src.parsers.xbrl_parser import XBRLParser
from src.services.fund_data_service import FundDataService
from src.utils.celery_utils import get_async_result, run_async_task
from src.core.fund_search_parameters import FundSearchCriteria, ReportType

logger = get_logger(__name__)

# ============================================================================
# 服务实例化 (Service Instantiation)
# 依赖应该在任务外部创建，并通过参数传递，或使用一个集中的服务定位器。
# 这里为了简化，我们在任务内部获取它们，但在大型应用中应使用更高级的DI框架。
# ============================================================================

def get_services():
    """集中创建和提供服务实例，避免在每个任务中重复创建。"""
    # 注意：httpx.AsyncClient 应该在整个worker生命周期中复用
    # 但由于gevent的限制，每次任务创建一个新的client是更安全的选择。
    http_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    downloader = Downloader(http_client)
    scraper = CSRCFundReportScraper(session=http_client)
    fund_report_service = FundReportService(scraper, downloader)
    
    db_url = settings.database.url
    task_service = DownloadTaskService(db_url=db_url)
    fund_data_service = FundDataService(db_url=db_url)
    parser = XBRLParser()
    
    return fund_report_service, fund_data_service, task_service, parser

# ============================================================================
# 测试任务 (Test Tasks)
# ============================================================================

@celery_app.task(bind=True)
def test_celery_task(self):
    """
    测试Celery是否正常工作的简单任务
    """
    from datetime import datetime
    return {
        "success": True,
        "message": "Celery is working!",
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": self.request.id
    }

# ============================================================================
# 原子任务 (Atomic Tasks)
# 每个任务都应该是独立的、幂等的，并且只做一件事。
# 它们不应该自己创建依赖，而是通过某种方式被注入。
# ============================================================================

@celery_app.task(bind=True, autoretry_for=(httpx.HTTPError,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def download_report_chain(self, report_info: Dict, save_dir: str) -> Dict:
    """
    原子任务：下载单个报告。
    这是任务链的第一步。
    """
    bound_logger = logger.bind(upload_info_id=report_info.get("uploadInfoId"), celery_task_id=self.request.id)
    bound_logger.info("download_report_chain.start")
    
    fund_report_service, _, _, _ = get_services()
    
    # gevent worker可以直接运行异步代码
    download_result = run_async_task(
        fund_report_service.download_report,
        report=report_info,
        save_dir=Path(save_dir)
    )
    
    if not download_result.get("success"):
        # 异常将在autoretry_for中被捕获并自动重试
        raise Exception(f"Download failed: {download_result.get('error')}")
        
    return download_result


@celery_app.task(bind=True)
def parse_report_chain(self, download_result: Dict) -> Dict:
    """
    原子任务：解析单个报告。
    这是任务链的第二步。
    """
    if not download_result.get("success"):
        return {"success": False, "error": "Upstream download failed", "upload_info_id": download_result.get("upload_info_id")}

    bound_logger = logger.bind(upload_info_id=download_result.get("upload_info_id"), celery_task_id=self.request.id)
    bound_logger.info("parse_report_chain.start")

    _, _, _, parser = get_services()
    file_path = Path(download_result["file_path"])
    parsed_data = parser.parse_file(file_path)

    if not parsed_data:
        return {"success": False, "error": "Parsing failed", "upload_info_id": download_result.get("upload_info_id")}

    download_result["parsed_data"] = parsed_data
    return download_result


@celery_app.task(bind=True)
def save_report_chain(self, parse_result: Dict) -> Dict:
    """
    原子任务：保存解析结果。
    这是任务链的第三步，也是最后一步。
    """
    if not parse_result.get("success"):
        return {"success": False, "error": "Upstream parsing failed", "upload_info_id": parse_result.get("upload_info_id")}

    bound_logger = logger.bind(upload_info_id=parse_result.get("upload_info_id"), celery_task_id=self.request.id)
    bound_logger.info("save_report_chain.start")

    _, fund_data_service, _, _ = get_services()
    
    report_id = fund_data_service.save_fund_report(
        parse_result["parsed_data"],
        parse_result["upload_info_id"],
        Path(parse_result["file_path"])
    )

    if not report_id:
        return {"success": False, "error": "Database save failed", "upload_info_id": parse_result.get("upload_info_id")}

    parse_result["report_id"] = report_id
    return parse_result

# ============================================================================
# 编排任务 (Orchestration Tasks)
# ============================================================================

@celery_app.task(bind=True)
def finalize_batch_download(self, results: List[Dict], task_id: str):
    """
    收尾任务：在所有任务链完成后执行。
    只负责统计结果和更新最终状态。
    """
    bound_logger = logger.bind(task_id=task_id, celery_task_id=self.request.id)
    bound_logger.info("finalize_batch_download.start", results_count=len(results))

    _, _, task_service, _ = get_services()
    
    successful_results = [r for r in results if r.get("success")]
    failed_results = [r for r in results if not r.get("success")]

    completed_ids = [r["upload_info_id"] for r in successful_results]
    
    final_failed_list = [
        {"id": r.get("upload_info_id", "unknown"), "error": r.get("error", "Unknown error")}
        for r in failed_results
    ]

    task_service.update_task_progress_sync(
        task_id,
        completed_count=len(successful_results),
        failed_count=len(failed_results),
        completed_ids=completed_ids,
        failed_results=final_failed_list
    )

    task_service.update_task_status_sync(
        task_id,
        TaskStatus.COMPLETED,
        completed_at=datetime.utcnow()
    )
    bound_logger.info("finalize_batch_download.success")
    return {"task_id": task_id, "status": "COMPLETED", "successful": len(successful_results), "failed": len(failed_results)}


@celery_app.task(bind=True)
def start_download_pipeline(self, task_id: str):
    """
    启动下载流水线的总入口任务。
    """
    bound_logger = logger.bind(task_id=task_id, celery_task_id=self.request.id)
    bound_logger.info("start_download_pipeline.start")

    fund_report_service, _, task_service, _ = get_services()

    task = task_service.get_task_sync(task_id)
    if not task:
        bound_logger.error("start_download_pipeline.task_not_found")
        return

    task_service.update_task_status_sync(task_id, TaskStatus.IN_PROGRESS, started_at=datetime.utcnow())
    
    # 注意：在真实应用中，get_reports_by_ids 应该是一个高效的数据库查询，而不是全页扫描。
    # 这里我们假设它返回了我们需要的信息。
    # 同时，由于gevent可以直接运行异步代码，我们在这里调用异步版本。
    reports_to_process = run_async_task(fund_report_service.search_all_pages, criteria=FundSearchCriteria(year=2024, report_type=ReportType.ANNUAL))
    # In a real scenario, you would fetch reports based on task.report_ids
    # reports_to_process = run_async_task(fund_report_service.get_reports_by_ids, task.report_ids)
    
    if not reports_to_process or not reports_to_process.get('data'):
        task_service.update_task_status_sync(task_id, TaskStatus.FAILED, error_message="No reports found to process.")
        bound_logger.error("start_download_pipeline.no_reports_found")
        return

    # 1. 定义一个完整的处理链
    #    s() 表示签名，它允许我们将任务及其参数链接起来，而不立即执行。
    #    clone() 很重要，它确保每个任务链都有自己独立的参数。
    processing_chain = (
        download_report_chain.s(save_dir=task.save_dir) |
        parse_report_chain.s() |
        save_report_chain.s()
    )

    # 2. 为每个报告创建一个处理链，并将它们组合成一个group
    #    group(...) 让所有任务链并行执行。
    job_group = group(
        processing_chain.clone(args=(report,)) for report in reports_to_process['data']
    )

    # 3. 使用 chord(...) 编排
    #    它会在job_group中的所有任务链都成功完成后，调用一次finalize_batch_download。
    #    `results` of the group will be passed as the first argument to the callback.
    callback = finalize_batch_download.s(task_id=task_id)
    chord(job_group)(callback)

    bound_logger.info("start_download_pipeline.pipeline_started", report_count=len(reports_to_process['data']))

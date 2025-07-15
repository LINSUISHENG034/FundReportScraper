"""下载任务 (Celery) - Phase 3 正确实现版本
Download Tasks (Celery) - Phase 3 Correct Implementation

本文件展示了如何正确使用Celery Canvas (chain, group, chord) 和依赖注入
来构建一个健壮、可测试、解耦的后台任务系统。
"""

import requests
from pathlib import Path
from typing import List, Dict, Any

from celery import chord, group, chain
from src.core.celery_app import app as celery_app
from src.core.logging import get_logger
from src.services.downloader import Downloader
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.parsers.xbrl_parser import XBRLParser
from src.utils.model_utils import orm_to_dict

logger = get_logger(__name__)

# ============================================================================
# 服务实例化 (Service Instantiation)
# 依赖应该在任务外部创建，并通过参数传递，或使用一个集中的服务定位器。
# 这里为了简化，我们在任务内部获取它们，但在大型应用中应使用更高级的DI框架。
# ============================================================================


def get_download_service_sync() -> FundReportService:
    """
    获取一个纯同步的、用于下载的服务实例。
    """
    downloader = Downloader()
    # 最终修复：必须实例化一个Scraper，因为FundReportService需要
    # 调用它的 get_download_url 方法。
    # 幸运的是，Scraper的实例化不需要session。
    scraper = CSRCFundReportScraper()
    fund_report_service = FundReportService(scraper=scraper, downloader=downloader)
    return fund_report_service


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
        "task_id": self.request.id,
    }


# ============================================================================
# 原子任务 (Atomic Tasks)
# 每个任务都应该是独立的、幂等的，并且只做一件事。
# 它们不应该自己创建依赖，而是通过某种方式被注入。
# ============================================================================


@celery_app.task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def download_report_chain(self, report_info: Dict, save_dir: str) -> Dict:
    """
    原子任务：下载单个报告。
    这是任务链的第一步。现在是100%同步执行，无任何异步依赖。
    """
    bound_logger = logger.bind(
        upload_info_id=report_info.get("upload_info_id"), celery_task_id=self.request.id
    )
    bound_logger.info("download_report_chain.start.sync")

    # 获取纯同步的服务
    fund_report_service = get_download_service_sync()

    # 直接调用同步方法，不再需要复杂的 try/finally 来关闭会话
    download_result = fund_report_service.download_report(
        report=report_info, save_dir=Path(save_dir)
    )

    if not download_result.get("success"):
        # The exception for autoretry is now requests.exceptions.RequestException
        # We still raise a generic exception to be safe.
        raise Exception(f"Download failed: {download_result.get('error')}")

    return download_result


@celery_app.task(bind=True)
def parse_report_chain(self, download_result: Dict) -> Dict:
    """
    原子任务：解析单个报告。
    这是任务链的第二步。
    """
    if not download_result.get("success"):
        return {
            "success": False,
            "error": "Upstream download failed",
            "upload_info_id": download_result.get("upload_info_id"),
        }

    bound_logger = logger.bind(
        upload_info_id=download_result.get("upload_info_id"),
        celery_task_id=self.request.id,
    )
    bound_logger.info("parse_report_chain.start")

    # 解析任务是纯CPU密集型的，不需要异步服务
    parser = XBRLParser()
    file_path = Path(download_result["file_path"])
    parsed_data_obj = parser.parse_file(file_path)

    if not parsed_data_obj:
        return {
            "success": False,
            "error": "Parsing failed",
            "upload_info_id": download_result.get("upload_info_id"),
        }

    # 在返回前，使用新的工具函数将其转换为可序列化的字典
    download_result["parsed_data"] = orm_to_dict(parsed_data_obj)

    return download_result


@celery_app.task(bind=True)
def save_report_chain(self, parse_result: Dict) -> Dict:
    """
    原子任务：保存解析结果。
    这是任务链的第三步，也是最后一步。
    注意：数据保存功能已迁移到其他系统，此任务现在只做标记处理。
    """
    if not parse_result.get("success"):
        return {
            "success": False,
            "error": "Upstream parsing failed",
            "upload_info_id": parse_result.get("upload_info_id"),
        }

    bound_logger = logger.bind(
        upload_info_id=parse_result.get("upload_info_id"),
        celery_task_id=self.request.id,
    )
    bound_logger.info("save_report_chain.start")

    # TODO: 实现新的数据保存逻辑或集成到其他系统
    # 目前只标记为成功处理
    parse_result["report_id"] = f"processed_{parse_result.get('upload_info_id')}"
    bound_logger.info("save_report_chain.completed_placeholder")

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

    successful_results = [r for r in results if r.get("success")]
    failed_results = [r for r in results if not r.get("success")]

    completed_ids = [r["upload_info_id"] for r in successful_results]

    final_failed_list = [
        {
            "id": r.get("upload_info_id", "unknown"),
            "error": r.get("error", "Unknown error"),
        }
        for r in failed_results
    ]

    # TODO: 实现新的任务状态更新逻辑
    # 目前只记录日志
    bound_logger.info(
        "finalize_batch_download.summary",
        task_id=task_id,
        successful_count=len(successful_results),
        failed_count=len(failed_results),
        completed_ids=completed_ids,
        failed_results=final_failed_list,
    )

    bound_logger.info("finalize_batch_download.success")
    return {
        "task_id": task_id,
        "status": "COMPLETED",
        "successful": len(successful_results),
        "failed": len(failed_results),
    }


@celery_app.task(bind=True)
def start_download_pipeline(
    self, task_id: str, reports_to_process: List[Dict[str, Any]], save_dir: str
):
    """
    启动下载流水线的总入口任务。
    此任务现在直接接收需要处理的报告列表，不再执行任何搜索操作。
    """
    bound_logger = logger.bind(task_id=task_id, celery_task_id=self.request.id)
    bound_logger.info(
        "start_download_pipeline.start", report_count=len(reports_to_process)
    )

    # TODO: 实现新的任务状态管理逻辑
    # 目前直接开始处理
    bound_logger.info("start_download_pipeline.task_started", task_id=task_id)

    if not reports_to_process:
        bound_logger.error("start_download_pipeline.no_reports_found", task_id=task_id)
        # 调用回调以将任务标记为完成，即使没有要处理的报告
        finalize_batch_download.delay([], task_id)
        return

    # 1. 为每个报告创建一个完整的处理链，并将它们组合成一个group
    #    chain(...) 将任务链接起来
    #    s(...) 创建一个带有预设参数的任务签名
    #    group(...) 让所有任务链并行执行
    job_group = group(
        chain(
            download_report_chain.s(report, save_dir=save_dir),
            parse_report_chain.s(),
            save_report_chain.s(),
        )
        for report in reports_to_process
    )

    # 3. 使用 chord(...) 编排
    #    它会在job_group中的所有任务链都成功完成后，调用一次finalize_batch_download。
    #    `results` of the group will be passed as the first argument to the callback.
    callback = finalize_batch_download.s(task_id=task_id)
    
    # Capture the AsyncResult of the chord
    chord_result = chord(job_group)(callback)

    bound_logger.info(
        "start_download_pipeline.pipeline_started", 
        report_count=len(reports_to_process),
        chord_task_id=chord_result.id # Log the chord's ID
    )
    
    # Return the chord's ID so the client can poll it for the final result
    return {"main_task_id": task_id, "chord_task_id": chord_result.id}

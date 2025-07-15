"""Tasks package initialization."""

# Phase 3: 导入新的任务分解架构
from .download_tasks import (
    test_celery_task,
    download_report_chain,
    parse_report_chain,
    save_report_chain,
    start_download_pipeline,
    finalize_batch_download,
)

__all__ = [
    "test_celery_task",
    "download_report_chain",
    "parse_report_chain",
    "save_report_chain",
    "start_download_pipeline",
    "finalize_batch_download",
]

# 其他任务模块暂时注释掉，避免导入错误
# from .scraping_tasks import scrape_fund_reports, scrape_single_fund_report
# from .parsing_tasks import parse_xbrl_file, batch_parse_xbrl_files
# from .monitoring_tasks import check_task_health, cleanup_expired_tasks

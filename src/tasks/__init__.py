"""Tasks package initialization."""

# Phase 5: 只导入可用的任务模块
from .download_tasks import download_fund_report_task, test_celery_task

__all__ = [
    "download_fund_report_task",
    "test_celery_task"
]

# 其他任务模块暂时注释掉，避免导入错误
# from .scraping_tasks import scrape_fund_reports, scrape_single_fund_report
# from .parsing_tasks import parse_xbrl_file, batch_parse_xbrl_files
# from .monitoring_tasks import check_task_health, cleanup_expired_tasks
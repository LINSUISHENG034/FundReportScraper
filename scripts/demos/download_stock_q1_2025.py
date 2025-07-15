import asyncio
from src.core.fund_search_parameters import ReportType, FundType, FundSearchCriteria
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService


async def main():
    """下载2025年股票型基金第一季度报告"""
    print("--- 开始下载任务 ---")

    criteria = FundSearchCriteria(
        year=2025, report_type=ReportType.QUARTERLY_Q1, fund_type=FundType.STOCK
    )

    save_dir = "data/stock_q1_2025"
    limit = 10  #  仅下载10个报告作为示例

    async with CSRCFundReportScraper() as scraper:
        task_service = DownloadTaskService()

        print(f"[1/3] 正在搜索报告...")
        reports, has_next = await scraper.get_report_list(
            year=criteria.year,
            report_type=criteria.report_type,
            fund_type=criteria.fund_type.value if criteria.fund_type else None,
        )

        if not reports:
            print("未找到符合条件的报告。")
            return

        # 应用限制
        if len(reports) > limit:
            reports = reports[:limit]

        print(f"找到 {len(reports)} 份报告。")

        print(f"[2/3] 正在创建下载任务...")
        # 从报告字典中提取 'announcementId'
        report_ids = [report["announcementId"] for report in reports]
        task_id = await task_service.create_and_dispatch_task(report_ids, save_dir)
        print(f"任务已创建，ID: {task_id}")

        print(f"[3/3] 正在监控下载进度...")
        await monitor_task(task_service, task_id)


async def monitor_task(task_service: DownloadTaskService, task_id: str):
    while True:
        task = await task_service.get_task(task_id)
        if not task:
            print("\n错误：找不到任务。")
            break

        progress = (
            (task.completed_count / task.total_count) * 100
            if task.total_count > 0
            else 0
        )
        progress_bar = f"[{'#' * int(progress // 10):<10}] {progress:.2f}%"
        status_text = f"状态: {task.status.value}, 进度: {task.completed_count}/{task.total_count} {progress_bar}"
        print(f"\r{status_text}", end="")

        if task.status in ["COMPLETED", "FAILED"]:
            print(f"\n任务完成，最终状态: {task.status.value}")
            if task.error_message:
                print(f"错误信息: {task.error_message}")
            break

        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())

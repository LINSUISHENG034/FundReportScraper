import asyncio
import click
from datetime import datetime
from typing import Optional

from src.core.fund_search_parameters import ReportType, FundType, FundSearchCriteria
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.download_task_service import DownloadTaskService

# Phase 3: 任务编排已迁移到 start_download_pipeline，通过 DownloadTaskService 调用


@click.group()
def cli():
    """基金报告下载命令行工具"""
    pass


@cli.command()
@click.option(
    "--report-type",
    type=click.Choice(["ANNUAL", "SEMI_ANNUAL", "QUARTERLY", "FUND_PROFILE"]),
    required=True,
    help="报告类型 (QUARTERLY, ANNUAL, etc.)",
)
@click.option(
    "--fund-type", type=click.Choice([e.value for e in FundType]), help="基金类型"
)
@click.option("--year", type=int, default=datetime.now().year, help="报告年份")
@click.option(
    "--quarter",
    type=click.IntRange(1, 4),
    help="报告季度 (当 report-type 为 QUARTERLY 时必须提供)",
)
@click.option("--fund-code", help="基金代码")
@click.option("--fund-name", help="基金名称")
@click.option("--save-dir", default="data/cli_downloads", help="下载文件保存目录")
@click.option("--limit", type=int, default=10, help="要下载的报告数量上限")
def download(
    report_type: str,
    fund_type: str,
    year: int,
    quarter: Optional[int],
    fund_code: Optional[str],
    fund_name: Optional[str],
    save_dir: str,
    limit: int,
):
    """根据条件搜索并下载基金报告"""
    click.echo("--- 开始下载任务 ---")

    final_report_type: ReportType
    if report_type == "QUARTERLY":
        if not quarter:
            raise click.UsageError("使用 'QUARTERLY' 报告类型时, 必须提供 --quarter 参数。")
        quarter_map = {
            1: ReportType.QUARTERLY_Q1,
            2: ReportType.QUARTERLY_Q2,
            3: ReportType.QUARTERLY_Q3,
            4: ReportType.QUARTERLY_Q4,
        }
        final_report_type = quarter_map[quarter]
    else:
        if quarter:
            click.echo("警告: --quarter 参数仅在 --report-type 为 'QUARTERLY' 时有效，将被忽略。")
        final_report_type = ReportType[report_type]

    criteria = FundSearchCriteria(
        report_type=final_report_type,
        fund_type=FundType(fund_type) if fund_type else None,
        year=year,
        fund_code=fund_code,
        fund_short_name=fund_name,
    )

    async def main():
        async with CSRCFundReportScraper() as scraper:
            report_service = FundReportService(scraper)
            task_service = DownloadTaskService()

            click.echo(f"[1/3] 正在搜索报告...")
            reports = await report_service.search_all_pages(criteria, limit=limit)

            if not reports:
                click.echo("未找到符合条件的报告。")
                return

            click.echo(f"找到 {len(reports)} 份报告。")
            report_ids = [report["id"] for report in reports]

            click.echo(f"[2/3] 正在创建下载任务...")
            task_id = await task_service.create_and_dispatch_task(report_ids, save_dir)
            click.echo(f"任务已创建，ID: {task_id}")

            click.echo(f"[3/3] 正在监控下载进度...")
            await monitor_task(task_service, task_id)

    asyncio.run(main())


async def monitor_task(task_service: DownloadTaskService, task_id: str):
    while True:
        task = await task_service.get_task(task_id)
        if not task:
            click.echo("\n错误：找不到任务。")
            break

        progress = (
            (task.completed_count / task.total_count) * 100
            if task.total_count > 0
            else 0
        )
        progress_bar = f"[{'#' * int(progress // 10):<10}] {progress:.2f}%"
        status_text = f"状态: {task.status.value}, 进度: {task.completed_count}/{task.total_count} {progress_bar}"
        click.echo(f"\r{status_text}", nl=False)

        if task.status in ["COMPLETED", "FAILED"]:
            click.echo(f"\n任务完成，最终状态: {task.status.value}")
            if task.error_message:
                click.echo(f"错误信息: {task.error_message}")
            break

        await asyncio.sleep(2)


if __name__ == "__main__":
    cli()

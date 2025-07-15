"""
调试下载工作流 - 单进程模式
Debug Download Workflow - Single Process Mode

本脚本旨在绕过 FastAPI 和 Celery 的复杂性，直接在单进程中测试
从服务层发起的搜索和下载流程，以便于调试和定位问题。
"""
import asyncio
import logging
from pathlib import Path

# 配置一个简单的、清晰的日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 提前导入所有需要的模块
try:
    from src.core.fund_search_parameters import FundSearchCriteria, ReportType
    from src.services.fund_report_service import FundReportService
    from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
    from src.services.downloader import Downloader
    from src.core.config import settings
    logging.info("所有模块导入成功。")
except ImportError as e:
    logging.error(f"模块导入失败: {e}")
    logging.error("请确保您已经从项目根目录运行此脚本，并且虚拟环境已激活。")
    exit(1)


async def main():
    """主调试函数"""
    logging.info("="*50)
    logging.info("开始单进程下载流程调试...")
    logging.info("="*50)

    # --- 1. 初始化所有服务 ---
    # 我们在这里手动创建所有需要的服务实例，模拟 Celery 任务中的 get_services()
    scraper = None
    downloader = None
    fund_report_service = None
    
    try:
        # 注意：我们不传入 session，让 Scraper 自己管理
        scraper = CSRCFundReportScraper()
        downloader = Downloader()
        fund_report_service = FundReportService(scraper=scraper, downloader=downloader)
        logging.info("服务初始化成功。")
    except Exception as e:
        logging.error(f"服务初始化失败: {e}", exc_info=True)
        return

    # --- 2. 定义搜索条件 ---
    # 使用与 verify_phase4_e2e_download.py 相同的搜索条件
    criteria = FundSearchCriteria(
        year=2025,
        report_type=ReportType.QUARTERLY_Q1,
        fund_code="004899"
    )
    logging.info(f"使用的搜索条件: {criteria.get_description()}")

    # --- 3. 执行报告搜索 ---
    reports_to_download = []
    try:
        logging.info("探针[1]: 即将调用 fund_report_service.search_reports...")
        search_result = await fund_report_service.search_reports(criteria)
        
        if search_result and search_result.get("success"):
            reports_to_download = search_result.get("data", [])
            if reports_to_download:
                logging.info(f"探针[2]: 搜索成功，找到 {len(reports_to_download)} 个报告。")
                # 打印报告的关键信息以供检查
                for report in reports_to_download:
                    logging.info(f"  - 待下载报告: fund_code={report.get('fund_code')}, upload_info_id={report.get('upload_info_id')}")
            else:
                logging.warning("探针[2]: 搜索调用成功，但未返回任何报告。")
        else:
            logging.error(f"探针[2]: 搜索失败。返回结果: {search_result}")
            return

    except Exception as e:
        logging.error(f"探针[2]: 在调用 search_reports 时发生未知异常: {e}", exc_info=True)
        return

    # --- 4. 执行单个报告下载 ---
    if not reports_to_download:
        logging.warning("没有可供下载的报告，调试结束。")
        return

    # 只下载第一个报告以进行调试
    report_to_download = reports_to_download[0]
    save_dir = Path(settings.downloader.save_path)
    
    try:
        logging.info(f"探针[3]: 即将调用 fund_report_service.download_report for {report_to_download.get('upload_info_id')}...")
        download_result = await fund_report_service.download_report(report_to_download, save_dir)
        
        if download_result and download_result.get("success"):
            logging.info("探针[4]: 下载成功！")
            logging.info(f"  - 文件路径: {download_result.get('file_path')}")
            logging.info(f"  - 文件大小: {download_result.get('file_size')} 字节")
            
            # 验证文件是否存在
            file_path = Path(download_result.get('file_path'))
            if file_path.exists():
                logging.info(f"  - 文件验证: 成功，文件 '{file_path}' 已在磁盘上找到。")
            else:
                logging.error(f"  - 文件验证: 失败！文件 '{file_path}' 未在磁盘上找到。")
        else:
            logging.error(f"探针[4]: 下载失败。返回结果: {download_result}")

    except Exception as e:
        logging.error(f"探针[4]: 在调用 download_report 时发生未知异常: {e}", exc_info=True)
        return
    
    finally:
        # --- 5. 清理资源 ---
        # 如果 scraper 创建了内部 session，确保它被关闭
        if scraper and hasattr(scraper, 'close'):
            await scraper.close()
            logging.info("Scraper session 已关闭。")
        logging.info("="*50)
        logging.info("调试脚本执行完毕。")
        logging.info("="*50)


if __name__ == "__main__":
    # 使用 asyncio.run 来执行主异步函数
    asyncio.run(main())

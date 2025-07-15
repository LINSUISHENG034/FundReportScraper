#!/usr/bin/env python3
"""
批量下载2025年年度报告并实现解析
Batch download and parse 2025 annual reports
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.logging import get_logger
from src.models.database import ReportType
from src.scrapers.fund_scraper import FundReportScraper
from src.services.qdii_fund_service import QDIIFundService
from src.parsers.xbrl_parser import XBRLParser

logger = get_logger(__name__)


class AnnualReportBatchProcessor:
    """
    2025年年度报告批量处理器
    2025 Annual Report Batch Processor
    """

    def __init__(self):
        self.scraper = FundReportScraper()
        self.qdii_service = QDIIFundService()
        self.parser = XBRLParser()

        logger.info("annual_processor.initialized")

    async def get_all_annual_reports(
        self,
        year: int = 2024,
        max_pages: Optional[int] = None,
        fund_type_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取指定年份的所有年度报告
        Get all annual reports for specified year
        """
        logger.info(
            "annual_processor.get_all_reports.start",
            year=year,
            max_pages=max_pages,
            fund_type_filter=fund_type_filter,
        )

        all_reports = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                logger.info(
                    "annual_processor.max_pages_reached", page=page, max_pages=max_pages
                )
                break

            try:
                # 使用年度报告的参数
                reports, has_next = await self.scraper.get_report_list(
                    year=year,
                    report_type=ReportType.ANNUAL,  # 年度报告
                    page=page,
                    page_size=100,
                    fund_type=fund_type_filter,  # 可以筛选特定基金类型
                )

                all_reports.extend(reports)

                logger.info(
                    "annual_processor.page_complete",
                    page=page,
                    page_reports=len(reports),
                    total_reports=len(all_reports),
                    has_next=has_next,
                )

                if not has_next:
                    logger.info("annual_processor.last_page_reached")
                    break

                page += 1

                # 添加延迟避免请求过快
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error("annual_processor.page_error", page=page, error=str(e))
                break

        logger.info(
            "annual_processor.get_all_reports.complete",
            total_reports=len(all_reports),
            total_pages=page - 1,
        )

        return all_reports

    async def batch_download_and_parse(
        self,
        reports: List[Dict],
        save_dir: Optional[Path] = None,
        max_concurrent: int = 3,
        parse_xbrl: bool = True,
    ) -> Dict:
        """
        批量下载和解析报告
        Batch download and parse reports
        """
        if save_dir is None:
            save_dir = Path("data/annual_reports_2025")

        save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "annual_processor.batch_process.start",
            reports_count=len(reports),
            save_dir=str(save_dir),
            max_concurrent=max_concurrent,
            parse_xbrl=parse_xbrl,
        )

        results = {
            "total_reports": len(reports),
            "successful_downloads": 0,
            "failed_downloads": 0,
            "successful_parsing": 0,
            "failed_parsing": 0,
            "download_details": [],
            "parsing_results": [],
            "errors": [],
            "statistics": {
                "fund_companies": {},
                "fund_types": {},
                "qdii_funds": 0,
                "total_file_size": 0,
            },
        }

        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_report(report: Dict, index: int) -> Dict:
            """处理单个报告"""
            async with semaphore:
                return await self._process_single_report(
                    report, index, len(reports), save_dir, parse_xbrl
                )

        # 并发处理所有报告
        tasks = [process_single_report(report, i) for i, report in enumerate(reports)]

        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 汇总结果
        for result in completed_results:
            if isinstance(result, Exception):
                results["errors"].append(str(result))
                results["failed_downloads"] += 1
            elif isinstance(result, dict):
                results["download_details"].append(result)

                if result.get("download_success"):
                    results["successful_downloads"] += 1
                    results["statistics"]["total_file_size"] += result.get(
                        "file_size", 0
                    )

                    # 统计基金公司
                    company = result.get("fund_company", "Unknown")
                    results["statistics"]["fund_companies"][company] = (
                        results["statistics"]["fund_companies"].get(company, 0) + 1
                    )

                    # 检查是否为QDII基金
                    fund_name = result.get("fund_name", "")
                    if self.qdii_service.is_qdii_fund(fund_name):
                        results["statistics"]["qdii_funds"] += 1
                else:
                    results["failed_downloads"] += 1

                if result.get("parsing_success"):
                    results["successful_parsing"] += 1
                    results["parsing_results"].append(result.get("parsing_result"))
                elif result.get("parsing_attempted"):
                    results["failed_parsing"] += 1

        # 保存结果汇总
        self._save_batch_results(results, save_dir)

        logger.info(
            "annual_processor.batch_process.complete",
            total_reports=results["total_reports"],
            successful_downloads=results["successful_downloads"],
            failed_downloads=results["failed_downloads"],
            successful_parsing=results["successful_parsing"],
            failed_parsing=results["failed_parsing"],
            success_rate=f"{(results['successful_downloads'] / results['total_reports'] * 100):.1f}%",
        )

        return results

    async def _process_single_report(
        self, report: Dict, index: int, total: int, save_dir: Path, parse_xbrl: bool
    ) -> Dict:
        """处理单个报告"""
        upload_info_id = report.get("upload_info_id")
        fund_code = report.get("fund_code", "unknown")
        fund_name = report.get("fund_short_name", "unknown")
        fund_company = report.get("organ_name", "unknown")

        result = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "fund_company": fund_company,
            "upload_info_id": upload_info_id,
            "index": index + 1,
            "total": total,
            "download_success": False,
            "parsing_attempted": False,
            "parsing_success": False,
        }

        try:
            logger.info(
                "annual_processor.processing_report",
                progress=f"{index+1}/{total}",
                fund_code=fund_code,
                fund_name=fund_name,
            )

            if not upload_info_id:
                raise ValueError("Missing upload_info_id")

            # 下载XBRL内容
            content = await self.scraper.download_xbrl_content(upload_info_id)

            # 保存文件
            file_path = self._save_report_file(content, fund_code, "ANNUAL", save_dir)

            result.update(
                {
                    "download_success": True,
                    "file_path": str(file_path),
                    "file_size": len(content),
                    "download_time": datetime.now().isoformat(),
                }
            )

            # 解析XBRL内容
            if parse_xbrl:
                result["parsing_attempted"] = True
                try:
                    parsing_result = await self._parse_xbrl_content(content, fund_code)
                    result.update(
                        {
                            "parsing_success": parsing_result.get(
                                "parsing_success", False
                            ),
                            "parsing_result": parsing_result,
                        }
                    )
                except Exception as e:
                    result["parsing_error"] = str(e)

            logger.info(
                "annual_processor.report_success",
                fund_code=fund_code,
                file_size=len(content),
                parsing_success=result.get("parsing_success", False),
            )

        except Exception as e:
            error_msg = f"Processing failed for {fund_code}: {str(e)}"
            result["error"] = str(e)

            logger.error(
                "annual_processor.report_failed", fund_code=fund_code, error=str(e)
            )

        return result

    def _save_report_file(
        self, content: bytes, fund_code: str, report_type: str, save_dir: Path
    ) -> Path:
        """保存报告文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{fund_code}_{report_type}_{timestamp}.xbrl"
        file_path = save_dir / filename

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path

    async def _parse_xbrl_content(self, content: bytes, fund_code: str) -> Dict:
        """解析XBRL内容"""
        try:
            self.parser.load_from_content(content)

            # 提取结构化数据
            fund_info = self.parser.extract_fund_basic_info()
            asset_allocation = self.parser.extract_asset_allocation()
            top_holdings = self.parser.extract_top_holdings()
            industry_allocation = self.parser.extract_industry_allocation()

            return {
                "fund_code": fund_code,
                "parsing_success": True,
                "fund_basic_info": fund_info.__dict__ if fund_info else None,
                "asset_allocation": asset_allocation.__dict__
                if asset_allocation
                else None,
                "top_holdings_count": len(top_holdings) if top_holdings else 0,
                "industry_allocation_count": len(industry_allocation)
                if industry_allocation
                else 0,
                "parsing_time": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "fund_code": fund_code,
                "parsing_success": False,
                "parsing_error": str(e),
                "parsing_time": datetime.now().isoformat(),
            }

    def _save_batch_results(self, results: Dict, save_dir: Path):
        """保存批量处理结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = save_dir / f"batch_results_{timestamp}.json"

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info("annual_processor.results_saved", results_file=str(results_file))


async def test_annual_reports_capability():
    """测试年度报告处理能力"""
    print("=== 测试2024年年度报告处理能力 ===")

    processor = AnnualReportBatchProcessor()

    try:
        # 测试1: 获取少量年度报告进行测试
        print("\n1. 获取2024年年度报告样本...")
        sample_reports = await processor.get_all_annual_reports(
            year=2024, max_pages=1  # 只获取第一页进行测试
        )

        print(f"   获取到 {len(sample_reports)} 条年度报告")

        if sample_reports:
            print("   示例年度报告:")
            for i, report in enumerate(sample_reports[:5]):
                fund_code = report.get("fund_code", "N/A")
                fund_name = report.get("fund_short_name", "N/A")
                company = report.get("organ_name", "N/A")
                upload_id = report.get("upload_info_id", "N/A")

                print(f"     {i+1}. {fund_code} - {fund_name}")
                print(f"        管理公司: {company}")
                print(f"        上传ID: {upload_id}")

        # 测试2: 批量下载和解析（少量样本）
        if sample_reports:
            print(f"\n2. 测试批量下载和解析...")
            test_reports = sample_reports[:3]  # 只测试前3个

            results = await processor.batch_download_and_parse(
                reports=test_reports,
                save_dir=Path("data/annual_test"),
                max_concurrent=2,
                parse_xbrl=True,
            )

            print(f"   批量处理结果:")
            print(f"   总报告数: {results['total_reports']}")
            print(f"   下载成功: {results['successful_downloads']}")
            print(f"   下载失败: {results['failed_downloads']}")
            print(f"   解析成功: {results['successful_parsing']}")
            print(f"   解析失败: {results['failed_parsing']}")
            print(f"   总文件大小: {results['statistics']['total_file_size']:,} 字节")

            if results["download_details"]:
                print(f"\n   详细结果:")
                for detail in results["download_details"]:
                    fund_code = detail["fund_code"]
                    fund_name = detail["fund_name"]
                    success = "✅" if detail["download_success"] else "❌"
                    parsing = "✅" if detail.get("parsing_success") else "❌"

                    print(f"     {success} {fund_code} - {fund_name}")
                    if detail["download_success"]:
                        print(f"        文件大小: {detail['file_size']:,} 字节")
                        print(f"        XBRL解析: {parsing}")

        return len(sample_reports) > 0

    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def full_batch_download():
    """完整批量下载所有2024年年度报告"""
    print("=== 完整批量下载2024年年度报告 ===")

    processor = AnnualReportBatchProcessor()

    try:
        # 获取所有年度报告
        print("\n1. 获取所有2024年年度报告...")
        all_reports = await processor.get_all_annual_reports(year=2024)

        print(f"   总共找到 {len(all_reports)} 条2024年年度报告")

        if not all_reports:
            print("   ❌ 未找到任何年度报告")
            return False

        # 统计基金类型
        fund_companies = {}
        qdii_count = 0

        for report in all_reports:
            company = report.get("organ_name", "未知")
            fund_companies[company] = fund_companies.get(company, 0) + 1

            fund_name = report.get("fund_short_name", "")
            if processor.qdii_service.is_qdii_fund(fund_name):
                qdii_count += 1

        print(f"\n   统计信息:")
        print(f"   基金公司数量: {len(fund_companies)}")
        print(f"   QDII基金数量: {qdii_count}")
        print(f"   前5大基金公司:")

        for company, count in sorted(
            fund_companies.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            print(f"     {company}: {count} 只基金")

        # 询问用户是否继续
        print(f"\n⚠️  即将下载 {len(all_reports)} 个基金的年度报告")
        print(f"   预估文件大小: {len(all_reports) * 100} KB - {len(all_reports) * 500} KB")
        print(
            f"   预估下载时间: {len(all_reports) * 2 // 60} - {len(all_reports) * 5 // 60} 分钟"
        )

        user_input = input("\n是否继续批量下载？(y/N): ").strip().lower()

        if user_input != "y":
            print("   用户取消下载")
            return False

        # 开始批量下载
        print(f"\n2. 开始批量下载和解析...")
        results = await processor.batch_download_and_parse(
            reports=all_reports,
            save_dir=Path("data/annual_reports_2024_full"),
            max_concurrent=5,  # 适度并发
            parse_xbrl=True,
        )

        # 显示最终结果
        print(f"\n🎯 批量下载完成!")
        print(f"   总报告数: {results['total_reports']}")
        print(f"   下载成功: {results['successful_downloads']}")
        print(f"   下载失败: {results['failed_downloads']}")
        print(f"   解析成功: {results['successful_parsing']}")
        print(f"   解析失败: {results['failed_parsing']}")
        print(
            f"   成功率: {(results['successful_downloads'] / results['total_reports'] * 100):.1f}%"
        )
        print(
            f"   总文件大小: {results['statistics']['total_file_size'] / 1024 / 1024:.1f} MB"
        )
        print(f"   QDII基金数量: {results['statistics']['qdii_funds']}")

        return True

    except Exception as e:
        print(f"   ❌ 批量下载失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("2025年年度报告批量下载和解析工具")
    print("=" * 60)

    print("\n选择操作模式:")
    print("1. 测试模式 - 下载少量报告进行测试")
    print("2. 完整模式 - 下载所有2024年年度报告")
    print("3. 退出")

    while True:
        choice = input("\n请选择 (1/2/3): ").strip()

        if choice == "1":
            print("\n🧪 启动测试模式...")
            success = await test_annual_reports_capability()
            if success:
                print("\n✅ 测试模式完成，功能验证成功！")
                print("   可以选择完整模式下载所有报告")
            else:
                print("\n❌ 测试模式失败，请检查网络连接和配置")
            break

        elif choice == "2":
            print("\n🚀 启动完整模式...")
            success = await full_batch_download()
            if success:
                print("\n✅ 完整批量下载完成！")
            else:
                print("\n❌ 批量下载失败")
            break

        elif choice == "3":
            print("\n👋 退出程序")
            break

        else:
            print("❌ 无效选择，请输入 1、2 或 3")


if __name__ == "__main__":
    asyncio.run(main())

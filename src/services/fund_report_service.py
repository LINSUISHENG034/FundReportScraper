"""
基金报告业务服务层
Fund Report Business Service Layer

提供基金报告相关的业务逻辑，解耦API层和数据访问层
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional

from src.core.logging import get_logger
from src.core.fund_search_parameters import FundSearchCriteria, ReportType, FundType
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.downloader import Downloader

logger = get_logger(__name__)


class FundReportService:
    """
    基金报告业务服务
    Fund Report Business Service
    """
    
    def __init__(self, scraper: CSRCFundReportScraper, downloader: Downloader):
        self.scraper = scraper
        self.downloader = downloader
        
    async def search_reports(self, criteria: FundSearchCriteria) -> Dict:
        """
        搜索基金报告
        Search fund reports
        """
        bound_logger = logger.bind(
            criteria=criteria.get_description(),
            page=criteria.page,
            page_size=criteria.page_size
        )
        
        bound_logger.info("fund_report_service.search_reports.start")
        
        try:
            reports = await self.scraper.search_reports(criteria)
            
            result = {
                "success": True,
                "data": reports,
                "pagination": {
                    "page": criteria.page,
                    "page_size": criteria.page_size,
                    "total": len(reports)
                },
                "criteria": {
                    "year": criteria.year,
                    "report_type": criteria.report_type.value,
                    "report_type_name": ReportType.get_description(criteria.report_type),
                    "fund_type": criteria.fund_type.value if criteria.fund_type else None,
                    "fund_type_name": FundType.get_description(criteria.fund_type) if criteria.fund_type else None,
                    "fund_company_short_name": criteria.fund_company_short_name,
                    "fund_code": criteria.fund_code,
                    "fund_short_name": criteria.fund_short_name
                }
            }
            
            bound_logger.info(
                "fund_report_service.search_reports.success",
                total_found=len(reports)
            )
            
            return result
            
        except Exception as e:
            bound_logger.error(
                "fund_report_service.search_reports.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "pagination": {
                    "page": criteria.page,
                    "page_size": criteria.page_size,
                    "total": 0
                }
            }
    
    async def search_all_pages(
        self, 
        criteria: FundSearchCriteria, 
        max_pages: Optional[int] = None
    ) -> Dict:
        """
        获取所有页面的报告
        Get all pages of reports
        """
        bound_logger = logger.bind(
            criteria=criteria.get_description(),
            max_pages=max_pages
        )
        
        bound_logger.info("fund_report_service.search_all_pages.start")
        
        all_reports = []
        page = 1
        
        try:
            while True:
                if max_pages and page > max_pages:
                    bound_logger.info(
                        "fund_report_service.search_all_pages.max_pages_reached",
                        page=page,
                        max_pages=max_pages
                    )
                    break
                
                # 更新页码
                current_criteria = FundSearchCriteria(
                    year=criteria.year,
                    report_type=criteria.report_type,
                    fund_type=criteria.fund_type,
                    fund_company_short_name=criteria.fund_company_short_name,
                    fund_code=criteria.fund_code,
                    fund_short_name=criteria.fund_short_name,
                    start_upload_date=criteria.start_upload_date,
                    end_upload_date=criteria.end_upload_date,
                    page=page,
                    page_size=criteria.page_size
                )
                
                reports = await self.scraper.search_reports(current_criteria)
                
                if not reports:
                    bound_logger.info(
                        "fund_report_service.search_all_pages.no_more_data",
                        page=page
                    )
                    break
                
                all_reports.extend(reports)
                bound_logger.info(
                    "fund_report_service.search_all_pages.page_completed",
                    page=page,
                    page_reports=len(reports),
                    total_reports=len(all_reports)
                )
                
                # 如果返回的报告数少于页面大小，说明是最后一页
                if len(reports) < criteria.page_size:
                    bound_logger.info(
                        "fund_report_service.search_all_pages.last_page_reached",
                        page=page
                    )
                    break
                
                page += 1
                await asyncio.sleep(1)  # 避免请求过快
            
            result = {
                "success": True,
                "data": all_reports,
                "pagination": {
                    "total_pages": page,
                    "total_reports": len(all_reports),
                    "page_size": criteria.page_size
                },
                "criteria": {
                    "year": criteria.year,
                    "report_type": criteria.report_type.value,
                    "report_type_name": ReportType.get_description(criteria.report_type)
                }
            }
            
            bound_logger.info(
                "fund_report_service.search_all_pages.success",
                total_pages=page,
                total_reports=len(all_reports)
            )
            
            return result
            
        except Exception as e:
            bound_logger.error(
                "fund_report_service.search_all_pages.error",
                error=str(e),
                error_type=type(e).__name__,
                page=page,
                total_reports=len(all_reports)
            )
            return {
                "success": False,
                "error": str(e),
                "data": all_reports,  # 返回已获取的数据
                "pagination": {
                    "total_pages": page - 1,
                    "total_reports": len(all_reports),
                    "page_size": criteria.page_size
                }
            }
    
    async def download_report(self, report: Dict, save_dir: Path) -> Dict:
        """
        下载单个报告 (已重构)
        此方法现在只负责业务流程（构造URL和路径），并将实际下载委托给Downloader服务。
        """
        bound_logger = logger.bind(
            fund_code=report.get('fund_code', 'Unknown'),
            upload_info_id=report.get('upload_info_id', 'Unknown')
        )
        bound_logger.info("fund_report_service.download_report.start")

        try:
            # 使用 snake_case 访问, 与 API 和任务层保持一致
            upload_info_id = report['upload_info_id']
            fund_code = report['fund_code']

            # 1. 构造下载URL
            download_url = self.scraper.get_download_url(upload_info_id)
            
            # 2. 生成确定性的文件名和路径，便于验证
            filename = f"{fund_code}_{upload_info_id}.xbrl"
            file_path = save_dir / filename

            # 3. 委托给Downloader服务
            download_result = await self.downloader.download_to_file(download_url, file_path)
            
            # 4. 附加业务信息并返回
            if download_result["success"]:
                download_result.update({
                    "fund_code": fund_code,
                    "upload_info_id": upload_info_id,
                    "filename": filename
                })
            else:
                download_result.update({"fund_code": fund_code})

            return download_result

        except KeyError as e:
            error_msg = f"报告字典中缺少关键字段: {e}"
            bound_logger.error("fund_report_service.download_report.missing_key", error=error_msg)
            return {"success": False, "error": error_msg, "fund_code": report.get('fund_code', 'Unknown')}
        except Exception as e:
            bound_logger.error("fund_report_service.download_report.error", error=str(e), error_type=type(e).__name__)
            return {"success": False, "error": str(e), "fund_code": report.get('fund_code', 'Unknown')}
    
    # batch_download, enhanced_batch_download, and all _sync methods have been removed
    # as per the Phase 3 refactoring plan.
    # The new Celery-based task decomposition architecture should be used for batch processing.

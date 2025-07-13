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

logger = get_logger(__name__)


class FundReportService:
    """
    基金报告业务服务
    Fund Report Business Service
    """
    
    def __init__(self, scraper: CSRCFundReportScraper):
        self.scraper = scraper
        
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
        下载单个报告
        Download single report
        """
        bound_logger = logger.bind(
            fund_code=report.get('fundCode', 'Unknown'),
            upload_info_id=report.get('uploadInfoId', 'Unknown')
        )

        bound_logger.info("fund_report_service.download_report.start")

        try:
            upload_info_id = report['uploadInfoId']
            fund_code = report['fundCode']

            # 使用爬虫的下载方法（已修复重定向问题）
            content = await self.scraper.download_xbrl_content(upload_info_id)

            # 生成文件名
            timestamp = int(time.time())
            filename = f"{fund_code}_REPORT_{timestamp}.xbrl"
            file_path = save_dir / filename

            # 保存文件
            save_dir.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(content)

            # 验证文件是否成功保存
            if file_path.exists() and file_path.stat().st_size > 0:
                bound_logger.info(
                    "fund_report_service.download_report.success",
                    filename=filename,
                    file_size=len(content),
                    saved_size=file_path.stat().st_size
                )

                return {
                    "success": True,
                    "filename": filename,
                    "file_path": str(file_path),
                    "file_size": len(content),
                    "fund_code": fund_code,
                    "upload_info_id": upload_info_id
                }
            else:
                bound_logger.error(
                    "fund_report_service.download_report.save_failed",
                    filename=filename,
                    content_size=len(content)
                )
                return {
                    "success": False,
                    "error": "文件保存失败",
                    "fund_code": fund_code
                }

        except Exception as e:
            bound_logger.error(
                "fund_report_service.download_report.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "fund_code": report.get('fundCode', 'Unknown')
            }
    
    async def batch_download(
        self, 
        reports: List[Dict], 
        save_dir: Path, 
        max_concurrent: int = 3
    ) -> Dict:
        """
        批量下载报告
        Batch download reports
        """
        bound_logger = logger.bind(
            total_reports=len(reports),
            save_dir=str(save_dir),
            max_concurrent=max_concurrent
        )
        
        bound_logger.info("fund_report_service.batch_download.start")
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(report):
            async with semaphore:
                return await self.download_report(report, save_dir)
        
        try:
            start_time = time.time()
            
            # 执行批量下载
            results = await asyncio.gather(
                *[download_with_semaphore(report) for report in reports],
                return_exceptions=True
            )
            
            end_time = time.time()
            
            # 统计结果
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            failed_count = len(reports) - success_count
            
            result = {
                "success": True,
                "statistics": {
                    "total": len(reports),
                    "success": success_count,
                    "failed": failed_count,
                    "duration": end_time - start_time
                },
                "results": results,
                "save_dir": str(save_dir)
            }
            
            bound_logger.info(
                "fund_report_service.batch_download.success",
                total=len(reports),
                success=success_count,
                failed=failed_count,
                duration=end_time - start_time
            )
            
            return result
            
        except Exception as e:
            bound_logger.error(
                "fund_report_service.batch_download.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "statistics": {
                    "total": len(reports),
                    "success": 0,
                    "failed": len(reports),
                    "duration": 0
                }
            }

    async def enhanced_batch_download(
        self,
        criteria: FundSearchCriteria,
        save_dir: Path,
        max_concurrent: int = 3,
        max_reports: Optional[int] = None
    ) -> Dict:
        """
        增强的批量下载功能
        基于验证的实现，支持搜索+下载一体化
        Enhanced batch download based on validated implementation
        """
        bound_logger = logger.bind(
            criteria=criteria.get_description(),
            save_dir=str(save_dir),
            max_concurrent=max_concurrent,
            max_reports=max_reports
        )

        bound_logger.info("fund_report_service.enhanced_batch_download.start")

        try:
            start_time = time.time()

            # 第一步：搜索所有符合条件的报告
            bound_logger.info("fund_report_service.enhanced_batch_download.searching")
            search_result = await self.search_all_pages(criteria)

            if not search_result["success"]:
                return {
                    "success": False,
                    "error": f"搜索失败: {search_result.get('error', 'Unknown error')}",
                    "statistics": {
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "duration": time.time() - start_time
                    }
                }

            all_reports = search_result["data"]

            # 限制下载数量
            if max_reports and len(all_reports) > max_reports:
                all_reports = all_reports[:max_reports]
                bound_logger.info(
                    "fund_report_service.enhanced_batch_download.limited",
                    original_count=len(search_result["data"]),
                    limited_count=len(all_reports)
                )

            if not all_reports:
                return {
                    "success": True,
                    "message": "没有找到符合条件的报告",
                    "statistics": {
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "duration": time.time() - start_time
                    }
                }

            bound_logger.info(
                "fund_report_service.enhanced_batch_download.found_reports",
                total_reports=len(all_reports)
            )

            # 第二步：批量下载
            bound_logger.info("fund_report_service.enhanced_batch_download.downloading")
            download_result = await self.batch_download(all_reports, save_dir, max_concurrent)

            # 合并结果
            total_duration = time.time() - start_time
            download_result["statistics"]["duration"] = total_duration
            download_result["search_info"] = {
                "criteria": criteria.get_description(),
                "total_pages": search_result.get("pagination", {}).get("total_pages", 0),
                "total_found": len(search_result["data"])
            }

            bound_logger.info(
                "fund_report_service.enhanced_batch_download.completed",
                total_duration=total_duration,
                success_count=download_result.get("statistics", {}).get("success", 0),
                failed_count=download_result.get("statistics", {}).get("failed", 0)
            )

            return download_result

        except Exception as e:
            bound_logger.error(
                "fund_report_service.enhanced_batch_download.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "statistics": {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "duration": time.time() - start_time
                }
            }

    async def get_report_by_upload_id(self, upload_info_id: str) -> Optional[Dict]:
        """
        根据upload_info_id获取报告信息
        Get report information by upload_info_id

        注意：这是一个简化实现，实际应该从数据库或缓存中获取
        """
        bound_logger = logger.bind(upload_info_id=upload_info_id)
        bound_logger.info("fund_report_service.get_report_by_upload_id.start")

        try:
            # 简化实现：构建基本的报告信息
            # 在实际应用中，这应该从数据库或通过API查询获取
            upload_id_str = str(upload_info_id)
            report = {
                "uploadInfoId": upload_id_str,
                "fundCode": f"FUND_{upload_id_str[:6]}",
                "fundId": upload_id_str,
                "organName": "基金管理有限公司",
                "reportSendDate": "2024-04-30",
                "reportDesp": f"基金报告_{upload_id_str}"
            }

            bound_logger.info(
                "fund_report_service.get_report_by_upload_id.success",
                fund_code=report["fundCode"]
            )

            return report

        except Exception as e:
            bound_logger.error(
                "fund_report_service.get_report_by_upload_id.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None




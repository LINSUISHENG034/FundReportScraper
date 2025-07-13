"""
QDII基金识别和批量下载服务
QDII Fund Identification and Batch Download Service
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.core.config import settings
from src.core.logging import get_logger
from src.models.database import ReportType
from src.scrapers.fund_scraper import FundReportScraper
from src.parsers.xbrl_parser import XBRLParser

logger = get_logger(__name__)


class QDIIFundService:
    """
    QDII基金识别和批量下载服务
    QDII Fund Identification and Batch Download Service
    """
    
    def __init__(self):
        self.scraper = FundReportScraper()
        self.parser = XBRLParser()
        
        # QDII基金识别关键词（根据实际情况扩展）
        self.qdii_keywords = {
            # 直接标识
            'QDII', 'qdii',
            # 地区标识
            '海外', '全球', '国际', '境外', '离岸',
            '美国', '欧洲', '亚洲', '日本', '韩国', '印度', '越南',
            '香港', '港股', '台湾',
            # 市场标识
            '恒生', '标普', '纳斯达克', '道琼斯', 'MSCI',
            '中概股', '海外中概股',
            # 货币标识
            '美元', '港币', '欧元', '日元',
            # 其他标识
            'ETF联接', 'LOF'
        }
        
        logger.info(
            "qdii_service.initialized",
            keywords_count=len(self.qdii_keywords)
        )
    
    def is_qdii_fund(self, fund_name: str) -> bool:
        """
        判断是否为QDII基金
        Determine if a fund is QDII fund
        """
        if not fund_name:
            return False
        
        fund_name_lower = fund_name.lower()
        
        # 检查是否包含QDII关键词
        for keyword in self.qdii_keywords:
            if keyword.lower() in fund_name_lower:
                logger.debug(
                    "qdii_service.fund_identified",
                    fund_name=fund_name,
                    matched_keyword=keyword
                )
                return True
        
        return False
    
    async def get_qdii_reports_by_year(
        self,
        year: int,
        report_types: Optional[List[ReportType]] = None,
        max_pages_per_type: Optional[int] = None
    ) -> List[Dict]:
        """
        按年份获取QDII基金报告
        Get QDII fund reports by year
        """
        if report_types is None:
            report_types = [ReportType.ANNUAL, ReportType.SEMI_ANNUAL, ReportType.QUARTERLY]
        
        logger.info(
            "qdii_service.get_reports_start",
            year=year,
            report_types=[rt.value for rt in report_types],
            max_pages_per_type=max_pages_per_type
        )
        
        all_qdii_reports = []
        
        for report_type in report_types:
            try:
                logger.info(
                    "qdii_service.processing_report_type",
                    report_type=report_type.value,
                    year=year
                )
                
                # 获取该类型的所有报告（优先获取QDII类型）
                reports = await self.scraper.get_all_reports(
                    year=year,
                    report_type=report_type,
                    max_pages=max_pages_per_type,
                    fund_type="6020-6050"  # QDII基金类型代码
                )
                
                # 筛选QDII基金
                qdii_reports = []
                for report in reports:
                    fund_name = report.get('fund_short_name', '') or report.get('fund_name', '')
                    if self.is_qdii_fund(fund_name):
                        report['report_type'] = report_type.value
                        qdii_reports.append(report)
                
                all_qdii_reports.extend(qdii_reports)
                
                logger.info(
                    "qdii_service.report_type_complete",
                    report_type=report_type.value,
                    total_reports=len(reports),
                    qdii_reports=len(qdii_reports)
                )
                
            except Exception as e:
                logger.error(
                    "qdii_service.report_type_error",
                    report_type=report_type.value,
                    year=year,
                    error=str(e)
                )
                continue
        
        # 去重（同一基金可能有多个报告）
        unique_reports = self._deduplicate_reports(all_qdii_reports)
        
        logger.info(
            "qdii_service.get_reports_complete",
            year=year,
            total_qdii_reports=len(all_qdii_reports),
            unique_qdii_reports=len(unique_reports)
        )
        
        return unique_reports
    
    def _deduplicate_reports(self, reports: List[Dict]) -> List[Dict]:
        """
        去重报告（保留最新的）
        Deduplicate reports (keep the latest)
        """
        seen = {}
        
        for report in reports:
            fund_code = report.get('fund_code')
            report_type = report.get('report_type')
            
            if not fund_code:
                continue
            
            key = f"{fund_code}_{report_type}"
            
            if key not in seen:
                seen[key] = report
            else:
                # 比较上传日期，保留最新的
                current_date = report.get('upload_date', '')
                existing_date = seen[key].get('upload_date', '')
                
                if current_date > existing_date:
                    seen[key] = report
        
        return list(seen.values())
    
    async def batch_download_qdii_reports(
        self,
        reports: List[Dict],
        save_dir: Optional[Path] = None,
        parse_xbrl: bool = True
    ) -> Dict:
        """
        批量下载QDII基金报告
        Batch download QDII fund reports
        """
        if save_dir is None:
            save_dir = Path("data/qdii_reports")
        
        save_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            "qdii_service.batch_download_start",
            reports_count=len(reports),
            save_dir=str(save_dir),
            parse_xbrl=parse_xbrl
        )
        
        results = {
            'total_reports': len(reports),
            'successful_downloads': 0,
            'failed_downloads': 0,
            'download_details': [],
            'parsing_results': [],
            'errors': []
        }
        
        for i, report in enumerate(reports):
            try:
                upload_info_id = report.get('upload_info_id')
                fund_code = report.get('fund_code', 'unknown')
                fund_name = report.get('fund_short_name', 'unknown')
                
                logger.info(
                    "qdii_service.downloading_report",
                    progress=f"{i+1}/{len(reports)}",
                    fund_code=fund_code,
                    fund_name=fund_name,
                    upload_info_id=upload_info_id
                )
                
                if not upload_info_id:
                    raise ValueError("Missing upload_info_id")
                
                # 下载XBRL内容
                content = await self.scraper.download_xbrl_content(upload_info_id)
                
                # 保存文件
                file_path = self._save_report_file(
                    content, 
                    fund_code, 
                    report.get('report_type', 'unknown'),
                    save_dir
                )
                
                download_detail = {
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'upload_info_id': upload_info_id,
                    'file_path': str(file_path),
                    'file_size': len(content),
                    'download_time': datetime.now().isoformat(),
                    'success': True
                }
                
                # 解析XBRL内容
                if parse_xbrl:
                    try:
                        parsing_result = await self._parse_xbrl_content(content, fund_code)
                        download_detail['parsing_result'] = parsing_result
                        results['parsing_results'].append(parsing_result)
                    except Exception as e:
                        logger.warning(
                            "qdii_service.xbrl_parsing_failed",
                            fund_code=fund_code,
                            error=str(e)
                        )
                        download_detail['parsing_error'] = str(e)
                
                results['download_details'].append(download_detail)
                results['successful_downloads'] += 1
                
                logger.info(
                    "qdii_service.download_success",
                    fund_code=fund_code,
                    file_size=len(content),
                    file_path=str(file_path)
                )
                
            except Exception as e:
                error_msg = f"Download failed for {fund_code}: {str(e)}"
                logger.error(
                    "qdii_service.download_failed",
                    fund_code=fund_code,
                    error=str(e)
                )
                
                results['failed_downloads'] += 1
                results['errors'].append(error_msg)
                results['download_details'].append({
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'success': False,
                    'error': str(e)
                })
            
            # 添加延迟避免请求过快
            if i < len(reports) - 1:
                await asyncio.sleep(0.5)
        
        # 保存结果汇总
        self._save_batch_results(results, save_dir)
        
        logger.info(
            "qdii_service.batch_download_complete",
            total_reports=results['total_reports'],
            successful_downloads=results['successful_downloads'],
            failed_downloads=results['failed_downloads'],
            success_rate=f"{(results['successful_downloads'] / results['total_reports'] * 100):.1f}%"
        )
        
        return results
    
    def _save_report_file(
        self, 
        content: bytes, 
        fund_code: str, 
        report_type: str,
        save_dir: Path
    ) -> Path:
        """保存报告文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{fund_code}_{report_type}_{timestamp}.xbrl"
        file_path = save_dir / filename
        
        with open(file_path, 'wb') as f:
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
                'fund_code': fund_code,
                'parsing_success': True,
                'fund_basic_info': fund_info.__dict__ if fund_info else None,
                'asset_allocation': asset_allocation.__dict__ if asset_allocation else None,
                'top_holdings_count': len(top_holdings) if top_holdings else 0,
                'industry_allocation_count': len(industry_allocation) if industry_allocation else 0,
                'parsing_time': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'fund_code': fund_code,
                'parsing_success': False,
                'parsing_error': str(e),
                'parsing_time': datetime.now().isoformat()
            }
    
    def _save_batch_results(self, results: Dict, save_dir: Path):
        """保存批量处理结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = save_dir / f"batch_results_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(
            "qdii_service.results_saved",
            results_file=str(results_file)
        )

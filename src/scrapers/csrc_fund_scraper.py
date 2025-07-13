"""
按照文档指导的证监会基金报告爬虫
CSRC fund report scraper following documentation guidance
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

from src.core.config import settings
from src.core.logging import get_logger
from src.models.database import ReportType
from src.scrapers.base import BaseScraper, ParseError

logger = get_logger(__name__)


class CSRCFundReportScraper(BaseScraper):
    """
    按照文档指导的证监会基金报告爬虫
    CSRC fund report scraper following documentation guidance
    """
    
    def __init__(self):
        super().__init__(base_url=settings.target.base_url)
        self.search_url = settings.target.search_url
        self.instance_url = settings.target.instance_url
        
        logger.info(
            "csrc_scraper.initialized",
            search_url=self.search_url,
            instance_url=self.instance_url
        )
    
    async def get_report_list(
        self,
        year: int,
        report_type: ReportType,
        page: int = 1,
        page_size: int = 100,
        fund_type: Optional[str] = None,
        fund_company_short_name: Optional[str] = None,
        fund_code: Optional[str] = None,
        fund_short_name: Optional[str] = None,
        start_upload_date: Optional[str] = None,
        end_upload_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """
        按照文档指导获取基金报告列表
        Get fund report list following documentation guidance
        
        Args:
            year: 报告年份
            report_type: 报告类型
            page: 页码 (1-based)
            page_size: 每页数量
            
        Returns:
            Tuple of (report_list, has_next_page)
        """
        bound_logger = logger.bind(
            year=year,
            report_type=report_type.value,
            page=page,
            page_size=page_size
        )
        
        bound_logger.info("csrc_scraper.get_report_list.start")
        
        try:
            # 按照真实浏览器请求构建参数
            ao_data = self._build_ao_data(year, report_type, page, page_size, fund_type)
            
            # 构建查询字符串
            ao_data_json = json.dumps(ao_data)
            timestamp = int(time.time() * 1000)
            
            params = {
                "aoData": ao_data_json,
                "_": timestamp
            }
            
            # 发送GET请求（按照文档指导）
            url = f"{self.search_url}?{urlencode(params)}"
            
            response = await self.get(url)
            
            # 解析响应
            data = response.json()
            
            # 提取报告信息
            reports = []
            for item in data.get("aaData", []):
                report = self._parse_report_item(item)
                if report:
                    reports.append(report)
            
            total_count = data.get("iTotalRecords", 0)
            has_next_page = (page * page_size) < total_count
            
            bound_logger.info(
                "csrc_scraper.get_report_list.success",
                reports_found=len(reports),
                total_count=total_count,
                has_next_page=has_next_page
            )
            
            return reports, has_next_page
            
        except Exception as e:
            bound_logger.error(
                "csrc_scraper.get_report_list.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ParseError(f"获取报告列表失败: {e}")
    
    def _build_ao_data(
        self,
        year: int,
        report_type: ReportType,
        page: int,
        page_size: int,
        fund_type: Optional[str] = None,
        fund_company_short_name: Optional[str] = None,
        fund_code: Optional[str] = None,
        fund_short_name: Optional[str] = None,
        start_upload_date: Optional[str] = None,
        end_upload_date: Optional[str] = None
    ) -> List[Dict]:
        """
        按照真实浏览器请求构建aoData参数
        Build aoData parameters following real browser request
        """
        # 报告类型代码映射（根据真实浏览器请求）
        report_type_mapping = {
            ReportType.QUARTERLY: "FB030010",    # 第一季度报告
            ReportType.SEMI_ANNUAL: "FB020010",  # 中报
            ReportType.ANNUAL: "FB010010"        # 年报
        }

        # 基金类型代码映射
        fund_type_mapping = {
            "股票型": "6020-6010",
            "混合型": "6020-6020",
            "债券型": "6020-6030",
            "货币型": "6020-6040",
            "QDII": "6020-6050",
            "FOF": "6020-6060"
        }

        display_start = (page - 1) * page_size

        # 按照真实浏览器请求的完整参数列表
        ao_data = [
            {"name": "sEcho", "value": page},
            {"name": "iColumns", "value": 6},
            {"name": "sColumns", "value": ",,,,,"},
            {"name": "iDisplayStart", "value": display_start},
            {"name": "iDisplayLength", "value": page_size},
            {"name": "mDataProp_0", "value": "fundCode"},
            {"name": "mDataProp_1", "value": "fundId"},
            {"name": "mDataProp_2", "value": "organName"},
            {"name": "mDataProp_3", "value": "reportSendDate"},
            {"name": "mDataProp_4", "value": "reportDesp"},
            {"name": "mDataProp_5", "value": "uploadInfoId"},
            {"name": "fundType", "value": fund_type or ""},  # 基金类型，空表示所有类型
            {"name": "reportTypeCode", "value": report_type_mapping.get(report_type, "FB030010")},
            {"name": "reportYear", "value": str(year)},
            {"name": "fundCompanyShortName", "value": ""},
            {"name": "fundCode", "value": ""},
            {"name": "fundShortName", "value": ""},
            {"name": "startUploadDate", "value": ""},
            {"name": "endUploadDate", "value": ""}
        ]

        logger.debug(
            "csrc_scraper.ao_data_built",
            ao_data=ao_data,
            report_type_code=report_type_mapping.get(report_type, "FB030010"),
            fund_type=fund_type,
            year=year
        )

        return ao_data
    
    def _parse_report_item(self, item) -> Optional[Dict]:
        """
        解析单个报告项目
        Parse individual report item

        根据真实响应，item是字典格式，包含以下字段：
        uploadInfoId, reportYear, uploadDate, reportSendDate, reportDesp,
        fundId, fundCode, fundShortName, organName, classificationCode, fundSign
        """
        try:
            # 处理字典格式的响应数据
            if isinstance(item, dict):
                report = {
                    "upload_info_id": item.get("uploadInfoId"),
                    "fund_code": item.get("fundCode"),
                    "fund_short_name": item.get("fundShortName"),
                    "organ_name": item.get("organName"),
                    "report_year": item.get("reportYear"),
                    "upload_date": item.get("uploadDate"),
                    "report_send_date": item.get("reportSendDate"),
                    "report_desp": item.get("reportDesp"),
                    "fund_id": item.get("fundId"),
                    "classification_code": item.get("classificationCode"),
                    "fund_sign": item.get("fundSign"),
                    "raw_data": item
                }

                # 验证必要字段（uploadInfoId是关键）
                if not report["upload_info_id"]:
                    logger.warning(
                        "csrc_scraper.parse_item.missing_upload_info_id",
                        item=item
                    )
                    return None

                logger.debug(
                    "csrc_scraper.parse_item.success",
                    upload_info_id=report["upload_info_id"],
                    fund_code=report["fund_code"],
                    fund_name=report["fund_short_name"]
                )

                return report

            # 兼容旧的列表格式（如果有的话）
            elif isinstance(item, list):
                if len(item) < 9:
                    logger.warning(
                        "csrc_scraper.parse_item.insufficient_data",
                        item_length=len(item),
                        item_preview=str(item)[:100]
                    )
                    return None

                # 按照文档指导的字段顺序解析
                report = {
                    "upload_info_id": self._extract_upload_info_id(str(item[0])),
                    "fund_code": self._extract_fund_code(str(item[1])),
                    "fund_short_name": self._clean_text(str(item[2])),
                    "organ_name": self._clean_text(str(item[3])),
                    "report_year": str(item[4]) if len(item) > 4 else None,
                    "upload_date": self._parse_date(str(item[5])) if len(item) > 5 else None,
                    "report_send_date": self._parse_date(str(item[6])) if len(item) > 6 else None,
                    "report_desp": self._clean_text(str(item[7])) if len(item) > 7 else None,
                    "fund_id": str(item[8]) if len(item) > 8 else None,
                    "classification_code": str(item[9]) if len(item) > 9 else None,
                    "fund_sign": str(item[10]) if len(item) > 10 else None,
                    "raw_data": item
                }

                return report

            else:
                logger.warning(
                    "csrc_scraper.parse_item.unknown_format",
                    item_type=type(item),
                    item=str(item)[:200]
                )
                return None

        except Exception as e:
            logger.warning(
                "csrc_scraper.parse_item.error",
                error=str(e),
                item=str(item)[:200]
            )
            return None
    
    def _extract_upload_info_id(self, text: str) -> Optional[str]:
        """提取uploadInfoId"""
        import re
        # 查找链接中的instanceid参数
        match = re.search(r'instanceid=([^&"\']+)', text)
        if match:
            return match.group(1)
        
        # 或者直接查找数字ID
        match = re.search(r'\b(\d{8,})\b', text)
        return match.group(1) if match else None
    
    def _extract_fund_code(self, text: str) -> Optional[str]:
        """提取基金代码"""
        import re
        match = re.search(r'\b(\d{6})\b', text)
        return match.group(1) if match else None

    def _extract_fund_code_from_name(self, fund_name: str) -> Optional[str]:
        """从基金名称中提取基金代码"""
        import re
        if not fund_name:
            return None
        # 尝试从基金名称中提取6位数字代码
        match = re.search(r'\((\d{6})\)', fund_name)
        if match:
            return match.group(1)
        # 尝试其他格式
        match = re.search(r'(\d{6})', fund_name)
        return match.group(1) if match else None
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        import re
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 清理空白字符
        return text.strip()
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """解析日期字符串"""
        try:
            # 尝试多种日期格式
            import re
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
            if date_match:
                return date_match.group(1)
            
            date_match = re.search(r'(\d{4}/\d{2}/\d{2})', date_str)
            if date_match:
                return date_match.group(1).replace('/', '-')
            
            return None
        except:
            return None
    
    async def download_xbrl_content(self, upload_info_id: str) -> bytes:
        """
        下载XBRL内容
        Download XBRL content using uploadInfoId
        """
        bound_logger = logger.bind(upload_info_id=upload_info_id)
        bound_logger.info("csrc_scraper.download_xbrl.start")

        try:
            url = f"{self.instance_url}?instanceid={upload_info_id}"

            # 使用支持重定向的请求
            response = await self.get(url, follow_redirects=True)
            content = response.content

            # 检查是否是有效的XBRL内容
            if len(content) < 100:
                bound_logger.warning(
                    "csrc_scraper.download_xbrl.small_content",
                    content_size=len(content),
                    content_preview=content[:50]
                )

            bound_logger.info(
                "csrc_scraper.download_xbrl.success",
                content_size=len(content),
                content_type=response.headers.get("content-type"),
                final_url=str(response.url)
            )

            return content

        except Exception as e:
            bound_logger.error(
                "csrc_scraper.download_xbrl.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def download_report_file(
        self,
        file_url: str,
        fund_code: str,
        report_date: str,
        report_type: ReportType
    ) -> bytes:
        """
        兼容原有接口的下载方法
        Compatible download method for existing interface
        """
        # 如果file_url是upload_info_id，使用新的下载方法
        if file_url.isdigit() and len(file_url) >= 8:
            return await self.download_xbrl_content(file_url)
        else:
            # 否则使用原有的直接下载方法
            response = await self.get(file_url)
            return response.content
    
    async def get_all_reports(
        self,
        year: int,
        report_type: ReportType,
        max_pages: Optional[int] = None
    ) -> List[Dict]:
        """
        获取所有报告（分页获取）
        Get all reports with pagination
        """
        logger.info(
            "csrc_scraper.get_all_reports.start",
            year=year,
            report_type=report_type.value,
            max_pages=max_pages
        )
        
        all_reports = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                logger.info(
                    "csrc_scraper.get_all_reports.max_pages_reached",
                    page=page,
                    max_pages=max_pages
                )
                break
            
            try:
                reports, has_next = await self.get_report_list(
                    year=year,
                    report_type=report_type,
                    page=page,
                    page_size=100
                )
                
                all_reports.extend(reports)
                
                logger.info(
                    "csrc_scraper.get_all_reports.page_complete",
                    page=page,
                    page_reports=len(reports),
                    total_reports=len(all_reports),
                    has_next=has_next
                )
                
                if not has_next:
                    break
                
                page += 1
                
                # 添加延迟避免请求过快
                await self.rate_limiter.acquire()
                
            except Exception as e:
                logger.error(
                    "csrc_scraper.get_all_reports.page_error",
                    page=page,
                    error=str(e)
                )
                break
        
        logger.info(
            "csrc_scraper.get_all_reports.complete",
            total_reports=len(all_reports),
            total_pages=page - 1
        )
        
        return all_reports

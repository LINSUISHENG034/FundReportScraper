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
from src.core.fund_search_parameters import FundSearchCriteria, ReportType as NewReportType, FundType
from httpx import AsyncClient
from src.scrapers.base import BaseScraper, ParseError

logger = get_logger(__name__)


class CSRCFundReportScraper(BaseScraper):
    """
    按照文档指导的证监会基金报告爬虫
    CSRC fund report scraper following documentation guidance
    """
    
    def __init__(self, session: Optional[AsyncClient] = None):
        super().__init__(base_url=settings.target.base_url, session=session)
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
        report_type: NewReportType,
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
            # 按照验证结果构建参数，传递所有6个搜索参数
            ao_data = self._build_ao_data(
                year, report_type, page, page_size, fund_type,
                fund_company_short_name, fund_code, fund_short_name,
                start_upload_date, end_upload_date
            )
            
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

    async def search_reports(self, criteria: FundSearchCriteria) -> List[Dict]:
        """
        使用搜索条件对象进行报告搜索
        Search reports using FundSearchCriteria object
        """
        bound_logger = logger.bind(
            criteria=criteria.get_description(),
            page=criteria.page,
            page_size=criteria.page_size
        )

        bound_logger.info("csrc_scraper.search_reports.start")

        try:
            # 构建aoData参数
            ao_data = criteria.to_ao_data_list()

            # 构建查询字符串
            ao_data_json = json.dumps(ao_data)
            timestamp = int(time.time() * 1000)

            params = {
                'aoData': ao_data_json,
                '_': timestamp
            }

            # 发送请求
            response = await self.session.get(self.search_url, params=params)

            if response.status_code == 200:
                # 强制解析JSON，忽略Content-Type（基于验证结果）
                try:
                    data = response.json()
                    reports = data.get('aaData', [])

                    bound_logger.info(
                        "csrc_scraper.search_reports.success",
                        total_records=data.get('iTotalRecords', 0),
                        returned_count=len(reports)
                    )

                    return reports

                except Exception as json_error:
                    bound_logger.error(
                        "csrc_scraper.search_reports.json_parse_error",
                        error=str(json_error),
                        response_text=response.text[:200]
                    )
                    raise ParseError(f"JSON解析失败: {json_error}")
            else:
                bound_logger.error(
                    "csrc_scraper.search_reports.http_error",
                    status_code=response.status_code,
                    response_text=response.text[:200]
                )
                raise ParseError(f"HTTP请求失败: {response.status_code}")

        except Exception as e:
            bound_logger.error(
                "csrc_scraper.search_reports.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ParseError(f"搜索报告失败: {e}")

    async def scrape(self, **kwargs) -> List[Dict]:
        """
        实现抽象基类的scrape方法
        Implementation of abstract scrape method
        """
        # 从kwargs中提取参数
        year = kwargs.get('year', 2024)
        report_type = kwargs.get('report_type', NewReportType.ANNUAL)
        page = kwargs.get('page', 1)
        page_size = kwargs.get('page_size', 20)

        # 调用get_report_list方法
        reports, has_more = await self.get_report_list(
            year=year,
            report_type=report_type,
            page=page,
            page_size=page_size,
            **{k: v for k, v in kwargs.items() if k not in ['year', 'report_type', 'page', 'page_size']}
        )

        return reports

    def _build_ao_data(
        self,
        year: int,
        report_type: NewReportType,
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
        按照验证结果构建aoData参数
        Build aoData parameters based on validated implementation
        """
        display_start = (page - 1) * page_size

        # 定义报告类型映射
        report_type_mapping = {
            NewReportType.QUARTERLY_Q1: "FB030010",
            NewReportType.QUARTERLY_Q2: "FB030020",
            NewReportType.QUARTERLY_Q3: "FB030030",
            NewReportType.SEMI_ANNUAL: "FB020000",
            NewReportType.ANNUAL: "FB010000",
            NewReportType.PROSPECTUS: "FB040000",
            NewReportType.LISTING_ANNOUNCEMENT: "FB070000",
            NewReportType.FUND_PROFILE: "FB080000",
        }

        # 直接使用新的报告类型枚举值
        if isinstance(report_type, NewReportType):
            report_type_code = report_type.value
        else:
            # 兼容旧的 ReportType
            legacy_report_type_mapping = {
                ReportType.QUARTERLY: NewReportType.QUARTERLY_Q1.value,
                ReportType.SEMI_ANNUAL: NewReportType.SEMI_ANNUAL.value,
                ReportType.ANNUAL: NewReportType.ANNUAL.value
            }
            report_type_code = legacy_report_type_mapping.get(report_type, NewReportType.QUARTERLY_Q1.value)

        # 处理特殊情况：基金产品资料概要需要空的reportYear
        report_year = "" if report_type_code == NewReportType.FUND_PROFILE.value else str(year)

        # 按照验证的实现构建完整参数列表
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
            {"name": "fundType", "value": fund_type or ""},
            {"name": "reportTypeCode", "value": report_type_code},
            {"name": "reportYear", "value": report_year},
            {"name": "fundCompanyShortName", "value": fund_company_short_name or ""},
            {"name": "fundCode", "value": fund_code or ""},
            {"name": "fundShortName", "value": fund_short_name or ""},
            {"name": "startUploadDate", "value": start_upload_date or ""},
            {"name": "endUploadDate", "value": end_upload_date or ""}
        ]

        logger.debug(
            "csrc_scraper.ao_data_built",
            ao_data=ao_data,
            report_type_code=report_type_code,
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

            bound_logger.info(
                "csrc_scraper.download_xbrl.request_url",
                url=url
            )

            # 使用专门的下载会话，确保重定向处理正确
            if not self.session:
                await self.start_session()

            # 直接使用session.get，确保重定向被正确处理
            response = await self.session.get(url)

            bound_logger.info(
                "csrc_scraper.download_xbrl.response_received",
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                content_length=response.headers.get("content-length"),
                final_url=str(response.url),
                is_redirect=str(response.url) != url
            )

            # 检查响应状态
            if response.status_code != 200:
                bound_logger.error(
                    "csrc_scraper.download_xbrl.http_error",
                    status_code=response.status_code,
                    response_text=response.text[:200]
                )
                raise Exception(f"HTTP {response.status_code}: {response.text[:100]}")

            content = response.content

            # 检查是否是有效的XBRL内容
            if len(content) < 100:
                bound_logger.warning(
                    "csrc_scraper.download_xbrl.small_content",
                    content_size=len(content),
                    content_preview=content[:50]
                )

            # 检查内容类型
            content_type = response.headers.get("content-type", "").lower()
            if "xml" not in content_type and "xbrl" not in content_type:
                # 检查内容是否以XML开头
                content_str = content.decode('utf-8', errors='ignore')[:200]
                if not content_str.strip().startswith('<?xml'):
                    bound_logger.warning(
                        "csrc_scraper.download_xbrl.unexpected_content_type",
                        content_type=content_type,
                        content_preview=content_str[:100]
                    )

            bound_logger.info(
                "csrc_scraper.download_xbrl.success",
                content_size=len(content),
                content_type=content_type,
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
        report_type: NewReportType
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
        report_type: NewReportType,
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

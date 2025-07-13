"""
XBRL解析器 (Phase 4)
XBRL Parser (Phase 4)

解析基金报告XBRL文件，提取关键财务数据
专门针对从CSRC下载的HTML格式基金报告文件
"""

import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
import chardet

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedFundData:
    """
    解析后的基金数据结构
    Parsed fund data structure
    """
    # 基金基本信息
    fund_code: str
    fund_name: str
    fund_manager: Optional[str] = None
    
    # 报告信息
    report_type: str = ""
    report_period_start: Optional[date] = None
    report_period_end: Optional[date] = None
    report_year: Optional[int] = None
    report_quarter: Optional[int] = None
    
    # 基金规模和净值
    total_net_assets: Optional[Decimal] = None
    total_shares: Optional[Decimal] = None
    net_asset_value: Optional[Decimal] = None
    accumulated_nav: Optional[Decimal] = None
    
    # 资产配置
    asset_allocations: List[Dict[str, Any]] = None
    
    # 前十大持仓
    top_holdings: List[Dict[str, Any]] = None
    
    # 行业配置
    industry_allocations: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.asset_allocations is None:
            self.asset_allocations = []
        if self.top_holdings is None:
            self.top_holdings = []
        if self.industry_allocations is None:
            self.industry_allocations = []


class XBRLParser:
    """
    XBRL解析器 (Phase 4版本)
    XBRL Parser (Phase 4 Version)
    
    专门用于解析从CSRC下载的基金报告HTML文件
    """
    
    def __init__(self):
        self.logger = logger.bind(component="xbrl_parser_v4")
        
        # 常用的数据提取模式
        self.patterns = {
            'fund_code': [
                r'基金代码[：:]\s*([A-Z0-9]{6})',
                r'Fund Code[：:]\s*([A-Z0-9]{6})',
                r'([0-9]{6})\s*基金',
                r'基金简称.*?([0-9]{6})',
            ],
            'fund_name': [
                r'基金名称[：:]\s*([^<>\n\r\t]+?)(?:\s|$)',
                r'Fund Name[：:]\s*([^<>\n\r\t]+?)(?:\s|$)',
                r'基金简称[：:]\s*([^<>\n\r\t]+?)(?:\s|$)',
            ],
            'net_asset_value': [
                r'基金份额净值[：:]\s*([0-9,]+\.?[0-9]*)',
                r'单位净值[：:]\s*([0-9,]+\.?[0-9]*)',
                r'Net Asset Value[：:]\s*([0-9,]+\.?[0-9]*)',
                r'份额净值.*?([0-9]+\.[0-9]+)',
            ],
            'total_net_assets': [
                r'基金资产净值[：:]\s*([0-9,]+\.?[0-9]*)',
                r'净资产[：:]\s*([0-9,]+\.?[0-9]*)',
                r'Total Net Assets[：:]\s*([0-9,]+\.?[0-9]*)',
                r'资产净值.*?([0-9,]+\.?[0-9]*)',
            ],
            'report_period': [
                r'报告期间[：:]\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)\s*至\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)',
                r'([0-9]{4}-[0-9]{2}-[0-9]{2})\s*至\s*([0-9]{4}-[0-9]{2}-[0-9]{2})',
                r'报告期.*?([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*?([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)',
            ]
        }
    
    def parse_file(self, file_path: Path) -> Optional[ParsedFundData]:
        """
        解析XBRL文件
        Parse XBRL file
        """
        bound_logger = self.logger.bind(file_path=str(file_path))
        bound_logger.info("xbrl_parser.parse_file.start")
        
        try:
            if not file_path.exists():
                bound_logger.error("xbrl_parser.parse_file.file_not_found")
                return None
            
            # 读取文件内容
            content = self._read_file_content(file_path)
            if not content:
                bound_logger.error("xbrl_parser.parse_file.empty_content")
                return None
            
            # 解析HTML/XML内容
            soup = BeautifulSoup(content, 'html.parser')
            
            # 提取基金基本信息
            fund_data = ParsedFundData(
                fund_code="UNKNOWN",
                fund_name="未知基金"
            )
            
            # 解析基本信息
            self._parse_basic_info(soup, fund_data, bound_logger)
            
            # 解析报告期间
            self._parse_report_period(soup, fund_data, bound_logger)
            
            # 解析净值信息
            self._parse_nav_info(soup, fund_data, bound_logger)
            
            # 解析资产配置
            self._parse_asset_allocation(soup, fund_data, bound_logger)
            
            # 解析前十大持仓
            self._parse_top_holdings(soup, fund_data, bound_logger)
            
            # 解析行业配置
            self._parse_industry_allocation(soup, fund_data, bound_logger)
            
            bound_logger.info(
                "xbrl_parser.parse_file.success",
                fund_code=fund_data.fund_code,
                fund_name=fund_data.fund_name[:50],
                nav=fund_data.net_asset_value,
                assets_count=len(fund_data.asset_allocations),
                holdings_count=len(fund_data.top_holdings),
                industries_count=len(fund_data.industry_allocations)
            )
            
            return fund_data
            
        except Exception as e:
            bound_logger.error(
                "xbrl_parser.parse_file.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """读取文件内容，自动检测编码"""
        try:
            # 先尝试检测编码
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                encoding_result = chardet.detect(raw_data)
                encoding = encoding_result.get('encoding', 'utf-8')
            
            # 使用检测到的编码读取文件
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            self.logger.error(
                "xbrl_parser.read_file.error",
                file_path=str(file_path),
                error=str(e)
            )
            return None
    
    def _parse_basic_info(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析基金基本信息"""
        text_content = soup.get_text()
        
        # 提取基金代码
        fund_code = self._extract_by_patterns(text_content, self.patterns['fund_code'])
        if fund_code:
            fund_data.fund_code = fund_code
            bound_logger.info("xbrl_parser.basic_info.fund_code", code=fund_code)
        
        # 提取基金名称
        fund_name = self._extract_by_patterns(text_content, self.patterns['fund_name'])
        if fund_name:
            fund_data.fund_name = fund_name.strip()
            bound_logger.info("xbrl_parser.basic_info.fund_name", name=fund_name[:50])
        
        # 尝试从表格中提取更准确的信息
        self._extract_from_tables(soup, fund_data, bound_logger)
    
    def _parse_report_period(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析报告期间"""
        text_content = soup.get_text()
        
        for pattern in self.patterns['report_period']:
            match = re.search(pattern, text_content)
            if match:
                try:
                    start_str, end_str = match.groups()
                    
                    # 解析日期
                    start_date = self._parse_date_string(start_str)
                    end_date = self._parse_date_string(end_str)
                    
                    if start_date and end_date:
                        fund_data.report_period_start = start_date
                        fund_data.report_period_end = end_date
                        fund_data.report_year = end_date.year
                        
                        # 判断报告类型和季度
                        month = end_date.month
                        if month == 12:
                            fund_data.report_type = "年度报告"
                            fund_data.report_quarter = None
                        elif month == 6:
                            fund_data.report_type = "半年度报告"
                            fund_data.report_quarter = 2
                        elif month == 3:
                            fund_data.report_type = "第一季度报告"
                            fund_data.report_quarter = 1
                        elif month == 9:
                            fund_data.report_type = "第三季度报告"
                            fund_data.report_quarter = 3
                        
                        bound_logger.info(
                            "xbrl_parser.report_period.parsed",
                            start=start_date,
                            end=end_date,
                            type=fund_data.report_type
                        )
                        break
                        
                except Exception as e:
                    bound_logger.warning(
                        "xbrl_parser.report_period.parse_error",
                        pattern=pattern,
                        match=match.groups(),
                        error=str(e)
                    )
    
    def _parse_nav_info(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析净值信息"""
        text_content = soup.get_text()
        
        # 提取单位净值
        nav = self._extract_by_patterns(text_content, self.patterns['net_asset_value'])
        if nav:
            try:
                fund_data.net_asset_value = Decimal(nav.replace(',', ''))
                bound_logger.info("xbrl_parser.nav_info.nav", value=fund_data.net_asset_value)
            except (InvalidOperation, ValueError) as e:
                bound_logger.warning("xbrl_parser.nav_info.nav_parse_error", value=nav, error=str(e))
        
        # 提取总净资产
        total_assets = self._extract_by_patterns(text_content, self.patterns['total_net_assets'])
        if total_assets:
            try:
                fund_data.total_net_assets = Decimal(total_assets.replace(',', ''))
                bound_logger.info("xbrl_parser.nav_info.total_assets", value=fund_data.total_net_assets)
            except (InvalidOperation, ValueError) as e:
                bound_logger.warning("xbrl_parser.nav_info.assets_parse_error", value=total_assets, error=str(e))
    
    def _extract_by_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """使用正则表达式模式提取数据"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """解析日期字符串"""
        try:
            # 处理中文日期格式
            if '年' in date_str and '月' in date_str and '日' in date_str:
                # 2024年3月31日
                match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
                if match:
                    year, month, day = map(int, match.groups())
                    return date(year, month, day)
            
            # 处理标准日期格式
            elif '-' in date_str:
                # 2024-03-31
                parts = date_str.split('-')
                if len(parts) == 3:
                    year, month, day = map(int, parts)
                    return date(year, month, day)
            
        except (ValueError, AttributeError):
            pass
        
        return None

    def _extract_from_tables(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """从表格中提取信息"""
        # 这里可以添加更复杂的表格解析逻辑
        pass

    def _parse_asset_allocation(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析资产配置"""
        # 查找包含"资产配置"或"投资组合"的表格
        tables = soup.find_all('table')

        for table in tables:
            table_text = table.get_text()
            if any(keyword in table_text for keyword in ['资产配置', '投资组合', '资产类别', '大类资产']):
                self._extract_asset_allocation_from_table(table, fund_data, bound_logger)
                break

    def _parse_top_holdings(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析前十大持仓"""
        # 查找包含"前十大"或"重仓股"的表格
        tables = soup.find_all('table')

        for table in tables:
            table_text = table.get_text()
            if any(keyword in table_text for keyword in ['前十大', '重仓股', '前10大', '主要持仓']):
                self._extract_top_holdings_from_table(table, fund_data, bound_logger)
                break

    def _parse_industry_allocation(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析行业配置"""
        # 查找包含"行业配置"或"行业分布"的表格
        tables = soup.find_all('table')

        for table in tables:
            table_text = table.get_text()
            if any(keyword in table_text for keyword in ['行业配置', '行业分布', '行业投资', '申万行业']):
                self._extract_industry_allocation_from_table(table, fund_data, bound_logger)
                break

    def _extract_asset_allocation_from_table(self, table: Tag, fund_data: ParsedFundData, bound_logger):
        """从表格中提取资产配置信息"""
        # 简化实现，实际需要根据具体的表格结构来解析
        rows = table.find_all('tr')
        for row in rows[1:]:  # 跳过表头
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                try:
                    asset_type = cells[0].get_text().strip()
                    market_value_text = cells[1].get_text().strip()
                    percentage_text = cells[2].get_text().strip()

                    # 解析数值
                    market_value = self._parse_number(market_value_text)
                    percentage = self._parse_percentage(percentage_text)

                    if asset_type and (market_value or percentage):
                        allocation = {
                            'asset_type': asset_type,
                            'asset_name': asset_type,
                            'market_value': market_value,
                            'percentage': percentage
                        }
                        fund_data.asset_allocations.append(allocation)

                except Exception as e:
                    bound_logger.warning("xbrl_parser.asset_allocation.row_error", error=str(e))

    def _extract_top_holdings_from_table(self, table: Tag, fund_data: ParsedFundData, bound_logger):
        """从表格中提取前十大持仓信息"""
        # 简化实现
        rows = table.find_all('tr')
        rank = 1

        for row in rows[1:]:  # 跳过表头
            if rank > 10:  # 只取前10大
                break

            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                try:
                    security_name = cells[0].get_text().strip()
                    market_value_text = cells[1].get_text().strip()
                    percentage_text = cells[2].get_text().strip()

                    market_value = self._parse_number(market_value_text)
                    percentage = self._parse_percentage(percentage_text)

                    if security_name and (market_value or percentage):
                        holding = {
                            'holding_type': '股票',
                            'security_code': None,
                            'security_name': security_name,
                            'shares': None,
                            'market_value': market_value,
                            'percentage': percentage,
                            'rank': rank
                        }
                        fund_data.top_holdings.append(holding)
                        rank += 1

                except Exception as e:
                    bound_logger.warning("xbrl_parser.top_holdings.row_error", error=str(e))

    def _extract_industry_allocation_from_table(self, table: Tag, fund_data: ParsedFundData, bound_logger):
        """从表格中提取行业配置信息"""
        # 简化实现
        rows = table.find_all('tr')

        for row in rows[1:]:  # 跳过表头
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                try:
                    industry_name = cells[0].get_text().strip()
                    market_value_text = cells[1].get_text().strip()
                    percentage_text = cells[2].get_text().strip()

                    market_value = self._parse_number(market_value_text)
                    percentage = self._parse_percentage(percentage_text)

                    if industry_name and (market_value or percentage):
                        allocation = {
                            'industry_code': None,
                            'industry_name': industry_name,
                            'industry_level': 1,
                            'market_value': market_value,
                            'percentage': percentage,
                            'rank': None
                        }
                        fund_data.industry_allocations.append(allocation)

                except Exception as e:
                    bound_logger.warning("xbrl_parser.industry_allocation.row_error", error=str(e))

    def _parse_number(self, text: str) -> Optional[Decimal]:
        """解析数字"""
        try:
            # 移除逗号和其他非数字字符
            cleaned = re.sub(r'[,，\s]', '', text)
            # 提取数字部分
            match = re.search(r'[\d.]+', cleaned)
            if match:
                return Decimal(match.group())
        except (InvalidOperation, ValueError):
            pass
        return None

    def _parse_percentage(self, text: str) -> Optional[Decimal]:
        """解析百分比"""
        try:
            # 移除%符号和空格
            cleaned = text.replace('%', '').replace(' ', '').replace('％', '')
            match = re.search(r'[\d.]+', cleaned)
            if match:
                return Decimal(match.group())
        except (InvalidOperation, ValueError):
            pass
        return None

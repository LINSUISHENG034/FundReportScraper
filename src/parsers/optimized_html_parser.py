#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的HTML解析器
用于解析基金报告的HTML内容
"""

import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any
from pathlib import Path
from bs4 import BeautifulSoup, Tag

from ..models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
from ..core.logging import get_logger
from .base_parser import BaseParser, ParserType, ParseResult


class OptimizedHTMLParser(BaseParser):
    """优化的HTML解析器"""
    
    def __init__(self):
        super().__init__(ParserType.HTML_LEGACY)
        self.logger = get_logger(__name__)
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """检查是否能够解析给定的内容"""
        if not content:
            return False
        
        # 检查是否包含HTML标签
        html_indicators = ['<table', '<tr', '<td', '<div', '<span']
        content_lower = content.lower()
        
        # 至少包含一个HTML标签
        has_html = any(indicator in content_lower for indicator in html_indicators)
        
        # 检查是否包含基金报告相关关键词
        fund_keywords = ['基金代码', '基金名称', '投资组合', '资产配置', '前十']
        has_fund_content = any(keyword in content for keyword in fund_keywords)
        
        return has_html and has_fund_content
    
    def parse_content(self, content: str, file_path: Optional[Path] = None):
        """解析内容并返回解析结果"""
        try:
            fund_report = self.parse(content)
            return self._create_success_result(fund_report, file_path)
        except Exception as e:
            error_msg = f"HTML解析失败: {str(e)}"
            self.logger.error(error_msg, file_path=str(file_path) if file_path else None)
            return self._create_error_result(error_msg, file_path)
    
    def parse(self, html_content: str) -> FundReport:
        """解析HTML内容"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 创建基金报告对象
            fund_report = FundReport()
            
            # 提取基本信息
            self._extract_basic_info(soup, fund_report)
            
            # 提取额外信息
            self._extract_additional_info(soup, fund_report)
            
            # 提取报告期间
            self._extract_report_period(soup, fund_report)
            
            # 提取表格数据
            self._extract_table_data(soup, fund_report)
            
            return fund_report
            
        except Exception as e:
            self.logger.error(f"HTML解析失败: {e}")
            raise
    
    def _extract_basic_info(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取基本信息"""
        # 基金代码
        fund_code = self._search_by_labels(soup, ["基金代码", "代码"])
        if fund_code:
            fund_report.fund_code = fund_code
        
        # 基金名称
        fund_name = self._search_by_labels(soup, ["基金名称", "基金简称", "名称"])
        if fund_name:
            fund_report.fund_name = fund_name
        
        # 净值
        nav = self._search_by_labels(soup, ["单位净值", "净值", "基金单位净值"])
        if nav:
            fund_report.net_asset_value = self._parse_decimal(nav)
        
        # 总净资产
        total_assets = self._search_by_labels(soup, ["基金资产净值", "资产净值", "净资产"])
        if total_assets:
            fund_report.total_net_assets = self._parse_decimal(total_assets)
    
    def _extract_additional_info(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取额外信息"""
        # 基金经理
        fund_manager = self._search_by_labels(soup, ["基金经理", "经理"])
        if fund_manager and not hasattr(fund_report, 'fund_manager'):
            fund_report.fund_manager = fund_manager
        
        # 托管人
        custodian = self._search_by_labels(soup, ["基金托管人", "托管人", "托管银行"])
        if custodian and not hasattr(fund_report, 'custodian'):
            fund_report.custodian = custodian
        
        # 管理公司
        management_company = self._search_by_labels(soup, ["基金管理人", "管理人", "管理公司"])
        if management_company and not hasattr(fund_report, 'management_company'):
            fund_report.management_company = management_company
        
        # 基金类型
        fund_type = self._search_by_labels(soup, ["基金类型", "类型", "基金性质"])
        if fund_type and not hasattr(fund_report, 'fund_type'):
            fund_report.fund_type = fund_type
    
    def _search_by_labels(self, soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
        """通过标签搜索值"""
        for label in labels:
            # 搜索包含标签的元素
            elements = soup.find_all(text=re.compile(label))
            for element in elements:
                parent = element.parent
                if parent:
                    # 查找同级或下级元素中的值
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        text = next_sibling.get_text().strip()
                        if text and text not in [label, ":", "："]:
                            return text
                    
                    # 查找父元素的下一个兄弟元素
                    parent_next = parent.parent.find_next_sibling() if parent.parent else None
                    if parent_next:
                        text = parent_next.get_text().strip()
                        if text and text not in [label, ":", "："]:
                            return text
        
        return None
    
    def _extract_report_period(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取报告期间"""
        # 搜索报告期间相关的文本
        period_patterns = [
            r"报告期间?[：:]?\s*(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?\s*[至到-]\s*(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?",
            r"(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?\s*[至到-]\s*(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?",
            r"报告期[：:]?\s*(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?"
        ]
        
        text_content = soup.get_text()
        
        for pattern in period_patterns:
            matches = re.search(pattern, text_content)
            if matches:
                groups = matches.groups()
                if len(groups) >= 6:  # 开始和结束日期
                    try:
                        start_date = f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                        end_date = f"{groups[3]}-{groups[4].zfill(2)}-{groups[5].zfill(2)}"
                        fund_report.report_period_start = start_date
                        fund_report.report_period_end = end_date
                        return
                    except (ValueError, IndexError):
                        continue
                elif len(groups) >= 3:  # 只有结束日期
                    try:
                        end_date = f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                        fund_report.report_period_end = end_date
                        # 推断开始日期（假设为季度报告）
                        month = int(groups[1])
                        if month in [3, 6, 9, 12]:
                            start_month = month - 2
                            if start_month <= 0:
                                start_month = 12 + start_month
                                start_year = int(groups[0]) - 1
                            else:
                                start_year = int(groups[0])
                            start_date = f"{start_year}-{str(start_month).zfill(2)}-01"
                            fund_report.report_period_start = start_date
                        return
                    except (ValueError, IndexError):
                        continue
    
    def _extract_table_data(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取表格数据"""
        tables = soup.find_all("table")
        
        for table in tables:
            table_type = self._identify_table_type(table)
            
            if table_type == "asset_allocation":
                allocations = self._parse_asset_allocation_table(table)
                if allocations:
                    fund_report.asset_allocations = allocations
            
            elif table_type == "top_holdings":
                holdings = self._parse_top_holdings_table(table)
                if holdings:
                    fund_report.top_holdings = holdings
            
            elif table_type == "industry_allocation":
                allocations = self._parse_industry_allocation_table(table)
                if allocations:
                    fund_report.industry_allocations = allocations
            
            elif table_type == "stock_portfolio":
                holdings = self._parse_stock_portfolio_table(table)
                if holdings:
                    if not fund_report.top_holdings:
                        fund_report.top_holdings = holdings
                    else:
                        fund_report.top_holdings.extend(holdings)
            
            elif table_type == "bond_portfolio":
                holdings = self._parse_bond_portfolio_table(table)
                if holdings:
                    if not fund_report.top_holdings:
                        fund_report.top_holdings = holdings
                    else:
                        fund_report.top_holdings.extend(holdings)
            
            elif table_type == "top_ten_stocks":
                holdings = self._parse_top_ten_stocks_table(table)
                if holdings:
                    fund_report.top_holdings = holdings
    
    def _identify_table_type(self, table: Tag) -> Optional[str]:
        """识别表格类型"""
        table_text = table.get_text().lower()
        
        if any(keyword in table_text for keyword in ["资产配置", "资产分布", "投资分布"]):
            return "asset_allocation"
        elif any(keyword in table_text for keyword in ["前十大", "前10大", "重仓股票", "主要持仓"]):
            return "top_holdings"
        elif any(keyword in table_text for keyword in ["行业配置", "行业分布", "按行业分类"]):
            return "industry_allocation"
        elif any(keyword in table_text for keyword in ["股票投资组合", "股票明细"]):
            return "stock_portfolio"
        elif any(keyword in table_text for keyword in ["债券投资组合", "债券明细"]):
            return "bond_portfolio"
        elif any(keyword in table_text for keyword in ["前十名股票", "前10名股票"]):
            return "top_ten_stocks"
        
        return None
    
    def _parse_asset_allocation_table(self, table: Tag) -> List[AssetAllocation]:
        """解析资产配置表"""
        allocations = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return allocations
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            asset_type_idx = self._find_column_index(headers, ["资产类型", "类型", "品种"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            
            # 解析数据行
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                asset_type = None
                market_value = None
                percentage = None
                
                if asset_type_idx is not None and asset_type_idx < len(cells):
                    asset_type = cells[asset_type_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if asset_type:
                    allocation = AssetAllocation(
                        asset_type=asset_type,
                        market_value=market_value,
                        percentage=percentage
                    )
                    allocations.append(allocation)
            
        except Exception as e:
            self.logger.warning("资产配置表解析失败", error=str(e))
        
        return allocations
    
    def _parse_stock_portfolio_table(self, table: Tag) -> List[TopHolding]:
        """解析股票投资组合表"""
        holdings = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return holdings
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            name_idx = self._find_column_index(headers, ["名称", "证券名称", "股票名称"])
            code_idx = self._find_column_index(headers, ["代码", "证券代码", "股票代码"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            shares_idx = self._find_column_index(headers, ["数量", "股数", "持股数量"])
            
            # 解析数据行
            rank = 1
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                security_name = None
                security_code = None
                market_value = None
                percentage = None
                shares = None
                
                if name_idx is not None and name_idx < len(cells):
                    security_name = cells[name_idx].get_text().strip()
                
                if code_idx is not None and code_idx < len(cells):
                    security_code = cells[code_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if shares_idx is not None and shares_idx < len(cells):
                    shares = self._parse_decimal(cells[shares_idx].get_text().strip())
                
                if security_name:
                    holding = TopHolding(
                        holding_type="股票",
                        security_code=security_code,
                        security_name=security_name,
                        shares=shares,
                        market_value=market_value,
                        percentage=percentage,
                        rank=rank
                    )
                    holdings.append(holding)
                    rank += 1
            
        except Exception as e:
            self.logger.warning("股票投资组合表解析失败", error=str(e))
        
        return holdings
    
    def _parse_bond_portfolio_table(self, table: Tag) -> List[TopHolding]:
        """解析债券投资组合表"""
        holdings = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return holdings
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            name_idx = self._find_column_index(headers, ["名称", "证券名称", "债券名称"])
            code_idx = self._find_column_index(headers, ["代码", "证券代码", "债券代码"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            shares_idx = self._find_column_index(headers, ["数量", "面值", "持有数量"])
            
            # 解析数据行
            rank = 1
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                security_name = None
                security_code = None
                market_value = None
                percentage = None
                shares = None
                
                if name_idx is not None and name_idx < len(cells):
                    security_name = cells[name_idx].get_text().strip()
                
                if code_idx is not None and code_idx < len(cells):
                    security_code = cells[code_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if shares_idx is not None and shares_idx < len(cells):
                    shares = self._parse_decimal(cells[shares_idx].get_text().strip())
                
                if security_name:
                    holding = TopHolding(
                        holding_type="债券",
                        security_code=security_code,
                        security_name=security_name,
                        shares=shares,
                        market_value=market_value,
                        percentage=percentage,
                        rank=rank
                    )
                    holdings.append(holding)
                    rank += 1
            
        except Exception as e:
            self.logger.warning("债券投资组合表解析失败", error=str(e))
        
        return holdings
    
    def _parse_top_ten_stocks_table(self, table: Tag) -> List[TopHolding]:
        """解析前十名股票表"""
        holdings = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return holdings
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            name_idx = self._find_column_index(headers, ["名称", "证券名称", "股票名称"])
            code_idx = self._find_column_index(headers, ["代码", "证券代码", "股票代码"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            shares_idx = self._find_column_index(headers, ["数量", "股数", "持股数量"])
            
            # 解析数据行
            rank = 1
            for row in rows[1:]:
                if rank > 10:  # 限制为前10大
                    break
                
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                security_name = None
                security_code = None
                market_value = None
                percentage = None
                shares = None
                
                if name_idx is not None and name_idx < len(cells):
                    security_name = cells[name_idx].get_text().strip()
                
                if code_idx is not None and code_idx < len(cells):
                    security_code = cells[code_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if shares_idx is not None and shares_idx < len(cells):
                    shares = self._parse_decimal(cells[shares_idx].get_text().strip())
                
                if security_name:
                    holding = TopHolding(
                        holding_type="股票",
                        security_code=security_code,
                        security_name=security_name,
                        shares=shares,
                        market_value=market_value,
                        percentage=percentage,
                        rank=rank
                    )
                    holdings.append(holding)
                    rank += 1
            
        except Exception as e:
            self.logger.warning("前十名股票表解析失败", error=str(e))
        
        return holdings
    
    def _parse_top_holdings_table(self, table: Tag) -> List[TopHolding]:
        """解析前十大持仓表"""
        holdings = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return holdings
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            name_idx = self._find_column_index(headers, ["名称", "证券名称", "股票名称"])
            code_idx = self._find_column_index(headers, ["代码", "证券代码", "股票代码"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            
            # 解析数据行
            rank = 1
            for row in rows[1:]:
                if rank > 10:  # 限制为前10大
                    break
                
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                security_name = None
                security_code = None
                market_value = None
                percentage = None
                
                if name_idx is not None and name_idx < len(cells):
                    security_name = cells[name_idx].get_text().strip()
                
                if code_idx is not None and code_idx < len(cells):
                    security_code = cells[code_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if security_name:
                    holding = TopHolding(
                        holding_type="股票",
                        security_code=security_code,
                        security_name=security_name,
                        shares=None,
                        market_value=market_value,
                        percentage=percentage,
                        rank=rank
                    )
                    holdings.append(holding)
                    rank += 1
            
        except Exception as e:
            self.logger.warning("持仓表解析失败", error=str(e))
        
        return holdings
    
    def _parse_industry_allocation_table(self, table: Tag) -> List[IndustryAllocation]:
        """解析行业配置表"""
        allocations = []
        
        try:
            rows = table.find_all("tr")
            if len(rows) < 2:
                return allocations
            
            # 简化的表头识别
            header_row = rows[0]
            headers = [cell.get_text().strip().lower() for cell in header_row.find_all(["th", "td"])]
            
            # 查找关键列的索引
            industry_idx = self._find_column_index(headers, ["行业", "行业名称", "申万行业"])
            value_idx = self._find_column_index(headers, ["市值", "金额", "价值"])
            percentage_idx = self._find_column_index(headers, ["占比", "比例", "百分比"])
            
            # 解析数据行
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                
                industry_name = None
                market_value = None
                percentage = None
                
                if industry_idx is not None and industry_idx < len(cells):
                    industry_name = cells[industry_idx].get_text().strip()
                
                if value_idx is not None and value_idx < len(cells):
                    market_value = self._parse_decimal(cells[value_idx].get_text().strip())
                
                if percentage_idx is not None and percentage_idx < len(cells):
                    percentage = self._parse_decimal(cells[percentage_idx].get_text().strip())
                
                if industry_name and (market_value or percentage):
                    allocation = IndustryAllocation(
                        industry_name=industry_name,
                        market_value=market_value,
                        percentage=percentage
                    )
                    allocations.append(allocation)
            
        except Exception as e:
            self.logger.warning("行业配置表解析失败", error=str(e))
        
        return allocations
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """查找包含关键词的列索引"""
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in keywords):
                return i
        return None
    
    def _parse_decimal(self, text: str) -> Optional[Decimal]:
        """解析数值"""
        if not text or text.strip() in ["-", "--", "—", "N/A", "n/a", ""]:
            return None
        
        try:
            # 清理数值字符串
            cleaned = re.sub(r"[^\d.,-]", "", text.strip())
            if not cleaned:
                return None
            
            # 处理逗号分隔符
            cleaned = cleaned.replace(",", "")
            
            return Decimal(cleaned)
            
        except (InvalidOperation, ValueError):
            return None
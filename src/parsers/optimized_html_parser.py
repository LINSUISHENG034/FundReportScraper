"""
优化的HTML解析器 - 基于现有逻辑的简化和优化版本
Optimized HTML parser - simplified and optimized version based on existing logic
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag

from src.core.logging import get_logger
from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
from src.parsers.base_parser import BaseParser, ParseResult, ParserType


class OptimizedHTMLParser(BaseParser):
    """优化的HTML解析器"""
    
    def __init__(self):
        super().__init__(ParserType.HTML_LEGACY)
        
        # 优化的字段匹配模式
        self.field_patterns = {
            "fund_code": [
                r"基金主?代码[：:]?\s*([A-Za-z0-9]{6})",
                r"基金代码[：:]?\s*([A-Za-z0-9]{6})",
                r"产品代码[：:]?\s*([A-Za-z0-9]{6})"
            ],
            "fund_name": [
                r"基金名称[：:]?\s*([^\n\r]+)",
                r"基金全称[：:]?\s*([^\n\r]+)",
                r"基金简称[：:]?\s*([^\n\r]+)"
            ],
            "net_asset_value": [
                r"基金份额净值[：:]?\s*([\d.]+)",
                r"份额净值[：:]?\s*([\d.]+)",
                r"单位净值[：:]?\s*([\d.]+)",
                r"报告期末基金份额净值[：:]?\s*([\d.]+)"
            ],
            "total_net_assets": [
                r"基金资产净值[：:]?\s*([\d,]+\.?\d*)",
                r"资产净值[：:]?\s*([\d,]+\.?\d*)",
                r"报告期末基金资产净值[：:]?\s*([\d,]+\.?\d*)",
                r"资产总计[：:]?\s*([\d,]+\.?\d*)"
            ]
        }
        
        # 标签搜索关键词
        self.label_keywords = {
            "fund_code": ["基金主代码", "基金代码", "产品代码"],
            "fund_name": ["基金名称", "基金全称", "基金简称"],
            "net_asset_value": ["基金份额净值", "份额净值", "单位净值", "报告期末基金份额净值"],
            "total_net_assets": ["基金资产净值", "资产净值", "报告期末基金资产净值", "资产总计"]
        }
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """检查是否能够解析给定的内容"""
        if not content:
            return False
        
        # 检查HTML特征
        html_indicators = [
            r'<html[^>]*>',
            r'<head[^>]*>',
            r'<body[^>]*>',
            r'<table[^>]*>',
            r'<div[^>]*>'
        ]
        
        content_lower = content.lower()
        html_matches = sum(1 for pattern in html_indicators 
                          if re.search(pattern, content_lower))
        
        # 检查基金报告关键词
        fund_keywords = ["基金代码", "基金名称", "份额净值", "资产净值"]
        fund_matches = sum(1 for keyword in fund_keywords 
                          if keyword in content)
        
        # HTML特征 + 基金关键词
        return html_matches >= 2 and fund_matches >= 2
    
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """解析HTML内容"""
        try:
            soup = BeautifulSoup(content, "html.parser")
            fund_report = FundReport()
            
            # 提取基本信息
            self._extract_basic_info(soup, fund_report)
            
            # 提取表格数据
            self._extract_table_data(soup, fund_report)
            
            return self._create_success_result(fund_report, file_path)
            
        except Exception as e:
            self.logger.error("HTML解析异常", error=str(e))
            return self._create_error_result(f"HTML解析异常: {str(e)}")
    
    def _extract_basic_info(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取基本信息"""
        # 方法1: 使用正则表达式在全文中搜索
        full_text = soup.get_text()
        self._extract_with_regex(full_text, fund_report)
        
        # 方法2: 使用结构化标签搜索补充缺失字段
        self._extract_with_labels(soup, fund_report)
        
        self.logger.debug("基本信息提取完成",
                         fund_code=fund_report.fund_code,
                         fund_name=fund_report.fund_name,
                         nav=str(fund_report.net_asset_value) if fund_report.net_asset_value else None,
                         total_assets=str(fund_report.total_net_assets) if fund_report.total_net_assets else None)
    
    def _extract_with_regex(self, text: str, fund_report: FundReport):
        """使用正则表达式提取信息"""
        for field, patterns in self.field_patterns.items():
            if getattr(fund_report, field) is not None:
                continue  # 字段已有值，跳过
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    
                    if field in ["net_asset_value", "total_net_assets"]:
                        decimal_value = self._parse_decimal(value)
                        if decimal_value:
                            setattr(fund_report, field, decimal_value)
                            break
                    else:
                        if value and len(value) > 1:
                            setattr(fund_report, field, value)
                            break
    
    def _extract_with_labels(self, soup: BeautifulSoup, fund_report: FundReport):
        """使用标签搜索提取信息"""
        for field, keywords in self.label_keywords.items():
            if getattr(fund_report, field) is not None:
                continue  # 字段已有值，跳过
            
            for keyword in keywords:
                value = self._find_value_by_label(soup, keyword)
                if value:
                    if field in ["net_asset_value", "total_net_assets"]:
                        decimal_value = self._parse_decimal(value)
                        if decimal_value:
                            setattr(fund_report, field, decimal_value)
                            break
                    else:
                        if len(value) > 1:
                            setattr(fund_report, field, value)
                            break
    
    def _find_value_by_label(self, soup: BeautifulSoup, label: str) -> Optional[str]:
        """通过标签查找对应的值 - 简化版本"""
        try:
            # 查找包含标签的元素
            label_elements = soup.find_all(text=re.compile(label, re.IGNORECASE))
            
            for label_element in label_elements:
                if not label_element.parent:
                    continue
                
                # 策略1: 值在同一个元素内
                parent_text = label_element.parent.get_text(strip=True)
                match = re.search(f"{re.escape(label)}\\s*[:：]?\\s*([\\w.-]+)", parent_text)
                if match and len(match.group(1)) > 1:
                    return match.group(1)
                
                # 策略2: 值在下一个兄弟元素中
                next_sibling = label_element.parent.find_next_sibling()
                if next_sibling:
                    sibling_text = next_sibling.get_text(strip=True)
                    if sibling_text and len(sibling_text) > 1:
                        return sibling_text
                
                # 策略3: 值在表格的下一个单元格中
                if label_element.parent.name in ['td', 'th']:
                    next_cell = label_element.parent.find_next_sibling(['td', 'th'])
                    if next_cell:
                        cell_text = next_cell.get_text(strip=True)
                        if cell_text and len(cell_text) > 1:
                            return cell_text
                
                # 策略4: 值在父元素的后续文本中
                parent = label_element.parent
                for next_elem in parent.find_next_siblings(limit=3):
                    if next_elem.get_text(strip=True):
                        text = next_elem.get_text(strip=True)
                        if len(text) > 1:
                            return text
            
        except Exception as e:
            self.logger.debug(f"标签搜索失败: {label}", error=str(e))
        
        return None
    
    def _extract_table_data(self, soup: BeautifulSoup, fund_report: FundReport):
        """提取表格数据"""
        try:
            tables = soup.find_all("table")
            
            for table in tables:
                table_type = self._identify_table_type(table)
                
                if table_type == "asset_allocation":
                    fund_report.asset_allocations = self._parse_asset_allocation_table(table)
                elif table_type == "top_holdings":
                    fund_report.top_holdings = self._parse_top_holdings_table(table)
                elif table_type == "industry_allocation":
                    fund_report.industry_allocations = self._parse_industry_allocation_table(table)
            
            self.logger.debug("表格数据提取完成",
                             asset_allocations=len(fund_report.asset_allocations or []),
                             top_holdings=len(fund_report.top_holdings or []),
                             industry_allocations=len(fund_report.industry_allocations or []))
            
        except Exception as e:
            self.logger.warning("表格数据提取失败", error=str(e))
    
    def _identify_table_type(self, table: Tag) -> Optional[str]:
        """识别表格类型 - 简化版本"""
        table_text = table.get_text().lower()
        
        # 排除明显不相关的表格
        exclude_keywords = ["关联方", "交易", "费用", "审计", "托管", "会计", "声明"]
        if any(keyword in table_text for keyword in exclude_keywords):
            return None
        
        # 检查表格行数
        rows = table.find_all("tr")
        if len(rows) < 3:
            return None
        
        # 简化的表格类型识别
        if any(keyword in table_text for keyword in ["资产配置", "投资组合", "大类资产"]):
            return "asset_allocation"
        elif any(keyword in table_text for keyword in ["前十大", "重仓股", "主要持仓"]):
            return "top_holdings"
        elif any(keyword in table_text for keyword in ["行业配置", "行业分布", "申万行业"]):
            return "industry_allocation"
        
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
            asset_type_idx = self._find_column_index(headers, ["资产", "类别", "类型", "品种"])
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
                
                if asset_type and (market_value or percentage):
                    allocation = AssetAllocation(
                        asset_type=asset_type,
                        asset_name=asset_type,
                        market_value=market_value,
                        percentage=percentage
                    )
                    allocations.append(allocation)
            
        except Exception as e:
            self.logger.warning("资产配置表解析失败", error=str(e))
        
        return allocations
    
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
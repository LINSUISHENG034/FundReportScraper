"""重构后的XBRL解析器

使用智能表格解析机制，动态识别表头，避免硬编码列索引。
采用更灵活和鲁棒的解析策略。
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation
from datetime import date

from bs4 import BeautifulSoup, Tag
import chardet
from src.core.logging import get_logger
# 最终修复：导入真正的SQLAlchemy ORM模型，而不是使用本地的dataclass
from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation


class SmartTableParser:
    """智能表格解析器"""

    def __init__(self):
        # 增强的表头关键词映射
        self.header_mappings = {
            # 资产配置表头
            "asset_type": ["资产类别", "投资类别", "资产类型", "大类资产", "资产", "投资品种", "投资标的"],
            "market_value": ["市值", "公允价值", "金额", "投资金额", "市场价值", "价值", "投资市值", "持仓市值"],
            "percentage": ["占比", "比例", "百分比", "占净值比例", "占基金资产净值比例", "占基金净值比例", "净值占比"],
            # 持仓表头
            "security_name": ["证券名称", "股票名称", "证券简称", "名称", "持仓名称", "股票简称", "证券"],
            "security_code": ["证券代码", "股票代码", "代码", "证券代码"],
            "shares": ["持股数量", "数量", "股数", "持有股数", "持仓数量", "持有数量"],
            "rank": ["序号", "排名", "名次", "排序"],
            # 行业配置表头
            "industry_name": ["行业名称", "行业", "申万行业", "行业分类", "行业类别", "所属行业"],
            "industry_code": ["行业代码", "代码", "申万代码"],
        }

        # 表格识别关键词优化
        self.table_keywords = {
            "asset_allocation": {
                "primary": ["资产配置", "投资组合", "资产类别", "大类资产"],
                "secondary": ["股票", "债券", "现金", "银行存款", "其他资产"],
            },
            "top_holdings": {
                "primary": ["前十大", "重仓股", "前10大", "主要持仓", "股票投资"],
                "secondary": ["持股", "投资明细", "重仓", "前十名"],
            },
            "industry_allocation": {
                "primary": ["行业配置", "行业分布", "行业投资", "申万行业"],
                "secondary": ["行业分类", "行业类别", "按行业"],
            },
        }

    def identify_table_type(self, table: Tag) -> Optional[str]:
        """优化的表格类型识别"""
        table_text = table.get_text().lower()
        exclude_keywords = ["关联方", "交易", "费用", "审计", "托管", "会计", "声明", "签字", "附注"]
        if any(keyword in table_text for keyword in exclude_keywords) or len(table.find_all("tr")) < 3:
            return None

        scores = {
            table_type: sum(3 for kw in keywords["primary"] if kw in table_text) + sum(1 for kw in keywords["secondary"] if kw in table_text)
            for table_type, keywords in self.table_keywords.items()
        }
        
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] >= 3:
                return best_type
        return None

    def parse_table_headers(self, table: Tag) -> Dict[str, int]:
        """增强的动态表头解析"""
        best_mapping, best_score = {}, 0
        for row in table.find_all("tr")[:5]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2: continue
            
            current_mapping, score = {}, 0
            for i, cell in enumerate(cells):
                cell_text = cell.get_text().strip().lower()
                for field, keywords in self.header_mappings.items():
                    if any(kw in cell_text for kw in keywords):
                        current_mapping[field] = i
                        score += 1
                        break
            
            if score > best_score:
                best_mapping, best_score = current_mapping, score
        return best_mapping

    def _parse_decimal(self, text: str) -> Optional[Decimal]:
        """从文本中解析Decimal数值"""
        if not text or text.strip() in ["-", "--", "—", "N/A", "n/a"]: return None
        try:
            cleaned = re.sub(r"[^\d.,-]", "", text)
            return Decimal(cleaned.replace(",", ""))
        except (InvalidOperation, ValueError):
            return None

    def extract_cell_value(self, cell: Tag, value_type: str = "text") -> Any:
        """提取并解析单元格的值"""
        text = cell.get_text().strip()
        if value_type == "decimal":
            return self._parse_decimal(text)
        return text if text and text not in ["-", "--", "—", "N/A", "n/a"] else None

    def parse_asset_allocation_table(self, table: Tag) -> List[AssetAllocation]:
        """解析资产配置表并返回AssetAllocation对象列表"""
        headers = self.parse_table_headers(table)
        if not headers: return []
        
        allocations = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < len(headers): continue
            
            try:
                asset_type = self.extract_cell_value(cells[headers["asset_type"]])
                market_value = self.extract_cell_value(cells[headers["market_value"]], "decimal")
                percentage = self.extract_cell_value(cells[headers["percentage"]], "decimal")
                
                if asset_type and (market_value is not None or percentage is not None):
                    allocations.append(AssetAllocation(
                        asset_type=asset_type,
                        asset_name=asset_type,
                        market_value=market_value,
                        percentage=percentage
                    ))
            except (KeyError, IndexError):
                continue
        return allocations

    def parse_top_holdings_table(self, table: Tag) -> List[TopHolding]:
        """解析前十大持仓表并返回TopHolding对象列表"""
        headers = self.parse_table_headers(table)
        if not headers: return []

        holdings = []
        rank = 1
        for row in table.find_all("tr")[1:]:
            if rank > 10: break
            cells = row.find_all(["td", "th"])
            if len(cells) < len(headers): continue

            try:
                name = self.extract_cell_value(cells[headers["security_name"]])
                if name:
                    holdings.append(TopHolding(
                        holding_type="股票",
                        security_code=self.extract_cell_value(cells[headers["security_code"]]) if "security_code" in headers else None,
                        security_name=name,
                        shares=self.extract_cell_value(cells[headers["shares"]], "decimal") if "shares" in headers else None,
                        market_value=self.extract_cell_value(cells[headers["market_value"]], "decimal"),
                        percentage=self.extract_cell_value(cells[headers["percentage"]], "decimal"),
                        rank=rank
                    ))
                    rank += 1
            except (KeyError, IndexError):
                continue
        return holdings

    def parse_industry_allocation_table(self, table: Tag) -> List[IndustryAllocation]:
        """解析行业配置表并返回IndustryAllocation对象列表"""
        headers = self.parse_table_headers(table)
        if not headers: return []

        allocations = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < len(headers): continue

            try:
                name = self.extract_cell_value(cells[headers["industry_name"]])
                if name:
                    allocations.append(IndustryAllocation(
                        industry_name=name,
                        market_value=self.extract_cell_value(cells[headers["market_value"]], "decimal"),
                        percentage=self.extract_cell_value(cells[headers["percentage"]], "decimal")
                    ))
            except (KeyError, IndexError):
                continue
        return allocations


class XBRLParser:
    """重构后的XBRL解析器"""

    def __init__(self):
        self.logger = get_logger("xbrl_parser")
        self.table_parser = SmartTableParser()
        self.patterns = {
            "fund_code": [r"基金代码[：:]?\s*([A-Za-z0-9]{6})"],
            "fund_name": [r"基金名称[：:]?\s*([^\n\r]+)"],
            "report_period": [r"报告期自\s*(\d{4}年\d{1,2}月\d{1,2}日)\s*至\s*(\d{4}年\d{1,2}月\d{1,2}日)"],
            "net_asset_value": [r"基金份额净值[：:]?\s*([\d.]+)"],
            "total_net_assets": [r"资产总计[：:]?\s*([\d,]+\.\d+)"],
        }

    def parse_file(self, file_path: Path) -> Optional[FundReport]:
        """解析XBRL文件并返回一个FundReport ORM对象"""
        bound_logger = self.logger.bind(file_path=str(file_path))
        try:
            content = self._read_file_with_encoding(file_path)
            if not content: return None
            
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator=" ", strip=True)
            
            fund_report = FundReport()
            
            self._parse_basic_info(text_content, fund_report)
            self._parse_tables(soup, fund_report)

            bound_logger.info("xbrl_parser.parse_complete", fund_code=fund_report.fund_code)
            return fund_report

        except Exception as e:
            bound_logger.error("xbrl_parser.parse_error", error=str(e))
            return None

    def _read_file_with_encoding(self, file_path: Path) -> Optional[str]:
        """自动检测编码并读取文件"""
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read()
            encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
            return raw_data.decode(encoding, errors="ignore")
        except IOError as e:
            self.logger.warning("xbrl_parser.file_read_error", error=str(e))
            return None

    def _extract_by_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """使用正则表达式模式提取数据"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match: return match.group(1).strip()
        return None

    def _parse_basic_info(self, text: str, report: FundReport):
        """解析基本信息并填充到FundReport对象"""
        report.fund_code = self._extract_by_patterns(text, self.patterns["fund_code"])
        report.fund_name = self._extract_by_patterns(text, self.patterns["fund_name"])
        
        period_match = self._extract_by_patterns(text, self.patterns["report_period"])
        if period_match:
            # This part needs a more robust date parsing logic
            pass

        try:
            nav_str = self._extract_by_patterns(text, self.patterns["net_asset_value"])
            if nav_str: report.net_asset_value = Decimal(nav_str)
            
            total_assets_str = self._extract_by_patterns(text, self.patterns["total_net_assets"])
            if total_assets_str: report.total_net_assets = Decimal(total_assets_str.replace(",", ""))
        except (InvalidOperation, ValueError):
            self.logger.warning("Failed to parse NAV or total assets.")

    def _parse_tables(self, soup: BeautifulSoup, report: FundReport):
        """解析所有表格并填充到FundReport对象"""
        tables = soup.find_all("table")
        for table in tables:
            table_type = self.table_parser.identify_table_type(table)
            if table_type == "asset_allocation":
                report.asset_allocations = self.table_parser.parse_asset_allocation_table(table)
            elif table_type == "top_holdings":
                report.top_holdings = self.table_parser.parse_top_holdings_table(table)
            elif table_type == "industry_allocation":
                report.industry_allocations = self.table_parser.parse_industry_allocation_table(table)

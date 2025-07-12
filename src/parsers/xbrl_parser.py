"""
XBRL parser for fund reports.
基金报告XBRL解析器，基于arelle库实现。

根据技术原理文档，XBRL是高度格式化的数据，可以根据标签精确提取各类表格或文本数据。
主要提取内容：
1. 资产配置表
2. 前十大重仓股
3. 行业配置
4. 基金基本信息
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AssetAllocation:
    """资产配置数据结构"""
    stock_investments: Optional[Decimal] = None
    stock_ratio: Optional[Decimal] = None
    bond_investments: Optional[Decimal] = None
    bond_ratio: Optional[Decimal] = None
    fund_investments: Optional[Decimal] = None
    fund_ratio: Optional[Decimal] = None
    cash_and_equivalents: Optional[Decimal] = None
    cash_ratio: Optional[Decimal] = None
    other_investments: Optional[Decimal] = None
    other_ratio: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None


@dataclass
class TopHolding:
    """前十大重仓股数据结构"""
    rank: int
    stock_code: str
    stock_name: str
    shares_held: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    portfolio_ratio: Optional[Decimal] = None


@dataclass
class IndustryAllocation:
    """行业配置数据结构"""
    industry_name: str
    industry_code: Optional[str] = None
    market_value: Optional[Decimal] = None
    portfolio_ratio: Optional[Decimal] = None


@dataclass
class FundBasicInfo:
    """基金基本信息"""
    fund_code: str
    fund_name: str
    report_date: datetime
    net_asset_value: Optional[Decimal] = None
    total_shares: Optional[Decimal] = None
    unit_nav: Optional[Decimal] = None
    accumulated_nav: Optional[Decimal] = None
    fund_manager: Optional[str] = None
    management_company: Optional[str] = None


class XBRLParseError(Exception):
    """XBRL解析错误"""
    pass


class XBRLParser:
    """
    XBRL报告解析器
    
    支持解析基金定期报告中的关键数据，包括：
    - 基金基本信息
    - 资产配置表
    - 前十大重仓股
    - 行业配置
    """
    
    def __init__(self):
        """初始化解析器"""
        self.namespaces = {}
        self.root = None
        self.fund_info = None
        
        # 常见的XBRL命名空间
        self.common_namespaces = {
            'xbrl': 'http://www.xbrl.org/2003/instance',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'iso4217': 'http://www.xbrl.org/2003/iso4217',
            'link': 'http://www.xbrl.org/2003/linkbase',
            'xl': 'http://www.xbrl.org/2003/XLink',
        }
        
        logger.info("xbrl_parser.initialized")
    
    def load_from_file(self, file_path: Union[str, Path]) -> None:
        """
        从文件加载XBRL数据
        
        Args:
            file_path: XBRL文件路径
            
        Raises:
            XBRLParseError: 解析失败时抛出
        """
        bound_logger = logger.bind(file_path=str(file_path))
        bound_logger.info("xbrl_parser.load_file.start")
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise XBRLParseError(f"文件不存在: {file_path}")
            
            # 解析XML
            tree = ET.parse(file_path)
            self.root = tree.getroot()
            
            # 提取命名空间
            self._extract_namespaces()
            
            bound_logger.info(
                "xbrl_parser.load_file.success",
                namespaces_count=len(self.namespaces),
                root_tag=self.root.tag
            )
            
        except ET.ParseError as e:
            bound_logger.error(
                "xbrl_parser.load_file.xml_error",
                error=str(e)
            )
            raise XBRLParseError(f"XML解析错误: {e}")
        
        except Exception as e:
            bound_logger.error(
                "xbrl_parser.load_file.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise XBRLParseError(f"文件加载失败: {e}")
    
    def load_from_content(self, content: Union[str, bytes]) -> None:
        """
        从内容加载XBRL数据
        
        Args:
            content: XBRL内容（字符串或字节）
            
        Raises:
            XBRLParseError: 解析失败时抛出
        """
        logger.info("xbrl_parser.load_content.start")
        
        try:
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            # 解析XML
            self.root = ET.fromstring(content)
            
            # 提取命名空间
            self._extract_namespaces()
            
            logger.info(
                "xbrl_parser.load_content.success",
                content_length=len(content),
                namespaces_count=len(self.namespaces)
            )
            
        except ET.ParseError as e:
            logger.error(
                "xbrl_parser.load_content.xml_error",
                error=str(e)
            )
            raise XBRLParseError(f"XML解析错误: {e}")
        
        except Exception as e:
            logger.error(
                "xbrl_parser.load_content.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise XBRLParseError(f"内容解析失败: {e}")
    
    def _extract_namespaces(self) -> None:
        """提取XML命名空间"""
        if self.root is None:
            return
        
        # 从根元素提取命名空间
        for key, value in self.root.attrib.items():
            if key.startswith('xmlns'):
                if ':' in key:
                    prefix = key.split(':', 1)[1]
                else:
                    prefix = 'default'
                self.namespaces[prefix] = value
        
        # 合并常用命名空间
        for prefix, uri in self.common_namespaces.items():
            if prefix not in self.namespaces:
                self.namespaces[prefix] = uri
        
        logger.debug(
            "xbrl_parser.namespaces_extracted",
            namespaces=list(self.namespaces.keys())
        )
    
    def extract_fund_basic_info(self) -> Optional[FundBasicInfo]:
        """
        提取基金基本信息
        
        Returns:
            基金基本信息对象，提取失败时返回None
        """
        if self.root is None:
            raise XBRLParseError("尚未加载XBRL数据")
        
        logger.info("xbrl_parser.extract_basic_info.start")
        
        try:
            # 提取基金代码和名称
            fund_code = self._find_element_value([
                './/FundCode', './/fundCode', './/基金代码',
                './/*[contains(local-name(), "FundCode")]',
                './/*[contains(local-name(), "fundCode")]'
            ])
            
            fund_name = self._find_element_value([
                './/FundName', './/fundName', './/基金名称',
                './/*[contains(local-name(), "FundName")]',
                './/*[contains(local-name(), "fundName")]'
            ])
            
            # 提取报告日期
            report_date = self._extract_report_date()
            
            # 提取净资产价值相关数据
            net_asset_value = self._find_decimal_value([
                './/NetAssetValue', './/netAssetValue', './/基金净资产',
                './/*[contains(local-name(), "NetAsset")]'
            ])
            
            total_shares = self._find_decimal_value([
                './/TotalShares', './/totalShares', './/基金份额总额',
                './/*[contains(local-name(), "TotalShare")]'
            ])
            
            unit_nav = self._find_decimal_value([
                './/UnitNAV', './/unitNAV', './/单位净值',
                './/*[contains(local-name(), "UnitNAV")]',
                './/*[contains(local-name(), "NetAssetValuePerUnit")]'
            ])
            
            accumulated_nav = self._find_decimal_value([
                './/AccumulatedNAV', './/accumulatedNAV', './/累计净值',
                './/*[contains(local-name(), "AccumulatedNAV")]'
            ])
            
            # 提取基金管理人信息
            fund_manager = self._find_element_value([
                './/FundManager', './/fundManager', './/基金经理',
                './/*[contains(local-name(), "FundManager")]'
            ])
            
            management_company = self._find_element_value([
                './/ManagementCompany', './/managementCompany', './/管理公司',
                './/*[contains(local-name(), "ManagementCompany")]'
            ])
            
            if not fund_code:
                logger.warning("xbrl_parser.extract_basic_info.no_fund_code")
                return None
            
            fund_info = FundBasicInfo(
                fund_code=fund_code,
                fund_name=fund_name or f"未知基金({fund_code})",
                report_date=report_date or datetime.now(),
                net_asset_value=net_asset_value,
                total_shares=total_shares,
                unit_nav=unit_nav,
                accumulated_nav=accumulated_nav,
                fund_manager=fund_manager,
                management_company=management_company
            )
            
            self.fund_info = fund_info
            
            logger.info(
                "xbrl_parser.extract_basic_info.success",
                fund_code=fund_code,
                fund_name=fund_name
            )
            
            return fund_info
            
        except Exception as e:
            logger.error(
                "xbrl_parser.extract_basic_info.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def _extract_report_date(self) -> Optional[datetime]:
        """提取报告日期"""
        # 尝试从不同的可能位置提取报告日期
        date_patterns = [
            './/ReportDate', './/reportDate', './/报告日期',
            './/*[contains(local-name(), "ReportDate")]',
            './/*[contains(local-name(), "PeriodEnd")]',
            './/context/period/instant',
            './/context/period/endDate'
        ]
        
        for pattern in date_patterns:
            elements = self.root.findall(pattern, self.namespaces)
            for element in elements:
                date_str = element.text
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        return parsed_date
        
        return None
    
    def _find_element_value(self, xpath_patterns: List[str]) -> Optional[str]:
        """根据多个XPath模式查找元素值"""
        if self.root is None:
            return None
        
        for pattern in xpath_patterns:
            try:
                elements = self.root.findall(pattern, self.namespaces)
                for element in elements:
                    if element.text and element.text.strip():
                        return element.text.strip()
            except Exception as e:
                logger.debug(
                    "xbrl_parser.xpath_search_failed",
                    pattern=pattern,
                    error=str(e)
                )
                continue
        
        return None
    
    def _find_decimal_value(self, xpath_patterns: List[str]) -> Optional[Decimal]:
        """根据多个XPath模式查找数值"""
        value_str = self._find_element_value(xpath_patterns)
        if value_str:
            return self._parse_decimal(value_str)
        return None
    
    def _parse_decimal(self, value_str: str) -> Optional[Decimal]:
        """解析数值字符串为Decimal"""
        try:
            # 清理字符串：移除逗号、空格等
            cleaned = re.sub(r'[,\s\u00a0]', '', value_str)
            
            # 处理中文数字单位
            if '万' in cleaned:
                cleaned = cleaned.replace('万', '')
                multiplier = Decimal('10000')
            elif '亿' in cleaned:
                cleaned = cleaned.replace('亿', '')
                multiplier = Decimal('100000000')
            else:
                multiplier = Decimal('1')
            
            # 提取数值部分
            match = re.search(r'-?\d+\.?\d*', cleaned)
            if match:
                number = Decimal(match.group())
                return number * multiplier
            
        except Exception as e:
            logger.debug(
                "xbrl_parser.parse_decimal_failed",
                value_str=value_str,
                error=str(e)
            )
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
        
        # 常见日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.debug(
            "xbrl_parser.parse_date_failed",
            date_str=date_str
        )
        return None
    
    def extract_asset_allocation(self) -> Optional[AssetAllocation]:
        """
        提取资产配置表数据
        
        Returns:
            资产配置对象，提取失败时返回None
        """
        if self.root is None:
            raise XBRLParseError("尚未加载XBRL数据")
        
        logger.info("xbrl_parser.extract_asset_allocation.start")
        
        try:
            # 股票投资相关
            stock_investments = self._find_decimal_value([
                './/StockInvestments', './/stockInvestments', './/股票投资',
                './/*[contains(local-name(), "Stock") and contains(local-name(), "Investment")]',
                './/*[contains(local-name(), "权益投资")]',
                './/*[contains(local-name(), "股票")]//MarketValue'
            ])
            
            stock_ratio = self._find_decimal_value([
                './/StockRatio', './/stockRatio', './/股票占比',
                './/*[contains(local-name(), "Stock") and contains(local-name(), "Ratio")]',
                './/*[contains(local-name(), "权益投资占比")]'
            ])
            
            # 债券投资相关
            bond_investments = self._find_decimal_value([
                './/BondInvestments', './/bondInvestments', './/债券投资',
                './/*[contains(local-name(), "Bond") and contains(local-name(), "Investment")]',
                './/*[contains(local-name(), "债券")]//MarketValue'
            ])
            
            bond_ratio = self._find_decimal_value([
                './/BondRatio', './/bondRatio', './/债券占比',
                './/*[contains(local-name(), "Bond") and contains(local-name(), "Ratio")]'
            ])
            
            # 基金投资相关
            fund_investments = self._find_decimal_value([
                './/FundInvestments', './/fundInvestments', './/基金投资',
                './/*[contains(local-name(), "Fund") and contains(local-name(), "Investment")]'
            ])
            
            fund_ratio = self._find_decimal_value([
                './/FundRatio', './/fundRatio', './/基金占比',
                './/*[contains(local-name(), "Fund") and contains(local-name(), "Ratio")]'
            ])
            
            # 现金及现金等价物
            cash_and_equivalents = self._find_decimal_value([
                './/CashAndEquivalents', './/cashAndEquivalents', './/现金及现金等价物',
                './/*[contains(local-name(), "Cash")]',
                './/*[contains(local-name(), "货币资金")]'
            ])
            
            cash_ratio = self._find_decimal_value([
                './/CashRatio', './/cashRatio', './/现金占比',
                './/*[contains(local-name(), "Cash") and contains(local-name(), "Ratio")]'
            ])
            
            # 其他投资
            other_investments = self._find_decimal_value([
                './/OtherInvestments', './/otherInvestments', './/其他投资',
                './/*[contains(local-name(), "Other") and contains(local-name(), "Investment")]'
            ])
            
            other_ratio = self._find_decimal_value([
                './/OtherRatio', './/otherRatio', './/其他占比',
                './/*[contains(local-name(), "Other") and contains(local-name(), "Ratio")]'
            ])
            
            # 总资产
            total_assets = self._find_decimal_value([
                './/TotalAssets', './/totalAssets', './/总资产',
                './/*[contains(local-name(), "Total") and contains(local-name(), "Asset")]',
                './/NetAssetValue', './/netAssetValue'
            ])
            
            # 如果没有找到任何资产配置数据，返回None
            if not any([stock_investments, bond_investments, fund_investments, 
                       cash_and_equivalents, other_investments, total_assets]):
                logger.warning("xbrl_parser.extract_asset_allocation.no_data")
                return None
            
            allocation = AssetAllocation(
                stock_investments=stock_investments,
                stock_ratio=stock_ratio,
                bond_investments=bond_investments,
                bond_ratio=bond_ratio,
                fund_investments=fund_investments,
                fund_ratio=fund_ratio,
                cash_and_equivalents=cash_and_equivalents,
                cash_ratio=cash_ratio,
                other_investments=other_investments,
                other_ratio=other_ratio,
                total_assets=total_assets
            )
            
            logger.info(
                "xbrl_parser.extract_asset_allocation.success",
                has_stock=stock_investments is not None,
                has_bond=bond_investments is not None,
                has_cash=cash_and_equivalents is not None
            )
            
            return allocation
            
        except Exception as e:
            logger.error(
                "xbrl_parser.extract_asset_allocation.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def extract_top_holdings(self, limit: int = 10) -> List[TopHolding]:
        """
        提取前十大重仓股数据
        
        Args:
            limit: 提取的持仓数量限制
            
        Returns:
            重仓股列表
        """
        if self.root is None:
            raise XBRLParseError("尚未加载XBRL数据")
        
        logger.info("xbrl_parser.extract_top_holdings.start", limit=limit)
        
        try:
            holdings = []
            
            # 查找重仓股相关的表格或节点
            holdings_patterns = [
                './/TopHoldings', './/topHoldings', './/前十大重仓股',
                './/*[contains(local-name(), "TopHolding")]',
                './/*[contains(local-name(), "重仓股")]',
                './/*[contains(local-name(), "StockHolding")]',
                './/*[contains(local-name(), "Holdings")]//Stock',
                './/table[contains(@class, "holdings")]//tr',
                './/table[contains(@id, "holdings")]//tr'
            ]
            
            for pattern in holdings_patterns:
                elements = self.root.findall(pattern, self.namespaces)
                if elements:
                    holdings = self._parse_holdings_from_elements(elements, limit)
                    if holdings:
                        break
            
            # 如果上述方法没有找到，尝试通过更通用的方式查找
            if not holdings:
                holdings = self._extract_holdings_generic(limit)
            
            logger.info(
                "xbrl_parser.extract_top_holdings.success",
                holdings_count=len(holdings)
            )
            
            return holdings[:limit]
            
        except Exception as e:
            logger.error(
                "xbrl_parser.extract_top_holdings.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    def extract_industry_allocation(self) -> List[IndustryAllocation]:
        """
        提取行业配置数据
        
        Returns:
            行业配置列表
        """
        if self.root is None:
            raise XBRLParseError("尚未加载XBRL数据")
        
        logger.info("xbrl_parser.extract_industry_allocation.start")
        
        try:
            industries = []
            
            # 查找行业配置相关的节点
            industry_patterns = [
                './/IndustryAllocation', './/industryAllocation', './/行业配置',
                './/*[contains(local-name(), "Industry")]',
                './/*[contains(local-name(), "行业")]',
                './/*[contains(local-name(), "Sector")]',
                './/table[contains(@class, "industry")]//tr',
                './/table[contains(@id, "industry")]//tr'
            ]
            
            for pattern in industry_patterns:
                elements = self.root.findall(pattern, self.namespaces)
                if elements:
                    industries = self._parse_industries_from_elements(elements)
                    if industries:
                        break
            
            # 如果上述方法没有找到，尝试通用方式
            if not industries:
                industries = self._extract_industries_generic()
            
            logger.info(
                "xbrl_parser.extract_industry_allocation.success",
                industries_count=len(industries)
            )
            
            return industries
            
        except Exception as e:
            logger.error(
                "xbrl_parser.extract_industry_allocation.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    def _parse_holdings_from_elements(self, elements: List[ET.Element], limit: int) -> List[TopHolding]:
        """从元素列表解析重仓股数据"""
        holdings = []
        
        for i, element in enumerate(elements[:limit]):
            try:
                # 提取股票代码
                stock_code = self._find_element_value_in_subtree(element, [
                    './/StockCode', './/stockCode', './/股票代码',
                    './/*[contains(local-name(), "Code")]'
                ])
                
                # 提取股票名称
                stock_name = self._find_element_value_in_subtree(element, [
                    './/StockName', './/stockName', './/股票名称',
                    './/*[contains(local-name(), "Name")]'
                ])
                
                if not stock_code and not stock_name:
                    continue
                
                # 提取持仓数量
                shares_held = self._find_decimal_value_in_subtree(element, [
                    './/SharesHeld', './/sharesHeld', './/持股数量',
                    './/*[contains(local-name(), "Shares")]'
                ])
                
                # 提取市值
                market_value = self._find_decimal_value_in_subtree(element, [
                    './/MarketValue', './/marketValue', './/市值',
                    './/*[contains(local-name(), "Value")]'
                ])
                
                # 提取占比
                portfolio_ratio = self._find_decimal_value_in_subtree(element, [
                    './/PortfolioRatio', './/portfolioRatio', './/占比',
                    './/*[contains(local-name(), "Ratio")]',
                    './/*[contains(local-name(), "Percent")]'
                ])
                
                holding = TopHolding(
                    rank=i + 1,
                    stock_code=stock_code or f"UNKNOWN_{i+1}",
                    stock_name=stock_name or f"未知股票_{i+1}",
                    shares_held=shares_held,
                    market_value=market_value,
                    portfolio_ratio=portfolio_ratio
                )
                
                holdings.append(holding)
                
            except Exception as e:
                logger.debug(
                    "xbrl_parser.parse_holding_failed",
                    index=i,
                    error=str(e)
                )
                continue
        
        return holdings
    
    def _extract_holdings_generic(self, limit: int) -> List[TopHolding]:
        """通用的重仓股提取方法"""
        holdings = []
        
        # 尝试查找所有包含股票信息的元素
        stock_elements = self.root.findall('.//*[contains(local-name(), "Stock")]', self.namespaces)
        
        for i, element in enumerate(stock_elements[:limit]):
            try:
                stock_code = element.get('code') or element.text
                if stock_code and len(stock_code) == 6 and stock_code.isdigit():
                    holding = TopHolding(
                        rank=i + 1,
                        stock_code=stock_code,
                        stock_name=f"股票_{stock_code}"
                    )
                    holdings.append(holding)
            except Exception:
                continue
        
        return holdings
    
    def _parse_industries_from_elements(self, elements: List[ET.Element]) -> List[IndustryAllocation]:
        """从元素列表解析行业配置数据"""
        industries = []
        
        for element in elements:
            try:
                # 提取行业名称
                industry_name = self._find_element_value_in_subtree(element, [
                    './/IndustryName', './/industryName', './/行业名称',
                    './/*[contains(local-name(), "Industry")]',
                    './/*[contains(local-name(), "Sector")]'
                ])
                
                if not industry_name:
                    continue
                
                # 提取行业代码
                industry_code = self._find_element_value_in_subtree(element, [
                    './/IndustryCode', './/industryCode', './/行业代码',
                    './/*[contains(local-name(), "Code")]'
                ])
                
                # 提取市值
                market_value = self._find_decimal_value_in_subtree(element, [
                    './/MarketValue', './/marketValue', './/市值',
                    './/*[contains(local-name(), "Value")]'
                ])
                
                # 提取占比
                portfolio_ratio = self._find_decimal_value_in_subtree(element, [
                    './/PortfolioRatio', './/portfolioRatio', './/占比',
                    './/*[contains(local-name(), "Ratio")]',
                    './/*[contains(local-name(), "Percent")]'
                ])
                
                industry = IndustryAllocation(
                    industry_name=industry_name,
                    industry_code=industry_code,
                    market_value=market_value,
                    portfolio_ratio=portfolio_ratio
                )
                
                industries.append(industry)
                
            except Exception as e:
                logger.debug(
                    "xbrl_parser.parse_industry_failed",
                    error=str(e)
                )
                continue
        
        return industries
    
    def _extract_industries_generic(self) -> List[IndustryAllocation]:
        """通用的行业配置提取方法"""
        industries = []
        
        # 尝试查找所有包含行业信息的元素
        industry_elements = self.root.findall('.//*[contains(local-name(), "Industry")]', self.namespaces)
        
        for element in industry_elements:
            try:
                industry_name = element.text
                if industry_name and len(industry_name.strip()) > 0:
                    industry = IndustryAllocation(
                        industry_name=industry_name.strip()
                    )
                    industries.append(industry)
            except Exception:
                continue
        
        return industries
    
    def _find_element_value_in_subtree(self, element: ET.Element, xpath_patterns: List[str]) -> Optional[str]:
        """在子树中查找元素值"""
        for pattern in xpath_patterns:
            try:
                sub_elements = element.findall(pattern, self.namespaces)
                for sub_element in sub_elements:
                    if sub_element.text and sub_element.text.strip():
                        return sub_element.text.strip()
            except Exception:
                continue
        return None
    
    def _find_decimal_value_in_subtree(self, element: ET.Element, xpath_patterns: List[str]) -> Optional[Decimal]:
        """在子树中查找数值"""
        value_str = self._find_element_value_in_subtree(element, xpath_patterns)
        if value_str:
            return self._parse_decimal(value_str)
        return None
    
    def get_all_elements_info(self) -> Dict[str, Any]:
        """获取所有元素信息，用于调试和分析XBRL结构"""
        if self.root is None:
            return {}
        
        def analyze_element(element, path=""):
            """递归分析元素"""
            current_path = f"{path}/{element.tag}" if path else element.tag
            
            info = {
                "tag": element.tag,
                "attrib": element.attrib,
                "text": element.text.strip() if element.text else None,
                "path": current_path
            }
            
            children = {}
            for child in element:
                child_name = child.tag
                if child_name not in children:
                    children[child_name] = []
                children[child_name].append(analyze_element(child, current_path))
            
            if children:
                info["children"] = children
            
            return info
        
        return analyze_element(self.root)
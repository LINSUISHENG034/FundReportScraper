"""基金XBRL报告专业解析器

基于基金行业特点的XBRL解析器，结合Arelle专业库和LLM智能辅助，
实现高质量的基金报告数据提取。
"""

import asyncio
import json
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from bs4 import BeautifulSoup
from pydantic import BaseModel, field_validator, Field

from src.core.logging import get_logger
from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
from src.parsers.base_parser import BaseParser, ParseResult, ParserType


class FundBasicInfo(BaseModel):
    """基金基本信息验证模型"""
    fund_code: str = Field(..., pattern=r'^\d{6}$')
    fund_name: str = Field(..., min_length=1, max_length=200)
    fund_manager: Optional[str] = Field(None, max_length=200)
    report_date: date
    report_type: str
    net_asset_value: Optional[Decimal] = Field(None, ge=0)
    total_net_assets: Optional[Decimal] = Field(None, ge=0)
    
    @field_validator('fund_code')
    @classmethod
    def validate_fund_code(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('基金代码必须是6位数字')
        return v


class AssetAllocationData(BaseModel):
    """资产配置数据验证模型"""
    asset_type: str = Field(..., min_length=1, max_length=50)
    market_value: Optional[Decimal] = Field(None, ge=0)
    percentage: Optional[Decimal] = Field(None, ge=0, le=1)
    
    @field_validator('asset_type')
    @classmethod
    def validate_asset_type(cls, v):
        valid_types = [
            '股票投资', '债券投资', '基金投资', '银行存款',
            '买入返售金融资产', '其他资产', '现金及现金等价物'
        ]
        # 允许包含这些关键词的变体
        if not any(keyword in v for keyword in ['股票', '债券', '基金', '存款', '现金', '其他']):
            raise ValueError(f'无效的资产类型: {v}')
        return v


class StockHoldingData(BaseModel):
    """股票持仓数据验证模型"""
    rank: int = Field(..., ge=1, le=10)
    stock_code: str = Field(..., pattern=r'^\d{6}$')
    stock_name: str = Field(..., min_length=1, max_length=100)
    market_value: Optional[Decimal] = Field(None, ge=0)
    percentage: Optional[Decimal] = Field(None, ge=0, le=1)
    shares: Optional[int] = Field(None, ge=0)


class FundXBRLParser(BaseParser):
    """基金XBRL报告专业解析器"""
    
    def __init__(self, use_llm_assist: bool = True):
        super().__init__(ParserType.XBRL_NATIVE)
        self.logger = get_logger("fund_xbrl_parser")
        self.use_llm_assist = use_llm_assist
        self.llm_assistant = None
        
        # 初始化LLM助手
        if use_llm_assist:
            try:
                from src.parsers.llm_assistant import OllamaLLMAssistant
                self.llm_assistant = OllamaLLMAssistant()
                self.logger.info("LLM助手初始化成功")
            except ImportError:
                self.logger.warning("无法加载LLM助手，将使用传统解析方法")
                self.use_llm_assist = False
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """检查是否能够解析给定的XBRL内容"""
        if not content:
            return False
        
        # 检查XBRL标识
        xbrl_indicators = [
            '<html', '<xbrl', 'xmlns:xbrl', 'xbrl.xsd',
            '基金', '年度报告', '季度报告', '半年报'
        ]
        
        content_lower = content.lower()
        return any(indicator.lower() in content_lower for indicator in xbrl_indicators)
    
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """解析XBRL内容"""
        try:
            self.logger.info("开始解析XBRL内容", file_path=str(file_path) if file_path else None)
            
            # 解析HTML结构
            soup = BeautifulSoup(content, 'lxml')
            
            # 提取基本信息
            basic_info = self._extract_basic_info(soup, file_path)
            if not basic_info:
                return self._create_error_result("无法提取基金基本信息")
            
            # 创建基金报告对象
            fund_report = self._create_fund_report(basic_info)
            
            # 提取资产配置数据
            asset_allocations = self._extract_asset_allocations(soup)
            fund_report.asset_allocations = asset_allocations
            
            # 提取前十大持仓
            top_holdings = self._extract_top_holdings(soup)
            fund_report.top_holdings = top_holdings
            
            # 提取行业配置
            industry_allocations = self._extract_industry_allocations(soup)
            fund_report.industry_allocations = industry_allocations
            
            # 数据质量验证
            validation_result = self.validate_result(fund_report)
            
            # 使用LLM进行数据验证和修复
            # 暂时禁用LLM增强功能以避免事件循环冲突
            # if self.use_llm_assist and self.llm_assistant:
            #     fund_report = await self._llm_enhance_data(fund_report, soup)
            
            return ParseResult(
                success=True,
                fund_report=fund_report,
                parser_type=self.parser_type,
                errors=[],
                warnings=validation_result.warnings if validation_result else [],
                metadata={
                    'file_path': str(file_path) if file_path else None,
                    'parsing_method': 'fund_xbrl_parser',
                    'llm_assisted': self.use_llm_assist,
                    'validation_score': validation_result.completeness_score if validation_result else 0.0
                }
            )
            
        except Exception as e:
            self.logger.error("XBRL解析失败", error=str(e), file_path=str(file_path) if file_path else None)
            return self._create_error_result(f"解析异常: {str(e)}")
    
    def _extract_basic_info(self, soup: BeautifulSoup, file_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """提取基金基本信息"""
        try:
            # 从标题中提取基金名称和报告信息
            title_element = soup.find('p', style=lambda x: x and 'font-size:18px' in x)
            if not title_element:
                title_element = soup.find('title')
            
            if not title_element:
                return None
            
            title_text = title_element.get_text(strip=True)
            
            # 提取基金代码（从文件名或内容中）
            fund_code = self._extract_fund_code(title_text, soup, file_path)
            if not fund_code:
                return None
            
            # 提取基金名称
            fund_name = self._extract_fund_name(title_text)
            
            # 提取报告日期和类型
            report_period_start, report_period_end, report_type = self._extract_report_info(title_text, soup)
            
            # 提取基金管理人
            fund_manager = self._extract_fund_manager(soup)
            
            # 提取净值信息
            nav_info = self._extract_nav_info(soup)
            
            return {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'fund_manager': fund_manager,
                'report_period_start': report_period_start,
                'report_period_end': report_period_end,
                'report_type': report_type,
                **nav_info
            }
            
        except Exception as e:
            self.logger.error("提取基本信息失败", error=str(e))
            return None
    
    def _extract_fund_code(self, title_text: str, soup: BeautifulSoup, file_path: Optional[Path] = None) -> Optional[str]:
        """提取基金代码"""
        # 从标题中查找6位数字
        code_pattern = r'(\d{6})'
        match = re.search(code_pattern, title_text)
        if match:
            return match.group(1)
        
        # 从页面其他位置查找
        for element in soup.find_all(text=re.compile(r'基金代码.*?(\d{6})')):
            match = re.search(r'(\d{6})', element)
            if match:
                return match.group(1)
        
        # 从文件名中提取基金代码
        if file_path:
            # 处理file_path可能是字符串或Path对象的情况
            if isinstance(file_path, str):
                filename = Path(file_path).name
            else:
                filename = file_path.name
            match = re.search(code_pattern, filename)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_fund_name(self, title_text: str) -> str:
        """提取基金名称"""
        # 移除报告类型和日期信息
        name = re.sub(r'\d{4}年.*?报告', '', title_text)
        name = re.sub(r'\d{4}-\d{2}-\d{2}', '', name)
        name = name.strip()
        
        # 如果名称太短，返回原标题
        if len(name) < 5:
            return title_text
        
        return name
    
    def _extract_report_info(self, title_text: str, soup: BeautifulSoup) -> Tuple[date, date, str]:
        """提取报告期间开始日期、结束日期和报告类型"""
        # 首先从页面内容中查找报告期间信息
        page_text = soup.get_text()
        
        # 查找"本报告期自...起至...止"的模式
        period_pattern = r'本报告期自(\d{4})年(\d{1,2})月(\d{1,2})日起至(\d{4})年(\d{1,2})月(\d{1,2})日止'
        period_match = re.search(period_pattern, page_text)
        
        if period_match:
            start_year, start_month, start_day = map(int, period_match.groups()[:3])
            end_year, end_month, end_day = map(int, period_match.groups()[3:])
            report_period_start = date(start_year, start_month, start_day)
            report_period_end = date(end_year, end_month, end_day)
        else:
            # 备选方案：查找标准日期格式
            date_pattern = r'(\d{4})-(\d{2})-(\d{2})'
            date_match = re.search(date_pattern, title_text)
            
            if date_match:
                year, month, day = map(int, date_match.groups())
                report_period_end = date(year, month, day)
            else:
                # 从页面内容中查找日期
                date_match = re.search(date_pattern, page_text)
                if date_match:
                    year, month, day = map(int, date_match.groups())
                    report_period_end = date(year, month, day)
                else:
                    # 默认使用从标题提取的年份的12月31日
                    year_match = re.search(r'(\d{4})年', title_text)
                    if year_match:
                        year = int(year_match.group(1))
                        report_period_end = date(year, 12, 31)
                    else:
                        # 最后的备选方案：使用2024年12月31日
                        report_period_end = date(2024, 12, 31)
            
            # 根据报告类型推断开始日期
            report_period_start = self._infer_period_start(report_period_end, title_text)
        
        # 确定报告类型
        if '年度报告' in title_text or '年报' in title_text:
            report_type = 'ANNUAL'
        elif '半年' in title_text:
            report_type = 'SEMI_ANNUAL'
        elif 'Q1' in title_text or '一季' in title_text:
            report_type = 'Q1'
        elif 'Q2' in title_text or '二季' in title_text:
            report_type = 'Q2'
        elif 'Q3' in title_text or '三季' in title_text:
            report_type = 'Q3'
        elif 'Q4' in title_text or '四季' in title_text:
            report_type = 'Q4'
        else:
            report_type = 'QUARTERLY'
        
        return report_period_start, report_period_end, report_type
    
    def _infer_period_start(self, period_end: date, title_text: str) -> date:
        """根据报告期结束日期和报告类型推断开始日期"""
        year = period_end.year
        
        if '年度报告' in title_text or '年报' in title_text:
            # 年报：1月1日到12月31日
            return date(year, 1, 1)
        elif '半年' in title_text:
            # 半年报：1月1日到6月30日
            return date(year, 1, 1)
        elif 'Q1' in title_text or '一季' in title_text:
            # 一季报：1月1日到3月31日
            return date(year, 1, 1)
        elif 'Q2' in title_text or '二季' in title_text:
            # 二季报：4月1日到6月30日
            return date(year, 4, 1)
        elif 'Q3' in title_text or '三季' in title_text:
            # 三季报：7月1日到9月30日
            return date(year, 7, 1)
        elif 'Q4' in title_text or '四季' in title_text:
            # 四季报：10月1日到12月31日
            return date(year, 10, 1)
        else:
            # 默认为年报
            return date(year, 1, 1)
    
    def _extract_fund_manager(self, soup: BeautifulSoup) -> Optional[str]:
        """提取基金管理人"""
        # 查找包含"基金管理人"的文本
        for element in soup.find_all(text=re.compile(r'基金管理人[：:](.*?)')):
            match = re.search(r'基金管理人[：:](.*?)(?:基金托管人|$)', element)
            if match:
                return match.group(1).strip()
        
        # 从页面标题区域查找
        for p in soup.find_all('p', style=lambda x: x and 'color:#fff' in x):
            text = p.get_text(strip=True)
            if '基金管理人' in text:
                manager = text.replace('基金管理人：', '').replace('基金管理人:', '')
                return manager.strip()
        
        return None
    
    def _extract_nav_info(self, soup: BeautifulSoup) -> Dict[str, Optional[Decimal]]:
        """提取净值信息"""
        nav_info = {
            'net_asset_value': None,
            'total_net_assets': None,
            'total_shares': None,
            'accumulated_nav': None
        }
        
        # 查找包含净值信息的表格
        for table in soup.find_all('table', class_='bb'):
            rows = table.find_all('tr')
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                
                # 查找单位净值
                if any('单位净值' in cell for cell in cells):
                    for i, cell in enumerate(cells):
                        if '单位净值' in cell and i + 1 < len(cells):
                            nav_info['net_asset_value'] = self._parse_decimal(cells[i + 1])
                
                # 查找基金总净资产
                if any('基金总净资产' in cell or '净资产总值' in cell for cell in cells):
                    for i, cell in enumerate(cells):
                        if ('基金总净资产' in cell or '净资产总值' in cell) and i + 1 < len(cells):
                            nav_info['total_net_assets'] = self._parse_decimal(cells[i + 1])
        
        return nav_info
    
    def _extract_asset_allocations(self, soup: BeautifulSoup) -> List[AssetAllocation]:
        """提取资产配置数据"""
        allocations = []
        
        # 查找资产配置相关的表格
        for table in soup.find_all('table', class_='bb'):
            # 检查表格是否包含资产配置信息
            table_text = table.get_text()
            if not any(keyword in table_text for keyword in [
                '资产配置', '投资组合', '股票投资', '债券投资', 
                '基金的资产组合情况', '基金资产组合', '除基础设施资产支持证券之外',
                '固定收益投资', '货币资金', '其他资产'
            ]):
                continue
            
            rows = table.find_all('tr')
            headers = []
            
            # 查找表头
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                if any('资产' in cell or '投资' in cell for cell in cells):
                    headers = cells
                    break
            
            if not headers:
                continue
            
            # 解析数据行
            for row in rows[1:]:  # 跳过表头
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if len(cells) < 2:
                    continue
                
                # 识别资产类型 - 处理不同的表格结构
                asset_type = None
                start_col = 0
                
                # 检查第一列是否为序号（纯数字）
                if cells[0].isdigit() and len(cells) > 2:
                    # 第一列是序号，第二列是资产类型
                    asset_type = cells[1]
                    start_col = 2
                else:
                    # 第一列是资产类型
                    asset_type = cells[0]
                    start_col = 1
                
                if not asset_type or asset_type in ['合计', '总计', '小计']:
                    continue
                
                # 提取市值和比例
                market_value = None
                percentage = None
                
                for cell in cells[start_col:]:
                    if '%' in cell:
                        percentage = self._parse_percentage(cell)
                    elif self._is_numeric(cell):
                        market_value = self._parse_decimal(cell)
                
                if market_value is not None or percentage is not None:
                    allocation = AssetAllocation(
                        asset_type=asset_type,
                        market_value=market_value,
                        percentage=percentage
                    )
                    allocations.append(allocation)
        
        return allocations
    
    def _extract_top_holdings(self, soup: BeautifulSoup) -> List[TopHolding]:
        """提取前十大持仓数据"""
        holdings = []
        
        # 查找持仓相关的表格
        for table in soup.find_all('table', class_='bb'):
            table_text = table.get_text()
            if not any(keyword in table_text for keyword in [
                '前十大', '重仓股', '持仓明细', '股票名称', 
                '债券明细', '基金投资明细', '资产支持证券',
                '买入返售金融资产'
            ]):
                continue
            
            rows = table.find_all('tr')
            
            # 解析数据行
            rank = 1
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if len(cells) < 3:
                    continue
                
                # 跳过表头行
                if any(header in cells[0] for header in ['序号', '排名', '股票代码', '证券代码']):
                    continue
                
                # 尝试解析股票信息
                stock_code = None
                stock_name = None
                market_value = None
                percentage = None
                
                for cell in cells:
                    if re.match(r'^\d{6}$', cell):  # 股票代码
                        stock_code = cell
                    elif '%' in cell:
                        percentage = self._parse_percentage(cell)
                    elif self._is_numeric(cell) and not stock_code:  # 可能是市值
                        market_value = self._parse_decimal(cell)
                    elif not stock_code and len(cell) > 2:  # 可能是股票名称
                        stock_name = cell
                
                if stock_code and stock_name:
                    holding = TopHolding(
                        rank=rank,
                        holding_type='股票',
                        security_code=stock_code,
                        security_name=stock_name,
                        market_value=market_value,
                        percentage=percentage
                    )
                    holdings.append(holding)
                    rank += 1
                    
                    if rank > 10:  # 只取前十大
                        break
        
        return holdings
    
    def _extract_industry_allocations(self, soup: BeautifulSoup) -> List[IndustryAllocation]:
        """提取行业配置数据"""
        allocations = []
        
        # 查找行业配置相关的表格
        for table in soup.find_all('table', class_='bb'):
            table_text = table.get_text()
            if not any(keyword in table_text for keyword in ['行业配置', '行业分布', '行业投资']):
                continue
            
            rows = table.find_all('tr')
            
            # 解析数据行
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if len(cells) < 2:
                    continue
                
                # 跳过表头行
                if any(header in cells[0] for header in ['行业名称', '行业', '序号']):
                    continue
                
                industry_name = cells[0]
                if not industry_name or industry_name in ['合计', '总计']:
                    continue
                
                # 提取市值和比例
                market_value = None
                percentage = None
                
                for cell in cells[1:]:
                    if '%' in cell:
                        percentage = self._parse_percentage(cell)
                    elif self._is_numeric(cell):
                        market_value = self._parse_decimal(cell)
                
                if market_value is not None or percentage is not None:
                    allocation = IndustryAllocation(
                        industry_name=industry_name,
                        market_value=market_value,
                        percentage=percentage
                    )
                    allocations.append(allocation)
        
        return allocations
    
    def _create_fund_report(self, basic_info: Dict[str, Any]) -> FundReport:
        """创建基金报告对象"""
        return FundReport(
            fund_code=basic_info['fund_code'],
            fund_name=basic_info['fund_name'],
            fund_manager=basic_info.get('fund_manager'),
            report_type=basic_info['report_type'],
            report_period_end=basic_info['report_period_end'],
            report_period_start=basic_info['report_period_start'],
            report_year=basic_info['report_period_end'].year,
            report_quarter=self._get_quarter_from_type(basic_info['report_type']),
            net_asset_value=basic_info.get('net_asset_value'),
            total_net_assets=basic_info.get('total_net_assets'),
            total_shares=basic_info.get('total_shares'),
            accumulated_nav=basic_info.get('accumulated_nav'),
            upload_info_id=f"{basic_info['fund_code']}_{basic_info['report_period_end'].strftime('%Y%m%d')}",
            llm_assisted=self.use_llm_assist,  # 设置LLM辅助标志
            parsed_at=datetime.now()
        )
    
    def _get_quarter_from_type(self, report_type: str) -> Optional[int]:
        """从报告类型获取季度"""
        quarter_map = {
            'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4
        }
        return quarter_map.get(report_type)
    
    async def _llm_enhance_data(self, fund_report: FundReport, soup: BeautifulSoup) -> FundReport:
        """使用LLM增强数据质量"""
        try:
            # 验证资产配置数据
            if fund_report.asset_allocations:
                allocation_data = [
                    {
                        'asset_type': a.asset_type,
                        'market_value': float(a.market_value) if a.market_value else None,
                        'percentage': float(a.percentage) if a.percentage else None
                    }
                    for a in fund_report.asset_allocations
                ]
                
                validation_result = await self.llm_assistant.validate_extracted_data(
                    allocation_data, '资产配置数据'
                )
                
                if not validation_result.get('is_valid', True):
                    self.logger.warning("LLM检测到资产配置数据问题", issues=validation_result.get('issues', []))
            
            return fund_report
            
        except Exception as e:
            self.logger.error("LLM数据增强失败", error=str(e))
            return fund_report
    
    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        """解析数值字符串为Decimal"""
        if not value or value in ['-', '--', '']:
            return None
        
        try:
            # 清理数值字符串
            clean_value = re.sub(r'[,，\s]', '', value)
            clean_value = re.sub(r'[^\d.-]', '', clean_value)
            
            if not clean_value:
                return None
            
            return Decimal(clean_value)
        except (InvalidOperation, ValueError):
            return None
    
    def _parse_percentage(self, value: str) -> Optional[Decimal]:
        """解析百分比字符串"""
        if not value or value in ['-', '--', '']:
            return None
        
        try:
            # 移除百分号和其他字符
            clean_value = value.replace('%', '').replace('，', '').replace(',', '').strip()
            clean_value = re.sub(r'[^\d.-]', '', clean_value)
            
            if not clean_value:
                return None
            
            # 转换为小数（除以100）
            return Decimal(clean_value) / 100
        except (InvalidOperation, ValueError):
            return None
    
    def _is_numeric(self, value: str) -> bool:
        """检查字符串是否为数值"""
        if not value:
            return False
        
        clean_value = re.sub(r'[,，\s]', '', value)
        clean_value = re.sub(r'[^\d.-]', '', clean_value)
        
        try:
            float(clean_value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _create_error_result(self, error_message: str) -> ParseResult:
        """创建错误结果"""
        return ParseResult(
            success=False,
            fund_report=None,
            parser_type=self.parser_type,
            errors=[error_message],
            warnings=[],
            metadata={}
        )
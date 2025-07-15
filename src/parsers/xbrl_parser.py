"""重构后的XBRL解析器

使用智能表格解析机制，动态识别表头，避免硬编码列索引。
采用更灵活和鲁棒的解析策略。
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation
from datetime import date
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag
import chardet
from structlog import get_logger


@dataclass
class ParsedFundData:
    """解析后的基金数据结构"""
    # 基本信息
    fund_code: Optional[str] = None
    fund_name: Optional[str] = None
    fund_manager: Optional[str] = None
    
    # 报告信息
    report_type: Optional[str] = None
    report_year: Optional[int] = None
    report_quarter: Optional[int] = None
    report_period_start: Optional[date] = None
    report_period_end: Optional[date] = None
    
    # 净值信息
    net_asset_value: Optional[Decimal] = None
    total_net_assets: Optional[Decimal] = None
    
    # 投资组合数据
    asset_allocations: List[Dict[str, Any]] = field(default_factory=list)
    top_holdings: List[Dict[str, Any]] = field(default_factory=list)
    industry_allocations: List[Dict[str, Any]] = field(default_factory=list)


class SmartTableParser:
    """智能表格解析器"""
    
    def __init__(self):
        # 增强的表头关键词映射
        self.header_mappings = {
            # 资产配置表头
            'asset_type': ['资产类别', '投资类别', '资产类型', '大类资产', '资产', '投资品种', '投资标的'],
            'market_value': ['市值', '公允价值', '金额', '投资金额', '市场价值', '价值', '投资市值', '持仓市值'],
            'percentage': ['占比', '比例', '百分比', '占净值比例', '占基金资产净值比例', '占基金净值比例', '净值占比'],
            
            # 持仓表头
            'security_name': ['证券名称', '股票名称', '证券简称', '名称', '持仓名称', '股票简称', '证券'],
            'security_code': ['证券代码', '股票代码', '代码', '证券代码'],
            'shares': ['持股数量', '数量', '股数', '持有股数', '持仓数量', '持有数量'],
            'rank': ['序号', '排名', '名次', '排序'],
            
            # 行业配置表头
            'industry_name': ['行业名称', '行业', '申万行业', '行业分类', '行业类别', '所属行业'],
            'industry_code': ['行业代码', '代码', '申万代码']
        }
        
        # 表格识别关键词优化
        self.table_keywords = {
            'asset_allocation': {
                'primary': ['资产配置', '投资组合', '资产类别', '大类资产'],
                'secondary': ['股票', '债券', '现金', '银行存款', '其他资产']
            },
            'top_holdings': {
                'primary': ['前十大', '重仓股', '前10大', '主要持仓', '股票投资'],
                'secondary': ['持股', '投资明细', '重仓', '前十名']
            },
            'industry_allocation': {
                'primary': ['行业配置', '行业分布', '行业投资', '申万行业'],
                'secondary': ['行业分类', '行业类别', '按行业']
            }
        }
        
        # 数值解析正则表达式
        self.number_patterns = [
            r'([\d,]+\.\d+)',  # 带小数点的数字
            r'([\d,]+)',       # 整数
            r'([\d.]+)',       # 简单数字
        ]
        
        # 百分比解析正则表达式
        self.percentage_patterns = [
            r'([\d.]+)%',
            r'([\d.]+)％',
            r'([\d.]+)',
        ]
    
    def identify_table_type(self, table: Tag) -> Optional[str]:
        """优化的表格类型识别"""
        table_text = table.get_text().lower()
        
        # 排除明显不相关的表格
        exclude_keywords = ['关联方', '交易', '费用', '审计', '托管', '会计', '声明', '签字', '附注']
        if any(keyword in table_text for keyword in exclude_keywords):
            return None
        
        # 检查表格是否有足够的数据行
        rows = table.find_all('tr')
        if len(rows) < 3:  # 至少需要表头+2行数据
            return None
        
        # 计算匹配分数
        scores = {}
        
        for table_type, keywords in self.table_keywords.items():
            score = 0
            
            # 主要关键词权重更高
            for keyword in keywords['primary']:
                if keyword in table_text:
                    score += 3
            
            # 次要关键词权重较低
            for keyword in keywords['secondary']:
                if keyword in table_text:
                    score += 1
            
            scores[table_type] = score
        
        # 返回得分最高的表格类型（至少需要3分）
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] >= 3:
                return best_type
        
        return None
    
    def parse_table_headers(self, table: Tag) -> Dict[str, int]:
        """增强的动态表头解析"""
        header_mapping = {}
        best_mapping = {}
        best_score = 0
        
        # 查找表头行，扩展检查范围
        header_rows = table.find_all('tr')[:5]  # 检查前5行
        
        for row_idx, row in enumerate(header_rows):
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:  # 至少要有2列才可能是有效表头
                continue
            
            current_mapping = {}
            score = 0
            
            for i, cell in enumerate(cells):
                cell_text = cell.get_text().strip().lower()
                
                # 匹配表头关键词，使用模糊匹配
                for field_name, keywords in self.header_mappings.items():
                    for keyword in keywords:
                        if keyword in cell_text:
                            current_mapping[field_name] = i
                            score += len(keyword)  # 更长的关键词得分更高
                            break
            
            # 记录最佳匹配
            if score > best_score and len(current_mapping) >= 2:
                best_mapping = current_mapping
                best_score = score
        
        return best_mapping
    
    def extract_cell_value(self, cell: Tag, value_type: str = 'text') -> Any:
        """提取单元格值"""
        if not cell:
            return None
        
        text = cell.get_text().strip()
        if not text or text in ['-', '--', '—', 'N/A', 'n/a']:
            return None
        
        if value_type == 'number':
            return self._parse_number(text)
        elif value_type == 'percentage':
            return self._parse_percentage(text)
        else:
            return text
    
    def _parse_number(self, text: str) -> Optional[Decimal]:
        """增强的数字解析"""
        if not text or text.strip() in ['-', '--', '—', 'N/A', 'n/a', '']:
            return None
        
        try:
            # 处理负数
            is_negative = '-' in text or '负' in text
            
            # 清理文本，保留数字、小数点、逗号
            cleaned = re.sub(r'[^\d.,]', '', text)
            
            # 处理单位
            multiplier = Decimal('1')
            if '万' in text:
                multiplier = Decimal('10000')
            elif '亿' in text:
                multiplier = Decimal('100000000')
            elif '千' in text:
                multiplier = Decimal('1000')
            
            # 提取数字，优化正则表达式
            patterns = [
                r'([\d,]+\.\d+)',  # 带小数点的数字
                r'([\d,]+)',       # 整数
                r'([\d.]+)',       # 简单数字
            ]
            
            for pattern in patterns:
                match = re.search(pattern, cleaned)
                if match:
                    number_str = match.group(1).replace(',', '')
                    result = Decimal(number_str) * multiplier
                    return -result if is_negative else result
        
        except (InvalidOperation, ValueError, AttributeError):
            pass
        
        return None
    
    def _parse_percentage(self, text: str) -> Optional[Decimal]:
        """增强的百分比解析"""
        if not text or text.strip() in ['-', '--', '—', 'N/A', 'n/a', '']:
            return None
        
        try:
            # 处理负数
            is_negative = '-' in text or '负' in text
            
            # 移除百分号和空格
            cleaned = text.replace('%', '').replace('％', '').replace(' ', '').replace(',', '')
            
            # 优化的百分比模式
            patterns = [
                r'([\d.]+)',
                r'([\d]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, cleaned)
                if match:
                    result = Decimal(match.group(1))
                    return -result if is_negative else result
        
        except (InvalidOperation, ValueError, AttributeError):
            pass
        
        return None
    
    def parse_asset_allocation_table(self, table: Tag) -> List[Dict[str, Any]]:
        """解析资产配置表"""
        header_mapping = self.parse_table_headers(table)
        if not header_mapping:
            return []
        
        allocations = []
        rows = table.find_all('tr')
        
        # 跳过表头行，从数据行开始
        data_start_idx = self._find_data_start_index(rows)
        
        for row in rows[data_start_idx:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            allocation = {}
            
            # 提取资产类型
            if 'asset_type' in header_mapping and header_mapping['asset_type'] < len(cells):
                asset_type = self.extract_cell_value(cells[header_mapping['asset_type']])
                if asset_type:
                    allocation['asset_type'] = asset_type
                    allocation['asset_name'] = asset_type
            
            # 提取市值
            if 'market_value' in header_mapping and header_mapping['market_value'] < len(cells):
                market_value = self.extract_cell_value(
                    cells[header_mapping['market_value']], 'number'
                )
                if market_value:
                    allocation['market_value'] = market_value
            
            # 提取占比
            if 'percentage' in header_mapping and header_mapping['percentage'] < len(cells):
                percentage = self.extract_cell_value(
                    cells[header_mapping['percentage']], 'percentage'
                )
                if percentage:
                    allocation['percentage'] = percentage
            
            # 只有当至少有资产类型和（市值或占比）时才添加
            if allocation.get('asset_type') and (
                allocation.get('market_value') or allocation.get('percentage')
            ):
                allocations.append(allocation)
        
        # 数据质量验证
        return self._validate_data_quality(allocations, 'asset_allocation')
    
    def parse_top_holdings_table(self, table: Tag) -> List[Dict[str, Any]]:
        """解析前十大持仓表"""
        header_mapping = self.parse_table_headers(table)
        if not header_mapping:
            return []
        
        holdings = []
        rows = table.find_all('tr')
        data_start_idx = self._find_data_start_index(rows)
        
        rank = 1
        for row in rows[data_start_idx:]:
            if rank > 10:  # 只取前10大
                break
            
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            holding = {}
            
            # 提取证券名称
            if 'security_name' in header_mapping and header_mapping['security_name'] < len(cells):
                security_name = self.extract_cell_value(cells[header_mapping['security_name']])
                if security_name:
                    holding['security_name'] = security_name
            
            # 提取证券代码
            if 'security_code' in header_mapping and header_mapping['security_code'] < len(cells):
                security_code = self.extract_cell_value(cells[header_mapping['security_code']])
                if security_code:
                    holding['security_code'] = security_code
            
            # 提取持股数量
            if 'shares' in header_mapping and header_mapping['shares'] < len(cells):
                shares = self.extract_cell_value(cells[header_mapping['shares']], 'number')
                if shares:
                    holding['shares'] = shares
            
            # 提取市值
            if 'market_value' in header_mapping and header_mapping['market_value'] < len(cells):
                market_value = self.extract_cell_value(
                    cells[header_mapping['market_value']], 'number'
                )
                if market_value:
                    holding['market_value'] = market_value
            
            # 提取占比
            if 'percentage' in header_mapping and header_mapping['percentage'] < len(cells):
                percentage = self.extract_cell_value(
                    cells[header_mapping['percentage']], 'percentage'
                )
                if percentage:
                    holding['percentage'] = percentage
            
            # 设置默认值
            holding['holding_type'] = '股票'
            holding['rank'] = rank
            
            # 只有当至少有证券名称时才添加
            if holding.get('security_name'):
                holdings.append(holding)
                rank += 1
        
        # 数据质量验证
        return self._validate_data_quality(holdings, 'top_holdings')
    
    def parse_industry_allocation_table(self, table: Tag) -> List[Dict[str, Any]]:
        """解析行业配置表"""
        header_mapping = self.parse_table_headers(table)
        if not header_mapping:
            return []
        
        allocations = []
        rows = table.find_all('tr')
        data_start_idx = self._find_data_start_index(rows)
        
        for row in rows[data_start_idx:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            allocation = {}
            
            # 提取行业名称
            if 'industry_name' in header_mapping and header_mapping['industry_name'] < len(cells):
                industry_name = self.extract_cell_value(cells[header_mapping['industry_name']])
                if industry_name:
                    allocation['industry_name'] = industry_name
            
            # 提取行业代码
            if 'industry_code' in header_mapping and header_mapping['industry_code'] < len(cells):
                industry_code = self.extract_cell_value(cells[header_mapping['industry_code']])
                if industry_code:
                    allocation['industry_code'] = industry_code
            
            # 提取市值
            if 'market_value' in header_mapping and header_mapping['market_value'] < len(cells):
                market_value = self.extract_cell_value(
                    cells[header_mapping['market_value']], 'number'
                )
                if market_value:
                    allocation['market_value'] = market_value
            
            # 提取占比
            if 'percentage' in header_mapping and header_mapping['percentage'] < len(cells):
                percentage = self.extract_cell_value(
                    cells[header_mapping['percentage']], 'percentage'
                )
                if percentage:
                    allocation['percentage'] = percentage
            
            # 设置默认值
            allocation['industry_level'] = 1
            allocation['rank'] = None
            
            # 只有当至少有行业名称时才添加
            if allocation.get('industry_name'):
                allocations.append(allocation)
        
        # 数据质量验证
        return self._validate_data_quality(allocations, 'industry_allocation')
    
    def _find_data_start_index(self, rows: List[Tag]) -> int:
        """智能找到数据行的开始索引"""
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            row_text = row.get_text().strip()
            
            # 跳过明显的表头行
            if any(keyword in row_text.lower() for keyword in 
                   ['序号', '名称', '代码', '数量', '金额', '比例', '类别', '行业']):
                continue
            
            # 检查是否包含数字数据
            if re.search(r'[\d.]+%|[\d,]+\.\d+|[\d,]+', row_text):
                return i
        
        return 1  # 默认跳过第一行
    
    def _validate_data_quality(self, data_list: List[Dict[str, Any]], data_type: str) -> List[Dict[str, Any]]:
        """数据质量验证和清理"""
        if not data_list:
            return data_list
        
        validated_data = []
        
        for item in data_list:
            # 基本验证
            if not item:
                continue
            
            # 根据数据类型进行特定验证
            if data_type == 'asset_allocation':
                asset_type = item.get('asset_type', '')
                if not asset_type:
                    continue
                
                # 排除明显不相关的资产类型
                exclude_types = ['关联方', '交易对手', '审计费', '托管费', '管理费', '销售费']
                if any(exclude in asset_type for exclude in exclude_types):
                    continue
                
                # 验证百分比合理性
                if item.get('percentage') and item['percentage'] > 100:
                    continue
            
            elif data_type == 'top_holdings':
                security_name = item.get('security_name', '')
                if not security_name:
                    continue
                
                # 排除明显不相关的证券名称
                exclude_names = ['合计', '小计', '总计', '其他', '现金', '银行存款']
                if any(exclude in security_name for exclude in exclude_names):
                    continue
                
                # 验证持股数量为正数
                if item.get('shares') and item['shares'] <= 0:
                    continue
            
            elif data_type == 'industry_allocation':
                industry_name = item.get('industry_name', '')
                if not industry_name:
                    continue
                
                # 排除明显不相关的行业名称
                exclude_industries = ['合计', '小计', '总计', '其他']
                if any(exclude in industry_name for exclude in exclude_industries):
                    continue
            
            validated_data.append(item)
        
        return validated_data


class XBRLParser:
    """重构后的XBRL解析器"""
    
    def __init__(self):
        self.logger = get_logger("xbrl_parser_refactored")
        self.table_parser = SmartTableParser()
        
        # 基本信息提取模式
        self.patterns = {
            'fund_code': [
                r'基金代码[：:]*\s*([A-Za-z0-9]{6})',
                r'代码[：:]*\s*([A-Za-z0-9]{6})',
                r'([A-Za-z0-9]{6})\s*基金',
            ],
            'fund_name': [
                r'基金名称[：:]*\s*([^\n\r]{2,50}?)(?=\s|$)',
                r'基金简称[：:]*\s*([^\n\r]{2,50}?)(?=\s|$)',
                r'([^\n\r]{2,50}?)(?:基金|Fund)',
            ],
            'fund_manager': [
                r'基金管理人[：:]*\s*([^\n\r]{2,50}?)(?=\s|$)',
                r'管理人[：:]*\s*([^\n\r]{2,50}?)(?=\s|$)',
            ],
            'report_period': [
                r'报告期间[：:]*\s*(\d{4}年\d{1,2}月\d{1,2}日)\s*至\s*(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}-\d{1,2}-\d{1,2})\s*至\s*(\d{4}-\d{1,2}-\d{1,2})',
            ],
            'net_asset_value': [
                r'基金份额净值[：:]*\s*([\d.]+)',
                r'单位净值[：:]*\s*([\d.]+)',
                r'净值[：:]*\s*([\d.]+)',
            ],
            'total_net_assets': [
                r'基金资产净值[：:]*\s*([\d,]+\.?\d*)',
                r'净资产[：:]*\s*([\d,]+\.?\d*)',
                r'总净资产[：:]*\s*([\d,]+\.?\d*)',
            ]
        }
    
    def parse_file(self, file_path: Path) -> Optional[ParsedFundData]:
        """解析XBRL文件"""
        bound_logger = self.logger.bind(file_path=str(file_path))
        
        try:
            # 读取文件
            content = self._read_file_with_encoding(file_path)
            if not content:
                bound_logger.warning("xbrl_parser.file_empty")
                return None
            
            # 解析HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # 创建数据对象
            fund_data = ParsedFundData()
            
            # 解析各个部分
            self._parse_basic_info(soup, fund_data, bound_logger)
            self._parse_report_period(soup, fund_data, bound_logger)
            self._parse_nav_info(soup, fund_data, bound_logger)
            self._parse_investment_data(soup, fund_data, bound_logger)
            
            bound_logger.info(
                "xbrl_parser.parse_complete",
                fund_code=fund_data.fund_code,
                fund_name=fund_data.fund_name[:30] if fund_data.fund_name else None,
                asset_allocations_count=len(fund_data.asset_allocations),
                top_holdings_count=len(fund_data.top_holdings),
                industry_allocations_count=len(fund_data.industry_allocations)
            )
            
            return fund_data
            
        except Exception as e:
            bound_logger.error("xbrl_parser.parse_error", error=str(e))
            return None
    
    def _read_file_with_encoding(self, file_path: Path) -> Optional[str]:
        """自动检测编码并读取文件"""
        if not file_path.exists():
            return None
        
        try:
            # 读取文件的一部分来检测编码
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # 读取前10KB
            
            # 检测编码
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            
            # 读取完整文件
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            self.logger.warning("xbrl_parser.file_read_error", file_path=str(file_path), error=str(e))
            return None
    
    def _parse_basic_info(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析基本信息"""
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
        
        # 提取基金管理人
        fund_manager = self._extract_by_patterns(text_content, self.patterns['fund_manager'])
        if fund_manager:
            fund_data.fund_manager = fund_manager.strip()
            bound_logger.info("xbrl_parser.basic_info.fund_manager", manager=fund_manager[:50])
    
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
    
    def _parse_investment_data(self, soup: BeautifulSoup, fund_data: ParsedFundData, bound_logger):
        """解析投资组合数据"""
        tables = soup.find_all('table')
        
        for table in tables:
            table_type = self.table_parser.identify_table_type(table)
            
            if table_type == 'asset_allocation':
                allocations = self.table_parser.parse_asset_allocation_table(table)
                fund_data.asset_allocations.extend(allocations)
                bound_logger.info(
                    "xbrl_parser.asset_allocation.parsed",
                    count=len(allocations)
                )
            
            elif table_type == 'top_holdings':
                holdings = self.table_parser.parse_top_holdings_table(table)
                fund_data.top_holdings.extend(holdings)
                bound_logger.info(
                    "xbrl_parser.top_holdings.parsed",
                    count=len(holdings)
                )
            
            elif table_type == 'industry_allocation':
                allocations = self.table_parser.parse_industry_allocation_table(table)
                fund_data.industry_allocations.extend(allocations)
                bound_logger.info(
                    "xbrl_parser.industry_allocation.parsed",
                    count=len(allocations)
                )
    
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
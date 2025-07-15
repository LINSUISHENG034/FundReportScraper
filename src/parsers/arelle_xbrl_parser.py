"""
基于Arelle库的XBRL原生解析器
Arelle-based native XBRL parser
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from decimal import Decimal, InvalidOperation

try:
    from arelle import Cntlr, ModelManager, FileSource
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelInstanceObject import ModelFact
    ARELLE_AVAILABLE = True
except ImportError:
    ARELLE_AVAILABLE = False
    # 创建占位符类以避免导入错误
    class Cntlr:
        class Cntlr:
            pass
    class ModelXbrl:
        pass
    class ModelFact:
        pass

from src.core.logging import get_logger
from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
from src.parsers.base_parser import BaseParser, ParseResult, ParserType


class ArelleXBRLParser(BaseParser):
    """基于Arelle库的XBRL解析器"""
    
    def __init__(self):
        super().__init__(ParserType.XBRL_NATIVE)
        
        if not ARELLE_AVAILABLE:
            self.logger.error("Arelle库未安装，XBRL解析器不可用")
            self._available = False
            return
        
        self._available = True
        
        # 初始化Arelle控制器
        try:
            self.cntlr = Cntlr.Cntlr(logFileName=None)
            self.model_manager = ModelManager.initialize(self.cntlr)
            self.logger.info("Arelle XBRL解析器初始化成功")
        except Exception as e:
            self.logger.error("Arelle初始化失败", error=str(e))
            self._available = False
        
        # XBRL概念到基金报告字段的映射
        self.concept_mappings = {
            # 基本信息映射
            "fund_code": [
                "FundCode", "基金代码", "基金主代码", "fund:FundCode",
                "基金简称代码", "ProductCode"
            ],
            "fund_name": [
                "FundName", "基金名称", "基金全称", "fund:FundName",
                "ProductName", "基金简称"
            ],
            "net_asset_value": [
                "NetAssetValue", "NetAssetValuePerShare", "份额净值",
                "基金份额净值", "单位净值", "fund:NetAssetValue",
                "NAV", "UnitNetAssetValue"
            ],
            "total_net_assets": [
                "TotalNetAssets", "NetAssets", "基金资产净值",
                "资产净值", "fund:TotalNetAssets", "TotalAssets"
            ]
        }
        
        # 表格相关概念映射
        self.table_concept_mappings = {
            "asset_allocation": [
                "AssetAllocation", "InvestmentPortfolio", "资产配置",
                "投资组合", "大类资产配置"
            ],
            "top_holdings": [
                "TopHoldings", "MajorHoldings", "前十大持仓",
                "重仓股", "主要持仓"
            ],
            "industry_allocation": [
                "IndustryAllocation", "SectorAllocation", "行业配置",
                "行业分布", "申万行业"
            ]
        }
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """检查是否能够解析给定的内容"""
        if not self._available:
            return False
        
        # 检查XBRL特征
        xbrl_indicators = [
            r'<xbrl[^>]*xmlns',
            r'<xbrli:xbrl',
            r'xmlns:xbrli=',
            r'http://www\.xbrl\.org/2003/instance',
            r'<context[^>]*id=',
            r'<unit[^>]*id='
        ]
        
        content_lower = content.lower()
        matches = sum(1 for pattern in xbrl_indicators 
                     if re.search(pattern, content_lower))
        
        # 至少匹配3个XBRL特征
        return matches >= 3
    
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """解析XBRL内容"""
        if not self._available:
            return self._create_error_result("Arelle库不可用")
        
        try:
            # 创建临时文件用于Arelle解析
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xbrl', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                # 使用Arelle加载XBRL文档
                file_source = FileSource.FileSource(temp_file_path)
                model_xbrl = self.model_manager.load(file_source)
                
                if not model_xbrl or model_xbrl.modelDocument is None:
                    return self._create_error_result("无法加载XBRL文档")
                
                # 提取基金报告数据
                fund_report = self._extract_fund_report(model_xbrl)
                
                if fund_report:
                    return self._create_success_result(fund_report, file_path)
                else:
                    return self._create_error_result("无法从XBRL文档中提取基金数据")
                    
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                
                # 关闭模型
                if 'model_xbrl' in locals() and model_xbrl:
                    model_xbrl.close()
                    
        except Exception as e:
            self.logger.error("XBRL解析异常", error=str(e))
            return self._create_error_result(f"XBRL解析异常: {str(e)}")
    
    def _extract_fund_report(self, model_xbrl: ModelXbrl) -> Optional[FundReport]:
        """从XBRL模型中提取基金报告数据"""
        try:
            fund_report = FundReport()
            
            # 提取基本信息
            self._extract_basic_info(model_xbrl, fund_report)
            
            # 提取表格数据
            self._extract_table_data(model_xbrl, fund_report)
            
            return fund_report
            
        except Exception as e:
            self.logger.error("基金报告数据提取失败", error=str(e))
            return None
    
    def _extract_basic_info(self, model_xbrl: ModelXbrl, fund_report: FundReport):
        """提取基本信息"""
        facts = model_xbrl.facts
        
        for fact in facts:
            if not isinstance(fact, ModelFact):
                continue
            
            concept_name = fact.concept.name if fact.concept else ""
            fact_value = fact.value if hasattr(fact, 'value') else str(fact)
            
            # 匹配基金代码
            if not fund_report.fund_code:
                for pattern in self.concept_mappings["fund_code"]:
                    if pattern.lower() in concept_name.lower():
                        fund_report.fund_code = self._clean_text_value(fact_value)
                        break
            
            # 匹配基金名称
            if not fund_report.fund_name:
                for pattern in self.concept_mappings["fund_name"]:
                    if pattern.lower() in concept_name.lower():
                        fund_report.fund_name = self._clean_text_value(fact_value)
                        break
            
            # 匹配净值
            if not fund_report.net_asset_value:
                for pattern in self.concept_mappings["net_asset_value"]:
                    if pattern.lower() in concept_name.lower():
                        decimal_value = self._parse_decimal_value(fact_value)
                        if decimal_value:
                            fund_report.net_asset_value = decimal_value
                        break
            
            # 匹配总资产净值
            if not fund_report.total_net_assets:
                for pattern in self.concept_mappings["total_net_assets"]:
                    if pattern.lower() in concept_name.lower():
                        decimal_value = self._parse_decimal_value(fact_value)
                        if decimal_value:
                            fund_report.total_net_assets = decimal_value
                        break
        
        self.logger.debug("基本信息提取完成",
                         fund_code=fund_report.fund_code,
                         fund_name=fund_report.fund_name,
                         nav=str(fund_report.net_asset_value) if fund_report.net_asset_value else None)
    
    def _extract_table_data(self, model_xbrl: ModelXbrl, fund_report: FundReport):
        """提取表格数据"""
        try:
            # 提取资产配置数据
            fund_report.asset_allocations = self._extract_asset_allocations(model_xbrl)
            
            # 提取前十大持仓数据
            fund_report.top_holdings = self._extract_top_holdings(model_xbrl)
            
            # 提取行业配置数据
            fund_report.industry_allocations = self._extract_industry_allocations(model_xbrl)
            
            self.logger.debug("表格数据提取完成",
                             asset_allocations=len(fund_report.asset_allocations or []),
                             top_holdings=len(fund_report.top_holdings or []),
                             industry_allocations=len(fund_report.industry_allocations or []))
            
        except Exception as e:
            self.logger.warning("表格数据提取失败", error=str(e))
    
    def _extract_asset_allocations(self, model_xbrl: ModelXbrl) -> List[AssetAllocation]:
        """提取资产配置数据"""
        allocations = []
        
        try:
            # 查找资产配置相关的事实
            for fact in model_xbrl.facts:
                if not isinstance(fact, ModelFact):
                    continue
                
                concept_name = fact.concept.name if fact.concept else ""
                
                # 检查是否为资产配置相关概念
                is_asset_concept = any(pattern.lower() in concept_name.lower() 
                                     for pattern in self.table_concept_mappings["asset_allocation"])
                
                if is_asset_concept:
                    # 尝试提取资产类型和数值
                    asset_type = self._extract_asset_type_from_concept(concept_name)
                    if asset_type:
                        market_value = self._parse_decimal_value(fact.value if hasattr(fact, 'value') else str(fact))
                        
                        allocation = AssetAllocation(
                            asset_type=asset_type,
                            asset_name=asset_type,
                            market_value=market_value,
                            percentage=None  # 百分比需要单独计算或查找
                        )
                        allocations.append(allocation)
            
        except Exception as e:
            self.logger.warning("资产配置数据提取失败", error=str(e))
        
        return allocations
    
    def _extract_top_holdings(self, model_xbrl: ModelXbrl) -> List[TopHolding]:
        """提取前十大持仓数据"""
        holdings = []
        
        try:
            # 查找持仓相关的事实
            for fact in model_xbrl.facts:
                if not isinstance(fact, ModelFact):
                    continue
                
                concept_name = fact.concept.name if fact.concept else ""
                
                # 检查是否为持仓相关概念
                is_holding_concept = any(pattern.lower() in concept_name.lower() 
                                       for pattern in self.table_concept_mappings["top_holdings"])
                
                if is_holding_concept:
                    # 尝试提取证券信息
                    security_name = self._extract_security_name_from_concept(concept_name)
                    if security_name:
                        market_value = self._parse_decimal_value(fact.value if hasattr(fact, 'value') else str(fact))
                        
                        holding = TopHolding(
                            holding_type="股票",
                            security_code=None,  # 需要从其他地方获取
                            security_name=security_name,
                            shares=None,
                            market_value=market_value,
                            percentage=None,
                            rank=len(holdings) + 1
                        )
                        holdings.append(holding)
                        
                        # 限制为前10大
                        if len(holdings) >= 10:
                            break
            
        except Exception as e:
            self.logger.warning("持仓数据提取失败", error=str(e))
        
        return holdings
    
    def _extract_industry_allocations(self, model_xbrl: ModelXbrl) -> List[IndustryAllocation]:
        """提取行业配置数据"""
        allocations = []
        
        try:
            # 查找行业配置相关的事实
            for fact in model_xbrl.facts:
                if not isinstance(fact, ModelFact):
                    continue
                
                concept_name = fact.concept.name if fact.concept else ""
                
                # 检查是否为行业配置相关概念
                is_industry_concept = any(pattern.lower() in concept_name.lower() 
                                        for pattern in self.table_concept_mappings["industry_allocation"])
                
                if is_industry_concept:
                    # 尝试提取行业名称
                    industry_name = self._extract_industry_name_from_concept(concept_name)
                    if industry_name:
                        market_value = self._parse_decimal_value(fact.value if hasattr(fact, 'value') else str(fact))
                        
                        allocation = IndustryAllocation(
                            industry_name=industry_name,
                            market_value=market_value,
                            percentage=None
                        )
                        allocations.append(allocation)
            
        except Exception as e:
            self.logger.warning("行业配置数据提取失败", error=str(e))
        
        return allocations
    
    def _clean_text_value(self, value: Any) -> Optional[str]:
        """清理文本值"""
        if value is None:
            return None
        
        text = str(value).strip()
        return text if text else None
    
    def _parse_decimal_value(self, value: Any) -> Optional[Decimal]:
        """解析数值"""
        if value is None:
            return None
        
        try:
            # 清理数值字符串
            value_str = str(value).strip()
            if not value_str or value_str in ["-", "--", "—", "N/A", "n/a"]:
                return None
            
            # 移除非数字字符（保留小数点和负号）
            cleaned = re.sub(r"[^\d.,-]", "", value_str)
            if not cleaned:
                return None
            
            # 处理逗号分隔符
            cleaned = cleaned.replace(",", "")
            
            return Decimal(cleaned)
            
        except (InvalidOperation, ValueError):
            return None
    
    def _extract_asset_type_from_concept(self, concept_name: str) -> Optional[str]:
        """从概念名称中提取资产类型"""
        # 常见资产类型映射
        asset_type_patterns = {
            "股票": ["stock", "equity", "股票"],
            "债券": ["bond", "债券", "固定收益"],
            "现金": ["cash", "现金", "银行存款"],
            "基金": ["fund", "基金", "投资基金"],
            "其他": ["other", "其他", "其它"]
        }
        
        concept_lower = concept_name.lower()
        for asset_type, patterns in asset_type_patterns.items():
            if any(pattern in concept_lower for pattern in patterns):
                return asset_type
        
        return None
    
    def _extract_security_name_from_concept(self, concept_name: str) -> Optional[str]:
        """从概念名称中提取证券名称"""
        # 这里需要更复杂的逻辑来提取证券名称
        # 暂时返回概念名称的简化版本
        if "holding" in concept_name.lower() or "持仓" in concept_name:
            # 尝试提取实际的证券名称
            parts = concept_name.split("_")
            if len(parts) > 1:
                return parts[-1]
        
        return None
    
    def _extract_industry_name_from_concept(self, concept_name: str) -> Optional[str]:
        """从概念名称中提取行业名称"""
        # 常见行业名称模式
        industry_patterns = [
            "制造业", "金融业", "信息技术", "医疗保健", "消费", "能源",
            "材料", "工业", "公用事业", "房地产", "通信"
        ]
        
        concept_lower = concept_name.lower()
        for industry in industry_patterns:
            if industry in concept_lower:
                return industry
        
        return None
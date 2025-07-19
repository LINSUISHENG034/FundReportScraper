"""基于Arelle命令行的XBRL解析器
Arelle Command-line based XBRL Parser

根据PHASE_8重构计划，这是一个全新的基于Arelle命令行工具的解析器实现。
由于Arelle库与Python 3.13存在兼容性问题，我们采用subprocess调用方式。
"""

import json
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

from src.core.logging import get_logger
from src.models.enhanced_fund_data import (
    ComprehensiveFundReport, BasicFundInfo, FinancialMetrics, 
    ReportMetadata, AssetAllocationData, HoldingData, IndustryAllocationData,
    ReportType, AssetType, ValidationStatus
)
from src.parsers.base_parser import BaseParser, ParseResult, ParserType


class ArelleParser(BaseParser):
    """基于Arelle命令行的XBRL解析器
    
    这是按照PHASE_8重构计划创建的新一代解析器，专门处理纯净的XBRL文件。
    使用subprocess调用Arelle命令行工具来解析XBRL，然后将结果映射到我们的数据模型。
    """
    
    def __init__(self):
        super().__init__(ParserType.XBRL_NATIVE)
        self.logger = get_logger("parser.arelle_cmdline")
        
        # XBRL概念到基金报告字段的映射规则
        self.concept_mappings = {
            "fund_code": [
                "FundCode", "基金代码", "基金主代码", "fund:FundCode",
                "基金简称代码", "ProductCode", "dei:EntityRegistrantName"
            ],
            "fund_name": [
                "FundName", "基金名称", "基金全称", "fund:FundName",
                "ProductName", "基金简称", "dei:DocumentPeriodEndDate"
            ],
            "net_asset_value": [
                "NetAssetValue", "NetAssetValuePerShare", "份额净值",
                "基金份额净值", "单位净值", "fund:NetAssetValue",
                "NAV", "UnitNetAssetValue", "csrc-mf-general:NetAssetValuePerShare"
            ],
            "total_net_assets": [
                "TotalNetAssets", "NetAssets", "基金资产净值",
                "资产净值", "fund:TotalNetAssets", "TotalAssets",
                "csrc-mf-general:TotalNetAssets"
            ],
            "total_shares": [
                "TotalShares", "基金总份额", "fund:TotalShares",
                "csrc-mf-general:TotalShares"
            ]
        }
        
        # 检查Arelle命令行工具是否可用
        self._arelle_available = self._check_arelle_availability()
        
    def _check_arelle_availability(self) -> bool:
        """检查Arelle命令行工具是否可用"""
        try:
            # 尝试多种可能的Arelle命令行调用方式
            commands_to_try = [
                ["arelleCmdLine", "--version"],
                ["python", "-m", "arelle.CntlrCmdLine", "--version"],
                ["poetry", "run", "python", "-m", "arelle.CntlrCmdLine", "--version"]
            ]
            
            for cmd in commands_to_try:
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    if result.returncode == 0:
                        self.logger.info(f"Arelle命令行工具可用: {' '.join(cmd)}")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
                    
            self.logger.warning("Arelle命令行工具不可用，将使用备用解析方案")
            return False
            
        except Exception as e:
            self.logger.error(f"检查Arelle可用性时出错: {str(e)}")
            return False
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """检查是否能够解析给定的内容
        
        Args:
            content: 文件内容
            file_path: 文件路径（可选）
            
        Returns:
            bool: 是否能够解析
        """
        # 简单返回True，因为我们假设传递给此解析器的都是预判过的纯XBRL文件
        return True
    
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """解析内容并返回解析结果
        
        Args:
            content: 文件内容
            file_path: 文件路径（可选）
            
        Returns:
            ParseResult: 解析结果
        """
        try:
            # 如果Arelle不可用，返回错误结果
            if not self._arelle_available:
                return self._create_error_result(
                    "Arelle命令行工具不可用，无法解析XBRL文件"
                )
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.xbrl', 
                delete=False, 
                encoding='utf-8'
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                # 调用Arelle命令行工具
                facts_json = self._run_arelle_command(temp_file_path)
                
                if not facts_json:
                    return self._create_error_result(
                        "Arelle命令行工具未返回有效的事实数据"
                    )
                
                # 将JSON事实映射到基金报告模型
                fund_report = self._map_facts_to_report(facts_json)
                
                if fund_report:
                    return self._create_success_result(fund_report, file_path)
                else:
                    return self._create_error_result(
                        "无法从XBRL事实中提取有效的基金报告数据"
                    )
                    
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                    
        except Exception as e:
            self.logger.error(f"XBRL解析异常: {str(e)}")
            return self._create_error_result(f"XBRL解析异常: {str(e)}")
    
    def _run_arelle_command(self, file_path: str) -> Optional[str]:
        """执行Arelle命令行工具
        
        Args:
            file_path: XBRL文件路径
            
        Returns:
            Optional[str]: 事实列表的JSON字符串，如果失败则返回None
        """
        try:
            # 创建临时日志文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.log', 
                delete=False
            ) as log_file:
                log_file_path = log_file.name
            
            try:
                # 构建Arelle命令
                cmd = [
                    "poetry", "run", "python", "-c",
                    f"""
import sys
sys.path.insert(0, '.')
try:
    from arelle import Cntlr, ModelManager, FileSource
    from arelle.ModelXbrl import ModelXbrl
    import json
    
    # 初始化Arelle控制器
    cntlr = Cntlr.Cntlr(logFileName='{log_file_path}')
    model_manager = ModelManager.initialize(cntlr)
    
    # 加载XBRL文档
    file_source = FileSource.FileSource('{file_path}')
    model_xbrl = model_manager.load(file_source)
    
    if model_xbrl and model_xbrl.modelDocument:
        facts = []
        for fact in model_xbrl.facts:
            fact_data = {{
                'concept': fact.concept.name if fact.concept else '',
                'value': str(fact.value) if hasattr(fact, 'value') else str(fact),
                'context': fact.contextID if hasattr(fact, 'contextID') else '',
                'unit': fact.unitID if hasattr(fact, 'unitID') else ''
            }}
            facts.append(fact_data)
        
        print(json.dumps(facts, ensure_ascii=False, indent=2))
    else:
        print('{{"error": "无法加载XBRL文档"}}')    
except Exception as e:
    print(f'{{"error": "解析异常: {{str(e)}}"}}')    
"""
                ]
                
                # 执行命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60  # 60秒超时
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                else:
                    self.logger.error(
                        f"Arelle命令执行失败: {result.stderr}"
                    )
                    return None
                    
            finally:
                # 清理日志文件
                try:
                    os.unlink(log_file_path)
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            self.logger.error("Arelle命令执行超时")
            return None
        except Exception as e:
            self.logger.error(f"执行Arelle命令时出错: {str(e)}")
            return None
    
    def _map_facts_to_report(self, facts_json: str) -> Optional[ComprehensiveFundReport]:
        """将Arelle输出的JSON事实列表映射到基金报告模型
        
        Args:
            facts_json: 事实列表的JSON字符串
            
        Returns:
            Optional[ComprehensiveFundReport]: 基金报告模型实例
        """
        try:
            facts_data = json.loads(facts_json)
            
            if isinstance(facts_data, dict) and 'error' in facts_data:
                self.logger.error(f"Arelle解析错误: {facts_data['error']}")
                return None
            
            if not isinstance(facts_data, list):
                self.logger.error("无效的事实数据格式")
                return None
            
            # 初始化数据容器
            basic_info_data = {}
            financial_data = {}
            metadata_data = {
                'report_type': ReportType.QUARTERLY,  # 默认值
                'report_period_start': date.today(),
                'report_period_end': date.today(),
                'report_year': date.today().year,
                'upload_info_id': f"arelle_parsed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'parsing_method': 'arelle_cmdline',
                'parsing_confidence': 0.8,
                'llm_assisted': False
            }
            
            # 遍历事实并映射到相应字段
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                value = fact.get('value', '')
                
                if not concept or not value:
                    continue
                
                # 映射基本信息
                self._map_basic_info(concept, value, basic_info_data)
                
                # 映射财务指标
                self._map_financial_metrics(concept, value, financial_data)
            
            # 构建基金报告模型
            try:
                basic_info = BasicFundInfo(
                    fund_code=basic_info_data.get('fund_code', '000000'),
                    fund_name=basic_info_data.get('fund_name', '未知基金'),
                    fund_manager=basic_info_data.get('fund_manager')
                )
                
                financial_metrics = FinancialMetrics(
                    net_asset_value=financial_data.get('net_asset_value'),
                    total_net_assets=financial_data.get('total_net_assets'),
                    total_shares=financial_data.get('total_shares')
                )
                
                report_metadata = ReportMetadata(**metadata_data)
                
                fund_report = ComprehensiveFundReport(
                    basic_info=basic_info,
                    financial_metrics=financial_metrics,
                    report_metadata=report_metadata,
                    parsed_at=datetime.now()
                )
                
                return fund_report
                
            except Exception as e:
                self.logger.error(f"构建基金报告模型时出错: {str(e)}")
                return None
                
        except json.JSONDecodeError as e:
            self.logger.error(f"解析JSON事实数据时出错: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"映射事实到报告时出错: {str(e)}")
            return None
    
    def _map_basic_info(self, concept: str, value: str, data_dict: Dict[str, Any]):
        """映射基本信息字段"""
        concept_lower = concept.lower()
        
        # 映射基金代码
        if not data_dict.get('fund_code'):
            for pattern in self.concept_mappings['fund_code']:
                if pattern.lower() in concept_lower:
                    cleaned_value = self._clean_text_value(value)
                    if cleaned_value and cleaned_value.isdigit():
                        data_dict['fund_code'] = cleaned_value
                        break
        
        # 映射基金名称
        if not data_dict.get('fund_name'):
            for pattern in self.concept_mappings['fund_name']:
                if pattern.lower() in concept_lower:
                    cleaned_value = self._clean_text_value(value)
                    if cleaned_value and len(cleaned_value) > 2:
                        data_dict['fund_name'] = cleaned_value
                        break
    
    def _map_financial_metrics(self, concept: str, value: str, data_dict: Dict[str, Any]):
        """映射财务指标字段"""
        concept_lower = concept.lower()
        
        # 映射净值
        if not data_dict.get('net_asset_value'):
            for pattern in self.concept_mappings['net_asset_value']:
                if pattern.lower() in concept_lower:
                    decimal_value = self._parse_decimal(value)
                    if decimal_value and decimal_value > 0:
                        data_dict['net_asset_value'] = decimal_value
                        break
        
        # 映射总净资产
        if not data_dict.get('total_net_assets'):
            for pattern in self.concept_mappings['total_net_assets']:
                if pattern.lower() in concept_lower:
                    decimal_value = self._parse_decimal(value)
                    if decimal_value and decimal_value > 0:
                        data_dict['total_net_assets'] = decimal_value
                        break
        
        # 映射总份额
        if not data_dict.get('total_shares'):
            for pattern in self.concept_mappings['total_shares']:
                if pattern.lower() in concept_lower:
                    decimal_value = self._parse_decimal(value)
                    if decimal_value and decimal_value > 0:
                        data_dict['total_shares'] = decimal_value
                        break
    
    def _clean_text_value(self, value: str) -> str:
        """清理文本值"""
        if not value:
            return ""
        return str(value).strip()
    
    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        """解析十进制数值"""
        if not value:
            return None
        
        try:
            # 移除常见的非数字字符
            cleaned = str(value).replace(',', '').replace('，', '').strip()
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
    
    def _create_success_result(
        self, 
        fund_report: ComprehensiveFundReport, 
        file_path: Optional[Path]
    ) -> ParseResult:
        """创建成功的解析结果"""
        # 将ComprehensiveFundReport转换为旧的FundReport格式以兼容现有接口
        from src.models.fund_data import FundReport
        
        legacy_report = FundReport()
        legacy_report.fund_code = fund_report.basic_info.fund_code
        legacy_report.fund_name = fund_report.basic_info.fund_name
        legacy_report.fund_manager = fund_report.basic_info.fund_manager
        legacy_report.net_asset_value = fund_report.financial_metrics.net_asset_value
        legacy_report.total_net_assets = fund_report.financial_metrics.total_net_assets
        legacy_report.total_shares = fund_report.financial_metrics.total_shares
        legacy_report.upload_info_id = fund_report.report_metadata.upload_info_id
        legacy_report.parsing_method = fund_report.report_metadata.parsing_method
        legacy_report.parsing_confidence = fund_report.report_metadata.parsing_confidence
        
        return ParseResult(
            success=True,
            fund_report=legacy_report,
            parser_type=self.parser_type,
            errors=[],
            warnings=[],
            metadata={
                "file_path": str(file_path) if file_path else None,
                "parsing_method": "arelle_cmdline",
                "comprehensive_report": fund_report
            }
        )
    
    def _create_error_result(self, error_message: str) -> ParseResult:
        """创建错误的解析结果"""
        return ParseResult(
            success=False,
            fund_report=None,
            parser_type=self.parser_type,
            errors=[error_message],
            warnings=[],
            metadata={}
        )
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
from src.core.fund_search_parameters import ReportType
from src.models.enhanced_fund_data import (
    ComprehensiveFundReport, BasicFundInfo, FinancialMetrics, 
    ReportMetadata, AssetAllocationData, HoldingData,
    IndustryAllocationData, AssetType
)
from src.parsers.base_parser import BaseParser, ParseResult, ParserType
from src.parsers.data_quality import AssetAllocationCalculator


class ArelleParser(BaseParser):
    """基于Arelle命令行的XBRL解析器
    
    这是按照PHASE_8重构计划创建的新一代解析器，专门处理纯净的XBRL文件。
    使用subprocess调用Arelle命令行工具来解析XBRL，然后将结果映射到我们的数据模型。
    """
    
    def __init__(self):
        super().__init__(ParserType.XBRL_NATIVE)
        self.logger = get_logger("parser.arelle_cmdline")
        self.asset_calculator = AssetAllocationCalculator()
        
        # 动态加载的分类标准映射（在解析时根据XBRL文件内容确定）
        self.current_taxonomy = None
        self.concept_mappings = {}
        
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
            
            # 动态加载分类标准映射
            taxonomy_config = self._load_taxonomy_mapping(content)
            self.current_taxonomy = taxonomy_config.get('taxonomy_info', {})
            self.concept_mappings = taxonomy_config.get('concept_mappings', {})
            
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
    
    def _load_taxonomy_mapping(self, xbrl_content: str) -> Dict[str, Any]:
        """动态加载XBRL分类标准映射
        
        Args:
            xbrl_content: XBRL文件内容
            
        Returns:
            Dict[str, Any]: 分类标准映射配置
        """
        try:
            # 提取schemaRef信息
            schema_ref = self._extract_schema_ref(xbrl_content)
            
            # 根据schemaRef确定分类标准
            taxonomy_file = self._determine_taxonomy_file(schema_ref)
            
            # 加载映射文件
            config_path = Path(__file__).parent.parent.parent / "config" / "xbrl_taxonomies" / taxonomy_file
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    taxonomy_config = json.load(f)
                taxonomy_name = taxonomy_config.get('taxonomy_info', {}).get('name', taxonomy_file)
                self.logger.info(f"成功加载分类标准映射: {taxonomy_file}")
                self.logger.info(f"Using taxonomy '{taxonomy_name}' based on schemaRef '{schema_ref}'")
                return taxonomy_config
            else:
                self.logger.warning(f"分类标准映射文件不存在: {taxonomy_file}，使用默认映射")
                return self._load_default_taxonomy()
                
        except Exception as e:
            self.logger.error(f"加载分类标准映射时出错: {str(e)}，使用默认映射")
            return self._load_default_taxonomy()
    
    def _extract_schema_ref(self, xbrl_content: str) -> str:
        """从XBRL内容中提取schemaRef信息
        
        Args:
            xbrl_content: XBRL文件内容
            
        Returns:
            str: schemaRef标识符
        """
        try:
            # 简单的正则表达式提取schemaRef
            import re
            
            # 查找link:schemaRef标签
            schema_ref_pattern = r'<link:schemaRef[^>]*xlink:href=["\']([^"\'>]+)["\'][^>]*>'
            matches = re.findall(schema_ref_pattern, xbrl_content, re.IGNORECASE)
            
            if matches:
                schema_ref = matches[0]
                self.logger.info(f"提取到schemaRef: {schema_ref}")
                return schema_ref
            
            # 如果没有找到，尝试查找命名空间声明
            namespace_pattern = r'xmlns:([^=]+)=["\']([^"\'>]*csrc[^"\'>]*)["\']'
            ns_matches = re.findall(namespace_pattern, xbrl_content, re.IGNORECASE)
            
            if ns_matches:
                namespace = ns_matches[0][1]
                self.logger.info(f"从命名空间提取到标识符: {namespace}")
                return namespace
            
            return "default"
            
        except Exception as e:
            self.logger.error(f"提取schemaRef时出错: {str(e)}")
            return "default"
    
    def _determine_taxonomy_file(self, schema_ref: str) -> str:
        """根据schemaRef确定分类标准文件
        
        Args:
            schema_ref: schemaRef标识符
            
        Returns:
            str: 分类标准文件名
        """
        schema_ref_lower = schema_ref.lower()
        
        # 根据schemaRef模式匹配分类标准
        if any(pattern in schema_ref_lower for pattern in ['csrc-mf-general', 'csrc-fund', 'csrc-mf']):
            return "csrc_v2.1.json"
        
        # 默认使用default.json
        return "default.json"
    
    def _load_default_taxonomy(self) -> Dict[str, Any]:
        """加载默认分类标准映射
        
        Returns:
            Dict[str, Any]: 默认分类标准映射配置
        """
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "xbrl_taxonomies" / "default.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载默认分类标准映射失败: {str(e)}")
            # 返回最基本的映射
            return {
                "taxonomy_info": {"name": "Fallback", "version": "1.0"},
                "concept_mappings": {}
            }
    
    def _run_arelle_command(self, file_path: str) -> Optional[str]:
        """使用Arelle命令行工具提取XBRL事实
        
        Args:
            file_path: XBRL文件路径
            
        Returns:
            Optional[str]: 事实列表的JSON字符串，如果失败则返回None
        """
        try:
            # 获取项目根目录和Arelle环境路径
            project_root = Path(__file__).parent.parent.parent
            arelle_cmd = project_root / "tools" / "arelle_env" / ".venv" / "Scripts" / "arelleCmdLine.exe"
            
            # 创建临时输出文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False
            ) as output_file:
                output_file_path = output_file.name
            
            try:
                # 构建Arelle命令
                cmd = [
                    str(arelle_cmd),
                    "--file", file_path,
                    "--facts", output_file_path,
                    "--factListCols", "Label Name contextRef unitRef Dec Value EntityScheme EntityIdentifier Period Dimensions",
                    "--logLevel", "WARNING"
                ]
                
                # 执行命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60  # 60秒超时
                )
                
                if result.returncode == 0:
                    # 记录Arelle警告信息（即使成功执行也可能有警告）
                    if result.stderr:
                        self.logger.warning(f"Arelle command produced warnings: {result.stderr}")
                    
                    # 读取输出文件
                    if os.path.exists(output_file_path):
                        with open(output_file_path, 'r', encoding='utf-8') as f:
                            facts_content = f.read().strip()
                        
                        if facts_content:
                            # 解析CSV格式的事实数据并转换为JSON
                            facts_json = self._parse_arelle_facts_csv(facts_content)
                            if facts_json:
                                self.logger.info("Arelle命令行工具成功提取事实")
                                return facts_json
                
                self.logger.error(f"Arelle命令执行失败: {result.stderr}")
                return None
                    
            finally:
                # 清理临时文件
                try:
                    os.unlink(output_file_path)
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            self.logger.error("Arelle命令执行超时")
            return None
        except Exception as e:
            self.logger.error(f"执行Arelle命令时出错: {str(e)}")
            return None
    
    def _parse_arelle_facts_csv(self, csv_content: str) -> Optional[str]:
        """解析Arelle输出的CSV格式事实数据
        
        Args:
            csv_content: CSV格式的事实数据
            
        Returns:
            Optional[str]: JSON格式的事实数据
        """
        try:
            import csv
            from io import StringIO
            
            facts = []
            csv_reader = csv.DictReader(StringIO(csv_content))
            
            for row in csv_reader:
                fact = {
                    'concept': row.get('Name', ''),
                    'value': row.get('Value', ''),
                    'context': row.get('contextRef', ''),
                    'unit': row.get('unitRef', ''),
                    'label': row.get('Label', ''),
                    'period': row.get('Period', ''),
                    'dimensions': row.get('Dimensions', '')
                }
                facts.append(fact)
            
            return json.dumps(facts, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"解析Arelle CSV输出时出错: {str(e)}")
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
                'report_type': ReportType.QUARTERLY,  # 默认值，将被动态解析覆盖
                'report_period_start': date.today(),  # 默认值，将被动态解析覆盖
                'report_period_end': date.today(),  # 默认值，将被动态解析覆盖
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
                
                # 映射报告元数据
                self._map_metadata(concept, value, metadata_data)
        
            # 基于上下文推断缺失的元数据
            metadata_data = self._infer_missing_metadata(metadata_data)
            
            # 映射复杂数据结构
            asset_allocations = self._map_asset_allocations(facts_data)
            top_holdings = self._map_top_holdings(facts_data)
            industry_allocations = self._map_industry_allocations(facts_data)
            
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
                
                # 确保报告类型不为None
                if not metadata_data.get('report_type'):
                    metadata_data['report_type'] = ReportType.UNKNOWN
                
                report_metadata = ReportMetadata(**metadata_data)
                
                fund_report = ComprehensiveFundReport(
                    basic_info=basic_info,
                    financial_metrics=financial_metrics,
                    report_metadata=report_metadata,
                    asset_allocations=asset_allocations,
                    top_holdings=top_holdings,
                    industry_allocations=industry_allocations,
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
        """映射基本信息字段（基于精确编码匹配）"""
        if not data_dict.get('fund_code') and self._matches_concept(concept, 'fund_code'):
            cleaned_value = self._clean_text_value(value)
            if cleaned_value and cleaned_value.isdigit():
                data_dict['fund_code'] = cleaned_value

        if not data_dict.get('fund_name') and self._matches_concept(concept, 'fund_name'):
            cleaned_value = self._clean_text_value(value)
            if cleaned_value and len(cleaned_value) > 2:
                data_dict['fund_name'] = cleaned_value

        if not data_dict.get('fund_manager') and self._matches_concept(concept, 'fund_manager'):
            cleaned_value = self._clean_text_value(value)
            if cleaned_value and len(cleaned_value) > 2:
                data_dict['fund_manager'] = cleaned_value

    def _map_financial_metrics(self, concept: str, value: str, data_dict: Dict[str, Any]):
        """映射财务指标字段（基于精确编码匹配）"""
        if not data_dict.get('net_asset_value') and self._matches_concept(concept, 'net_asset_value'):
            decimal_value = self._parse_decimal(value)
            if decimal_value is not None and decimal_value > 0:
                data_dict['net_asset_value'] = decimal_value

        if not data_dict.get('total_net_assets') and self._matches_concept(concept, 'total_net_assets'):
            decimal_value = self._parse_decimal(value)
            if decimal_value is not None and decimal_value > 0:
                data_dict['total_net_assets'] = decimal_value
        
        if not data_dict.get('period_profit') and self._matches_concept(concept, 'period_profit'):
            decimal_value = self._parse_decimal(value)
            if decimal_value is not None:
                data_dict['period_profit'] = decimal_value

    def _map_metadata(self, concept: str, value: str, data_dict: Dict[str, Any]):
        """动态映射报告元数据字段（基于精确编码匹配）"""
        if not data_dict.get('report_period_end_parsed') and self._matches_concept(concept, 'report_period_end'):
            parsed_date = self._parse_date(value)
            if parsed_date:
                data_dict['report_period_end'] = parsed_date
                data_dict['report_period_end_parsed'] = True
                data_dict['report_year'] = parsed_date.year

        if not data_dict.get('report_period_start_parsed') and self._matches_concept(concept, 'report_period_start'):
            parsed_date = self._parse_date(value)
            if parsed_date:
                data_dict['report_period_start'] = parsed_date
                data_dict['report_period_start_parsed'] = True

        if not data_dict.get('report_type_parsed') and self._matches_concept(concept, 'report_type_name'):
            # 对于报告类型，我们依然可以从值中推断，因为编码本身可能不包含类型信息
            report_type = self._parse_report_type(value)
            if report_type and report_type != ReportType.UNKNOWN:
                data_dict['report_type'] = report_type
                data_dict['report_type_parsed'] = True
        
        # 映射文档标题（用于推断报告类型）
        if 'title' in concept.lower() or '标题' in concept.lower():
            title = self._clean_text_value(value)
            if title:
                data_dict['document_title'] = title
                if not data_dict.get('report_type_parsed'):
                    inferred_type = self._parse_report_type(title)
                    if inferred_type and inferred_type != ReportType.UNKNOWN:
                        data_dict['report_type'] = inferred_type
                        data_dict['report_type_parsed'] = True
    
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
    
    def _parse_date(self, value: str) -> Optional[date]:
        """解析日期值"""
        if not value:
            return None
        
        try:
            # 尝试多种日期格式
            date_formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%Y年%m月%d日',
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S'
            ]
            
            cleaned_value = str(value).strip()
            for fmt in date_formats:
                try:
                    parsed_datetime = datetime.strptime(cleaned_value, fmt)
                    return parsed_datetime.date()
                except ValueError:
                    continue
            
            # 如果标准格式都失败，尝试ISO格式
            from dateutil.parser import parse
            parsed_datetime = parse(cleaned_value)
            return parsed_datetime.date()
            
        except Exception:
            return None
    
    def _parse_report_type(self, value: str) -> Optional[ReportType]:
        """
        动态解析报告类型
        基于PHASE_1.1_SPRINT_PLAN.md重构，支持更多报告类型识别模式
        """
        if not value:
            return ReportType.UNKNOWN
        
        value_lower = str(value).lower()
        
        # 注意：检查顺序很重要，更具体的关键词要先检查
        if any(keyword in value_lower for keyword in ['半年报', 'semi annual', 'semi-annual', '中期', '中报']):
            return ReportType.SEMI_ANNUAL
        elif any(keyword in value_lower for keyword in ['季报', 'quarter', 'quarterly', '季度', '一季', '二季', '三季', '四季']):
            return ReportType.QUARTERLY
        elif any(keyword in value_lower for keyword in ['月报', 'monthly', '月度']):
            return ReportType.MONTHLY
        elif any(keyword in value_lower for keyword in ['年报', 'annual', '年度']):
            return ReportType.ANNUAL
        
        return ReportType.UNKNOWN
    
    def _infer_report_type_from_period(self, start_date: date, end_date: date) -> ReportType:
        """
        基于报告期间推断报告类型
        
        Args:
            start_date: 报告期开始日期
            end_date: 报告期结束日期
            
        Returns:
            推断的报告类型
        """
        try:
            # 计算期间月数
            period_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            
            if period_months >= 11:  # 年报
                return ReportType.ANNUAL
            elif period_months >= 5:  # 半年报
                return ReportType.SEMI_ANNUAL
            elif period_months >= 2:  # 季报
                return ReportType.QUARTERLY
            else:  # 月报
                return ReportType.MONTHLY
                
        except Exception:
            return ReportType.UNKNOWN
    
    def _map_asset_allocations(self, facts_data: List[Dict]) -> List[AssetAllocationData]:
        """
        基于上下文的表格数据解析映射资产配置数据
        基于PHASE_1.1_SPRINT_PLAN.md重构，支持更精确的资产配置数据识别
        
        Args:
            facts_data: XBRL事实数据列表
            
        Returns:
            资产配置数据列表
        """
        asset_allocations = []
        
        try:
            # 按上下文分组资产配置数据，支持表格结构识别
            allocations_by_context = {}
            table_contexts = set()
            
            # 第一遍：识别资产配置相关的上下文
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                context = fact.get('context', '')
                
                if self._is_asset_concept(concept):
                    table_contexts.add(context)
            
            # 第二遍：提取资产配置数据
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                value = fact.get('value', '')
                context = fact.get('context', '')
                
                if not value or not context or context not in table_contexts:
                    continue
                
                # 初始化上下文
                if context not in allocations_by_context:
                    allocations_by_context[context] = {
                        'asset_type': '',
                        'asset_name': '',
                        'market_value': 0.0,
                        'percentage': 0.0,
                        'context_id': context
                    }
                
                # 映射资产配置字段
                self._map_asset_field(concept, value, allocations_by_context[context])
            
            # 构建和验证资产配置对象
            for context, allocation_data in allocations_by_context.items():
                if self._is_valid_asset_allocation(allocation_data):
                    asset_allocation = AssetAllocationData(
                        asset_type=allocation_data['asset_type'],
                        asset_name=allocation_data['asset_name'],
                        market_value=allocation_data['market_value'],
                        percentage=allocation_data['percentage']
                    )
                    asset_allocations.append(asset_allocation)
            
            # 如果没有找到基于上下文的数据，尝试聚合方式
            if not asset_allocations:
                asset_allocations = self._map_asset_allocations_aggregated(facts_data)
            
            # 使用AssetAllocationCalculator计算百分比
            if asset_allocations:
                asset_allocations = self.asset_calculator.calculate_percentages(asset_allocations)
            
            return asset_allocations
            
        except Exception as e:
            self.logger.error(f"映射资产配置数据时出错: {str(e)}")
            return []
    
    def _is_asset_concept(self, concept: str) -> bool:
        """
        判断概念是否与资产配置相关
        
        Args:
            concept: XBRL概念名称
            
        Returns:
            是否为资产配置相关概念
        """
        asset_keys = ['stock_investment', 'bond_investment', 'cash_and_equivalents', 'other_investments']
        
        for key in asset_keys:
            if self._matches_concept(concept, key):
                return True
        
        # 额外的资产配置识别模式
        concept_lower = concept.lower()
        asset_patterns = [
            '资产', '投资', 'asset', 'investment', '配置', 
            '股票', '债券', '现金', '基金', '衍生品'
        ]
        
        return any(pattern in concept_lower for pattern in asset_patterns)
    
    def _map_asset_field(self, concept: str, value: str, allocation_data: Dict[str, Any]):
        """
        映射单个资产配置字段
        
        Args:
            concept: XBRL概念名称
            value: 字段值
            allocation_data: 资产配置数据字典
        """
        # 确定资产类型和名称
        asset_type, asset_name = self._determine_asset_type_and_name(concept)
        if asset_type:
            allocation_data['asset_type'] = asset_type
            allocation_data['asset_name'] = asset_name
        
        # 映射市值和百分比
        decimal_value = self._parse_decimal(value)
        if decimal_value is not None:
            # 判断是市值还是百分比
            if self._is_percentage_concept(concept, value):
                # 处理百分比格式
                if decimal_value > 1:
                    decimal_value = decimal_value / 100
                allocation_data['percentage'] = decimal_value
            else:
                # 市值数据
                if decimal_value > 0:
                    allocation_data['market_value'] = decimal_value
    
    def _determine_asset_type_and_name(self, concept: str) -> tuple:
        """
        根据概念确定资产类型和名称
        
        Args:
            concept: XBRL概念名称
            
        Returns:
            (资产类型, 资产名称) 元组
        """
        concept_lower = concept.lower()
        
        # 股票相关
        if self._matches_concept(concept, 'stock_investment'):
            return (AssetType.STOCK, '股票投资')
        
        # 债券相关
        if self._matches_concept(concept, 'bond_investment'):
            return (AssetType.BOND, '债券投资')
        
        # 现金相关
        if self._matches_concept(concept, 'cash_and_equivalents'):
            return (AssetType.CASH, '现金及现金等价物')
        
        # 其他投资
        if self._matches_concept(concept, 'other_investments'):
            return (AssetType.OTHER, '其他投资')
        
        return ('', '')
    
    def _is_percentage_concept(self, concept: str, value: str) -> bool:
        """
        判断是否为百分比概念
        
        Args:
            concept: XBRL概念名称
            value: 字段值
            
        Returns:
            是否为百分比
        """
        concept_lower = concept.lower()
        value_str = str(value).lower()
        
        # 概念名称包含百分比关键词
        percentage_keywords = ['比例', 'percentage', 'ratio', 'percent', '占比', '百分比']
        if any(keyword in concept_lower for keyword in percentage_keywords):
            return True
        
        # 值包含百分号
        if '%' in value_str:
            return True
        
        return False
    
    def _is_valid_asset_allocation(self, allocation_data: Dict[str, Any]) -> bool:
        """
        验证资产配置数据是否有效
        
        Args:
            allocation_data: 资产配置数据字典
            
        Returns:
            是否为有效资产配置
        """
        # 必须有资产类型
        has_type = bool(allocation_data.get('asset_type'))
        
        # 必须有市值或比例信息
        has_value = bool(allocation_data.get('market_value', 0) > 0 or allocation_data.get('percentage', 0) > 0)
        
        return has_type and has_value
    
    def _map_asset_allocations_aggregated(self, facts_data: List[Dict]) -> List[AssetAllocationData]:
        """
        聚合方式映射资产配置数据（备用方案）
        
        Args:
            facts_data: XBRL事实数据列表
            
        Returns:
            资产配置数据列表
        """
        # 用于存储资产配置数据的临时字典
        assets_data = {
            AssetType.STOCK: {'market_value': Decimal('0'), 'percentage': Decimal('0'), 'name': '股票投资'},
            AssetType.BOND: {'market_value': Decimal('0'), 'percentage': Decimal('0'), 'name': '债券投资'},
            AssetType.CASH: {'market_value': Decimal('0'), 'percentage': Decimal('0'), 'name': '现金及现金等价物'},
            AssetType.OTHER: {'market_value': Decimal('0'), 'percentage': Decimal('0'), 'name': '其他投资'}
        }
        
        for fact in facts_data:
            if not isinstance(fact, dict):
                continue
            
            concept = fact.get('concept', '')
            value = fact.get('value', '')
            
            if not concept or not value:
                continue
            
            decimal_value = self._parse_decimal(value)
            if not decimal_value:
                continue
            
            # 确定资产类型
            asset_type, _ = self._determine_asset_type_and_name(concept)
            if not asset_type or asset_type not in assets_data:
                continue
            
            # 判断是市值还是百分比
            if self._is_percentage_concept(concept, value):
                if decimal_value > 1:
                    decimal_value = decimal_value / 100
                assets_data[asset_type]['percentage'] = decimal_value
            else:
                assets_data[asset_type]['market_value'] = decimal_value
        
        # 注意：百分比计算现在由AssetAllocationCalculator统一处理
        
        # 构建AssetAllocationData对象
        asset_allocations = []
        for asset_type, data in assets_data.items():
            if data['market_value'] > 0 or data['percentage'] > 0:
                allocation = AssetAllocationData(
                    asset_type=asset_type,
                    asset_name=data['name'],
                    market_value=data['market_value'],
                    percentage=data['percentage']
                )
                asset_allocations.append(allocation)
        
        return asset_allocations
    
    def _infer_missing_metadata(self, metadata_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于上下文推断缺失的元数据
        
        Args:
            metadata_data: 当前元数据字典
            
        Returns:
            补充后的元数据字典
        """
        # 如果没有明确的报告类型，尝试从期间推断
        if (not metadata_data.get('report_type_parsed') and 
            metadata_data.get('report_period_start') and 
            metadata_data.get('report_period_end')):
            
            inferred_type = self._infer_report_type_from_period(
                metadata_data['report_period_start'],
                metadata_data['report_period_end']
            )
            if inferred_type != ReportType.UNKNOWN:
                metadata_data['report_type'] = inferred_type
                metadata_data['report_type_parsed'] = True
        
        # 如果没有报告日期，使用期末日期
        if (not metadata_data.get('reporting_date_parsed') and 
            metadata_data.get('report_period_end')):
            metadata_data['reporting_date'] = metadata_data['report_period_end']
            metadata_data['reporting_date_parsed'] = True
        
        # 清理解析标记
        keys_to_remove = [k for k in metadata_data.keys() if k.endswith('_parsed')]
        for key in keys_to_remove:
            del metadata_data[key]
        
        return metadata_data
    
    def _map_top_holdings(self, facts_data: List[Dict]) -> List[HoldingData]:
        """
        基于上下文的表格数据解析映射前十大持仓数据
        基于PHASE_1.1_SPRINT_PLAN.md重构，支持更精确的持仓数据识别
        
        Args:
            facts_data: XBRL事实数据列表
            
        Returns:
            前十大持仓数据列表
        """
        holdings = []
        
        try:
            # 按上下文分组持仓数据，支持表格结构识别
            holdings_by_context = {}
            table_contexts = set()
            
            # 第一遍：识别持仓相关的上下文
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                context = fact.get('context', '')
                
                if self._is_holding_concept(concept):
                    table_contexts.add(context)
            
            # 第二遍：提取持仓数据
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                value = fact.get('value', '')
                context = fact.get('context', '')
                
                if not value or not context or context not in table_contexts:
                    continue
                
                # 初始化上下文
                if context not in holdings_by_context:
                    holdings_by_context[context] = {
                        'security_code': '',
                        'security_name': '',
                        'market_value': 0.0,
                        'percentage': 0.0,
                        'shares': 0.0,
                        'rank': None,
                        'context_id': context
                    }
                
                # 映射持仓字段
                self._map_holding_field(concept, value, holdings_by_context[context])
            
            # 构建和验证持仓对象
            for context, holding_data in holdings_by_context.items():
                if self._is_valid_holding(holding_data):
                    holding = HoldingData(
                        holding_type='股票',  # 默认为股票，可以根据需要扩展
                        security_code=holding_data['security_code'],
                        security_name=holding_data['security_name'],
                        shares=holding_data['shares'],
                        market_value=holding_data['market_value'],
                        percentage=holding_data['percentage'],
                        rank=holding_data.get('rank') or 0
                    )
                    holdings.append(holding)
            
            # 智能排序：优先使用排名，其次使用市值
            holdings = self._sort_holdings(holdings, holdings_by_context)
            
            # 重新分配排名
            for i, holding in enumerate(holdings[:10], 1):
                holding.rank = i
            
            # 返回前10个
            return holdings[:10]
            
        except Exception as e:
            self.logger.error(f"映射前十大持仓数据时出错: {str(e)}")
            return []
    
    def _is_holding_concept(self, concept: str) -> bool:
        """
        判断概念是否与持仓相关
        
        Args:
            concept: XBRL概念名称
            
        Returns:
            是否为持仓相关概念
        """
        holding_keys = [
            'holding_security_code', 'holding_security_name', 
            'holding_market_value', 'holding_percentage', 'holding_shares'
        ]
        
        for key in holding_keys:
            if self._matches_concept(concept, key):
                return True
        
        # 额外的持仓识别模式
        concept_lower = concept.lower()
        holding_patterns = [
            '持仓', '重仓', 'holding', 'position', '前十', 'top', 
            '股票投资明细', '债券投资明细', '基金投资明细'
        ]
        
        return any(pattern in concept_lower for pattern in holding_patterns)
    
    def _matches_concept(self, concept: str, mapping_key: str) -> bool:
        """
        检查概念是否与映射中的精确编码匹配。
        这是从模糊文本匹配到精确编码匹配的核心逻辑变更。
        
        Args:
            concept: 从Arelle获取的XBRL概念名称 (e.g., "csrc-mf-general:FundCode", "1375")
            mapping_key: self.concept_mappings中的键 (e.g., "fund_code")
            
        Returns:
            如果找到精确匹配则返回True
        """
        if mapping_key not in self.concept_mappings:
            return False

        codes_to_match = self.concept_mappings[mapping_key]
        
        # 1. 直接完全匹配 (e.g., concept is "dei:DocumentPeriodEndDate")
        if concept in codes_to_match:
            return True
        
        # 2. 匹配没有前缀的编码 (e.g., concept is "1375")
        base_concept = concept.split(':')[-1]
        if base_concept in codes_to_match:
            return True
            
        # 3. 匹配概念名称中包含的编码 (e.g., concept is "SomeHoldingDetail_1376")
        for code in codes_to_match:
            if f"_{code}" in concept or f":{code}" in concept:
                return True

        return False
    
    def _map_holding_field(self, concept: str, value: str, holding_data: Dict[str, Any]):
        """
        映射单个持仓字段
        
        Args:
            concept: XBRL概念名称
            value: 字段值
            holding_data: 持仓数据字典
        """
        if self._matches_concept(concept, 'holding_security_code'):
            code = self._clean_text_value(value)
            if code and len(code) >= 6:  # 有效的证券代码长度
                holding_data['security_code'] = code
                
        elif self._matches_concept(concept, 'holding_security_name'):
            name = self._clean_text_value(value)
            if name and len(name) > 1:  # 有效的证券名称
                holding_data['security_name'] = name
                
        elif self._matches_concept(concept, 'holding_market_value'):
            market_value = self._parse_decimal(value)
            if market_value and market_value > 0:
                holding_data['market_value'] = market_value
                
        elif self._matches_concept(concept, 'holding_percentage'):
            percentage = self._parse_decimal(value)
            if percentage is not None:
                # 处理百分比格式（可能是小数或百分数）
                if percentage > 1:
                    percentage = percentage / 100
                holding_data['percentage'] = percentage
                
        elif self._matches_concept(concept, 'holding_shares'):
            shares = self._parse_decimal(value)
            if shares and shares > 0:
                holding_data['shares'] = shares
                
        # 识别排名信息
        elif '排名' in concept.lower() or 'rank' in concept.lower() or '序号' in concept.lower():
            rank = self._parse_decimal(value)
            if rank and rank > 0:
                holding_data['rank'] = int(rank)
    
    def _is_valid_holding(self, holding_data: Dict[str, Any]) -> bool:
        """
        验证持仓数据是否有效
        
        Args:
            holding_data: 持仓数据字典
            
        Returns:
            是否为有效持仓
        """
        # 必须有证券代码或名称
        has_identifier = bool(holding_data.get('security_code') or holding_data.get('security_name'))
        
        # 必须有市值或比例信息
        has_value = bool(holding_data.get('market_value', 0) > 0 or holding_data.get('percentage', 0) > 0)
        
        return has_identifier and has_value
    
    def _sort_holdings(self, holdings: List[HoldingData], holdings_by_context: Dict[str, Dict]) -> List[HoldingData]:
        """
        智能排序持仓数据
        
        Args:
            holdings: 持仓数据列表
            holdings_by_context: 按上下文分组的持仓数据
            
        Returns:
            排序后的持仓数据列表
        """
        # 检查是否有排名信息
        has_rank = any(data.get('rank') for data in holdings_by_context.values())
        
        if has_rank:
            # 按排名排序
            def sort_key(holding):
                context_data = next(
                    (data for data in holdings_by_context.values() 
                     if data['security_code'] == holding.security_code or 
                        data['security_name'] == holding.security_name),
                    {}
                )
                rank = context_data.get('rank', 999)
                return (rank, -holding.market_value)
            
            holdings.sort(key=sort_key)
        else:
            # 按市值排序
            holdings.sort(key=lambda x: x.market_value, reverse=True)
        
        return holdings
    
    def _map_industry_allocations(self, facts_data: List[Dict]) -> List[IndustryAllocationData]:
        """
        基于上下文的表格数据解析映射行业配置数据
        基于PHASE_1.1_SPRINT_PLAN.md重构，支持更精确的行业配置数据识别
        
        Args:
            facts_data: XBRL事实数据列表
            
        Returns:
            行业配置数据列表
        """
        industry_allocations = []
        
        try:
            # 按上下文分组行业配置数据，支持表格结构识别
            allocations_by_context = {}
            table_contexts = set()
            
            # 第一遍：识别行业配置相关的上下文
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                context = fact.get('context', '')
                
                if self._is_industry_concept(concept):
                    table_contexts.add(context)
            
            # 第二遍：提取行业配置数据
            for fact in facts_data:
                if not isinstance(fact, dict):
                    continue
                    
                concept = fact.get('concept', '')
                value = fact.get('value', '')
                context = fact.get('context', '')
                
                if not value or not context or context not in table_contexts:
                    continue
                
                # 初始化上下文
                if context not in allocations_by_context:
                    allocations_by_context[context] = {
                        'industry_name': '',
                        'industry_code': '',
                        'market_value': 0.0,
                        'percentage': 0.0,
                        'rank': None,
                        'context_id': context
                    }
                
                # 映射行业配置字段
                self._map_industry_field(concept, value, allocations_by_context[context])
            
            # 构建和验证行业配置对象
            for context, allocation_data in allocations_by_context.items():
                if self._is_valid_industry_allocation(allocation_data):
                    industry_allocation = IndustryAllocationData(
                        industry_name=allocation_data['industry_name'],
                        industry_code=allocation_data['industry_code'],
                        market_value=allocation_data['market_value'],
                        percentage=allocation_data['percentage']
                    )
                    industry_allocations.append(industry_allocation)
            
            # 智能排序：优先使用排名，其次使用市值
            industry_allocations = self._sort_industry_allocations(industry_allocations, allocations_by_context)
            
            # 重新分配排名
            for i, allocation in enumerate(industry_allocations, 1):
                allocation.rank = i
            
            return industry_allocations
            
        except Exception as e:
            self.logger.error(f"映射行业配置数据时出错: {str(e)}")
            return []
    
    def _is_industry_concept(self, concept: str) -> bool:
        """
        判断概念是否与行业配置相关
        
        Args:
            concept: XBRL概念名称
            
        Returns:
            是否为行业配置相关概念
        """
        industry_keys = ['industry_name', 'industry_code']
        
        for key in industry_keys:
            if self._matches_concept(concept, key):
                return True
        
        # 额外的行业配置识别模式
        concept_lower = concept.lower()
        industry_patterns = [
            '行业', '板块', 'industry', 'sector', '分类', 
            '行业配置', '行业分布', '行业投资', '板块配置'
        ]
        
        return any(pattern in concept_lower for pattern in industry_patterns)
    
    def _map_industry_field(self, concept: str, value: str, allocation_data: Dict[str, Any]):
        """
        映射单个行业配置字段
        
        Args:
            concept: XBRL概念名称
            value: 字段值
            allocation_data: 行业配置数据字典
        """
        if self._matches_concept(concept, 'industry_name'):
            name = self._clean_text_value(value)
            if name and len(name) > 1:  # 有效的行业名称
                allocation_data['industry_name'] = name
                
        elif self._matches_concept(concept, 'industry_code'):
            code = self._clean_text_value(value)
            if code:  # 行业代码可以为空
                allocation_data['industry_code'] = code
                
        elif self._matches_concept(concept, 'holding_market_value'):
            market_value = self._parse_decimal(value)
            if market_value and market_value > 0:
                allocation_data['market_value'] = market_value
                
        elif self._matches_concept(concept, 'holding_percentage'):
            percentage = self._parse_decimal(value)
            if percentage is not None:
                # 处理百分比格式（可能是小数或百分数）
                if percentage > 1:
                    percentage = percentage / 100
                allocation_data['percentage'] = percentage
                
        # 识别排名信息
        elif '排名' in concept.lower() or 'rank' in concept.lower() or '序号' in concept.lower():
            rank = self._parse_decimal(value)
            if rank and rank > 0:
                allocation_data['rank'] = int(rank)
    
    def _is_valid_industry_allocation(self, allocation_data: Dict[str, Any]) -> bool:
        """
        验证行业配置数据是否有效
        
        Args:
            allocation_data: 行业配置数据字典
            
        Returns:
            是否为有效行业配置
        """
        # 必须有行业名称
        has_name = bool(allocation_data.get('industry_name'))
        
        # 必须有市值或比例信息
        has_value = bool(allocation_data.get('market_value', 0) > 0 or allocation_data.get('percentage', 0) > 0)
        
        return has_name and has_value
    
    def _sort_industry_allocations(self, allocations: List[IndustryAllocationData], 
                                 allocations_by_context: Dict[str, Dict]) -> List[IndustryAllocationData]:
        """
        智能排序行业配置数据
        
        Args:
            allocations: 行业配置数据列表
            allocations_by_context: 按上下文分组的行业配置数据
            
        Returns:
            排序后的行业配置数据列表
        """
        # 检查是否有排名信息
        has_rank = any(data.get('rank') for data in allocations_by_context.values())
        
        if has_rank:
            # 按排名排序
            def sort_key(allocation):
                context_data = next(
                    (data for data in allocations_by_context.values() 
                     if data['industry_name'] == allocation.industry_name),
                    {}
                )
                rank = context_data.get('rank', 999)
                return (rank, -float(allocation.market_value or 0))
            
            allocations.sort(key=sort_key)
        else:
            # 按市值排序
            allocations.sort(key=lambda x: float(x.market_value or 0), reverse=True)
        
        return allocations
    
    def _create_success_result(
        self, 
        fund_report: ComprehensiveFundReport, 
        file_path: Optional[Path]
    ) -> ParseResult:
        """创建成功的解析结果"""
        return ParseResult(
            success=True,
            fund_report=fund_report,  # 直接使用ComprehensiveFundReport，不再转换为旧格式
            parser_type=self.parser_type,
            errors=[],
            warnings=[],
            metadata={
                "file_path": str(file_path) if file_path else None,
                "parsing_method": "arelle_cmdline",
                "parsing_confidence": fund_report.report_metadata.parsing_confidence
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

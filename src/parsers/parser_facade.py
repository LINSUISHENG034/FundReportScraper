"""解析器门面模块

提供统一的解析接口，自动选择合适的解析器并处理解析结果。
集成质量监控、LLM辅助和数据修复功能。
"""

import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.core.logging import get_logger
from src.models.fund_data import FundReport
from src.parsers.base_parser import BaseParser, ParseResult, ParserType
from src.parsers.format_detector import FormatDetector, DocumentFormat
# from src.parsers.fund_xbrl_parser import FundXBRLParser  # 暂时注释，文件不存在
from src.parsers.data_quality import QualityMetricsCollector, QualityAlertSystem
from src.parsers.llm_assistant import OllamaLLMAssistant, DataRepairService, DataQualityValidator


@dataclass
class ParsingMetrics:
    """解析性能指标"""
    total_files_processed: int = 0
    successful_parses: int = 0
    failed_parses: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    format_distribution: Dict[str, int] = None
    parser_usage: Dict[str, int] = None
    
    def __post_init__(self):
        if self.format_distribution is None:
            self.format_distribution = {}
        if self.parser_usage is None:
            self.parser_usage = {}
    
    @property
    def success_rate(self) -> float:
        """解析成功率"""
        if self.total_files_processed == 0:
            return 0.0
        return self.successful_parses / self.total_files_processed
    
    def update_metrics(self, parse_result: ParseResult, processing_time: float, format_type: str):
        """更新指标"""
        self.total_files_processed += 1
        self.total_processing_time += processing_time
        self.average_processing_time = self.total_processing_time / self.total_files_processed
        
        if parse_result.success:
            self.successful_parses += 1
        else:
            self.failed_parses += 1
        
        # 更新格式分布
        self.format_distribution[format_type] = self.format_distribution.get(format_type, 0) + 1
        
        # 更新解析器使用统计
        parser_name = parse_result.parser_type.value
        self.parser_usage[parser_name] = self.parser_usage.get(parser_name, 0) + 1


class XBRLParserFacade:
    """增强型XBRL解析器门面类
    
    集成质量监控、LLM辅助和数据修复功能的统一解析接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = get_logger("xbrl_parser_facade")
        self.config = config or {}
        
        # 核心组件
        self.format_detector = FormatDetector()
        self._parsers: Dict[ParserType, BaseParser] = {}
        self._format_parser_mapping: Dict[DocumentFormat, List[ParserType]] = {
            DocumentFormat.XBRL: [ParserType.XBRL_NATIVE],
            DocumentFormat.IXBRL: [ParserType.XBRL_NATIVE, ParserType.HTML_LEGACY],
            DocumentFormat.HTML: [ParserType.HTML_LEGACY],
            DocumentFormat.UNKNOWN: [ParserType.HTML_LEGACY]
        }
        self.metrics = ParsingMetrics()
        
        # 质量监控组件
        self.quality_collector = QualityMetricsCollector()
        self.quality_validator = DataQualityValidator()
        self.alert_system = QualityAlertSystem(
            min_success_rate=self.config.get('min_success_rate', 0.9),
            min_quality_score=self.config.get('min_quality_score', 0.8),
            max_avg_parsing_time=self.config.get('max_avg_parsing_time', 30.0)
        )
        
        # LLM和数据修复组件
        self.llm_assistant = None
        self.data_repair_service = None
        
        # 初始化组件
        self._initialize_components()
        self._initialize_parsers()
    
    def _initialize_components(self):
        """初始化LLM和数据修复组件"""
        llm_config = self.config.get('llm_assistance', {})
        
        if llm_config.get('enabled', True):
            try:
                ollama_config = llm_config.get('ollama', {})
                self.llm_assistant = OllamaLLMAssistant(
                    base_url=ollama_config.get('base_url', 'http://localhost:11434'),
                    model=ollama_config.get('model', 'qwen2.5:7b'),
                    timeout=ollama_config.get('timeout', 30)
                )
                
                self.data_repair_service = DataRepairService(self.llm_assistant)
                self.logger.info("LLM助手和数据修复服务初始化成功")
                
            except Exception as e:
                self.logger.warning("LLM组件初始化失败", error=str(e))
                self.llm_assistant = None
                self.data_repair_service = None
    
    def _initialize_parsers(self):
        """初始化所有可用的解析器"""
        # try:
        #     # 注册基金专业XBRL解析器
        #     fund_parser = FundXBRLParser(use_llm_assist=self.llm_assistant is not None)
        #     self.register_parser(ParserType.XBRL_NATIVE, fund_parser)
        #     self.logger.info("已注册基金专业XBRL解析器")
        # except Exception as e:
        #     self.logger.error("注册基金XBRL解析器失败", error=str(e))
        
        # 暂时注册ArelleParser作为XBRL_NATIVE解析器
        try:
            from src.parsers.arelle_parser import ArelleParser
            arelle_parser = ArelleParser()
            self.register_parser(ParserType.XBRL_NATIVE, arelle_parser)
            self.logger.info("已注册Arelle XBRL解析器")
        except Exception as e:
            self.logger.error("注册Arelle XBRL解析器失败", error=str(e))
        
        try:
            # 注册传统HTML解析器作为备用
            from src.parsers.optimized_html_parser import OptimizedHTMLParser
            self.register_parser(ParserType.HTML_LEGACY, OptimizedHTMLParser())
            self.logger.info("已注册HTML备用解析器")
        except ImportError:
            self.logger.warning("无法导入HTML解析器")
        
        try:
            # 注册AI增强解析器
            from src.parsers.ai_enhanced_parser import AIEnhancedParser
            self.register_parser(ParserType.AI_ENHANCED, AIEnhancedParser())
            self.logger.info("已注册AI增强解析器")
        except ImportError:
            self.logger.warning("无法导入AI增强解析器")
    
    def register_parser(self, parser_type: ParserType, parser: BaseParser):
        """
        注册解析器
        
        Args:
            parser_type: 解析器类型
            parser: 解析器实例
        """
        self._parsers[parser_type] = parser
        self.logger.debug("解析器已注册", parser_type=parser_type.value)
    
    async def parse_file(self, file_path: Path) -> ParseResult:
        """解析文件（异步版本）"""
        start_time = time.time()
        
        try:
            self.logger.info("开始解析文件", file_path=str(file_path))
            
            # 读取文件内容
            content = self._read_file_safely(file_path)
            if not content:
                return self._create_error_result(f"无法读取文件: {file_path}")
            
            # 检测格式
            detected_format = self.format_detector.detect_format(content, file_path)
            format_details = self.format_detector.get_format_details(content, file_path)
            
            self.logger.info("文件格式检测完成", 
                           file_path=str(file_path),
                           detected_format=detected_format.value,
                           confidence_scores=format_details["confidence_scores"])
            
            # 解析内容
            result = await self.parse_content_async(content, file_path, detected_format)
            
            # 收集质量指标
            parsing_time = time.time() - start_time
            quality_metrics = self.quality_collector.collect_parsing_metrics(
                fund_report=result.fund_report,
                parsing_time=parsing_time,
                success=result.success,
                issues=result.errors,
                warnings=result.warnings
            )
            
            # 检查质量告警
            alerts = self.alert_system.check_quality_thresholds(self.quality_collector)
            if alerts:
                self.logger.warning("触发质量告警", alerts=alerts)
            
            # 更新传统指标
            self.metrics.update_metrics(result, parsing_time, detected_format.value)
            
            # 添加格式检测信息到元数据
            result.metadata.update({
                "detected_format": detected_format.value,
                "format_details": format_details,
                "processing_time": parsing_time,
                "quality_score": quality_metrics.overall_score
            })
            
            if result.success:
                self.logger.info(
                    "文件解析成功", 
                    file_path=str(file_path),
                    parsing_time=f"{parsing_time:.2f}s",
                    parser_type=result.parser_type.value,
                    quality_score=quality_metrics.overall_score
                )
            else:
                self.logger.error(
                    "文件解析失败", 
                    file_path=str(file_path),
                    errors=result.errors
                )
            
            return result
            
        except Exception as e:
            parsing_time = time.time() - start_time
            
            # 收集失败指标
            self.quality_collector.collect_parsing_metrics(
                fund_report=None,
                parsing_time=parsing_time,
                success=False,
                issues=[f"文件解析异常: {str(e)}"],
                warnings=[]
            )
            
            self.logger.error(
                "文件解析异常", 
                file_path=str(file_path),
                error=str(e)
            )
            
            error_result = self._create_error_result(f"解析异常: {str(e)}")
            self.metrics.update_metrics(error_result, parsing_time, "error")
            
            return error_result
    
    def parse_file_sync(self, file_path: Path) -> ParseResult:
        """解析文件（同步版本）"""
        return asyncio.run(self.parse_file(file_path))
    
    async def parse_content_async(self, 
                                 content: str, 
                                 file_path: Optional[Path] = None,
                                 format_hint: Optional[DocumentFormat] = None) -> ParseResult:
        """解析内容（异步版本，支持LLM增强）"""
        if not content or not content.strip():
            return self._create_error_result("内容为空")
        
        # 如果没有格式提示，自动检测
        if format_hint is None:
            format_hint = self.format_detector.detect_format(content, file_path)
        
        # 获取适用的解析器列表
        parser_types = self._format_parser_mapping.get(format_hint, [ParserType.HTML_LEGACY])
        
        # 尝试使用每个解析器
        last_error = None
        for parser_type in parser_types:
            parser = self._parsers.get(parser_type)
            if not parser:
                self.logger.warning("解析器未注册", parser_type=parser_type.value)
                continue
            
            try:
                # 检查解析器是否能处理该内容
                if not parser.can_parse(content, file_path):
                    self.logger.debug("解析器无法处理该内容", parser_type=parser_type.value)
                    continue
                
                # 尝试解析
                self.logger.info("尝试使用解析器", parser_type=parser_type.value)
                result = parser.parse_content(content, file_path)
                
                if result.success:
                    # 如果解析成功，进行质量验证和修复
                    result = await self._enhance_parsing_result(result, content)
                    
                    self.logger.info("解析成功", 
                                   parser_type=parser_type.value,
                                   completeness_score=result.metadata.get("completeness_score", 0))
                    return result
                else:
                    self.logger.warning("解析失败", 
                                      parser_type=parser_type.value,
                                      errors=result.errors)
                    last_error = result
                    
            except Exception as e:
                self.logger.error("解析器执行异常", 
                                parser_type=parser_type.value, 
                                error=str(e))
                last_error = self._create_error_result(f"解析器异常: {str(e)}")
        
        # 如果启用AI增强且所有解析器都失败，尝试AI增强解析
        if ParserType.AI_ENHANCED in self._parsers:
            try:
                ai_parser = self._parsers[ParserType.AI_ENHANCED]
                self.logger.info("尝试AI增强解析")
                result = ai_parser.parse_content(content, file_path)
                
                if result.success:
                    result = await self._enhance_parsing_result(result, content)
                    self.logger.info("AI增强解析成功", 
                                   completeness_score=result.metadata.get("completeness_score", 0))
                    return result
                else:
                    self.logger.warning("AI增强解析失败", errors=result.errors)
                    
            except Exception as e:
                self.logger.error("AI增强解析异常", error=str(e))
        
        # 所有解析器都失败
        if last_error:
            return last_error
        else:
            return self._create_error_result("没有可用的解析器能够处理该内容")
    
    def parse_content(self, 
                     content: str, 
                     file_path: Optional[Path] = None,
                     format_hint: Optional[DocumentFormat] = None) -> ParseResult:
        """解析内容（同步版本）"""
        return asyncio.run(self.parse_content_async(content, file_path, format_hint))
    
    async def _enhance_parsing_result(self, result: ParseResult, content: str) -> ParseResult:
        """增强解析结果"""
        if not result.success or not result.fund_report:
            return result
        
        try:
            # 质量验证
            validation_result = self.quality_validator.validate_fund_report(result.fund_report)
            
            # 如果有数据修复服务且发现问题，尝试修复
            if self.data_repair_service and validation_result.issues:
                self.logger.info("检测到数据质量问题，尝试修复", issues_count=len(validation_result.issues))
                
                repair_result = await self.data_repair_service.repair_fund_data(
                    result.fund_report, validation_result.issues, content
                )
                
                if repair_result.success and repair_result.repaired_data:
                    result.fund_report = repair_result.repaired_data
                    result.warnings.extend(repair_result.warnings)
                    result.metadata['data_repaired'] = True
                    result.metadata['repair_details'] = repair_result.repair_details
                    
                    self.logger.info("数据修复完成", 
                                   repaired_fields=len(repair_result.repair_details))
            
            # 更新元数据
            result.metadata.update({
                'quality_validated': True,
                'validation_score': validation_result.overall_score,
                'validation_issues': len(validation_result.issues)
            })
            
        except Exception as e:
            self.logger.warning("解析结果增强失败", error=str(e))
            result.warnings.append(f"解析结果增强失败: {str(e)}")
        
        return result
    
    def get_parsing_metrics(self) -> ParsingMetrics:
        """获取解析性能指标"""
        return self.metrics
    
    def reset_metrics(self):
        """重置性能指标"""
        self.metrics = ParsingMetrics()
    
    def get_available_parsers(self) -> List[ParserType]:
        """获取可用的解析器列表"""
        return list(self._parsers.keys())
    
    def is_parser_available(self, parser_type: ParserType) -> bool:
        """检查指定解析器是否可用"""
        return parser_type in self._parsers
    
    def _read_file_safely(self, file_path: Path) -> Optional[str]:
        """
        安全地读取文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 文件内容，失败时返回None
        """
        try:
            import chardet
            
            with open(file_path, "rb") as f:
                raw_data = f.read()
            
            encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
            return raw_data.decode(encoding, errors="ignore")
            
        except Exception as e:
            self.logger.error("文件读取失败", file_path=str(file_path), error=str(e))
            return None
    
    def _create_error_result(self, error_message: str) -> ParseResult:
        """创建错误结果"""
        return ParseResult(
            success=False,
            fund_report=None,
            parser_type=ParserType.HTML_LEGACY,  # 默认类型
            errors=[error_message],
            warnings=[],
            metadata={}
        )
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """获取质量指标"""
        # 检查质量阈值并获取告警
        recent_alerts = self.alert_system.check_quality_thresholds(self.quality_collector)
        
        return {
            'parsing_metrics': self.metrics,
            'quality_metrics': self.quality_collector.get_recent_metrics(),
            'recent_alerts': recent_alerts
        }
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """生成质量报告"""
        from src.parsers.data_quality import QualityReportGenerator
        
        report_generator = QualityReportGenerator()
        return report_generator.generate_daily_report(self.quality_collector)
    
    def get_llm_usage_stats(self) -> Dict[str, Any]:
        """获取LLM使用统计"""
        if self.llm_assistant:
            # OllamaLLMAssistant 暂时没有使用统计功能，返回基本信息
            return {
                'llm_enabled': True,
                'model': getattr(self.llm_assistant, 'model', 'unknown'),
                'base_url': getattr(self.llm_assistant, 'base_url', 'unknown'),
                'status': 'available'
            }
        return {'llm_enabled': False}
    
    def configure_quality_thresholds(self, **kwargs):
        """配置质量阈值"""
        self.alert_system.update_thresholds(**kwargs)
        self.logger.info("质量阈值已更新", thresholds=kwargs)


# 保持向后兼容性
# XBRLParserFacade is now the main class
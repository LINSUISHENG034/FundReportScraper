"""
XBRL解析器统一接口 - 提供统一的解析入口和路由机制
XBRL Parser Facade - provides unified parsing interface and routing mechanism
"""

import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.core.logging import get_logger
from src.models.fund_data import FundReport
from src.parsers.base_parser import BaseParser, ParseResult, ParserType
from src.parsers.format_detector import FormatDetector, DocumentFormat


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
    """XBRL解析器统一接口"""
    
    def __init__(self, enable_ai_enhancement: bool = True):
        self.logger = get_logger("parser_facade")
        self.format_detector = FormatDetector()
        self.enable_ai_enhancement = enable_ai_enhancement
        
        # 解析器注册表
        self._parsers: Dict[ParserType, BaseParser] = {}
        self._format_parser_mapping: Dict[DocumentFormat, List[ParserType]] = {
            DocumentFormat.XBRL: [ParserType.XBRL_NATIVE],
            DocumentFormat.IXBRL: [ParserType.XBRL_NATIVE, ParserType.HTML_LEGACY],
            DocumentFormat.HTML: [ParserType.HTML_LEGACY],
            DocumentFormat.UNKNOWN: [ParserType.HTML_LEGACY]
        }
        
        # 性能指标
        self.metrics = ParsingMetrics()
        
        # 初始化解析器
        self._initialize_parsers()
    
    def _initialize_parsers(self):
        """初始化所有可用的解析器"""
        try:
            # 延迟导入以避免循环依赖
            from src.parsers.arelle_xbrl_parser import ArelleXBRLParser
            self.register_parser(ParserType.XBRL_NATIVE, ArelleXBRLParser())
            self.logger.info("XBRL原生解析器已注册")
        except ImportError as e:
            self.logger.warning("无法加载XBRL原生解析器", error=str(e))
        
        try:
            from src.parsers.optimized_html_parser import OptimizedHTMLParser
            self.register_parser(ParserType.HTML_LEGACY, OptimizedHTMLParser())
            self.logger.info("HTML解析器已注册")
        except ImportError as e:
            self.logger.warning("无法加载HTML解析器", error=str(e))
        
        if self.enable_ai_enhancement:
            try:
                from src.parsers.ai_enhanced_parser import AIEnhancedParser
                self.register_parser(ParserType.AI_ENHANCED, AIEnhancedParser())
                self.logger.info("AI增强解析器已注册")
            except ImportError as e:
                self.logger.warning("无法加载AI增强解析器", error=str(e))
    
    def register_parser(self, parser_type: ParserType, parser: BaseParser):
        """
        注册解析器
        
        Args:
            parser_type: 解析器类型
            parser: 解析器实例
        """
        self._parsers[parser_type] = parser
        self.logger.debug("解析器已注册", parser_type=parser_type.value)
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """
        解析文件的统一入口
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParseResult: 解析结果
        """
        start_time = time.time()
        
        try:
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
            
            # 解析文件
            parse_result = self.parse_content(content, file_path, detected_format)
            
            # 更新性能指标
            processing_time = time.time() - start_time
            self.metrics.update_metrics(parse_result, processing_time, detected_format.value)
            
            # 添加格式检测信息到元数据
            parse_result.metadata.update({
                "detected_format": detected_format.value,
                "format_details": format_details,
                "processing_time": processing_time
            })
            
            return parse_result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error("文件解析异常", file_path=str(file_path), error=str(e))
            
            error_result = self._create_error_result(f"解析异常: {str(e)}")
            self.metrics.update_metrics(error_result, processing_time, "error")
            
            return error_result
    
    def parse_content(self, 
                     content: str, 
                     file_path: Optional[Path] = None,
                     format_hint: Optional[DocumentFormat] = None) -> ParseResult:
        """
        解析内容的统一入口
        
        Args:
            content: 文件内容
            file_path: 文件路径（可选）
            format_hint: 格式提示（可选）
            
        Returns:
            ParseResult: 解析结果
        """
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
        if self.enable_ai_enhancement and ParserType.AI_ENHANCED in self._parsers:
            try:
                ai_parser = self._parsers[ParserType.AI_ENHANCED]
                self.logger.info("尝试AI增强解析")
                result = ai_parser.parse_content(content, file_path)
                
                if result.success:
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
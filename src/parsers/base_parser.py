"""
基础解析器抽象类和相关异常定义
Base parser abstract class and related exception definitions
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from src.core.logging import get_logger
from src.models.fund_data import FundReport


class ParseError(Exception):
    """解析错误基类"""
    pass


class XBRLFormatError(ParseError):
    """XBRL格式错误"""
    pass


class DataExtractionError(ParseError):
    """数据提取错误"""
    pass


class ValidationError(ParseError):
    """数据验证错误"""
    pass


class ParserType(Enum):
    """解析器类型枚举"""
    XBRL_NATIVE = "xbrl_native"
    HTML_LEGACY = "html_legacy"
    AI_ENHANCED = "ai_enhanced"


@dataclass
class ParseResult:
    """解析结果数据类"""
    success: bool
    fund_report: Optional[FundReport]
    parser_type: ParserType
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    
    @property
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0


@dataclass
class ValidationResult:
    """数据验证结果"""
    is_valid: bool
    missing_required_fields: List[str]
    invalid_fields: List[str]
    warnings: List[str]
    completeness_score: float  # 0.0 - 1.0
    
    @property
    def has_critical_issues(self) -> bool:
        """是否有关键问题"""
        return len(self.missing_required_fields) > 0 or len(self.invalid_fields) > 0


class BaseParser(ABC):
    """解析器抽象基类"""
    
    def __init__(self, parser_type: ParserType):
        self.parser_type = parser_type
        self.logger = get_logger(f"parser.{parser_type.value}")
        self._required_fields = [
            "fund_code", "fund_name", "net_asset_value", "total_net_assets"
        ]
    
    @abstractmethod
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """
        检查是否能够解析给定的内容
        
        Args:
            content: 文件内容
            file_path: 文件路径（可选）
            
        Returns:
            bool: 是否能够解析
        """
        pass
    
    @abstractmethod
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """
        解析内容并返回解析结果
        
        Args:
            content: 文件内容
            file_path: 文件路径（可选）
            
        Returns:
            ParseResult: 解析结果
        """
        pass
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """
        解析文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParseResult: 解析结果
        """
        try:
            content = self._read_file_with_encoding(file_path)
            if not content:
                return ParseResult(
                    success=False,
                    fund_report=None,
                    parser_type=self.parser_type,
                    errors=[f"无法读取文件: {file_path}"],
                    warnings=[],
                    metadata={"file_path": str(file_path)}
                )
            
            return self.parse_content(content, file_path)
            
        except Exception as e:
            self.logger.error("文件解析失败", file_path=str(file_path), error=str(e))
            return ParseResult(
                success=False,
                fund_report=None,
                parser_type=self.parser_type,
                errors=[f"文件解析异常: {str(e)}"],
                warnings=[],
                metadata={"file_path": str(file_path)}
            )
    
    def validate_result(self, fund_report: FundReport) -> ValidationResult:
        """
        验证解析结果的数据质量
        
        Args:
            fund_report: 基金报告对象
            
        Returns:
            ValidationResult: 验证结果
        """
        missing_fields = []
        invalid_fields = []
        warnings = []
        
        # 检查必需字段
        for field in self._required_fields:
            value = getattr(fund_report, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)
        
        # 检查数值字段的有效性
        if fund_report.net_asset_value is not None:
            if fund_report.net_asset_value <= 0:
                invalid_fields.append("net_asset_value: 必须大于0")
        
        if fund_report.total_net_assets is not None:
            if fund_report.total_net_assets <= 0:
                invalid_fields.append("total_net_assets: 必须大于0")
        
        # 检查基金代码格式
        if fund_report.fund_code:
            if not fund_report.fund_code.isdigit() or len(fund_report.fund_code) != 6:
                warnings.append("基金代码格式可能不正确")
        
        # 计算完整性得分
        total_fields = len(self._required_fields)
        valid_fields = total_fields - len(missing_fields)
        completeness_score = valid_fields / total_fields if total_fields > 0 else 0.0
        
        # 考虑表格数据的完整性
        table_bonus = 0.0
        if fund_report.asset_allocations and len(fund_report.asset_allocations) > 0:
            table_bonus += 0.1
        if fund_report.top_holdings and len(fund_report.top_holdings) > 0:
            table_bonus += 0.1
        if fund_report.industry_allocations and len(fund_report.industry_allocations) > 0:
            table_bonus += 0.1
        
        completeness_score = min(1.0, completeness_score + table_bonus)
        
        return ValidationResult(
            is_valid=len(missing_fields) == 0 and len(invalid_fields) == 0,
            missing_required_fields=missing_fields,
            invalid_fields=invalid_fields,
            warnings=warnings,
            completeness_score=completeness_score
        )
    
    def _read_file_with_encoding(self, file_path: Path) -> Optional[str]:
        """
        自动检测编码并读取文件
        
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
            self.logger.warning("文件读取失败", file_path=str(file_path), error=str(e))
            return None
    
    def _create_success_result(self, 
                             fund_report: FundReport, 
                             file_path: Optional[Path] = None,
                             warnings: List[str] = None) -> ParseResult:
        """
        创建成功的解析结果
        
        Args:
            fund_report: 基金报告对象
            file_path: 文件路径
            warnings: 警告信息列表
            
        Returns:
            ParseResult: 解析结果
        """
        validation_result = self.validate_result(fund_report)
        
        metadata = {
            "completeness_score": validation_result.completeness_score,
            "validation_warnings": validation_result.warnings
        }
        
        if file_path:
            metadata["file_path"] = str(file_path)
        
        return ParseResult(
            success=True,
            fund_report=fund_report,
            parser_type=self.parser_type,
            errors=[],
            warnings=(warnings or []) + validation_result.warnings,
            metadata=metadata
        )
    
    def _create_error_result(self, 
                           error_message: str, 
                           file_path: Optional[Path] = None,
                           warnings: List[str] = None) -> ParseResult:
        """
        创建错误的解析结果
        
        Args:
            error_message: 错误信息
            file_path: 文件路径
            warnings: 警告信息列表
            
        Returns:
            ParseResult: 解析结果
        """
        metadata = {}
        if file_path:
            metadata["file_path"] = str(file_path)
        
        return ParseResult(
            success=False,
            fund_report=None,
            parser_type=self.parser_type,
            errors=[error_message],
            warnings=warnings or [],
            metadata=metadata
        )
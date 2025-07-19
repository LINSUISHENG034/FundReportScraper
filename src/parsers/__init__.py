"""Parsers package initialization."""

# 新的解析器系统
from .parser_facade import XBRLParserFacade
from .base_parser import BaseParser, ParseResult, ParserType
from .format_detector import FormatDetector, DocumentFormat

# 尝试导入具体的解析器实现
try:
    from .optimized_html_parser import OptimizedHTMLParser
except ImportError:
    OptimizedHTMLParser = None

try:
    from .arelle_parser import ArelleParser
except ImportError:
    ArelleParser = None

__all__ = [
    "XBRLParserFacade", 
    "BaseParser", 
    "ParseResult", 
    "ParserType",
    "FormatDetector", 
    "DocumentFormat",
    "OptimizedHTMLParser",
    "ArelleParser"
]

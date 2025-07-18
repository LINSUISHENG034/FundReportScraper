"""XBRL解析引擎核心模块

本模块包含增强型XBRL解析引擎的核心组件：
- TaxonomyManager: 分类标准管理器
- XBRLContext: 上下文解析器
- FactExtractor: 事实提取器
"""

from .taxonomy_manager import TaxonomyManager
from .xbrl_context import XBRLContext
from .fact_extractor import FactExtractor

__all__ = [
    'TaxonomyManager',
    'XBRLContext', 
    'FactExtractor'
]
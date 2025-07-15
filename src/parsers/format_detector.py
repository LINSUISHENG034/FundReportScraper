"""
格式检测器 - 自动识别文件格式并路由到相应的解析器
Format detector - automatically identify file format and route to appropriate parser
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

from src.core.logging import get_logger


class DocumentFormat(Enum):
    """文档格式枚举"""
    XBRL = "xbrl"           # 标准XBRL格式
    IXBRL = "ixbrl"         # 内联XBRL格式
    HTML = "html"           # HTML格式
    UNKNOWN = "unknown"     # 未知格式


class FormatDetector:
    """格式检测器"""
    
    def __init__(self):
        self.logger = get_logger("format_detector")
        
        # XBRL格式特征
        self.xbrl_patterns = [
            r'<xbrl[^>]*xmlns[^>]*>',
            r'<xbrli:xbrl[^>]*>',
            r'xmlns:xbrli=',
            r'http://www\.xbrl\.org/2003/instance',
            r'<context[^>]*id=',
            r'<unit[^>]*id=',
            r'<fact[^>]*>'
        ]
        
        # iXBRL格式特征
        self.ixbrl_patterns = [
            r'<html[^>]*xmlns:ix[^>]*>',
            r'xmlns:ix=',
            r'http://www\.xbrl\.org/2013/inlineXBRL',
            r'<ix:[^>]*>',
            r'ix:name=',
            r'ix:format=',
            r'<ix:nonNumeric[^>]*>',
            r'<ix:nonFraction[^>]*>'
        ]
        
        # HTML格式特征
        self.html_patterns = [
            r'<!DOCTYPE html',
            r'<html[^>]*>',
            r'<head[^>]*>',
            r'<body[^>]*>',
            r'<table[^>]*>',
            r'<div[^>]*>'
        ]
        
        # 基金报告特征关键词
        self.fund_report_keywords = [
            "基金代码", "基金名称", "基金简称", "份额净值", "资产净值",
            "前十大", "重仓股", "资产配置", "行业配置", "投资组合",
            "基金管理人", "基金托管人", "报告期", "季度报告", "年度报告"
        ]
    
    def detect_format(self, content: str, file_path: Optional[Path] = None) -> DocumentFormat:
        """
        检测文档格式
        
        Args:
            content: 文档内容
            file_path: 文件路径（可选，用于辅助判断）
            
        Returns:
            DocumentFormat: 检测到的格式
        """
        if not content or not content.strip():
            return DocumentFormat.UNKNOWN
        
        # 预处理内容 - 取前10000字符进行检测以提高性能
        content_sample = content[:10000].lower()
        
        # 检测XBRL格式
        if self._match_patterns(content_sample, self.xbrl_patterns):
            self.logger.debug("检测到XBRL格式", file_path=str(file_path) if file_path else None)
            return DocumentFormat.XBRL
        
        # 检测iXBRL格式
        if self._match_patterns(content_sample, self.ixbrl_patterns):
            self.logger.debug("检测到iXBRL格式", file_path=str(file_path) if file_path else None)
            return DocumentFormat.IXBRL
        
        # 检测HTML格式
        if self._match_patterns(content_sample, self.html_patterns):
            # 进一步验证是否为基金报告
            if self._contains_fund_keywords(content_sample):
                self.logger.debug("检测到HTML基金报告格式", file_path=str(file_path) if file_path else None)
                return DocumentFormat.HTML
            else:
                self.logger.warning("检测到HTML格式但不包含基金报告关键词", 
                                  file_path=str(file_path) if file_path else None)
                return DocumentFormat.HTML  # 仍然返回HTML，让解析器处理
        
        # 基于文件扩展名的辅助判断
        if file_path:
            ext = file_path.suffix.lower()
            if ext in ['.xbrl', '.xml']:
                # 可能是XBRL但格式不标准
                self.logger.debug("基于文件扩展名推断为XBRL格式", file_path=str(file_path))
                return DocumentFormat.XBRL
            elif ext in ['.html', '.htm']:
                self.logger.debug("基于文件扩展名推断为HTML格式", file_path=str(file_path))
                return DocumentFormat.HTML
        
        self.logger.warning("无法识别文档格式", file_path=str(file_path) if file_path else None)
        return DocumentFormat.UNKNOWN
    
    def get_format_confidence(self, content: str, file_path: Optional[Path] = None) -> Dict[DocumentFormat, float]:
        """
        获取各种格式的置信度分数
        
        Args:
            content: 文档内容
            file_path: 文件路径（可选）
            
        Returns:
            Dict[DocumentFormat, float]: 格式置信度字典
        """
        if not content or not content.strip():
            return {fmt: 0.0 for fmt in DocumentFormat}
        
        content_sample = content[:10000].lower()
        confidence_scores = {}
        
        # XBRL格式置信度
        xbrl_matches = sum(1 for pattern in self.xbrl_patterns 
                          if re.search(pattern, content_sample, re.IGNORECASE))
        confidence_scores[DocumentFormat.XBRL] = min(1.0, xbrl_matches / len(self.xbrl_patterns))
        
        # iXBRL格式置信度
        ixbrl_matches = sum(1 for pattern in self.ixbrl_patterns 
                           if re.search(pattern, content_sample, re.IGNORECASE))
        confidence_scores[DocumentFormat.IXBRL] = min(1.0, ixbrl_matches / len(self.ixbrl_patterns))
        
        # HTML格式置信度
        html_matches = sum(1 for pattern in self.html_patterns 
                          if re.search(pattern, content_sample, re.IGNORECASE))
        html_confidence = min(1.0, html_matches / len(self.html_patterns))
        
        # 如果是HTML，检查基金报告关键词以提高置信度
        if html_confidence > 0.3:
            fund_keyword_matches = sum(1 for keyword in self.fund_report_keywords 
                                     if keyword in content_sample)
            fund_confidence = min(1.0, fund_keyword_matches / len(self.fund_report_keywords))
            html_confidence = min(1.0, html_confidence + fund_confidence * 0.3)
        
        confidence_scores[DocumentFormat.HTML] = html_confidence
        
        # 文件扩展名加成
        if file_path:
            ext = file_path.suffix.lower()
            if ext in ['.xbrl', '.xml']:
                confidence_scores[DocumentFormat.XBRL] += 0.2
            elif ext in ['.html', '.htm']:
                confidence_scores[DocumentFormat.HTML] += 0.2
        
        # 归一化置信度分数
        for fmt in confidence_scores:
            confidence_scores[fmt] = min(1.0, confidence_scores[fmt])
        
        confidence_scores[DocumentFormat.UNKNOWN] = 1.0 - max(confidence_scores.values())
        
        return confidence_scores
    
    def is_fund_report(self, content: str) -> bool:
        """
        判断是否为基金报告文档
        
        Args:
            content: 文档内容
            
        Returns:
            bool: 是否为基金报告
        """
        if not content:
            return False
        
        content_sample = content[:5000].lower()
        keyword_matches = sum(1 for keyword in self.fund_report_keywords 
                            if keyword in content_sample)
        
        # 至少匹配3个关键词才认为是基金报告
        return keyword_matches >= 3
    
    def _match_patterns(self, content: str, patterns: list) -> bool:
        """
        检查内容是否匹配给定的模式列表
        
        Args:
            content: 内容
            patterns: 模式列表
            
        Returns:
            bool: 是否匹配
        """
        matches = sum(1 for pattern in patterns 
                     if re.search(pattern, content, re.IGNORECASE))
        
        # 至少匹配一半的模式才认为是该格式
        return matches >= len(patterns) * 0.5
    
    def _contains_fund_keywords(self, content: str) -> bool:
        """
        检查内容是否包含基金报告关键词
        
        Args:
            content: 内容
            
        Returns:
            bool: 是否包含关键词
        """
        keyword_matches = sum(1 for keyword in self.fund_report_keywords 
                            if keyword in content)
        
        # 至少匹配2个关键词
        return keyword_matches >= 2
    
    def get_format_details(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        获取格式检测的详细信息
        
        Args:
            content: 文档内容
            file_path: 文件路径（可选）
            
        Returns:
            Dict[str, Any]: 详细信息
        """
        detected_format = self.detect_format(content, file_path)
        confidence_scores = self.get_format_confidence(content, file_path)
        is_fund_report = self.is_fund_report(content)
        
        return {
            "detected_format": detected_format,
            "confidence_scores": confidence_scores,
            "is_fund_report": is_fund_report,
            "file_extension": file_path.suffix.lower() if file_path else None,
            "content_length": len(content),
            "sample_length": min(10000, len(content))
        }
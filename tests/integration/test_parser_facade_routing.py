"""ParserFacade路由逻辑集成测试

本测试文件验证ParserFacade的新路由逻辑是否按预期工作。
使用Mock来模拟各个解析器组件的行为。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.parsers.parser_facade import XBRLParserFacade
from src.parsers.base_parser import ParseResult, ParserType
from src.parsers.format_detector import DocumentFormat
from src.models.enhanced_fund_data import ComprehensiveFundReport


class TestParserFacadeRouting:
    """ParserFacade路由逻辑测试类"""
    
    @pytest.fixture
    def facade(self):
        """创建ParserFacade实例"""
        return XBRLParserFacade()
    
    @pytest.fixture
    def mock_success_result(self):
        """创建成功的解析结果"""
        return ParseResult(
            success=True,
            fund_report=Mock(spec=ComprehensiveFundReport),
            parser_type=ParserType.XBRL_NATIVE,
            errors=[],
            warnings=[],
            metadata={}
        )
    
    @pytest.fixture
    def mock_failure_result(self):
        """创建失败的解析结果"""
        return ParseResult(
            success=False,
            fund_report=None,
            parser_type=ParserType.XBRL_NATIVE,
            errors=["解析失败"],
            warnings=[],
            metadata={}
        )
    
    @pytest.mark.parametrize("format_type,expected_calls", [
        (DocumentFormat.IXBRL, "ixbrl_path"),
        (DocumentFormat.XBRL, "xbrl_path"),
        (DocumentFormat.HTML, "html_path"),
        (DocumentFormat.UNKNOWN, "html_path")
    ])
    @patch('src.parsers.parser_facade.XBRLParserFacade._enhance_parsing_result')
    async def test_routing_logic_success_paths(self, mock_enhance, facade, mock_success_result, format_type, expected_calls):
        """测试不同格式的成功路由路径"""
        # 设置mock返回值
        mock_enhance.return_value = mock_success_result
        
        # Mock各个解析器
        mock_arelle_parser = Mock()
        mock_arelle_parser.parse_content.return_value = mock_success_result
        facade._parsers[ParserType.XBRL_NATIVE] = mock_arelle_parser
        
        mock_html_parser = Mock()
        mock_html_parser.parse_content.return_value = mock_success_result
        facade._parsers[ParserType.HTML_LEGACY] = mock_html_parser
        
        # Mock iXBRL提取器
        facade.ixbrl_extractor.extract_to_string = Mock(return_value="<xbrl>extracted content</xbrl>")
        
        # 执行测试
        content = "test content"
        result = await facade.parse_content_async(content, format_hint=format_type)
        
        # 验证结果
        assert result.success
        
        # 验证调用次数
        if expected_calls == "ixbrl_path":
            # iXBRL路径：应该调用提取器和Arelle解析器
            facade.ixbrl_extractor.extract_to_string.assert_called_once_with(content)
            mock_arelle_parser.parse_content.assert_called_once()
            mock_html_parser.parse_content.assert_not_called()
        elif expected_calls == "xbrl_path":
            # 纯XBRL路径：应该直接调用Arelle解析器
            facade.ixbrl_extractor.extract_to_string.assert_not_called()
            mock_arelle_parser.parse_content.assert_called_once_with(content, None)
            mock_html_parser.parse_content.assert_not_called()
        elif expected_calls == "html_path":
            # HTML路径：应该调用HTML解析器
            facade.ixbrl_extractor.extract_to_string.assert_not_called()
            mock_arelle_parser.parse_content.assert_not_called()
            mock_html_parser.parse_content.assert_called_once_with(content, None)
    
    @patch('src.parsers.parser_facade.XBRLParserFacade._enhance_parsing_result')
    async def test_ixbrl_extraction_failure_fallback(self, mock_enhance, facade, mock_success_result):
        """测试iXBRL提取失败时的降级路径"""
        # 设置mock返回值
        mock_enhance.return_value = mock_success_result
        
        # Mock HTML解析器成功
        mock_html_parser = Mock()
        mock_html_parser.parse_content.return_value = mock_success_result
        facade._parsers[ParserType.HTML_LEGACY] = mock_html_parser
        
        # Mock iXBRL提取器失败
        facade.ixbrl_extractor.extract_to_string = Mock(return_value=None)
        
        # 执行测试
        content = "test ixbrl content"
        result = await facade.parse_content_async(content, format_hint=DocumentFormat.IXBRL)
        
        # 验证结果
        assert result.success
        
        # 验证调用次数
        facade.ixbrl_extractor.extract_to_string.assert_called_once_with(content)
        mock_html_parser.parse_content.assert_called_once_with(content, None)
    
    @patch('src.parsers.parser_facade.XBRLParserFacade._enhance_parsing_result')
    async def test_arelle_parser_failure_fallback(self, mock_enhance, facade, mock_failure_result, mock_success_result):
        """测试Arelle解析器失败时的降级路径"""
        # 设置mock返回值
        mock_enhance.return_value = mock_success_result
        
        # Mock Arelle解析器失败
        mock_arelle_parser = Mock()
        mock_arelle_parser.parse_content.return_value = mock_failure_result
        facade._parsers[ParserType.XBRL_NATIVE] = mock_arelle_parser
        
        # Mock HTML解析器成功
        mock_html_parser = Mock()
        mock_html_parser.parse_content.return_value = mock_success_result
        facade._parsers[ParserType.HTML_LEGACY] = mock_html_parser
        
        # Mock iXBRL提取器成功
        facade.ixbrl_extractor.extract_to_string = Mock(return_value="<xbrl>extracted content</xbrl>")
        
        # 执行测试
        content = "test ixbrl content"
        result = await facade.parse_content_async(content, format_hint=DocumentFormat.IXBRL)
        
        # 验证结果
        assert result.success
        
        # 验证调用次数
        facade.ixbrl_extractor.extract_to_string.assert_called_once_with(content)
        mock_arelle_parser.parse_content.assert_called_once()
        mock_html_parser.parse_content.assert_called_once_with(content, None)
    
    async def test_all_parsers_fail(self, facade, mock_failure_result):
        """测试所有解析器都失败的情况"""
        # Mock所有解析器都失败
        mock_arelle_parser = Mock()
        mock_arelle_parser.parse_content.return_value = mock_failure_result
        facade._parsers[ParserType.XBRL_NATIVE] = mock_arelle_parser
        
        mock_html_parser = Mock()
        mock_html_parser.parse_content.return_value = mock_failure_result
        facade._parsers[ParserType.HTML_LEGACY] = mock_html_parser
        
        # Mock iXBRL提取器失败
        facade.ixbrl_extractor.extract_to_string = Mock(return_value=None)
        
        # 执行测试
        content = "test content"
        result = await facade.parse_content_async(content, format_hint=DocumentFormat.IXBRL)
        
        # 验证结果
        assert not result.success
        assert "All parsing attempts failed." in result.errors
    
    async def test_format_detection_when_no_hint(self, facade, mock_success_result):
        """测试没有格式提示时的自动检测"""
        # Mock格式检测器
        facade.format_detector.detect_format = Mock(return_value=DocumentFormat.XBRL)
        
        # Mock Arelle解析器成功
        mock_arelle_parser = Mock()
        mock_arelle_parser.parse_content.return_value = mock_success_result
        facade._parsers[ParserType.XBRL_NATIVE] = mock_arelle_parser
        
        # Mock _enhance_parsing_result
        with patch.object(facade, '_enhance_parsing_result', return_value=mock_success_result):
            # 执行测试
            content = "test content"
            result = await facade.parse_content_async(content)  # 没有format_hint
            
            # 验证结果
            assert result.success
            
            # 验证格式检测被调用
            facade.format_detector.detect_format.assert_called_once_with(content, None)
            
            # 验证Arelle解析器被调用
            mock_arelle_parser.parse_content.assert_called_once_with(content, None)
    
    async def test_empty_content_handling(self, facade):
        """测试空内容的处理"""
        # 测试空字符串
        result = await facade.parse_content_async("")
        assert not result.success
        assert "内容为空" in result.errors
        
        # 测试只有空白字符的字符串
        result = await facade.parse_content_async("   \n\t   ")
        assert not result.success
        assert "内容为空" in result.errors
    
    async def test_missing_parsers_handling(self, facade):
        """测试缺少解析器时的处理"""
        # 清空所有解析器
        facade._parsers.clear()
        
        # 执行测试
        content = "test content"
        result = await facade.parse_content_async(content, format_hint=DocumentFormat.XBRL)
        
        # 验证结果
        assert not result.success
        assert "All parsing attempts failed." in result.errors
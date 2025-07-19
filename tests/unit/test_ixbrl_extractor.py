"""Unit tests for iXBRLExtractor module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.parsers.xbrl.ixbrl_extractor import iXBRLExtractor


class TestiXBRLExtractor:
    """Test cases for iXBRLExtractor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = iXBRLExtractor()
        
        # Sample iXBRL HTML content with embedded XBRL
        self.valid_ixbrl_content = """
        <!DOCTYPE html>
        <html>
        <head><title>XBRL Report</title></head>
        <body>
            <div>Some HTML content</div>
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                <context id="ctx1">
                    <entity>
                        <identifier scheme="http://example.com">123456</identifier>
                    </entity>
                    <period>
                        <instant>2023-12-31</instant>
                    </period>
                </context>
                <unit id="usd">
                    <measure>iso4217:USD</measure>
                </unit>
                <fact contextRef="ctx1" unitRef="usd">1000000</fact>
            </xbrl>
        </body>
        </html>
        """
        
        # Sample pure HTML content without XBRL
        self.pure_html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Regular HTML Page</title></head>
        <body>
            <div>This is just regular HTML content</div>
            <p>No XBRL data here</p>
        </body>
        </html>
        """
        
        # Sample XML content without XBRL
        self.pure_xml_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <root>
            <data>Some XML data</data>
            <item>Another item</item>
        </root>
        """
        
        # Sample iXBRL with multiple XBRL instances
        self.multiple_xbrl_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Multiple XBRL Report</title></head>
        <body>
            <div>First section</div>
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                <context id="ctx1">
                    <entity>
                        <identifier scheme="http://example.com">111111</identifier>
                    </entity>
                </context>
                <fact contextRef="ctx1">First XBRL</fact>
            </xbrl>
            <div>Second section</div>
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                <context id="ctx2">
                    <entity>
                        <identifier scheme="http://example.com">222222</identifier>
                    </entity>
                </context>
                <fact contextRef="ctx2">Second XBRL</fact>
            </xbrl>
        </body>
        </html>
        """
        
        # Malformed HTML content
        self.malformed_html_content = """
        <html>
        <head><title>Malformed HTML</title>
        <body>
            <div>Missing closing tags
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                <fact>Some data</fact>
            </xbrl>
        </body>
        """
    
    def test_init(self):
        """Test iXBRLExtractor initialization."""
        extractor = iXBRLExtractor()
        assert extractor.html_parser is not None
        # HTMLParser is properly initialized
        assert str(type(extractor.html_parser)) == "<class 'lxml.etree.HTMLParser'>"
    
    def test_extract_to_string_success(self):
        """Test successful XBRL extraction to string."""
        result = self.extractor.extract_to_string(self.valid_ixbrl_content)
        
        assert result is not None
        assert isinstance(result, str)
        assert '<?xml version=' in result
        assert 'xmlns="http://www.xbrl.org/2003/instance"' in result
        assert '<context id="ctx1">' in result
        # Note: lxml may normalize attribute names to lowercase
        assert '<fact contextref="ctx1" unitref="usd">1000000</fact>' in result
    
    def test_extract_to_string_pure_html(self):
        """Test extraction from pure HTML without XBRL returns None."""
        result = self.extractor.extract_to_string(self.pure_html_content)
        assert result is None
    
    def test_extract_to_string_pure_xml(self):
        """Test extraction from pure XML without XBRL returns None."""
        result = self.extractor.extract_to_string(self.pure_xml_content)
        assert result is None
    
    def test_extract_to_string_multiple_xbrl_instances(self):
        """Test extraction with multiple XBRL instances returns first one."""
        result = self.extractor.extract_to_string(self.multiple_xbrl_content)
        
        assert result is not None
        assert isinstance(result, str)
        assert '<?xml version=' in result
        assert 'xmlns="http://www.xbrl.org/2003/instance"' in result
        # Should contain the first XBRL instance (lxml may normalize attribute names)
        assert '<fact contextref="ctx1">First XBRL</fact>' in result
        # Should not contain the second XBRL instance
        assert '<fact contextref="ctx2">Second XBRL</fact>' not in result
    
    def test_extract_to_string_malformed_html(self):
        """Test extraction from malformed HTML with recover=True."""
        result = self.extractor.extract_to_string(self.malformed_html_content)
        
        # Should still work due to recover=True in HTMLParser
        assert result is not None
        assert isinstance(result, str)
        assert '<?xml version=' in result
        assert 'xmlns="http://www.xbrl.org/2003/instance"' in result
        assert '<fact>Some data</fact>' in result
    
    def test_extract_to_string_invalid_content(self):
        """Test extraction with invalid content returns None."""
        # Test with empty string
        result = self.extractor.extract_to_string("")
        assert result is None
        
        # Test with completely invalid content
        result = self.extractor.extract_to_string("invalid content")
        assert result is None
        
        # Test with content that causes parsing errors
        with patch('lxml.etree.fromstring', side_effect=Exception("Parsing error")):
            result = self.extractor.extract_to_string(self.valid_ixbrl_content)
            assert result is None
    
    def test_extract_to_tempfile_success(self):
        """Test successful XBRL extraction to temporary file."""
        result_path = self.extractor.extract_to_tempfile(self.valid_ixbrl_content)
        
        try:
            assert result_path is not None
            assert isinstance(result_path, Path)
            assert result_path.exists()
            assert result_path.suffix == '.xbrl'
            
            # Read the file content and verify
            content = result_path.read_text(encoding='utf-8')
            assert '<?xml version=' in content
            assert 'xmlns="http://www.xbrl.org/2003/instance"' in content
            assert '<context id="ctx1">' in content
            # Note: lxml may normalize attribute names to lowercase
            assert '<fact contextref="ctx1" unitref="usd">1000000</fact>' in content
        finally:
            # Clean up the temporary file
            if result_path and result_path.exists():
                result_path.unlink()
    
    def test_extract_to_tempfile_no_xbrl(self):
        """Test extraction to tempfile with no XBRL content returns None."""
        result_path = self.extractor.extract_to_tempfile(self.pure_html_content)
        assert result_path is None
    
    def test_extract_to_tempfile_cleanup(self):
        """Test that temporary files are properly created and can be cleaned up."""
        result_path = self.extractor.extract_to_tempfile(self.valid_ixbrl_content)
        
        assert result_path is not None
        assert result_path.exists()
        
        # Verify we can delete the file (proper cleanup)
        result_path.unlink()
        assert not result_path.exists()
    
    def test_extract_to_tempfile_file_creation_error(self):
        """Test handling of file creation errors."""
        # Mock tempfile.NamedTemporaryFile to raise an exception
        with patch('tempfile.NamedTemporaryFile', side_effect=Exception("File creation error")):
            result_path = self.extractor.extract_to_tempfile(self.valid_ixbrl_content)
            assert result_path is None
    
    def test_xpath_expressions(self):
        """Test that both XPath expressions work correctly."""
        # Test content with XBRL in body
        body_xbrl_content = """
        <html>
        <body>
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                <fact>Body XBRL</fact>
            </xbrl>
        </body>
        </html>
        """
        
        # Test content with XBRL outside body
        root_xbrl_content = """
        <html>
        <xbrl xmlns="http://www.xbrl.org/2003/instance">
            <fact>Root XBRL</fact>
        </xbrl>
        <body>
            <div>Some content</div>
        </body>
        </html>
        """
        
        # Both should work
        result1 = self.extractor.extract_to_string(body_xbrl_content)
        result2 = self.extractor.extract_to_string(root_xbrl_content)
        
        assert result1 is not None
        assert result2 is not None
        assert '<fact>Body XBRL</fact>' in result1
        assert '<fact>Root XBRL</fact>' in result2
    
    def test_boundary_cases(self):
        """Test various boundary cases."""
        # Empty XBRL element
        empty_xbrl_content = """
        <html>
        <body>
            <xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>
        </body>
        </html>
        """
        
        result = self.extractor.extract_to_string(empty_xbrl_content)
        assert result is not None
        assert 'xmlns="http://www.xbrl.org/2003/instance"' in result
        
        # XBRL with only whitespace
        whitespace_xbrl_content = """
        <html>
        <body>
            <xbrl xmlns="http://www.xbrl.org/2003/instance">
                
            </xbrl>
        </body>
        </html>
        """
        
        result = self.extractor.extract_to_string(whitespace_xbrl_content)
        assert result is not None
        assert 'xmlns="http://www.xbrl.org/2003/instance"' in result
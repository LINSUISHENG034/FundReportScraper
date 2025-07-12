"""
Tests for XBRL parser functionality.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from src.parsers.xbrl_parser import (
    XBRLParser, XBRLParseError, FundBasicInfo, AssetAllocation,
    TopHolding, IndustryAllocation
)


class TestXBRLParser:
    """Test XBRL parser implementation."""
    
    @pytest.fixture
    def sample_xbrl_content(self):
        """Sample XBRL content for testing."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:fund="http://example.com/fund"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    
    <context id="AsOf2023-12-31">
        <entity>
            <identifier scheme="http://www.csrc.gov.cn">000001</identifier>
        </entity>
        <period>
            <instant>2023-12-31</instant>
        </period>
    </context>
    
    <!-- Fund basic info -->
    <fund:FundCode contextRef="AsOf2023-12-31">000001</fund:FundCode>
    <fund:FundName contextRef="AsOf2023-12-31">华夏成长混合型证券投资基金</fund:FundName>
    <fund:NetAssetValue contextRef="AsOf2023-12-31" unitRef="CNY">15600000000</fund:NetAssetValue>
    <fund:TotalShares contextRef="AsOf2023-12-31" unitRef="shares">12000000000</fund:TotalShares>
    <fund:UnitNAV contextRef="AsOf2023-12-31" unitRef="CNY">1.3000</fund:UnitNAV>
    
    <!-- Asset allocation -->
    <fund:StockInvestments contextRef="AsOf2023-12-31" unitRef="CNY">10000000000</fund:StockInvestments>
    <fund:StockRatio contextRef="AsOf2023-12-31">0.6410</fund:StockRatio>
    <fund:BondInvestments contextRef="AsOf2023-12-31" unitRef="CNY">3000000000</fund:BondInvestments>
    <fund:BondRatio contextRef="AsOf2023-12-31">0.1923</fund:BondRatio>
    <fund:CashAndEquivalents contextRef="AsOf2023-12-31" unitRef="CNY">2600000000</fund:CashAndEquivalents>
    <fund:CashRatio contextRef="AsOf2023-12-31">0.1667</fund:CashRatio>
    
    <!-- Top holdings -->
    <fund:TopHoldings>
        <fund:Holding rank="1">
            <fund:StockCode>000858</fund:StockCode>
            <fund:StockName>五粮液</fund:StockName>
            <fund:MarketValue unitRef="CNY">800000000</fund:MarketValue>
            <fund:PortfolioRatio>0.0513</fund:PortfolioRatio>
        </fund:Holding>
        <fund:Holding rank="2">
            <fund:StockCode>000001</fund:StockCode>
            <fund:StockName>平安银行</fund:StockName>
            <fund:MarketValue unitRef="CNY">750000000</fund:MarketValue>
            <fund:PortfolioRatio>0.0481</fund:PortfolioRatio>
        </fund:Holding>
    </fund:TopHoldings>
    
    <!-- Industry allocation -->
    <fund:IndustryAllocation>
        <fund:Industry>
            <fund:IndustryName>制造业</fund:IndustryName>
            <fund:MarketValue unitRef="CNY">4500000000</fund:MarketValue>
            <fund:PortfolioRatio>0.2885</fund:PortfolioRatio>
        </fund:Industry>
        <fund:Industry>
            <fund:IndustryName>金融业</fund:IndustryName>
            <fund:MarketValue unitRef="CNY">3200000000</fund:MarketValue>
            <fund:PortfolioRatio>0.2051</fund:PortfolioRatio>
        </fund:Industry>
    </fund:IndustryAllocation>
    
</xbrl>'''
    
    @pytest.fixture
    def simple_xbrl_content(self):
        """Simple XBRL content with minimal data."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance">
    <FundCode>000002</FundCode>
    <FundName>易方达平稳增长混合</FundName>
    <ReportDate>2023-12-31</ReportDate>
</xbrl>'''
    
    @pytest.fixture
    def parser(self):
        """Create XBRLParser instance."""
        return XBRLParser()
    
    def test_initialization(self, parser):
        """Test parser initialization."""
        assert parser.namespaces == {}
        assert parser.root is None
        assert parser.fund_info is None
        assert "xbrl" in parser.common_namespaces
    
    def test_load_from_content_success(self, parser, sample_xbrl_content):
        """Test successful content loading."""
        parser.load_from_content(sample_xbrl_content)
        
        assert parser.root is not None
        assert parser.root.tag.endswith("xbrl")
        assert len(parser.namespaces) > 0
    
    def test_load_from_content_bytes(self, parser, sample_xbrl_content):
        """Test loading from bytes content."""
        bytes_content = sample_xbrl_content.encode('utf-8')
        parser.load_from_content(bytes_content)
        
        assert parser.root is not None
    
    def test_load_from_content_invalid_xml(self, parser):
        """Test loading invalid XML content."""
        invalid_content = "<xbrl><unclosed_tag></xbrl>"
        
        with pytest.raises(XBRLParseError) as exc_info:
            parser.load_from_content(invalid_content)
        
        assert "XML解析错误" in str(exc_info.value)
    
    def test_load_from_file_not_exists(self, parser, tmp_path):
        """Test loading from non-existent file."""
        non_existent_file = tmp_path / "non_existent.xbrl"
        
        with pytest.raises(XBRLParseError) as exc_info:
            parser.load_from_file(non_existent_file)
        
        assert "文件不存在" in str(exc_info.value)
    
    def test_load_from_file_success(self, parser, sample_xbrl_content, tmp_path):
        """Test successful file loading."""
        test_file = tmp_path / "test.xbrl"
        test_file.write_text(sample_xbrl_content, encoding='utf-8')
        
        parser.load_from_file(test_file)
        
        assert parser.root is not None
    
    def test_extract_fund_basic_info_no_data(self, parser):
        """Test extracting basic info when no data is loaded."""
        with pytest.raises(XBRLParseError) as exc_info:
            parser.extract_fund_basic_info()
        
        assert "尚未加载XBRL数据" in str(exc_info.value)
    
    def test_extract_fund_basic_info_success(self, parser, sample_xbrl_content):
        """Test successful basic info extraction."""
        parser.load_from_content(sample_xbrl_content)
        fund_info = parser.extract_fund_basic_info()
        
        assert fund_info is not None
        assert fund_info.fund_code == "000001"
        assert fund_info.fund_name == "华夏成长混合型证券投资基金"
        assert fund_info.net_asset_value == Decimal("15600000000")
        assert fund_info.unit_nav == Decimal("1.3000")
    
    def test_extract_fund_basic_info_minimal(self, parser, simple_xbrl_content):
        """Test basic info extraction with minimal data."""
        parser.load_from_content(simple_xbrl_content)
        fund_info = parser.extract_fund_basic_info()
        
        assert fund_info is not None
        assert fund_info.fund_code == "000002"
        assert fund_info.fund_name == "易方达平稳增长混合"
    
    def test_extract_asset_allocation_success(self, parser, sample_xbrl_content):
        """Test successful asset allocation extraction."""
        parser.load_from_content(sample_xbrl_content)
        allocation = parser.extract_asset_allocation()
        
        assert allocation is not None
        assert allocation.stock_investments == Decimal("10000000000")
        assert allocation.stock_ratio == Decimal("0.6410")
        assert allocation.bond_investments == Decimal("3000000000")
        assert allocation.cash_and_equivalents == Decimal("2600000000")
    
    def test_extract_asset_allocation_no_data(self, parser, simple_xbrl_content):
        """Test asset allocation extraction with no data."""
        parser.load_from_content(simple_xbrl_content)
        allocation = parser.extract_asset_allocation()
        
        assert allocation is None
    
    def test_extract_top_holdings_success(self, parser, sample_xbrl_content):
        """Test successful top holdings extraction."""
        parser.load_from_content(sample_xbrl_content)
        holdings = parser.extract_top_holdings()
        
        assert len(holdings) == 2
        
        first_holding = holdings[0]
        assert first_holding.rank == 1
        assert first_holding.stock_code == "000858"
        assert first_holding.stock_name == "五粮液"
        assert first_holding.market_value == Decimal("800000000")
        assert first_holding.portfolio_ratio == Decimal("0.0513")
        
        second_holding = holdings[1]
        assert second_holding.rank == 2
        assert second_holding.stock_code == "000001"
        assert second_holding.stock_name == "平安银行"
    
    def test_extract_top_holdings_with_limit(self, parser, sample_xbrl_content):
        """Test top holdings extraction with limit."""
        parser.load_from_content(sample_xbrl_content)
        holdings = parser.extract_top_holdings(limit=1)
        
        assert len(holdings) == 1
        assert holdings[0].stock_code == "000858"
    
    def test_extract_industry_allocation_success(self, parser, sample_xbrl_content):
        """Test successful industry allocation extraction."""
        parser.load_from_content(sample_xbrl_content)
        industries = parser.extract_industry_allocation()
        
        assert len(industries) == 2
        
        first_industry = industries[0]
        assert first_industry.industry_name == "制造业"
        assert first_industry.market_value == Decimal("4500000000")
        assert first_industry.portfolio_ratio == Decimal("0.2885")
        
        second_industry = industries[1]
        assert second_industry.industry_name == "金融业"
        assert second_industry.market_value == Decimal("3200000000")
    
    def test_parse_decimal_various_formats(self, parser):
        """Test decimal parsing with various formats."""
        # Standard format
        assert parser._parse_decimal("1000.50") == Decimal("1000.50")
        
        # With commas
        assert parser._parse_decimal("1,000,000.50") == Decimal("1000000.50")
        
        # Chinese units
        assert parser._parse_decimal("100万") == Decimal("1000000")
        assert parser._parse_decimal("15.6亿") == Decimal("1560000000")
        
        # Negative numbers
        assert parser._parse_decimal("-1000.50") == Decimal("-1000.50")
        
        # Invalid format
        assert parser._parse_decimal("invalid") is None
        assert parser._parse_decimal("") is None
    
    def test_parse_date_various_formats(self, parser):
        """Test date parsing with various formats."""
        # Standard format
        date1 = parser._parse_date("2023-12-31")
        assert date1 == datetime(2023, 12, 31)
        
        # Alternative format
        date2 = parser._parse_date("2023/12/31")
        assert date2 == datetime(2023, 12, 31)
        
        # Chinese format
        date3 = parser._parse_date("2023年12月31日")
        assert date3 == datetime(2023, 12, 31)
        
        # Invalid format
        assert parser._parse_date("invalid date") is None
        assert parser._parse_date("") is None
    
    def test_get_all_elements_info_no_data(self, parser):
        """Test getting elements info when no data is loaded."""
        info = parser.get_all_elements_info()
        assert info == {}
    
    def test_get_all_elements_info_with_data(self, parser, simple_xbrl_content):
        """Test getting elements info with data."""
        parser.load_from_content(simple_xbrl_content)
        info = parser.get_all_elements_info()
        
        assert "tag" in info
        assert "path" in info
        assert info["tag"].endswith("xbrl")
    
    def test_find_element_value_multiple_patterns(self, parser, sample_xbrl_content):
        """Test finding element value with multiple XPath patterns."""
        parser.load_from_content(sample_xbrl_content)
        
        # Should find fund code using different patterns
        patterns = [
            './/NonExistentTag',
            './/FundCode',
            './/*[contains(local-name(), "FundCode")]'
        ]
        
        value = parser._find_element_value(patterns)
        assert value == "000001"
    
    def test_find_element_value_no_match(self, parser, sample_xbrl_content):
        """Test finding element value with no matching patterns."""
        parser.load_from_content(sample_xbrl_content)
        
        patterns = [
            './/NonExistentTag',
            './/AnotherNonExistentTag'
        ]
        
        value = parser._find_element_value(patterns)
        assert value is None
    
    def test_extract_report_date_from_context(self, parser, sample_xbrl_content):
        """Test extracting report date from context."""
        parser.load_from_content(sample_xbrl_content)
        
        date = parser._extract_report_date()
        assert date == datetime(2023, 12, 31)
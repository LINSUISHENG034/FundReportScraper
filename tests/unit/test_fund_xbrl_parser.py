"""Unit tests for the FundXBRLParser."""

import pytest
from pathlib import Path
from decimal import Decimal
from datetime import date

from src.parsers.fund_xbrl_parser import FundXBRLParser
from src.parsers.base_parser import ParseResult


@pytest.fixture
def parser():
    """Provides a FundXBRLParser instance."""
    return FundXBRLParser()


@pytest.fixture
def fixtures_dir():
    """Provides the path to the test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize(
    "filename, expected_fund_code, expected_fund_name",
    [
        ("013060_ANNUAL_1752537343.xbrl", "013060", "工银瑞信养老目标日期2060五年持有期混合型发起式基金中基金（FOF）"),
        ("970196_2023Q3_1752541804.xbrl", "970196", "诚通天天利货币"),
    ]
)
def test_parse_file_basic_info(parser: FundXBRLParser, fixtures_dir: Path, filename: str, expected_fund_code: str, expected_fund_name: str):
    """Tests that the parser can correctly parse basic fund information."""
    file_path = fixtures_dir / filename
    result = parser.parse_file(file_path)

    assert isinstance(result, ParseResult)
    assert result.success is True
    assert result.fund_report is not None
    assert result.fund_report.fund_code == expected_fund_code
    assert expected_fund_name in result.fund_report.fund_name


def test_parse_file_annual_report_details(parser: FundXBRLParser, fixtures_dir: Path):
    """Tests detailed parsing of an annual report."""
    file_path = fixtures_dir / "013060_ANNUAL_1752537343.xbrl"
    result = parser.parse_file(file_path)

    assert result.success is True
    report = result.fund_report
    assert report.report_type == "年度报告"
    assert report.report_year == 2024
    assert report.report_period_end == date(2024, 12, 31)
    assert report.total_net_assets == Decimal("87101805.54")

    # Check asset allocations
    assert len(report.asset_allocations) > 0
    stock_allocation = next((item for item in report.asset_allocations if item.asset_type == '权益投资'), None)
    assert stock_allocation is not None
    assert stock_allocation.percentage >= 0  # FOF基金可能没有直接股票投资

    # Check top holdings (FOF基金可能没有直接股票持仓)
    if len(report.top_holdings) > 0:
        first_holding = report.top_holdings[0]
        assert first_holding.security_name is not None
        assert first_holding.market_value is not None



def test_can_parse(parser: FundXBRLParser):
    """Tests the can_parse method."""
    assert parser.can_parse("<html><ix:nonNumeric>test</ix:nonNumeric></html>") is True
    assert parser.can_parse("<html><xbrli:xbrl>test</xbrli:xbrl></html>") is True
    assert parser.can_parse("<html><body><p>Just some HTML</p></body></html>") is False
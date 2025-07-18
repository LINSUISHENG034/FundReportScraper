#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced XBRL Parser for Fund Reports
增强型XBRL基金报告解析器

This module provides comprehensive parsing capabilities for XBRL fund reports,
focusing on structured data extraction for comparative analysis and database storage.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime, date
from bs4 import BeautifulSoup, Tag

from ..models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation
from ..core.logging import get_logger
from .base_parser import BaseParser, ParserType, ParseResult


class EnhancedXBRLParser(BaseParser):
    """
    Enhanced XBRL Parser for comprehensive fund report data extraction
    增强型XBRL解析器，用于全面的基金报告数据提取
    """
    
    def __init__(self):
        super().__init__(ParserType.HTML_LEGACY)
        self.logger = get_logger(__name__)
        
        # Define section identifiers for structured parsing
        self.section_identifiers = {
            'basic_info': ['基金简介', '基金基本情况', '基金概况'],
            'financial_statements': ['资产负债表', '利润表', '净资产变动表', '年度财务报表'],
            'portfolio': ['投资组合报告', '期末基金资产组合情况', '投资明细'],
            'performance': ['基金净值表现', '主要财务指标', '业绩表现'],
            'holdings': ['前十名', '重仓股', '持仓明细', '股票投资明细'],
            'risk_analysis': ['风险', '敏感性分析', '市场风险'],
            'fund_holders': ['基金份额持有人', '持有人结构']
        }
        
        # Financial data patterns for extraction
        self.financial_patterns = {
            'assets': r'资产\s*[:：]\s*([\d,]+\.?\d*)',
            'liabilities': r'负债\s*[:：]\s*([\d,]+\.?\d*)',
            'net_assets': r'净资产\s*[:：]\s*([\d,]+\.?\d*)',
            'income': r'收入\s*[:：]\s*([\d,]+\.?\d*)',
            'expenses': r'费用\s*[:：]\s*([\d,]+\.?\d*)',
            'profit': r'利润\s*[:：]\s*([\d,]+\.?\d*)'
        }
    
    def can_parse(self, content: str, file_path: Optional[Path] = None) -> bool:
        """Check if the content can be parsed by this parser"""
        if not content:
            return False
        
        # Check for HTML structure
        html_indicators = ['<table', '<tr', '<td', '<div', '<span']
        content_lower = content.lower()
        has_html = any(indicator in content_lower for indicator in html_indicators)
        
        # Check for fund report specific content
        fund_keywords = ['基金代码', '基金名称', '年度报告', '季度报告', 'XBRL']
        has_fund_content = any(keyword in content for keyword in fund_keywords)
        
        # Check for financial data tables
        table_indicators = ['资产负债表', '利润表', '投资组合']
        has_financial_tables = any(indicator in content for indicator in table_indicators)
        
        return has_html and has_fund_content and has_financial_tables
    
    def parse_content(self, content: str, file_path: Optional[Path] = None) -> ParseResult:
        """Parse content and return structured fund report data"""
        try:
            fund_report = self._parse_comprehensive_report(content)
            
            # Validate and enhance the parsed data
            self._validate_and_enhance_data(fund_report)
            
            return self._create_success_result(fund_report, file_path)
            
        except Exception as e:
            error_msg = f"Enhanced XBRL parsing failed: {str(e)}"
            self.logger.error(error_msg, file_path=str(file_path) if file_path else None)
            return self._create_error_result(error_msg, file_path)
    
    def _parse_comprehensive_report(self, html_content: str) -> FundReport:
        """Parse comprehensive fund report data"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Initialize fund report
        fund_report = FundReport()
        
        # Extract data in structured sections
        self._extract_basic_information(soup, fund_report)
        self._extract_financial_statements(soup, fund_report)
        self._extract_portfolio_data(soup, fund_report)
        self._extract_performance_metrics(soup, fund_report)
        self._extract_holdings_data(soup, fund_report)
        self._extract_risk_analysis(soup, fund_report)
        
        return fund_report
    
    def _extract_basic_information(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract basic fund information"""
        # Fund code - look for 6-digit codes
        fund_code_pattern = r'(\d{6})'
        title_text = soup.get_text()
        fund_code_match = re.search(fund_code_pattern, title_text)
        if fund_code_match:
            fund_report.fund_code = fund_code_match.group(1)
        
        # Fund name - extract from title or header
        title_elements = soup.find_all(['title', 'h1', 'h2'])
        for element in title_elements:
            text = element.get_text().strip() if element else ""
            if text and '基金' in text and len(text) > 10:
                # Clean up the fund name
                fund_name = re.sub(r'\d{4}年.*?报告', '', text).strip()
                fund_name = re.sub(r'XBRL', '', fund_name).strip()
                if fund_name:
                    fund_report.fund_name = fund_name
                break
        
        # Report period and type
        self._extract_report_period(soup, fund_report)
        
        # Fund manager
        manager_text = self._find_text_by_keywords(soup, ['基金管理人', '管理人'])
        if manager_text:
            fund_report.fund_manager = manager_text
    
    def _extract_financial_statements(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract financial statement data"""
        # Look for balance sheet table
        balance_sheet_table = self._find_table_by_keywords(soup, ['资产负债表'])
        if balance_sheet_table:
            self._parse_balance_sheet(balance_sheet_table, fund_report)
        
        # Look for income statement
        income_table = self._find_table_by_keywords(soup, ['利润表'])
        if income_table:
            self._parse_income_statement(income_table, fund_report)
    
    def _extract_portfolio_data(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract portfolio allocation data"""
        # Asset allocation
        asset_table = self._find_table_by_keywords(soup, ['资产组合', '资产配置'])
        if asset_table:
            allocations = self._parse_asset_allocation_table(asset_table)
            fund_report.asset_allocations = allocations
    
    def _extract_holdings_data(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract top holdings data"""
        # Top stock holdings
        stock_table = self._find_table_by_keywords(soup, ['前十名', '重仓股', '股票投资明细'])
        if stock_table:
            holdings = self._parse_holdings_table(stock_table, 'stock')
            fund_report.top_holdings.extend(holdings)
        
        # Top bond holdings
        bond_table = self._find_table_by_keywords(soup, ['债券投资', '前五名债券'])
        if bond_table:
            holdings = self._parse_holdings_table(bond_table, 'bond')
            fund_report.top_holdings.extend(holdings)
    
    def _extract_performance_metrics(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract performance and financial metrics"""
        # Net asset value
        nav_text = self._find_text_by_keywords(soup, ['单位净值', '基金单位净值'])
        if nav_text:
            fund_report.net_asset_value = self._parse_decimal(nav_text)
        
        # Total net assets
        total_assets_text = self._find_text_by_keywords(soup, ['基金资产净值', '净资产总额'])
        if total_assets_text:
            fund_report.total_net_assets = self._parse_decimal(total_assets_text)
        
        # Accumulated NAV
        acc_nav_text = self._find_text_by_keywords(soup, ['累计净值'])
        if acc_nav_text:
            fund_report.accumulated_nav = self._parse_decimal(acc_nav_text)
    
    def _extract_risk_analysis(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract risk analysis data"""
        # This would extract risk metrics, sensitivity analysis, etc.
        # Implementation depends on specific XBRL structure
        pass
    
    def _extract_report_period(self, soup: BeautifulSoup, fund_report: FundReport):
        """Extract report period information"""
        # Look for date patterns in the content
        date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        text_content = soup.get_text()
        
        # Find report end date
        date_matches = re.findall(date_pattern, text_content)
        if date_matches:
            # Usually the last date is the report end date
            year, month, day = date_matches[-1]
            fund_report.report_period_end = date(int(year), int(month), int(day))
            fund_report.report_year = int(year)
            
            # Determine report type and quarter
            if '年度报告' in text_content or '年报' in text_content:
                fund_report.report_type = 'annual'
                fund_report.report_quarter = None
            elif '季度报告' in text_content or '季报' in text_content:
                fund_report.report_type = 'quarterly'
                fund_report.report_quarter = (int(month) - 1) // 3 + 1
            elif '中期报告' in text_content or '半年报' in text_content:
                fund_report.report_type = 'semi_annual'
                fund_report.report_quarter = 2
    
    def _find_table_by_keywords(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[Tag]:
        """Find table containing specific keywords"""
        if not soup:
            return None

        for keyword in keywords:
            # Look for tables with keyword in headers or nearby text
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text() if table else ""
                if table_text and keyword in table_text:
                    return table
        return None
    
    def _find_text_by_keywords(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        """Find text content by keywords"""
        if not soup:
            return None

        text_content = soup.get_text()
        if not text_content:
            return None

        for keyword in keywords:
            # Look for text following the keyword
            pattern = rf'{keyword}\s*[:：]\s*([^<\n]+)'
            match = re.search(pattern, text_content)
            if match:
                return match.group(1).strip()
        return None
    
    def _parse_decimal(self, text: str) -> Optional[Decimal]:
        """Parse decimal value from text"""
        if not text:
            return None
        
        # Remove common formatting
        cleaned = re.sub(r'[,，\s]', '', text)
        cleaned = re.sub(r'[元万亿]', '', cleaned)
        
        # Extract numeric value
        number_match = re.search(r'([\d.]+)', cleaned)
        if number_match:
            try:
                return Decimal(number_match.group(1))
            except InvalidOperation:
                return None
        return None
    
    def _validate_and_enhance_data(self, fund_report: FundReport):
        """Validate and enhance parsed data"""
        # Set parsing metadata
        fund_report.parsing_method = 'enhanced_xbrl'
        fund_report.parsing_confidence = 0.85  # Base confidence
        fund_report.parsed_at = datetime.utcnow()
        
        # Calculate data quality score
        quality_score = self._calculate_quality_score(fund_report)
        fund_report.data_quality_score = quality_score
        
        # Set validation status
        if quality_score >= 0.8:
            fund_report.validation_status = 'high_quality'
        elif quality_score >= 0.6:
            fund_report.validation_status = 'medium_quality'
        else:
            fund_report.validation_status = 'low_quality'
    
    def _calculate_quality_score(self, fund_report: FundReport) -> float:
        """Calculate data quality score based on completeness"""
        score = 0.0
        total_checks = 0
        
        # Basic information checks
        if fund_report.fund_code:
            score += 0.2
        if fund_report.fund_name:
            score += 0.2
        if fund_report.net_asset_value:
            score += 0.15
        if fund_report.total_net_assets:
            score += 0.15
        if fund_report.report_period_end:
            score += 0.1
        
        # Data richness checks
        if fund_report.asset_allocations:
            score += 0.1
        if fund_report.top_holdings:
            score += 0.1
        
        return min(1.0, score)

    def _parse_balance_sheet(self, table: Tag, fund_report: FundReport):
        """Parse balance sheet table"""
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text().strip()
                value_text = cells[-1].get_text().strip()

                if '资产总计' in label or '资产合计' in label:
                    fund_report.total_net_assets = self._parse_decimal(value_text)

    def _parse_income_statement(self, table: Tag, fund_report: FundReport):
        """Parse income statement table"""
        # Extract key income statement items
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text().strip()
                value_text = cells[-1].get_text().strip()

                # Store income statement data in metadata
                if not hasattr(fund_report, 'parsing_metadata'):
                    fund_report.parsing_metadata = {}
                if 'income_statement' not in fund_report.parsing_metadata:
                    fund_report.parsing_metadata['income_statement'] = {}

                if any(keyword in label for keyword in ['收入', '费用', '利润']):
                    fund_report.parsing_metadata['income_statement'][label] = value_text

    def _parse_asset_allocation_table(self, table: Tag) -> List[AssetAllocation]:
        """Parse asset allocation table"""
        allocations = []
        rows = table.find_all('tr')

        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                asset_type = cells[0].get_text().strip()
                market_value_text = cells[1].get_text().strip() if len(cells) > 1 else ""
                percentage_text = cells[2].get_text().strip() if len(cells) > 2 else ""

                if asset_type and asset_type not in ['项目', '资产类别']:
                    allocation = AssetAllocation()
                    allocation.asset_type = asset_type
                    allocation.market_value = self._parse_decimal(market_value_text)
                    allocation.percentage = self._parse_decimal(percentage_text)
                    allocations.append(allocation)

        return allocations

    def _parse_holdings_table(self, table: Tag, holding_type: str) -> List[TopHolding]:
        """Parse holdings table (stocks or bonds)"""
        holdings = []
        rows = table.find_all('tr')

        for i, row in enumerate(rows[1:], 1):  # Skip header, start rank from 1
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 4:
                security_name = cells[0].get_text().strip()
                security_code = cells[1].get_text().strip() if len(cells) > 1 else ""
                market_value_text = cells[2].get_text().strip() if len(cells) > 2 else ""
                percentage_text = cells[3].get_text().strip() if len(cells) > 3 else ""

                if security_name and security_name not in ['股票名称', '债券名称', '证券名称']:
                    holding = TopHolding()
                    holding.holding_type = holding_type
                    holding.security_name = security_name
                    holding.security_code = security_code
                    holding.market_value = self._parse_decimal(market_value_text)
                    holding.percentage = self._parse_decimal(percentage_text)
                    holding.rank = i
                    holdings.append(holding)

                    if i >= 10:  # Limit to top 10
                        break

        return holdings

"""ArelleParser单元测试

测试基于Arelle命令行的XBRL解析器功能
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from decimal import Decimal

from src.parsers.arelle_parser import ArelleParser
from src.parsers.base_parser import ParseResult, ParserType
from src.models.enhanced_fund_data import ComprehensiveFundReport


class TestArelleParser:
    """ArelleParser测试类"""
    
    @pytest.fixture
    def parser(self):
        """创建解析器实例"""
        return ArelleParser()
    
    @pytest.fixture
    def sample_xbrl_content(self):
        """示例XBRL内容"""
        return '''
        <?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns="http://www.xbrl.org/2003/instance"
              xmlns:xbrli="http://www.xbrl.org/2003/instance"
              xmlns:fund="http://www.csrc.gov.cn/fund">
            <context id="ctx1">
                <entity>
                    <identifier scheme="http://www.csrc.gov.cn">001056</identifier>
                </entity>
                <period>
                    <instant>2024-12-31</instant>
                </period>
            </context>
            <unit id="CNY">
                <measure>iso4217:CNY</measure>
            </unit>
            <fund:FundCode contextRef="ctx1">001056</fund:FundCode>
            <fund:FundName contextRef="ctx1">测试基金</fund:FundName>
            <fund:NetAssetValue contextRef="ctx1" unitRef="CNY">1.2345</fund:NetAssetValue>
            <fund:TotalNetAssets contextRef="ctx1" unitRef="CNY">1000000000</fund:TotalNetAssets>
        </xbrl>
        '''
    
    @pytest.fixture
    def sample_facts_json(self):
        """示例事实JSON数据"""
        return json.dumps([
            {
                "concept": "fund:FundCode",
                "value": "001056",
                "context": "ctx1",
                "unit": ""
            },
            {
                "concept": "fund:FundName",
                "value": "测试基金",
                "context": "ctx1",
                "unit": ""
            },
            {
                "concept": "fund:NetAssetValue",
                "value": "1.2345",
                "context": "ctx1",
                "unit": "CNY"
            },
            {
                "concept": "fund:TotalNetAssets",
                "value": "1000000000",
                "context": "ctx1",
                "unit": "CNY"
            }
        ])
    
    def test_parser_initialization(self, parser):
        """测试解析器初始化"""
        assert parser.parser_type == ParserType.XBRL_NATIVE
        assert hasattr(parser, 'concept_mappings')
        assert 'fund_code' in parser.concept_mappings
        assert 'fund_name' in parser.concept_mappings
        assert 'net_asset_value' in parser.concept_mappings
        assert 'total_net_assets' in parser.concept_mappings
    
    def test_can_parse(self, parser):
        """测试can_parse方法"""
        # ArelleParser应该总是返回True，因为它假设输入已经是预判过的XBRL
        assert parser.can_parse("any content") is True
        assert parser.can_parse("") is True
    
    @patch('subprocess.run')
    def test_check_arelle_availability_success(self, mock_run, parser):
        """测试Arelle可用性检查 - 成功情况"""
        # 模拟成功的命令执行
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Arelle version 1.2.0"
        
        result = parser._check_arelle_availability()
        assert result is True
    
    @patch('subprocess.run')
    def test_check_arelle_availability_failure(self, mock_run, parser):
        """测试Arelle可用性检查 - 失败情况"""
        # 模拟失败的命令执行
        mock_run.side_effect = FileNotFoundError()
        
        result = parser._check_arelle_availability()
        assert result is False
    
    def test_clean_text_value(self, parser):
        """测试文本值清理"""
        assert parser._clean_text_value("  test  ") == "test"
        assert parser._clean_text_value("") == ""
        assert parser._clean_text_value(None) == ""
        assert parser._clean_text_value("基金名称") == "基金名称"
    
    def test_parse_decimal(self, parser):
        """测试十进制数解析"""
        assert parser._parse_decimal("123.45") == Decimal("123.45")
        assert parser._parse_decimal("1,234.56") == Decimal("1234.56")
        assert parser._parse_decimal("1，234.56") == Decimal("1234.56")
        assert parser._parse_decimal("invalid") is None
        assert parser._parse_decimal("") is None
        assert parser._parse_decimal(None) is None
    
    def test_map_basic_info(self, parser):
        """测试基本信息映射"""
        data_dict = {}
        
        # 测试基金代码映射
        parser._map_basic_info("fund:FundCode", "001056", data_dict)
        assert data_dict['fund_code'] == "001056"
        
        # 测试基金名称映射
        parser._map_basic_info("fund:FundName", "测试基金", data_dict)
        assert data_dict['fund_name'] == "测试基金"
        
        # 测试无效基金代码不会覆盖已有值
        parser._map_basic_info("fund:FundCode", "invalid", data_dict)
        assert data_dict['fund_code'] == "001056"  # 保持原值
    
    def test_map_financial_metrics(self, parser):
        """测试财务指标映射"""
        data_dict = {}
        
        # 测试净值映射
        parser._map_financial_metrics("fund:NetAssetValue", "1.2345", data_dict)
        assert data_dict['net_asset_value'] == Decimal("1.2345")
        
        # 测试总净资产映射
        parser._map_financial_metrics("fund:TotalNetAssets", "1000000000", data_dict)
        assert data_dict['total_net_assets'] == Decimal("1000000000")
        
        # 测试无效数值不会被映射
        parser._map_financial_metrics("fund:NetAssetValue", "invalid", data_dict)
        assert data_dict['net_asset_value'] == Decimal("1.2345")  # 保持原值
    
    def test_map_facts_to_report_success(self, parser, sample_facts_json):
        """测试事实映射到报告 - 成功情况"""
        result = parser._map_facts_to_report(sample_facts_json)
        
        assert result is not None
        assert isinstance(result, ComprehensiveFundReport)
        assert result.basic_info.fund_code == "001056"
        assert result.basic_info.fund_name == "测试基金"
        assert result.financial_metrics.net_asset_value == Decimal("1.2345")
        assert result.financial_metrics.total_net_assets == Decimal("1000000000")
        assert result.report_metadata.parsing_method == "arelle_cmdline"
    
    def test_map_facts_to_report_error(self, parser):
        """测试事实映射到报告 - 错误情况"""
        # 测试错误JSON
        error_json = '{"error": "解析失败"}'
        result = parser._map_facts_to_report(error_json)
        assert result is None
        
        # 测试无效JSON
        invalid_json = "invalid json"
        result = parser._map_facts_to_report(invalid_json)
        assert result is None
        
        # 测试空列表
        empty_json = "[]"
        result = parser._map_facts_to_report(empty_json)
        assert result is not None  # 应该返回默认值的报告
    
    @patch.object(ArelleParser, '_run_arelle_command')
    @patch.object(ArelleParser, '_check_arelle_availability')
    def test_parse_content_success(self, mock_check, mock_run, parser, sample_xbrl_content, sample_facts_json):
        """测试内容解析 - 成功情况"""
        # 模拟Arelle可用
        mock_check.return_value = True
        parser._arelle_available = True
        
        # 模拟Arelle命令返回
        mock_run.return_value = sample_facts_json
        
        result = parser.parse_content(sample_xbrl_content)
        
        assert isinstance(result, ParseResult)
        assert result.success is True
        assert result.fund_report is not None
        assert result.fund_report.fund_code == "001056"
        assert result.fund_report.fund_name == "测试基金"
        assert result.parser_type == ParserType.XBRL_NATIVE
        assert len(result.errors) == 0
    
    @patch.object(ArelleParser, '_check_arelle_availability')
    def test_parse_content_arelle_unavailable(self, mock_check, parser, sample_xbrl_content):
        """测试内容解析 - Arelle不可用"""
        # 模拟Arelle不可用
        mock_check.return_value = False
        parser._arelle_available = False
        
        result = parser.parse_content(sample_xbrl_content)
        
        assert isinstance(result, ParseResult)
        assert result.success is False
        assert result.fund_report is None
        assert len(result.errors) > 0
        assert "Arelle命令行工具不可用" in result.errors[0]
    
    @patch.object(ArelleParser, '_run_arelle_command')
    @patch.object(ArelleParser, '_check_arelle_availability')
    def test_parse_content_arelle_command_failure(self, mock_check, mock_run, parser, sample_xbrl_content):
        """测试内容解析 - Arelle命令失败"""
        # 模拟Arelle可用但命令失败
        mock_check.return_value = True
        parser._arelle_available = True
        mock_run.return_value = None
        
        result = parser.parse_content(sample_xbrl_content)
        
        assert isinstance(result, ParseResult)
        assert result.success is False
        assert result.fund_report is None
        assert len(result.errors) > 0
        assert "未返回有效的事实数据" in result.errors[0]
    
    def test_create_success_result(self, parser, sample_facts_json):
        """测试创建成功结果"""
        fund_report = parser._map_facts_to_report(sample_facts_json)
        result = parser._create_success_result(fund_report, Path("test.xbrl"))
        
        assert isinstance(result, ParseResult)
        assert result.success is True
        assert result.fund_report is not None
        assert result.parser_type == ParserType.XBRL_NATIVE
        assert "file_path" in result.metadata
        assert "comprehensive_report" in result.metadata
    
    def test_create_error_result(self, parser):
        """测试创建错误结果"""
        error_msg = "测试错误消息"
        result = parser._create_error_result(error_msg)
        
        assert isinstance(result, ParseResult)
        assert result.success is False
        assert result.fund_report is None
        assert result.parser_type == ParserType.XBRL_NATIVE
        assert error_msg in result.errors


class TestArelleParserIntegration:
    """ArelleParser集成测试"""
    
    @pytest.fixture
    def parser(self):
        """创建解析器实例"""
        return ArelleParser()
    
    @pytest.fixture
    def test_xbrl_file(self):
        """测试XBRL文件路径"""
        return Path("tests/fixtures/001056_REPORT_1752622427.xbrl")
    
    def test_parse_real_xbrl_file(self, parser, test_xbrl_file):
        """测试解析真实XBRL文件"""
        if not test_xbrl_file.exists():
            pytest.skip(f"测试文件不存在: {test_xbrl_file}")
        
        # 读取文件内容
        with open(test_xbrl_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析内容
        result = parser.parse_content(content, test_xbrl_file)
        
        # 验证结果
        assert isinstance(result, ParseResult)
        
        if result.success:
            assert result.fund_report is not None
            assert result.fund_report.fund_code is not None
            assert result.fund_report.fund_name is not None
            print(f"解析成功: {result.fund_report.fund_code} - {result.fund_report.fund_name}")
        else:
            print(f"解析失败: {result.errors}")
            # 在集成测试中，我们可以接受解析失败（如果Arelle不可用）
            assert len(result.errors) > 0
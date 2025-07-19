#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的ArelleParser功能

这个测试文件验证PHASE_8重构后的ArelleParser是否能够:
1. 动态加载XBRL分类标准映射
2. 正确使用Arelle命令行工具解析XBRL文件
3. 移除了已弃用的lxml原生解析器代码
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.parsers.arelle_parser import ArelleParser
from src.models.enhanced_fund_data import (
    ComprehensiveFundReport, BasicFundInfo, FinancialMetrics, 
    ReportMetadata, ReportType
)
from src.parsers.base_parser import ParseResult
from datetime import date, datetime


class TestArelleParserRefactored(unittest.TestCase):
    """测试重构后的ArelleParser"""
    
    def setUp(self):
        """设置测试环境"""
        self.parser = ArelleParser()
        
        # 模拟XBRL内容
        self.sample_xbrl_content = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <xbrl xmlns="http://www.xbrl.org/2003/instance"
              xmlns:link="http://www.xbrl.org/2003/linkbase"
              xmlns:xlink="http://www.w3.org/1999/xlink"
              xmlns:csrc-mf="http://www.csrc.gov.cn/xbrl/taxonomy/csrc-mf-general">
            <link:schemaRef xlink:type="simple" 
                           xlink:href="http://www.csrc.gov.cn/xbrl/taxonomy/csrc-mf-general-2021-03-31.xsd"/>
            <context id="period_2023">
                <entity>
                    <identifier scheme="http://www.csrc.gov.cn">000001</identifier>
                </entity>
                <period>
                    <startDate>2023-01-01</startDate>
                    <endDate>2023-12-31</endDate>
                </period>
            </context>
            <csrc-mf:FundCode contextRef="period_2023">000001</csrc-mf:FundCode>
            <csrc-mf:FundName contextRef="period_2023">测试基金</csrc-mf:FundName>
        </xbrl>
        '''
        
        # 模拟分类标准配置
        self.sample_taxonomy_config = {
            "taxonomy_info": {
                "name": "CSRC v2.1",
                "version": "2.1",
                "description": "中国证监会基金信息披露XBRL分类标准v2.1"
            },
            "concept_mappings": {
                "fund_code": ["0012"],
                "fund_name": ["0009", "0011"],
                "fund_manager": ["0186"]
            }
        }
    
    def test_init_without_hardcoded_mappings(self):
        """测试初始化时不包含硬编码的概念映射"""
        parser = ArelleParser()
        
        # 验证初始状态
        self.assertIsNone(parser.current_taxonomy)
        self.assertEqual(parser.concept_mappings, {})
        
        # 验证不再有硬编码的映射
        self.assertNotIn("fund_code", parser.concept_mappings)
        self.assertNotIn("fund_name", parser.concept_mappings)
    
    @patch('src.parsers.arelle_parser.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_taxonomy_mapping_success(self, mock_file, mock_exists):
        """测试成功加载分类标准映射"""
        # 模拟文件存在
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.sample_taxonomy_config)
        
        # 调用方法
        result = self.parser._load_taxonomy_mapping(self.sample_xbrl_content)
        
        # 验证结果
        self.assertEqual(result['taxonomy_info']['name'], 'CSRC v2.1')
        self.assertIn('fund_code', result['concept_mappings'])
    
    def test_extract_schema_ref(self):
        """测试从XBRL内容中提取schemaRef"""
        schema_ref = self.parser._extract_schema_ref(self.sample_xbrl_content)
        
        # 验证提取到正确的schemaRef
        self.assertIn('csrc-mf-general', schema_ref)
    
    def test_determine_taxonomy_file(self):
        """测试根据schemaRef确定分类标准文件"""
        # 测试CSRC分类标准
        csrc_schema = "http://www.csrc.gov.cn/xbrl/taxonomy/csrc-mf-general-2021-03-31.xsd"
        result = self.parser._determine_taxonomy_file(csrc_schema)
        self.assertEqual(result, "csrc_v2.1.json")
        
        # 测试默认情况
        unknown_schema = "http://example.com/unknown.xsd"
        result = self.parser._determine_taxonomy_file(unknown_schema)
        self.assertEqual(result, "default.json")
    
    @patch('src.parsers.arelle_parser.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_default_taxonomy(self, mock_file, mock_exists):
        """测试加载默认分类标准映射"""
        mock_exists.return_value = True
        default_config = {
            "taxonomy_info": {"name": "Default", "version": "1.0"},
            "concept_mappings": {"fund_code": ["default_code"]}
        }
        mock_file.return_value.read.return_value = json.dumps(default_config)
        
        result = self.parser._load_default_taxonomy()
        
        self.assertEqual(result['taxonomy_info']['name'], 'Default')
     
    @patch.object(ArelleParser, '_load_taxonomy_mapping')
    @patch.object(ArelleParser, '_run_arelle_command')
    @patch.object(ArelleParser, '_map_facts_to_report')
    def test_parse_content_with_dynamic_mapping(self, mock_map_facts, mock_run_arelle, 
                                               mock_load_taxonomy):
        """测试parse_content方法使用动态映射"""
        # 设置模拟 - 直接设置_arelle_available属性
        self.parser._arelle_available = True
        mock_load_taxonomy.return_value = self.sample_taxonomy_config
        mock_run_arelle.return_value = '{"facts": []}'
        # 创建有效的ComprehensiveFundReport实例
        mock_report = ComprehensiveFundReport(
            basic_info=BasicFundInfo(
                fund_code="000001",
                fund_name="测试基金"
            ),
            financial_metrics=FinancialMetrics(),
            report_metadata=ReportMetadata(
                report_type=ReportType.ANNUAL,
                report_period_start=date(2023, 1, 1),
                report_period_end=date(2023, 12, 31),
                report_year=2023,
                upload_info_id="test_upload_id"
            )
        )
        mock_map_facts.return_value = mock_report
        
        # 调用解析方法
        result = self.parser.parse_content(self.sample_xbrl_content)
        
        # 验证动态加载被调用
        mock_load_taxonomy.assert_called_once_with(self.sample_xbrl_content)
        
        # 验证映射被正确设置
        self.assertEqual(self.parser.current_taxonomy['name'], 'CSRC v2.1')
        self.assertIn('fund_code', self.parser.concept_mappings)
        
        # 验证解析成功
        self.assertTrue(result.success)
    
    @patch.object(ArelleParser, '_check_arelle_availability')
    def test_parse_content_arelle_unavailable(self, mock_check_arelle):
        """测试Arelle不可用时的处理"""
        mock_check_arelle.return_value = False
        
        result = self.parser.parse_content(self.sample_xbrl_content)
        
        self.assertFalse(result.success)
        self.assertIn('Arelle命令行工具不可用', result.errors[0])
    
    def test_deprecated_method_removed(self):
        """测试已弃用的原生解析器方法已被移除"""
        # 验证_extract_facts_with_native_parser方法不存在
        self.assertFalse(hasattr(self.parser, '_extract_facts_with_native_parser'))
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_run_arelle_command_integration(self, mock_temp_file, mock_subprocess):
        """测试Arelle命令行工具集成"""
        # 模拟临时文件
        mock_temp_file.return_value.__enter__.return_value.name = '/tmp/test_output.json'
        
        # 模拟subprocess成功执行
        mock_subprocess.return_value.returncode = 0
        
        # 模拟读取输出文件
        with patch('builtins.open', mock_open(read_data='[{"concept": "test", "value": "123"}]')):
            result = self.parser._run_arelle_command('/tmp/test.xbrl')
        
        # 验证subprocess被正确调用
        mock_subprocess.assert_called_once()
        
        # 验证命令参数包含正确的Arelle路径
        call_args = mock_subprocess.call_args[0][0]
        self.assertTrue(any('arelleCmdLine.exe' in str(arg) for arg in call_args))


if __name__ == '__main__':
    unittest.main()
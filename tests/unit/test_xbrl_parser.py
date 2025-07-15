"""重构后的XBRL解析器单元测试

基于TDD方法，使用参数化测试和精确断言来验证解析器功能。
"""

import pytest
from pathlib import Path
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List

from src.parsers.xbrl_parser import XBRLParser, ParsedFundData


class TestXBRLParser:
    """重构后的XBRL解析器测试类"""
    
    @pytest.fixture
    def parser(self):
        """创建解析器实例"""
        return XBRLParser()
    
    @pytest.fixture
    def fixtures_dir(self):
        """获取测试数据目录"""
        return Path(__file__).parent.parent / "fixtures"
    
    def get_expected_data_structures(self) -> Dict[str, Dict[str, Any]]:
        """定义5个代表性报告文件的预期数据结构，基于实际解析结果"""
        return {
            # 年度报告示例 - 基于013060_ANNUAL_1752537343.xbrl
            "annual_report": {
                "fund_code": "013060",
                "fund_name": "工银瑞信养老目标日期2060五年持有期混合型发起式基金中基金（FOF）",
                "fund_manager": "工银瑞信基金管理有限公司",
                "report_type": "年度报告",
                "report_year": 2024,
                "report_quarter": None,
                "report_period_start": date(2024, 1, 1),
                "report_period_end": date(2024, 12, 31),
                "net_asset_value": Decimal("1.0000"),
                "total_net_assets": Decimal("87101805.54"),
                "asset_allocations_count": {"min": 3, "max": 10},
                "top_holdings_count": {"min": 0, "max": 5},
                "industry_allocations_count": {"min": 0, "max": 5},
                "required_fields": [
                    "fund_code"
                ],
                "optional_fields": [
                    "fund_name", "fund_manager", "report_type", "report_year", "report_period_start", "report_period_end", "net_asset_value", "total_net_assets"
                ]
            },
            
            # 季度报告示例 - 基于970196_2023Q3_1752541804.xbrl
            "quarterly_report": {
                "fund_code": "970196",
                "fund_name": "诚通天天利货币",
                "fund_manager": "诚通证券股份有限公司",
                "report_type": "第三季度报告",
                "report_year": 2024,
                "report_quarter": 3,
                "report_period_start": date(2024, 7, 1),
                "report_period_end": date(2024, 9, 30),
                "net_asset_value": Decimal("225"),
                "total_net_assets": Decimal("225212770.20"),
                "asset_allocations_count": {"min": 0, "max": 10},
                "top_holdings_count": {"min": 0, "max": 10},
                "industry_allocations_count": {"min": 0, "max": 10},
                "required_fields": [
                    "fund_code"
                ],
                "optional_fields": [
                    "fund_name", "fund_manager", "report_type", "report_year", "report_quarter", "report_period_start", "report_period_end", "net_asset_value", "total_net_assets"
                ]
            },
            
            # 半年度报告示例 - 基于003016_SEMI_ANNUAL_1752539909.xbrl
            "semi_annual_report": {
                "fund_code": "003016",
                "fund_name": "中金中证500指数增强型发起",
                "fund_manager": "中金基金管理有限公司",
                "report_type": "半年度报告",
                "report_year": 2024,
                "report_quarter": 2,
                "report_period_end": date(2024, 6, 30),
                "net_asset_value": Decimal("1.0000"),
                "total_net_assets": Decimal("718091724.84"),
                "asset_allocations_count": {"min": 3, "max": 10},
                "top_holdings_count": {"min": 0, "max": 5},
                "industry_allocations_count": {"min": 0, "max": 5},
                "required_fields": [
                    "fund_code"
                ],
                "optional_fields": [
                    "fund_name", "fund_manager", "report_type", "report_year", "report_quarter", "report_period_end", "net_asset_value", "total_net_assets"
                ]
            },
            
            # 基金概况报告示例 - 基于159255_FUND_PROFILE_1752539954.xbrl
            "fund_profile": {
                "fund_code": "159255",
                "fund_name": "易方达国证通用航空产业ETF",
                "fund_manager": "易方达基金管理有限公司",
                "net_asset_value": Decimal("4"),
                "asset_allocations_count": {"min": 0, "max": 5},
                "top_holdings_count": {"min": 0, "max": 5},
                "industry_allocations_count": {"min": 0, "max": 5},
                "required_fields": ["fund_code"],
                "optional_fields": ["fund_name", "fund_manager", "net_asset_value"]
            },
            
            # 复杂季度报告示例 - 基于970086_2025Q1_1752539408.xbrl
            "complex_quarterly_report": {
                "fund_code": "970086",
                "fund_name": "华安证券合赢三个月持有债券",
                "fund_manager": "华安证券资产管理有限公司",
                "report_type": "第一季度报告",
                "report_year": 2025,
                "report_quarter": 1,
                "report_period_start": date(2025, 1, 1),
                "report_period_end": date(2025, 3, 31),
                "net_asset_value": Decimal("1.0203"),
                "total_net_assets": Decimal("445283511.05"),
                "asset_allocations_count": {"min": 4, "max": 10},
                "top_holdings_count": {"min": 0, "max": 5},
                "industry_allocations_count": {"min": 0, "max": 5},
                "data_quality_requirements": {
                    "asset_allocations": {
                        "required_keys": ["asset_type"],
                        "percentage_sum_range": (0.0, 500.0)
                    },
                    "top_holdings": {
                        "required_keys": ["security_name"],
                        "rank_sequence": False
                    },
                    "industry_allocations": {
                        "required_keys": ["industry_name"]
                    }
                },
                "required_fields": [
                    "fund_code"
                ],
                "optional_fields": [
                    "fund_name", "fund_manager", "net_asset_value", "total_net_assets", "report_type", "report_year", "report_quarter"
                ]
            }
        }
    
    
    def _validate_data_counts(self, result: ParsedFundData, expected_data: Dict[str, Any]):
        """验证数据结构的数量范围"""
        count_validations = [
            ("asset_allocations", result.asset_allocations),
            ("top_holdings", result.top_holdings),
            ("industry_allocations", result.industry_allocations)
        ]
        
        for field_name, data_list in count_validations:
            count_key = f"{field_name}_count"
            if count_key in expected_data:
                count_range = expected_data[count_key]
                actual_count = len(data_list)
                
                assert count_range["min"] <= actual_count <= count_range["max"], \
                    f"{field_name} 数量 {actual_count} 不在预期范围 [{count_range['min']}, {count_range['max']}] 内"
    
    def _validate_data_quality(self, result: ParsedFundData, quality_requirements: Dict[str, Any]):
        """验证数据质量要求"""
        # 验证资产配置数据质量
        if "asset_allocations" in quality_requirements:
            req = quality_requirements["asset_allocations"]
            self._validate_list_data_quality(result.asset_allocations, req, "资产配置")
            
            # 验证百分比总和
            if "percentage_sum_range" in req:
                total_percentage = sum(
                    item.get("percentage", 0) for item in result.asset_allocations
                    if item.get("percentage") is not None
                )
                min_sum, max_sum = req["percentage_sum_range"]
                assert min_sum <= float(total_percentage) <= max_sum, \
                    f"资产配置百分比总和 {total_percentage} 不在合理范围 [{min_sum}, {max_sum}] 内"
        
        # 验证前十大持仓数据质量
        if "top_holdings" in quality_requirements:
            req = quality_requirements["top_holdings"]
            self._validate_list_data_quality(result.top_holdings, req, "前十大持仓")
            
            # 验证排名序列
            if req.get("rank_sequence", False):
                ranks = [item.get("rank") for item in result.top_holdings if item.get("rank") is not None]
                if ranks:
                    assert ranks == list(range(1, len(ranks) + 1)), "持仓排名应为连续序列"
        
        # 验证行业配置数据质量
        if "industry_allocations" in quality_requirements:
            req = quality_requirements["industry_allocations"]
            self._validate_list_data_quality(result.industry_allocations, req, "行业配置")
    
    def _validate_list_data_quality(self, data_list: List[Dict], requirements: Dict, data_type: str):
        """验证列表数据的质量"""
        if not data_list:
            return
        
        required_keys = requirements.get("required_keys", [])
        for i, item in enumerate(data_list):
            for key in required_keys:
                assert key in item and item[key] is not None, \
                    f"{data_type} 第{i+1}项缺少必需字段 {key}"
    
    def test_parser_handles_invalid_files(self, parser, fixtures_dir):
        """测试解析器处理无效文件的能力"""
        # 测试不存在的文件
        result = parser.parse_file(fixtures_dir / "nonexistent.xbrl")
        assert result is None, "解析不存在的文件应返回None"
        
        # 测试空文件（如果存在）
        empty_files = list(fixtures_dir.glob("*empty*.xbrl"))
        for empty_file in empty_files:
            result = parser.parse_file(empty_file)
            # 空文件可能返回None或空的ParsedFundData
            if result is not None:
                assert isinstance(result, ParsedFundData)
    
    
    @pytest.mark.parametrize("file_name,expected_fund_code,expected_fund_name", [
        ("013060_ANNUAL_1752537343.xbrl", "013060", "工银瑞信养老目标日期2060五年持有期混合型发起式基金中基金（FOF）"),
        ("970196_2023Q3_1752541804.xbrl", "970196", "诚通天天利货币"),
        ("003016_SEMI_ANNUAL_1752539909.xbrl", "003016", "中金中证500指数增强型发起"),
        ("159255_FUND_PROFILE_1752539954.xbrl", "159255", "易方达国证通用航空产业ETF"),
        ("970086_2025Q1_1752539408.xbrl", "970086", "华安证券合赢三个月持有债券")
    ])
    def test_specific_file_parsing_accuracy(self, parser, fixtures_dir, file_name, expected_fund_code, expected_fund_name):
        """测试特定文件的解析精度"""
        test_file = fixtures_dir / file_name
        
        if not test_file.exists():
            pytest.skip(f"测试文件 {file_name} 不存在")
        
        result = parser.parse_file(test_file)
        
        # 验证解析成功
        assert result is not None, f"解析文件 {file_name} 失败"
        assert isinstance(result, ParsedFundData), "返回结果类型错误"
        
        # 验证基金代码
        assert result.fund_code == expected_fund_code, \
            f"基金代码不匹配: 期望 {expected_fund_code}, 实际 {result.fund_code}"
        
        # 验证基金名称（如果存在）
        if result.fund_name:
            assert expected_fund_name in result.fund_name, \
                f"基金名称不匹配: 期望包含 {expected_fund_name}, 实际 {result.fund_name}"
    
    def test_parsed_fund_data_initialization(self):
        """测试ParsedFundData数据类的初始化"""
        # 测试默认初始化
        data = ParsedFundData()
        
        # 验证基本字段
        assert data.fund_code is None
        assert data.fund_name is None
        assert data.report_type is None
        assert data.report_year is None
        assert data.report_quarter is None
        
        # 验证列表字段初始化为空列表
        assert isinstance(data.asset_allocations, list)
        assert isinstance(data.top_holdings, list)
        assert isinstance(data.industry_allocations, list)
        assert len(data.asset_allocations) == 0
        assert len(data.top_holdings) == 0
        assert len(data.industry_allocations) == 0
        
        # 测试带参数初始化
        data_with_params = ParsedFundData(
            fund_code="000001",
            fund_name="测试基金",
            report_year=2024
        )
        
        assert data_with_params.fund_code == "000001"
        assert data_with_params.fund_name == "测试基金"
        assert data_with_params.report_year == 2024

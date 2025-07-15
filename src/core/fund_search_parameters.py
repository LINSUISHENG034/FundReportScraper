"""
基金搜索参数枚举模块
Fund Search Parameters Enumeration Module

基于真实测试验证的准确参数定义
Based on real testing validation for accurate parameter definitions
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import date
import urllib.parse


class ReportType(str, Enum):
    """报告类型枚举 - 基于真实测试结果"""

    ANNUAL = "FB010010"  # 年度报告
    SEMI_ANNUAL = "FB020010"  # 中期报告
    QUARTERLY_Q1 = "FB030010"  # 第一季度报告
    QUARTERLY_Q2 = "FB030020"  # 第二季度报告
    QUARTERLY_Q3 = "FB030030"  # 第三季度报告
    QUARTERLY_Q4 = "FB030040"  # 第四季度报告
    FUND_PROFILE = "FA010070"  # 基金产品资料概要

    @classmethod
    def get_description(cls, value: str) -> str:
        """获取报告类型描述"""
        descriptions = {
            cls.ANNUAL: "年度报告",
            cls.SEMI_ANNUAL: "中期报告",
            cls.QUARTERLY_Q1: "第一季度报告",
            cls.QUARTERLY_Q2: "第二季度报告",
            cls.QUARTERLY_Q3: "第三季度报告",
            cls.QUARTERLY_Q4: "第四季度报告",
            cls.FUND_PROFILE: "基金产品资料概要",
        }
        return descriptions.get(value, "未知报告类型")


class FundType(str, Enum):
    """基金类型枚举 - 基于真实测试结果"""

    STOCK = "6020-6010"  # 股票型
    MONEY_MARKET = "6020-6020"  # 货币型
    BOND = "6020-6030"  # 债券型
    MIXED = "6020-6040"  # 混合型
    QDII = "6020-6050"  # QDII
    INFRASTRUCTURE = "6020-6084"  # 基础设施基金
    FOF = "6020-6094"  # 基金中基金(FOF)
    COMMODITY = "6020-6104"  # 商品基金

    @classmethod
    def get_description(cls, value: str) -> str:
        """获取基金类型描述"""
        descriptions = {
            cls.STOCK: "股票型",
            cls.MONEY_MARKET: "货币型",
            cls.BOND: "债券型",
            cls.MIXED: "混合型",
            cls.QDII: "QDII",
            cls.INFRASTRUCTURE: "基础设施基金",
            cls.FOF: "基金中基金(FOF)",
            cls.COMMODITY: "商品基金",
        }
        return descriptions.get(value, "未知基金类型")


@dataclass
class FundSearchCriteria:
    """基金搜索条件"""

    year: int
    report_type: ReportType
    fund_type: Optional[FundType] = None
    fund_company_short_name: Optional[str] = None
    fund_code: Optional[str] = None
    fund_short_name: Optional[str] = None
    start_upload_date: Optional[date] = None
    end_upload_date: Optional[date] = None
    page: int = 1
    page_size: int = 20

    def get_description(self) -> str:
        """获取搜索条件的描述"""
        parts = [f"{self.year}年", ReportType.get_description(self.report_type)]

        if self.fund_type:
            parts.append(FundType.get_description(self.fund_type))
        if self.fund_company_short_name:
            parts.append(f"公司:{self.fund_company_short_name}")
        if self.fund_code:
            parts.append(f"代码:{self.fund_code}")
        if self.fund_short_name:
            parts.append(f"名称:{self.fund_short_name}")

        return " | ".join(parts)

    def to_ao_data_params(self) -> Dict[str, Any]:
        """转换为aoData参数格式"""
        display_start = (self.page - 1) * self.page_size

        # 处理特殊情况：基金产品资料概要需要空的reportYear
        report_year = (
            "" if self.report_type == ReportType.FUND_PROFILE else str(self.year)
        )

        return {
            "sEcho": self.page,
            "iColumns": 6,
            "sColumns": ",,,,,",
            "iDisplayStart": display_start,
            "iDisplayLength": self.page_size,
            "mDataProp_0": "fundCode",
            "mDataProp_1": "fundId",
            "mDataProp_2": "organName",
            "mDataProp_3": "reportSendDate",
            "mDataProp_4": "reportDesp",
            "mDataProp_5": "uploadInfoId",
            "fundType": self.fund_type.value if self.fund_type else "",
            "reportTypeCode": self.report_type.value,
            "reportYear": report_year,
            "fundCompanyShortName": self.fund_company_short_name or "",
            "fundCode": self.fund_code or "",
            "fundShortName": self.fund_short_name or "",
            "startUploadDate": self.start_upload_date.strftime("%Y-%m-%d")
            if self.start_upload_date
            else "",
            "endUploadDate": self.end_upload_date.strftime("%Y-%m-%d")
            if self.end_upload_date
            else "",
        }

    def to_ao_data_list(self) -> List[Dict[str, Any]]:
        """转换为aoData列表格式（用于API请求）"""
        params = self.to_ao_data_params()
        return [{"name": key, "value": value} for key, value in params.items()]


class SearchPresets:
    """预设搜索条件"""

    @staticmethod
    def annual_reports_2024() -> FundSearchCriteria:
        """2024年年度报告"""
        return FundSearchCriteria(year=2024, report_type=ReportType.ANNUAL)

    @staticmethod
    def qdii_annual_2024() -> FundSearchCriteria:
        """2024年QDII基金年度报告"""
        return FundSearchCriteria(
            year=2024, report_type=ReportType.ANNUAL, fund_type=FundType.QDII
        )

    @staticmethod
    def quarterly_q1_2024() -> FundSearchCriteria:
        """2024年第一季度报告"""
        return FundSearchCriteria(year=2024, report_type=ReportType.QUARTERLY_Q1)

    @staticmethod
    def company_reports(company_name: str, year: int = 2024) -> FundSearchCriteria:
        """指定公司的年度报告"""
        return FundSearchCriteria(
            year=year,
            report_type=ReportType.ANNUAL,
            fund_company_short_name=company_name,
        )


# 向后兼容的映射（用于现有代码）
LEGACY_REPORT_TYPE_MAPPING = {
    "QUARTERLY": ReportType.QUARTERLY_Q1,
    "SEMI_ANNUAL": ReportType.SEMI_ANNUAL,
    "ANNUAL": ReportType.ANNUAL,
}

LEGACY_FUND_TYPE_MAPPING = {
    "股票型": FundType.STOCK,
    "混合型": FundType.MIXED,
    "债券型": FundType.BOND,
    "货币型": FundType.MONEY_MARKET,
    "QDII": FundType.QDII,
    "FOF": FundType.FOF,
}

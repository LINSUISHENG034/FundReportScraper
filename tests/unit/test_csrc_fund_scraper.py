"""CSRC基金报告爬虫单元测试"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
from httpx import Response

from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.core.fund_search_parameters import ReportType, FundType
from src.scrapers.base import ParseError


class TestCSRCFundScraper:
    """CSRC基金报告爬虫测试类"""
    
    @pytest.fixture
    def scraper(self):
        """创建爬虫实例"""
        return CSRCFundReportScraper()
    
    @pytest.fixture
    def mock_session(self):
        """创建模拟的HTTP会话"""
        session = AsyncMock()
        return session
    
    def test_build_ao_data_basic(self, scraper):
        """测试_build_ao_data基本功能"""
        ao_data = scraper._build_ao_data(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=20
        )
        
        # 验证返回类型
        assert isinstance(ao_data, list), "ao_data应为列表"
        assert len(ao_data) > 0, "ao_data不应为空"
        
        # 验证必要的参数
        ao_dict = {item['name']: item['value'] for item in ao_data}
        
        # 验证分页参数
        assert ao_dict['sEcho'] == 1, "页码参数错误"
        assert ao_dict['iDisplayStart'] == 0, "显示起始位置错误"
        assert ao_dict['iDisplayLength'] == 20, "页面大小错误"
        
        # 验证报告类型
        assert ao_dict['reportTypeCode'] == ReportType.ANNUAL.value, "报告类型代码错误"
        assert ao_dict['reportYear'] == '2024', "报告年份错误"
        
        # 验证列定义
        assert ao_dict['iColumns'] == 6, "列数错误"
        assert 'mDataProp_0' in ao_dict, "缺少列属性定义"
        assert ao_dict['mDataProp_0'] == 'fundCode', "列属性定义错误"
    
    def test_build_ao_data_with_pagination(self, scraper):
        """测试_build_ao_data分页功能"""
        # 测试第2页
        ao_data = scraper._build_ao_data(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=2,
            page_size=50
        )
        
        ao_dict = {item['name']: item['value'] for item in ao_data}
        
        # 验证分页计算
        assert ao_dict['sEcho'] == 2, "页码错误"
        assert ao_dict['iDisplayStart'] == 50, "显示起始位置计算错误"
        assert ao_dict['iDisplayLength'] == 50, "页面大小错误"
        
        # 测试第3页
        ao_data = scraper._build_ao_data(
            year=2023,
            report_type=ReportType.QUARTERLY_Q1,
            page=3,
            page_size=100
        )
        
        ao_dict = {item['name']: item['value'] for item in ao_data}
        assert ao_dict['iDisplayStart'] == 200, "第3页显示起始位置计算错误"
    
    def test_build_ao_data_with_optional_parameters(self, scraper):
        """测试_build_ao_data可选参数"""
        ao_data = scraper._build_ao_data(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=20,
            fund_type="混合型",
            fund_company_short_name="工银瑞信",
            fund_code="001648",
            fund_short_name="工银瑞信",
            start_upload_date="2024-01-01",
            end_upload_date="2024-12-31"
        )
        
        ao_dict = {item['name']: item['value'] for item in ao_data}
        
        # 验证可选参数
        assert ao_dict['fundType'] == "混合型", "基金类型参数错误"
        assert ao_dict['fundCompanyShortName'] == "工银瑞信", "基金公司参数错误"
        assert ao_dict['fundCode'] == "001648", "基金代码参数错误"
        assert ao_dict['fundShortName'] == "工银瑞信", "基金简称参数错误"
        assert ao_dict['startUploadDate'] == "2024-01-01", "开始日期参数错误"
        assert ao_dict['endUploadDate'] == "2024-12-31", "结束日期参数错误"
    
    def test_build_ao_data_empty_optional_parameters(self, scraper):
        """测试_build_ao_data空的可选参数"""
        ao_data = scraper._build_ao_data(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=20
        )
        
        ao_dict = {item['name']: item['value'] for item in ao_data}
        
        # 验证空的可选参数
        assert ao_dict['fundType'] == "", "空基金类型应为空字符串"
        assert ao_dict['fundCompanyShortName'] == "", "空基金公司应为空字符串"
        assert ao_dict['fundCode'] == "", "空基金代码应为空字符串"
        assert ao_dict['fundShortName'] == "", "空基金简称应为空字符串"
        assert ao_dict['startUploadDate'] == "", "空开始日期应为空字符串"
        assert ao_dict['endUploadDate'] == "", "空结束日期应为空字符串"
    
    @pytest.mark.asyncio
    async def test_get_report_list_success(self, scraper):
        """测试get_report_list成功场景"""
        # 模拟成功的响应数据
        mock_response_data = {
            "aaData": [
                {
                    "uploadInfoId": "1752537342",
                    "fundCode": "001648",
                    "fundShortName": "工银瑞信新蓝筹股票",
                    "organName": "工银瑞信基金管理有限公司",
                    "reportYear": "2024",
                    "uploadDate": "2024-04-30",
                    "reportSendDate": "2024-04-30",
                    "reportDesp": "2024年年度报告",
                    "fundId": "001648",
                    "classificationCode": "FB010000",
                    "fundSign": "A"
                },
                {
                    "uploadInfoId": "1752537343",
                    "fundCode": "002958",
                    "fundShortName": "工银瑞信新材料新能源股票",
                    "organName": "工银瑞信基金管理有限公司",
                    "reportYear": "2024",
                    "uploadDate": "2024-04-30",
                    "reportSendDate": "2024-04-30",
                    "reportDesp": "2024年年度报告",
                    "fundId": "002958",
                    "classificationCode": "FB010000",
                    "fundSign": "A"
                }
            ],
            "iTotalRecords": 150,
            "iTotalDisplayRecords": 150
        }
        
        # 创建模拟响应
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        
        # 模拟get方法
        with patch.object(scraper, 'get', return_value=mock_response) as mock_get:
            reports, has_next = await scraper.get_report_list(
                year=2024,
                report_type=ReportType.ANNUAL,
                page=1,
                page_size=20
            )
            
            # 验证调用
            mock_get.assert_called_once()
            call_args = mock_get.call_args[0][0]
            assert "aoData" in call_args, "请求URL应包含aoData参数"
            
            # 验证返回结果
            assert len(reports) == 2, "应返回2个报告"
            assert has_next is True, "应该有下一页"
            
            # 验证报告数据结构
            first_report = reports[0]
            assert first_report['upload_info_id'] == "1752537342", "uploadInfoId错误"
            assert first_report['fund_code'] == "001648", "基金代码错误"
            assert first_report['fund_short_name'] == "工银瑞信新蓝筹股票", "基金名称错误"
            assert first_report['organ_name'] == "工银瑞信基金管理有限公司", "机构名称错误"
    
    @pytest.mark.asyncio
    async def test_get_report_list_no_next_page(self, scraper):
        """测试get_report_list无下一页场景"""
        mock_response_data = {
            "aaData": [
                {
                    "uploadInfoId": "1752537342",
                    "fundCode": "001648",
                    "fundShortName": "工银瑞信新蓝筹股票",
                    "organName": "工银瑞信基金管理有限公司",
                    "reportYear": "2024"
                }
            ],
            "iTotalRecords": 1,
            "iTotalDisplayRecords": 1
        }
        
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        
        with patch.object(scraper, 'get', return_value=mock_response):
            reports, has_next = await scraper.get_report_list(
                year=2024,
                report_type=ReportType.ANNUAL,
                page=1,
                page_size=20
            )
            
            assert len(reports) == 1, "应返回1个报告"
            assert has_next is False, "不应该有下一页"
    
    @pytest.mark.asyncio
    async def test_get_report_list_http_error(self, scraper):
        """测试get_report_list HTTP错误场景"""
        # 模拟HTTP错误
        with patch.object(scraper, 'get', side_effect=Exception("HTTP 500 Error")):
            with pytest.raises(ParseError) as exc_info:
                await scraper.get_report_list(
                    year=2024,
                    report_type=ReportType.ANNUAL,
                    page=1,
                    page_size=20
                )
            
            assert "获取报告列表失败" in str(exc_info.value), "错误信息不正确"
    
    @pytest.mark.asyncio
    async def test_get_report_list_invalid_json(self, scraper):
        """测试get_report_list JSON解析错误场景"""
        # 模拟JSON解析错误
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with patch.object(scraper, 'get', return_value=mock_response):
            with pytest.raises(ParseError):
                await scraper.get_report_list(
                    year=2024,
                    report_type=ReportType.ANNUAL,
                    page=1,
                    page_size=20
                )
    
    @pytest.mark.asyncio
    async def test_download_xbrl_content_success(self, scraper):
        """测试download_xbrl_content成功场景"""
        upload_info_id = "1752537342"
        mock_content = b'<?xml version="1.0" encoding="UTF-8"?>\n<xbrl>test content</xbrl>'
        
        # 创建模拟响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_content
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.url = f"http://example.com/instance?instanceid={upload_info_id}"
        
        # 模拟session
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        scraper.session = mock_session
        
        # 执行下载
        content = await scraper.download_xbrl_content(upload_info_id)
        
        # 验证结果
        assert content == mock_content, "下载内容不匹配"
        mock_session.get.assert_called_once()
        
        # 验证URL构造
        call_args = mock_session.get.call_args[0][0]
        assert upload_info_id in call_args, "URL应包含uploadInfoId"
    
    @pytest.mark.asyncio
    async def test_download_xbrl_content_http_error(self, scraper):
        """测试download_xbrl_content HTTP错误场景"""
        upload_info_id = "1752537342"
        
        # 创建模拟404响应
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        scraper.session = mock_session
        
        # 执行下载并验证异常
        with pytest.raises(Exception) as exc_info:
            await scraper.download_xbrl_content(upload_info_id)
        
        assert "HTTP 404" in str(exc_info.value), "错误信息应包含HTTP状态码"
    
    @pytest.mark.asyncio
    async def test_download_xbrl_content_no_session(self, scraper):
        """测试download_xbrl_content无会话场景"""
        upload_info_id = "1752537342"
        
        # 确保没有会话
        scraper.session = None
        
        # 模拟start_session方法
        with patch.object(scraper, 'start_session', new_callable=AsyncMock) as mock_start:
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'test content'
            mock_response.headers = {"content-type": "application/xml"}
            mock_response.url = "http://example.com"
            
            mock_session.get.return_value = mock_response
            
            # 在start_session调用后设置session
            async def set_session():
                scraper.session = mock_session
            
            mock_start.side_effect = set_session
            
            # 执行下载
            content = await scraper.download_xbrl_content(upload_info_id)
            
            # 验证start_session被调用
            mock_start.assert_called_once()
            assert content == b'test content', "下载内容不匹配"
    
    def test_parse_report_item_dict_format(self, scraper):
        """测试_parse_report_item字典格式解析"""
        item = {
            "uploadInfoId": "1752537342",
            "fundCode": "001648",
            "fundShortName": "工银瑞信新蓝筹股票",
            "organName": "工银瑞信基金管理有限公司",
            "reportYear": "2024",
            "uploadDate": "2024-04-30",
            "reportSendDate": "2024-04-30",
            "reportDesp": "2024年年度报告",
            "fundId": "001648",
            "classificationCode": "FB010000",
            "fundSign": "A"
        }
        
        result = scraper._parse_report_item(item)
        
        assert result is not None, "解析结果不应为None"
        assert result['upload_info_id'] == "1752537342", "uploadInfoId解析错误"
        assert result['fund_code'] == "001648", "基金代码解析错误"
        assert result['fund_short_name'] == "工银瑞信新蓝筹股票", "基金名称解析错误"
        assert result['organ_name'] == "工银瑞信基金管理有限公司", "机构名称解析错误"
        assert result['raw_data'] == item, "原始数据应被保存"
    
    def test_parse_report_item_missing_upload_info_id(self, scraper):
        """测试_parse_report_item缺少uploadInfoId场景"""
        item = {
            "fundCode": "001648",
            "fundShortName": "工银瑞信新蓝筹股票",
            "organName": "工银瑞信基金管理有限公司"
        }
        
        result = scraper._parse_report_item(item)
        
        assert result is None, "缺少uploadInfoId时应返回None"
    
    def test_parse_report_item_invalid_format(self, scraper):
        """测试_parse_report_item无效格式场景"""
        # 测试字符串格式
        result = scraper._parse_report_item("invalid string")
        assert result is None, "无效格式应返回None"
        
        # 测试None
        result = scraper._parse_report_item(None)
        assert result is None, "None应返回None"
        
        # 测试空字典
        result = scraper._parse_report_item({})
        assert result is None, "空字典应返回None"
"""报告搜索API集成测试
Reports Search API Integration Tests

为reports.py API端点提供端到端测试覆盖
"""

import pytest
from httpx import AsyncClient


class TestReportsAPI:
    """报告搜索API测试类"""

    @pytest.mark.asyncio
    async def test_search_reports_success_minimal_params(self, client: AsyncClient):
        """测试基本搜索成功 - 仅使用必填参数"""
        response = await client.get("/api/reports?year=2024&report_type=FB010010")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "pagination" in data
        assert "search_criteria" in data
        
        # 验证分页信息结构
        pagination = data["pagination"]
        assert "page" in pagination
        assert "page_size" in pagination
        assert "total_items" in pagination
        assert "total_pages" in pagination
        
        # 验证搜索条件信息
        search_criteria = data["search_criteria"]
        assert search_criteria["year"] == 2024
        assert search_criteria["report_type"] == "FB010010"

    @pytest.mark.asyncio
    async def test_search_reports_success_all_params(self, client: AsyncClient):
        """测试使用所有可选参数的成功搜索"""
        params = {
            "year": 2024,
            "report_type": "FB010010",
            "page": 1,
            "page_size": 10,
            "fund_type": "6020-6050",
            "fund_company_short_name": "工银瑞信",
            "fund_code": "164906",
            "fund_short_name": "工银全球",
            "start_upload_date": "2024-01-01",
            "end_upload_date": "2024-12-31"
        }
        
        response = await client.get("/api/reports", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # 验证分页参数被正确应用
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 10
        
        # 验证搜索条件被正确记录
        search_criteria = data["search_criteria"]
        assert search_criteria["fund_type"] == "6020-6050"
        assert search_criteria["fund_company_short_name"] == "工银瑞信"
        assert search_criteria["start_upload_date"] == "2024-01-01"
        assert search_criteria["end_upload_date"] == "2024-12-31"

    @pytest.mark.asyncio
    async def test_search_reports_invalid_report_type(self, client: AsyncClient):
        """测试无效的报告类型"""
        response = await client.get("/api/reports?year=2024&report_type=INVALID_TYPE")
        assert response.status_code == 400
        
        error_detail = response.json()["detail"]
        assert "无效的报告类型" in error_detail
        assert "INVALID_TYPE" in error_detail

    @pytest.mark.asyncio
    async def test_search_reports_invalid_fund_type(self, client: AsyncClient):
        """测试无效的基金类型"""
        response = await client.get("/api/reports?year=2024&report_type=FB010010&fund_type=INVALID_FUND_TYPE")
        assert response.status_code == 400
        
        error_detail = response.json()["detail"]
        assert "无效的基金类型" in error_detail
        assert "INVALID_FUND_TYPE" in error_detail

    @pytest.mark.asyncio
    async def test_search_reports_invalid_date_range(self, client: AsyncClient):
        """测试无效的日期范围（开始日期晚于结束日期）"""
        params = {
            "year": 2024,
            "report_type": "FB010010",
            "start_upload_date": "2024-12-31",
            "end_upload_date": "2024-01-01"
        }
        
        response = await client.get("/api/reports", params=params)
        assert response.status_code == 400
        
        error_detail = response.json()["detail"]
        assert "开始日期" in error_detail
        assert "不能晚于结束日期" in error_detail

    @pytest.mark.asyncio
    async def test_search_reports_missing_required_params(self, client: AsyncClient):
        """测试缺少必填参数"""
        # 缺少year参数
        response = await client.get("/api/reports?report_type=FB010010")
        assert response.status_code == 422  # FastAPI validation error
        
        # 缺少report_type参数
        response = await client.get("/api/reports?year=2024")
        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_search_reports_invalid_year_range(self, client: AsyncClient):
        """测试无效的年份范围"""
        # 年份太小
        response = await client.get("/api/reports?year=1999&report_type=FB010010")
        assert response.status_code == 422
        
        # 年份太大
        response = await client.get("/api/reports?year=2031&report_type=FB010010")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_reports_invalid_page_params(self, client: AsyncClient):
        """测试无效的分页参数"""
        # 页码小于1
        response = await client.get("/api/reports?year=2024&report_type=FB010010&page=0")
        assert response.status_code == 422
        
        # 页面大小超过限制
        response = await client.get("/api/reports?year=2024&report_type=FB010010&page_size=101")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_report_types_success(self, client: AsyncClient):
        """测试获取报告类型端点"""
        response = await client.get("/api/reports/types")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # 验证数据结构
        if data["data"]:
            report_type = data["data"][0]
            assert "code" in report_type
            assert "name" in report_type
            assert "value" in report_type

    @pytest.mark.asyncio
    async def test_get_fund_types_success(self, client: AsyncClient):
        """测试获取基金类型端点"""
        response = await client.get("/api/reports/fund-types")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # 验证数据结构
        if data["data"]:
            fund_type = data["data"][0]
            assert "code" in fund_type
            assert "name" in fund_type
            assert "value" in fund_type

    @pytest.mark.asyncio
    async def test_search_reports_response_structure(self, client: AsyncClient):
        """测试搜索响应的数据结构完整性"""
        response = await client.get("/api/reports?year=2024&report_type=FB010010")
        assert response.status_code == 200
        
        data = response.json()
        
        # 验证顶级结构
        required_fields = ["success", "pagination", "data", "search_criteria"]
        for field in required_fields:
            assert field in data
        
        # 验证分页信息结构
        pagination = data["pagination"]
        pagination_fields = ["page", "page_size", "total_items", "total_pages"]
        for field in pagination_fields:
            assert field in pagination
            assert isinstance(pagination[field], int)
        
        # 验证数据列表结构
        assert isinstance(data["data"], list)
        
        # 如果有数据，验证报告项目结构
        if data["data"]:
            report_item = data["data"][0]
            report_fields = [
                "upload_info_id", "fund_code", "fund_id", 
                "fund_short_name", "organ_name", "report_send_date", 
                "report_description"
            ]
            for field in report_fields:
                assert field in report_item
        
        # 验证搜索条件结构
        search_criteria = data["search_criteria"]
        assert "year" in search_criteria
        assert "report_type" in search_criteria
        assert "report_type_name" in search_criteria
"""
API endpoints automated tests.
API接口自动化测试。
"""

import pytest
import uuid
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from src.api.main import app
from src.models.database import Base, Fund, FundReport, ReportType
from src.models.connection import get_db_session


# 测试数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """覆盖数据库会话依赖"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# 覆盖数据库依赖
app.dependency_overrides[get_db_session] = override_get_db

# 创建测试客户端
client = TestClient(app)


@pytest.fixture(scope="module")
def setup_database():
    """设置测试数据库"""
    # 创建测试表
    Base.metadata.create_all(bind=engine)
    
    # 插入测试数据
    db = TestingSessionLocal()
    try:
        # 创建测试基金
        test_fund = Fund(
            fund_code="000001",
            fund_name="测试基金A",
            fund_company="测试基金管理有限公司",
            fund_type="股票型",
            establishment_date=date(2020, 1, 1)
        )
        db.add(test_fund)
        
        test_fund2 = Fund(
            fund_code="000002",
            fund_name="测试基金B",
            fund_company="测试基金管理有限公司",
            fund_type="债券型",
            establishment_date=date(2020, 6, 1)
        )
        db.add(test_fund2)
        
        # 创建测试报告
        test_report = FundReport(
            id=str(uuid.uuid4()),
            fund_code="000001",
            fund_name="测试基金A",
            report_type=ReportType.ANNUAL,
            report_date=date(2024, 12, 31),
            unit_nav=1.234,
            cumulative_nav=1.456,
            file_path="/test/reports/000001_2024.xbrl"
        )
        db.add(test_report)
        
        db.commit()
        
    finally:
        db.close()
    
    yield
    
    # 清理测试数据
    Base.metadata.drop_all(bind=engine)


class TestHealthCheck:
    """健康检查接口测试"""
    
    def test_health_check(self, setup_database):
        """测试健康检查接口"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data
    
    def test_root_endpoint(self):
        """测试根路径接口"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs_url" in data


class TestFundsAPI:
    """基金信息API测试"""
    
    def test_get_funds_list(self, setup_database):
        """测试获取基金列表"""
        response = client.get("/api/v1/funds/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert isinstance(data["data"], list)
    
    def test_get_funds_with_filters(self, setup_database):
        """测试带筛选条件的基金列表"""
        response = client.get("/api/v1/funds/?fund_type=股票型&page=1&size=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        # 应该返回股票型基金
        if data["data"]:
            assert data["data"][0]["fund_type"] == "股票型"
    
    def test_get_fund_detail(self, setup_database):
        """测试获取基金详情"""
        response = client.get("/api/v1/funds/000001")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["fund_code"] == "000001"
        assert data["data"]["fund_name"] == "测试基金A"
    
    def test_get_fund_detail_not_found(self, setup_database):
        """测试获取不存在的基金详情"""
        response = client.get("/api/v1/funds/999999")
        assert response.status_code == 404
    
    def test_get_fund_nav_history(self, setup_database):
        """测试获取基金净值历史"""
        response = client.get("/api/v1/funds/000001/nav-history")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    def test_get_fund_types(self, setup_database):
        """测试获取基金类型列表"""
        response = client.get("/api/v1/funds/types/list")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    def test_get_fund_companies(self, setup_database):
        """测试获取基金公司列表"""
        response = client.get("/api/v1/funds/companies/list")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


class TestReportsAPI:
    """报告信息API测试"""
    
    def test_get_reports_list(self, setup_database):
        """测试获取报告列表"""
        response = client.get("/api/v1/reports/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
    
    def test_get_reports_with_filters(self, setup_database):
        """测试带筛选条件的报告列表"""
        response = client.get("/api/v1/reports/?fund_code=000001&report_type=年报")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_get_fund_latest_report(self, setup_database):
        """测试获取基金最新报告"""
        response = client.get("/api/v1/reports/fund/000001/latest")
        
        # 可能返回200（有报告）或404（无报告）
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert data["data"]["fund_code"] == "000001"
    
    def test_get_fund_holdings_history(self, setup_database):
        """测试获取基金重仓股历史"""
        response = client.get("/api/v1/reports/fund/000001/holdings")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    def test_get_reports_stats(self, setup_database):
        """测试获取报告统计信息"""
        response = client.get("/api/v1/reports/stats/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        stats = data["data"]
        assert "total_reports" in stats
        assert "by_type" in stats


class TestTasksAPI:
    """任务管理API测试"""
    
    def test_get_tasks_list(self, setup_database):
        """测试获取任务列表"""
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
    
    def test_create_task(self, setup_database):
        """测试创建任务"""
        task_data = {
            "task_type": "fund_scraping",
            "parameters": {"fund_code": "000001"},
            "description": "测试任务"
        }
        
        response = client.post("/api/v1/tasks/", json=task_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        task_id = data["data"]["task_id"]
        assert task_id is not None
        
        return task_id
    
    def test_get_task_detail(self, setup_database):
        """测试获取任务详情"""
        # 先创建一个任务
        task_id = self.test_create_task(setup_database)
        
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == task_id
    
    def test_cancel_task(self, setup_database):
        """测试取消任务"""
        # 先创建一个任务
        task_id = self.test_create_task(setup_database)
        
        response = client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_delete_task(self, setup_database):
        """测试删除任务"""
        # 先创建一个任务
        task_id = self.test_create_task(setup_database)
        
        response = client.delete(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_get_tasks_stats(self, setup_database):
        """测试获取任务统计信息"""
        response = client.get("/api/v1/tasks/stats/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        stats = data["data"]
        assert "total_tasks" in stats
        assert "by_status" in stats
        assert "by_type" in stats


class TestAPIErrorHandling:
    """API错误处理测试"""
    
    def test_404_error(self, setup_database):
        """测试404错误处理"""
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "timestamp" in data
    
    def test_invalid_parameters(self, setup_database):
        """测试无效参数处理"""
        # 测试无效的页码
        response = client.get("/api/v1/funds/?page=0")
        assert response.status_code == 422  # Validation error
    
    def test_invalid_date_format(self, setup_database):
        """测试无效日期格式"""
        response = client.get("/api/v1/funds/000001/nav-history?start_date=invalid-date")
        assert response.status_code == 400


class TestAPIDocumentation:
    """API文档测试"""
    
    def test_openapi_schema(self):
        """测试OpenAPI schema"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
    
    def test_swagger_docs(self):
        """测试Swagger文档"""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_docs(self):
        """测试ReDoc文档"""
        response = client.get("/redoc")
        assert response.status_code == 200


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
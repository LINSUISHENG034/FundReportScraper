"""
报告搜索API路由
Reports Search API Routes

基于RESTful设计的报告搜索接口
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.core.fund_search_parameters import (
    FundSearchCriteria, ReportType, FundType
)
from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper


logger = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["报告搜索"])


from fastapi import Request

def get_fund_report_service(request: Request) -> FundReportService:
    """获取共享的基金报告服务实例"""
    return request.app.state.fund_report_service


# Pydantic 响应模型
class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_items: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")


class ReportItem(BaseModel):
    """报告项目"""
    upload_info_id: int = Field(..., description="上传信息ID，用于下载")
    fund_code: str = Field(..., description="基金代码")
    fund_id: int = Field(..., description="基金ID")
    fund_short_name: str = Field(..., description="基金简称")
    organ_name: str = Field(..., description="管理人名称")
    report_send_date: str = Field(..., description="报告发送日期")
    report_description: str = Field(..., description="报告描述")


class ReportSearchResponse(BaseModel):
    """报告搜索响应"""
    success: bool = Field(..., description="请求是否成功")
    pagination: PaginationInfo = Field(..., description="分页信息")
    data: list[ReportItem] = Field(..., description="报告列表")
    search_criteria: dict = Field(..., description="搜索条件")





@router.get("", response_model=ReportSearchResponse)
async def search_reports(
    year: int = Query(..., description="报告年度（必填）", example=2024, ge=2000, le=2030),
    report_type: str = Query(..., description="报告类型代码（必填）", example="FB010010"),
    page: int = Query(1, ge=1, description="页码", example=1),
    page_size: int = Query(20, ge=1, le=100, description="每页数量", example=20),
    fund_type: Optional[str] = Query(None, description="基金类型代码（可选）", example="6020-6050"),
    fund_company_short_name: Optional[str] = Query(None, description="基金管理人简称（可选）", example="工银瑞信"),
    fund_code: Optional[str] = Query(None, description="基金代码（可选）", example="164906"),
    fund_short_name: Optional[str] = Query(None, description="基金简称（可选）", example="工银全球"),
    start_upload_date: Optional[date] = Query(None, description="开始上传日期（可选）", example="2024-01-01"),
    end_upload_date: Optional[date] = Query(None, description="结束上传日期（可选）", example="2024-12-31"),
    service: FundReportService = Depends(get_fund_report_service)
) -> ReportSearchResponse:
    """
    搜索基金报告
    
    强大的报告搜索功能，支持全参数筛选和分页。
    返回带分页信息的报告列表，每个报告包含用于下载的 upload_info_id。
    """
    bound_logger = logger.bind(
        year=year,
        report_type=report_type,
        page=page,
        page_size=page_size
    )
    
    bound_logger.info("api.reports.search.start")
    
    try:
        # 参数验证日志
        bound_logger.info(
            "api.reports.search.params_validation",
            year=year,
            report_type=report_type,
            fund_type=fund_type,
            page=page,
            page_size=page_size
        )
        
        # 验证报告类型
        try:
            report_type_enum = ReportType(report_type)
            bound_logger.debug(
                "api.reports.search.report_type_valid",
                report_type=report_type,
                description=ReportType.get_description(report_type_enum)
            )
        except ValueError:
            valid_types = [f"{rt.value} ({ReportType.get_description(rt)})" for rt in ReportType]
            error_detail = f"无效的报告类型: {report_type}. 有效值: {valid_types}"
            bound_logger.warning(
                "api.reports.search.invalid_report_type",
                report_type=report_type,
                valid_types=[rt.value for rt in ReportType]
            )
            raise HTTPException(status_code=400, detail=error_detail)
        
        # 验证基金类型
        fund_type_enum = None
        if fund_type:
            try:
                fund_type_enum = FundType(fund_type)
                bound_logger.debug(
                    "api.reports.search.fund_type_valid",
                    fund_type=fund_type,
                    description=FundType.get_description(fund_type_enum)
                )
            except ValueError:
                valid_types = [f"{ft.value} ({FundType.get_description(ft)})" for ft in FundType]
                error_detail = f"无效的基金类型: {fund_type}. 有效值: {valid_types}"
                bound_logger.warning(
                    "api.reports.search.invalid_fund_type",
                    fund_type=fund_type,
                    valid_types=[ft.value for ft in FundType]
                )
                raise HTTPException(status_code=400, detail=error_detail)
        
        # 验证日期范围
        if start_upload_date and end_upload_date and start_upload_date > end_upload_date:
            error_detail = f"开始日期 ({start_upload_date}) 不能晚于结束日期 ({end_upload_date})"
            bound_logger.warning(
                "api.reports.search.invalid_date_range",
                start_date=start_upload_date,
                end_date=end_upload_date
            )
            raise HTTPException(status_code=400, detail=error_detail)
        
        # 构建搜索条件
        criteria = FundSearchCriteria(
            year=year,
            report_type=report_type_enum,
            fund_type=fund_type_enum,
            fund_company_short_name=fund_company_short_name,
            fund_code=fund_code,
            fund_short_name=fund_short_name,
            start_upload_date=start_upload_date,
            end_upload_date=end_upload_date,
            page=page,
            page_size=page_size
        )
        
        # 执行搜索
        search_result = await service.search_reports(criteria)
        
        if not search_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"搜索失败: {search_result.get('error', 'Unknown error')}"
            )
        
        # 转换数据格式
        reports_data = search_result.get("data", [])
        report_items = [
            ReportItem(
                upload_info_id=report.get("upload_info_id"),
                fund_code=report.get("fund_code"),
                fund_id=report.get("fund_id"),
                fund_short_name=report.get("fund_short_name"),
                organ_name=report.get("organ_name"),
                report_send_date=report.get("report_send_date"),
                report_description=report.get("report_desp")
            )
            for report in reports_data
        ]

        # 使用从服务层返回的准确分页信息
        pagination = PaginationInfo(
            page=criteria.page,
            page_size=criteria.page_size,
            total_items=search_result.get("total_count", 0),
            total_pages=search_result.get("total_pages", 0)
        )
        
        # 构建搜索条件信息
        search_criteria_info = {
            "year": year,
            "report_type": report_type,
            "report_type_name": ReportType.get_description(report_type_enum),
            "fund_type": fund_type,
            "fund_type_name": FundType.get_description(fund_type_enum) if fund_type_enum else None,
            "fund_company_short_name": fund_company_short_name,
            "fund_code": fund_code,
            "fund_short_name": fund_short_name,
            "start_upload_date": start_upload_date.isoformat() if start_upload_date else None,
            "end_upload_date": end_upload_date.isoformat() if end_upload_date else None
        }
        
        response = ReportSearchResponse(
            success=True,
            pagination=pagination,
            data=report_items,
            search_criteria=search_criteria_info
        )
        
        bound_logger.info(
            "api.reports.search.success",
            total_found=pagination.total_items,
            page=page,
            page_size=page_size
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.reports.search.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/types", tags=["参数枚举"])
async def get_report_types():
    """获取所有报告类型"""
    return {
        "success": True,
        "data": [
            {
                "code": rt.value,
                "name": ReportType.get_description(rt),
                "value": rt.value
            }
            for rt in ReportType
        ]
    }


@router.get("/fund-types", tags=["参数枚举"])
async def get_fund_types():
    """获取所有基金类型"""
    return {
        "success": True,
        "data": [
            {
                "code": ft.value,
                "name": FundType.get_description(ft),
                "value": ft.value
            }
            for ft in FundType
        ]
    }

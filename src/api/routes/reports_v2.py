"""
报告搜索API路由 (V2)
Reports Search API Routes (V2)

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

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["报告搜索"])


# Pydantic 响应模型
class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_items: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")


class ReportItem(BaseModel):
    """报告项目"""
    upload_info_id: str = Field(..., description="上传信息ID，用于下载")
    fund_code: str = Field(..., description="基金代码")
    fund_id: str = Field(..., description="基金ID")
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


def get_fund_report_service() -> FundReportService:
    """
    获取基金报告服务实例
    Get fund report service instance
    """
    from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
    scraper = CSRCFundReportScraper()
    return FundReportService(scraper)


@router.get("", response_model=ReportSearchResponse)
async def search_reports(
    year: int = Query(..., description="报告年度", example=2024),
    report_type: str = Query(..., description="报告类型代码", example="FB010010"),
    page: int = Query(1, ge=1, description="页码", example=1),
    page_size: int = Query(20, ge=1, le=100, description="每页数量", example=20),
    fund_type: Optional[str] = Query(None, description="基金类型代码", example="6020-6050"),
    fund_company_short_name: Optional[str] = Query(None, description="基金管理人简称", example="工银瑞信"),
    fund_code: Optional[str] = Query(None, description="基金代码", example="164906"),
    fund_short_name: Optional[str] = Query(None, description="基金简称", example="工银全球"),
    start_upload_date: Optional[date] = Query(None, description="开始上传日期", example="2024-01-01"),
    end_upload_date: Optional[date] = Query(None, description="结束上传日期", example="2024-12-31"),
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
        # 验证报告类型
        try:
            report_type_enum = ReportType(report_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的报告类型: {report_type}. 有效值: {[rt.value for rt in ReportType]}"
            )
        
        # 验证基金类型
        fund_type_enum = None
        if fund_type:
            try:
                fund_type_enum = FundType(fund_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的基金类型: {fund_type}. 有效值: {[ft.value for ft in FundType]}"
                )
        
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
        reports_data = search_result["data"]
        report_items = []
        
        for report in reports_data:
            report_item = ReportItem(
                upload_info_id=report.get("uploadInfoId", ""),
                fund_code=report.get("fundCode", ""),
                fund_id=report.get("fundId", ""),
                fund_short_name=report.get("fundShortName", ""),
                organ_name=report.get("organName", ""),
                report_send_date=report.get("reportSendDate", ""),
                report_description=report.get("reportDesp", "")
            )
            report_items.append(report_item)
        
        # 计算分页信息
        total_items = len(report_items)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages
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
            total_found=total_items,
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

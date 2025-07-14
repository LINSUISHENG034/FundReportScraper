"""
基金报告API路由
Fund Reports API Routes

基于验证结果的最优API设计
"""

from datetime import date
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel

from src.core.logging import get_logger
from src.core.fund_search_parameters import (
    FundSearchCriteria, ReportType, FundType, SearchPresets
)
from src.services.fund_report_service import FundReportService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/fund-reports", tags=["基金报告"])


def get_fund_report_service(request: Request) -> FundReportService:
    """
    依赖注入函数，用于获取共享的 FundReportService 实例
    """
    return request.app.state.fund_report_service


class SearchRequest(BaseModel):
    """搜索请求模型"""
    year: int
    report_type: str
    fund_type: Optional[str] = None
    fund_company_short_name: Optional[str] = None
    fund_code: Optional[str] = None
    fund_short_name: Optional[str] = None
    start_upload_date: Optional[date] = None
    end_upload_date: Optional[date] = None
    page: int = 1
    page_size: int = 20


class BatchDownloadRequest(BaseModel):
    """批量下载请求模型"""
    search_criteria: SearchRequest
    max_concurrent: int = 3
    save_dir: Optional[str] = None


@router.get("/search")
async def search_fund_reports(
    year: int = Query(..., description="报告年度"),
    report_type: str = Query(..., description="报告类型代码"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    fund_type: Optional[str] = Query(None, description="基金类型代码"),
    fund_company_short_name: Optional[str] = Query(None, description="基金管理人简称"),
    fund_code: Optional[str] = Query(None, description="基金代码"),
    fund_short_name: Optional[str] = Query(None, description="基金简称"),
    start_upload_date: Optional[date] = Query(None, description="开始上传日期 YYYY-MM-DD"),
    end_upload_date: Optional[date] = Query(None, description="结束上传日期 YYYY-MM-DD"),
    service: FundReportService = Depends(get_fund_report_service)
) -> dict:
    """
    搜索基金报告
    基于验证的6参数搜索功能
    """
    bound_logger = logger.bind(
        year=year,
        report_type=report_type,
        page=page,
        page_size=page_size
    )
    
    bound_logger.info("api.fund_reports.search.start")
    
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
        
        # 使用服务层搜索
        result = await service.search_reports(criteria)
        
        bound_logger.info(
            "api.fund_reports.search.success",
            total_found=result.get("pagination", {}).get("total", 0)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.fund_reports.search.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/search-all")
async def search_all_pages(
    year: int = Query(..., description="报告年度"),
    report_type: str = Query(..., description="报告类型代码"),
    fund_type: Optional[str] = Query(None, description="基金类型代码"),
    fund_company_short_name: Optional[str] = Query(None, description="基金管理人简称"),
    fund_code: Optional[str] = Query(None, description="基金代码"),
    fund_short_name: Optional[str] = Query(None, description="基金简称"),
    max_pages: Optional[int] = Query(None, ge=1, le=50, description="最大页数限制"),
    service: FundReportService = Depends(get_fund_report_service)
) -> dict:
    """
    获取所有页面的报告
    Get all pages of reports
    """
    bound_logger = logger.bind(
        year=year,
        report_type=report_type,
        max_pages=max_pages
    )
    
    bound_logger.info("api.fund_reports.search_all.start")
    
    try:
        # 验证参数
        try:
            report_type_enum = ReportType(report_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的报告类型: {report_type}"
            )
        
        fund_type_enum = None
        if fund_type:
            try:
                fund_type_enum = FundType(fund_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的基金类型: {fund_type}"
                )
        
        # 构建搜索条件
        criteria = FundSearchCriteria(
            year=year,
            report_type=report_type_enum,
            fund_type=fund_type_enum,
            fund_company_short_name=fund_company_short_name,
            fund_code=fund_code,
            fund_short_name=fund_short_name,
            page_size=100  # 使用较大的页面大小提高效率
        )
        
        # 使用服务层搜索所有页面
        result = await service.search_all_pages(criteria, max_pages)
        
        bound_logger.info(
            "api.fund_reports.search_all.success",
            total_pages=result.get("pagination", {}).get("total_pages", 0),
            total_reports=result.get("pagination", {}).get("total_reports", 0)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.fund_reports.search_all.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")



@router.get("/report-types")
async def get_report_types() -> dict:
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


@router.get("/fund-types")
async def get_fund_types() -> dict:
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


@router.post("/enhanced-batch-download")
async def enhanced_batch_download(
    request: BatchDownloadRequest,
    service: FundReportService = Depends(get_fund_report_service)
) -> dict:
    """
    增强的批量下载功能
    基于验证实现的搜索+下载一体化功能
    Enhanced batch download with integrated search and download
    """
    bound_logger = logger.bind(
        year=request.search_criteria.year,
        report_type=request.search_criteria.report_type,
        max_concurrent=request.max_concurrent
    )

    bound_logger.info("api.fund_reports.enhanced_batch_download.start")

    try:
        # 验证参数
        try:
            report_type_enum = ReportType(request.search_criteria.report_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"无效的报告类型: {request.search_criteria.report_type}"
            )

        fund_type_enum = None
        if request.search_criteria.fund_type:
            try:
                fund_type_enum = FundType(request.search_criteria.fund_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的基金类型: {request.search_criteria.fund_type}"
                )

        # 构建搜索条件
        criteria = FundSearchCriteria(
            year=request.search_criteria.year,
            report_type=report_type_enum,
            fund_type=fund_type_enum,
            fund_company_short_name=request.search_criteria.fund_company_short_name,
            fund_code=request.search_criteria.fund_code,
            fund_short_name=request.search_criteria.fund_short_name,
            start_upload_date=request.search_criteria.start_upload_date,
            end_upload_date=request.search_criteria.end_upload_date,
            page_size=100  # 使用较大的页面大小提高效率
        )

        # 设置保存目录
        save_dir = Path(request.save_dir) if request.save_dir else Path("data/enhanced_downloads")

        # 执行增强的批量下载
        result = await service.enhanced_batch_download(
            criteria=criteria,
            save_dir=save_dir,
            max_concurrent=request.max_concurrent,
            max_reports=getattr(request, 'max_reports', None)
        )

        bound_logger.info(
            "api.fund_reports.enhanced_batch_download.success",
            success_count=result.get("statistics", {}).get("success", 0),
            failed_count=result.get("statistics", {}).get("failed", 0),
            duration=result.get("statistics", {}).get("duration", 0)
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error(
            "api.fund_reports.enhanced_batch_download.error",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=f"增强批量下载失败: {str(e)}")


@router.get("/presets")
async def get_search_presets() -> dict:
    """获取预设搜索条件"""
    return {
        "success": True,
        "data": {
            "annual_2024": {
                "name": "2024年年度报告",
                "criteria": SearchPresets.annual_reports_2024().__dict__
            },
            "qdii_annual_2024": {
                "name": "2024年QDII基金年度报告",
                "criteria": SearchPresets.qdii_annual_2024().__dict__
            },
            "quarterly_q1_2024": {
                "name": "2024年第一季度报告",
                "criteria": SearchPresets.quarterly_q1_2024().__dict__
            }
        }
    }
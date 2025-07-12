"""
基金信息相关API路由
Fund information related API routes
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional

from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.models.database import Fund, FundReport
from src.api.schemas import (
    FundResponse, FundListResponse, FundBaseInfo, FundNavInfo,
    BaseResponse
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=FundListResponse, summary="获取基金列表")
async def get_funds(
    fund_code: Optional[str] = Query(None, description="基金代码"),
    fund_name: Optional[str] = Query(None, description="基金名称（支持模糊搜索）"),
    fund_company: Optional[str] = Query(None, description="基金公司（支持模糊搜索）"),
    fund_type: Optional[str] = Query(None, description="基金类型"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db_session)
):
    """
    获取基金列表，支持多条件筛选和分页
    Get fund list with filtering and pagination
    """
    logger.info("api.funds.get_funds.start", 
               fund_code=fund_code, 
               fund_name=fund_name,
               fund_company=fund_company,
               fund_type=fund_type,
               page=page, 
               size=size)
    
    try:
        # 构建查询条件
        query = db.query(Fund)
        
        if fund_code:
            query = query.filter(Fund.fund_code == fund_code)
        
        if fund_name:
            query = query.filter(Fund.fund_name.contains(fund_name))
        
        if fund_company:
            query = query.filter(Fund.fund_company.contains(fund_company))
            
        if fund_type:
            query = query.filter(Fund.fund_type == fund_type)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * size
        funds = query.offset(offset).limit(size).all()
        
        # 转换为响应模型
        fund_list = []
        for fund in funds:
            fund_info = FundBaseInfo(
                fund_code=fund.fund_code,
                fund_name=fund.fund_name,
                fund_company=fund.fund_company,
                fund_type=fund.fund_type,
                establishment_date=fund.establishment_date
            )
            fund_list.append(fund_info)
        
        logger.info("api.funds.get_funds.success", 
                   total=total, 
                   returned=len(fund_list))
        
        return FundListResponse(
            data=fund_list,
            total=total,
            page=page,
            size=size,
            message=f"成功获取 {len(fund_list)} 条基金信息"
        )
        
    except Exception as e:
        logger.error("api.funds.get_funds.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取基金列表失败: {str(e)}"
        )


@router.get("/{fund_code}", response_model=FundResponse, summary="获取基金详细信息")
async def get_fund_detail(
    fund_code: str,
    db: Session = Depends(get_db_session)
):
    """
    根据基金代码获取基金详细信息
    Get fund detail by fund code
    """
    logger.info("api.funds.get_fund_detail.start", fund_code=fund_code)
    
    try:
        # 查询基金基础信息
        fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
        
        if not fund:
            logger.warning("api.funds.get_fund_detail.not_found", fund_code=fund_code)
            raise HTTPException(
                status_code=404,
                detail=f"未找到基金代码为 {fund_code} 的基金"
            )
        
        # 获取最新的报告（用于净值信息）
        latest_report = db.query(FundReport)\
            .filter(FundReport.fund_code == fund_code)\
            .order_by(FundReport.report_date.desc())\
            .first()
        
        # 构建基础信息
        fund_info = FundBaseInfo(
            fund_code=fund.fund_code,
            fund_name=fund.fund_name,
            fund_company=fund.fund_company,
            fund_type=fund.fund_type,
            establishment_date=fund.establishment_date
        )
        
        # 构建净值信息（如果有最新报告）
        nav_info = None
        if latest_report:
            nav_info = FundNavInfo(
                unit_nav=latest_report.unit_nav,
                cumulative_nav=latest_report.cumulative_nav,
                nav_date=latest_report.report_date,
                daily_change=getattr(latest_report, 'daily_change', None),
                one_month_return=getattr(latest_report, 'one_month_return', None),
                one_year_return=getattr(latest_report, 'one_year_return', None),
                since_inception_return=getattr(latest_report, 'since_inception_return', None)
            )
        
        logger.info("api.funds.get_fund_detail.success", 
                   fund_code=fund_code,
                   has_nav_info=nav_info is not None)
        
        return FundResponse(
            data=fund_info,
            nav_info=nav_info,
            message=f"成功获取基金 {fund_code} 的详细信息"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.funds.get_fund_detail.error", 
                    fund_code=fund_code, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取基金详细信息失败: {str(e)}"
        )


@router.get("/{fund_code}/nav-history", response_model=BaseResponse, summary="获取基金净值历史")
async def get_fund_nav_history(
    fund_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="返回条数限制"),
    db: Session = Depends(get_db_session)
):
    """
    获取基金净值历史数据
    Get fund NAV history
    """
    logger.info("api.funds.get_fund_nav_history.start", 
               fund_code=fund_code,
               start_date=start_date,
               end_date=end_date,
               limit=limit)
    
    try:
        # 验证基金是否存在
        fund = db.query(Fund).filter(Fund.fund_code == fund_code).first()
        if not fund:
            raise HTTPException(
                status_code=404,
                detail=f"未找到基金代码为 {fund_code} 的基金"
            )
        
        # 构建查询
        query = db.query(FundReport).filter(FundReport.fund_code == fund_code)
        
        # 添加日期筛选
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(FundReport.report_date >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="开始日期格式错误，请使用 YYYY-MM-DD 格式"
                )
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(FundReport.report_date <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="结束日期格式错误，请使用 YYYY-MM-DD 格式"
                )
        
        # 按日期倒序排列并限制数量
        reports = query.order_by(FundReport.report_date.desc()).limit(limit).all()
        
        # 构建净值历史数据
        nav_history = []
        for report in reports:
            nav_data = {
                "date": report.report_date.isoformat(),
                "unit_nav": report.unit_nav,
                "cumulative_nav": report.cumulative_nav,
                "report_type": report.report_type.value if report.report_type else None
            }
            nav_history.append(nav_data)
        
        logger.info("api.funds.get_fund_nav_history.success", 
                   fund_code=fund_code,
                   records_count=len(nav_history))
        
        return BaseResponse(
            success=True,
            message=f"成功获取基金 {fund_code} 的 {len(nav_history)} 条净值历史记录",
            data=nav_history
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.funds.get_fund_nav_history.error", 
                    fund_code=fund_code, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取净值历史失败: {str(e)}"
        )


@router.get("/types/list", response_model=BaseResponse, summary="获取基金类型列表")
async def get_fund_types(
    db: Session = Depends(get_db_session)
):
    """
    获取所有基金类型列表
    Get all fund types
    """
    logger.info("api.funds.get_fund_types.start")
    
    try:
        # 查询所有不同的基金类型
        fund_types = db.query(Fund.fund_type).distinct().filter(
            Fund.fund_type.isnot(None)
        ).all()
        
        types_list = [ft[0] for ft in fund_types if ft[0]]
        
        logger.info("api.funds.get_fund_types.success", 
                   types_count=len(types_list))
        
        return BaseResponse(
            success=True,
            message=f"成功获取 {len(types_list)} 种基金类型",
            data=types_list
        )
        
    except Exception as e:
        logger.error("api.funds.get_fund_types.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取基金类型列表失败: {str(e)}"
        )


@router.get("/companies/list", response_model=BaseResponse, summary="获取基金公司列表")
async def get_fund_companies(
    db: Session = Depends(get_db_session)
):
    """
    获取所有基金公司列表
    Get all fund companies
    """
    logger.info("api.funds.get_fund_companies.start")
    
    try:
        # 查询所有不同的基金公司
        companies = db.query(Fund.fund_company).distinct().filter(
            Fund.fund_company.isnot(None)
        ).all()
        
        companies_list = [c[0] for c in companies if c[0]]
        
        logger.info("api.funds.get_fund_companies.success", 
                   companies_count=len(companies_list))
        
        return BaseResponse(
            success=True,
            message=f"成功获取 {len(companies_list)} 家基金公司",
            data=companies_list
        )
        
    except Exception as e:
        logger.error("api.funds.get_fund_companies.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取基金公司列表失败: {str(e)}"
        )
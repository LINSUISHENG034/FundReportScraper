"""
报告信息相关API路由
Report information related API routes
"""

from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional

from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.models.database import FundReport, AssetAllocation, TopHolding, IndustryAllocation, ReportType
from src.api.schemas import (
    ReportResponse, ReportListResponse, ReportDetail, 
    AssetAllocation as AssetAllocationSchema,
    TopHolding as TopHoldingSchema,
    IndustryAllocation as IndustryAllocationSchema,
    ReportTypeEnum, BaseResponse
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=ReportListResponse, summary="获取报告列表")
async def get_reports(
    fund_code: Optional[str] = Query(None, description="基金代码"),
    report_type: Optional[ReportTypeEnum] = Query(None, description="报告类型"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db_session)
):
    """
    获取报告列表，支持多条件筛选和分页
    Get report list with filtering and pagination
    """
    logger.info("api.reports.get_reports.start", 
               fund_code=fund_code,
               report_type=report_type,
               start_date=start_date,
               end_date=end_date,
               page=page, 
               size=size)
    
    try:
        # 构建查询条件
        query = db.query(FundReport)
        
        if fund_code:
            query = query.filter(FundReport.fund_code == fund_code)
        
        if report_type:
            # 将枚举值转换为数据库枚举
            db_report_type = ReportType(report_type.value)
            query = query.filter(FundReport.report_type == db_report_type)
        
        # 日期筛选
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
        
        # 获取总数
        total = query.count()
        
        # 分页查询，按报告日期倒序
        offset = (page - 1) * size
        reports = query.order_by(desc(FundReport.report_date)).offset(offset).limit(size).all()
        
        # 转换为响应模型
        report_list = []
        for report in reports:
            report_detail = ReportDetail(
                report_id=str(report.id),
                fund_code=report.fund_code,
                fund_name=report.fund_name or "",
                report_type=ReportTypeEnum(report.report_type.value),
                report_date=report.report_date,
                file_path=report.file_path,
                created_at=report.created_at,
                updated_at=report.updated_at,
                # 暂时设为空，后续可以关联查询
                asset_allocation=None,
                top_holdings=[],
                industry_allocation=[]
            )
            report_list.append(report_detail)
        
        logger.info("api.reports.get_reports.success", 
                   total=total, 
                   returned=len(report_list))
        
        return ReportListResponse(
            data=report_list,
            total=total,
            page=page,
            size=size,
            message=f"成功获取 {len(report_list)} 条报告信息"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.reports.get_reports.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取报告列表失败: {str(e)}"
        )


@router.get("/{report_id}", response_model=ReportResponse, summary="获取报告详细信息")
async def get_report_detail(
    report_id: str,
    db: Session = Depends(get_db_session)
):
    """
    根据报告ID获取报告详细信息，包括资产配置、重仓股、行业配置等
    Get report detail by report ID
    """
    logger.info("api.reports.get_report_detail.start", report_id=report_id)
    
    try:
        # 查询报告基础信息
        report = db.query(FundReport).filter(FundReport.id == report_id).first()
        
        if not report:
            logger.warning("api.reports.get_report_detail.not_found", report_id=report_id)
            raise HTTPException(
                status_code=404,
                detail=f"未找到ID为 {report_id} 的报告"
            )
        
        # 查询资产配置
        asset_allocation_obj = db.query(AssetAllocation).filter(
            AssetAllocation.report_id == report.id
        ).first()
        
        asset_allocation = None
        if asset_allocation_obj:
            asset_allocation = AssetAllocationSchema(
                stock_ratio=asset_allocation_obj.stock_ratio,
                bond_ratio=asset_allocation_obj.bond_ratio,
                cash_ratio=asset_allocation_obj.cash_ratio,
                other_ratio=asset_allocation_obj.other_ratio,
                total_assets=asset_allocation_obj.total_assets
            )
        
        # 查询前十大重仓股
        top_holdings_objs = db.query(TopHolding).filter(
            TopHolding.report_id == report.id
        ).order_by(TopHolding.holding_ratio.desc()).limit(10).all()
        
        top_holdings = []
        for holding in top_holdings_objs:
            top_holding = TopHoldingSchema(
                stock_code=holding.stock_code,
                stock_name=holding.stock_name,
                holding_ratio=holding.holding_ratio,
                market_value=holding.market_value,
                shares_held=holding.shares_held
            )
            top_holdings.append(top_holding)
        
        # 查询行业配置
        industry_allocation_objs = db.query(IndustryAllocation).filter(
            IndustryAllocation.report_id == report.id
        ).order_by(IndustryAllocation.allocation_ratio.desc()).all()
        
        industry_allocations = []
        for industry in industry_allocation_objs:
            industry_allocation = IndustryAllocationSchema(
                industry_name=industry.industry_name,
                allocation_ratio=industry.allocation_ratio,
                market_value=industry.market_value
            )
            industry_allocations.append(industry_allocation)
        
        # 构建完整报告信息
        report_detail = ReportDetail(
            report_id=str(report.id),
            fund_code=report.fund_code,
            fund_name=report.fund_name or "",
            report_type=ReportTypeEnum(report.report_type.value),
            report_date=report.report_date,
            file_path=report.file_path,
            asset_allocation=asset_allocation,
            top_holdings=top_holdings,
            industry_allocation=industry_allocations,
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        
        logger.info("api.reports.get_report_detail.success", 
                   report_id=report_id,
                   fund_code=report.fund_code,
                   has_asset_allocation=asset_allocation is not None,
                   top_holdings_count=len(top_holdings),
                   industry_allocations_count=len(industry_allocations))
        
        return ReportResponse(
            data=report_detail,
            message=f"成功获取报告 {report_id} 的详细信息"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.reports.get_report_detail.error", 
                    report_id=report_id, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取报告详细信息失败: {str(e)}"
        )


@router.get("/fund/{fund_code}/latest", response_model=ReportResponse, summary="获取基金最新报告")
async def get_fund_latest_report(
    fund_code: str,
    report_type: Optional[ReportTypeEnum] = Query(None, description="报告类型"),
    db: Session = Depends(get_db_session)
):
    """
    获取指定基金的最新报告
    Get latest report for specified fund
    """
    logger.info("api.reports.get_fund_latest_report.start", 
               fund_code=fund_code,
               report_type=report_type)
    
    try:
        # 构建查询
        query = db.query(FundReport).filter(FundReport.fund_code == fund_code)
        
        if report_type:
            db_report_type = ReportType(report_type.value)
            query = query.filter(FundReport.report_type == db_report_type)
        
        # 获取最新报告
        latest_report = query.order_by(desc(FundReport.report_date)).first()
        
        if not latest_report:
            logger.warning("api.reports.get_fund_latest_report.not_found", 
                          fund_code=fund_code)
            raise HTTPException(
                status_code=404,
                detail=f"未找到基金 {fund_code} 的报告"
            )
        
        # 递归调用获取详细信息
        return await get_report_detail(str(latest_report.id), db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.reports.get_fund_latest_report.error", 
                    fund_code=fund_code, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取最新报告失败: {str(e)}"
        )


@router.get("/fund/{fund_code}/holdings", response_model=BaseResponse, summary="获取基金重仓股历史")
async def get_fund_holdings_history(
    fund_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=50, description="每个报告期的重仓股数量"),
    db: Session = Depends(get_db_session)
):
    """
    获取基金重仓股历史变化
    Get fund holdings history
    """
    logger.info("api.reports.get_fund_holdings_history.start", 
               fund_code=fund_code,
               start_date=start_date,
               end_date=end_date,
               limit=limit)
    
    try:
        # 构建查询条件
        query = db.query(FundReport).filter(FundReport.fund_code == fund_code)
        
        # 日期筛选
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
        
        # 获取报告列表，按日期倒序
        reports = query.order_by(desc(FundReport.report_date)).all()
        
        holdings_history = []
        for report in reports:
            # 获取该报告的重仓股
            holdings = db.query(TopHolding).filter(
                TopHolding.report_id == report.id
            ).order_by(TopHolding.holding_ratio.desc()).limit(limit).all()
            
            if holdings:
                holdings_data = {
                    "report_date": report.report_date.isoformat(),
                    "report_type": report.report_type.value,
                    "holdings": [
                        {
                            "stock_code": h.stock_code,
                            "stock_name": h.stock_name,
                            "holding_ratio": h.holding_ratio,
                            "market_value": h.market_value
                        }
                        for h in holdings
                    ]
                }
                holdings_history.append(holdings_data)
        
        logger.info("api.reports.get_fund_holdings_history.success", 
                   fund_code=fund_code,
                   periods_count=len(holdings_history))
        
        return BaseResponse(
            success=True,
            message=f"成功获取基金 {fund_code} 的 {len(holdings_history)} 个报告期重仓股历史",
            data=holdings_history
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api.reports.get_fund_holdings_history.error", 
                    fund_code=fund_code, 
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取重仓股历史失败: {str(e)}"
        )


@router.get("/stats/summary", response_model=BaseResponse, summary="获取报告统计信息")
async def get_reports_stats(
    db: Session = Depends(get_db_session)
):
    """
    获取报告的统计信息
    Get reports statistics
    """
    logger.info("api.reports.get_reports_stats.start")
    
    try:
        # 总报告数
        total_reports = db.query(FundReport).count()
        
        # 按类型统计
        type_stats = {}
        for report_type in ReportType:
            count = db.query(FundReport).filter(
                FundReport.report_type == report_type
            ).count()
            type_stats[report_type.value] = count
        
        # 按基金公司统计前10
        company_stats = db.execute("""
            SELECT fund_company, COUNT(*) as report_count
            FROM fund_reports 
            WHERE fund_company IS NOT NULL
            GROUP BY fund_company 
            ORDER BY report_count DESC 
            LIMIT 10
        """).fetchall()
        
        # 最新报告日期
        latest_report = db.query(FundReport).order_by(
            desc(FundReport.report_date)
        ).first()
        
        latest_report_date = latest_report.report_date.isoformat() if latest_report else None
        
        stats = {
            "total_reports": total_reports,
            "by_type": type_stats,
            "top_companies": [
                {"company": row[0], "report_count": row[1]} 
                for row in company_stats
            ],
            "latest_report_date": latest_report_date
        }
        
        logger.info("api.reports.get_reports_stats.success", 
                   total_reports=total_reports)
        
        return BaseResponse(
            success=True,
            message="成功获取报告统计信息",
            data=stats
        )
        
    except Exception as e:
        logger.error("api.reports.get_reports_stats.error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )
"""
基金数据服务
Fund Data Service

管理基金报告数据的持久化和查询
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pathlib import Path

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from src.core.logging import get_logger
from src.models.fund_data import (
    FundReport, AssetAllocation, TopHolding, IndustryAllocation,
    create_fund_data_tables
)
from src.parsers.xbrl_parser import ParsedFundData

logger = get_logger(__name__)


class FundDataService:
    """
    基金数据服务
    Fund Data Service
    
    负责将解析后的基金数据保存到数据库，并提供查询功能
    """
    
    def __init__(self, db_url: str = "sqlite:///fund_reports.db"):
        """
        初始化基金数据服务
        
        Args:
            db_url: 数据库连接URL
        """
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # 确保数据表存在
        self._init_database()
        
        self.logger = logger.bind(component="fund_data_service", db_url=db_url)
        self.logger.info("fund_data_service.initialized")
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            create_fund_data_tables(self.engine)
            logger.info("fund_data_service.database.initialized")
        except Exception as e:
            logger.error(
                "fund_data_service.database.init_error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def save_fund_report(self, parsed_data: ParsedFundData, upload_info_id: str, file_path: Optional[Path] = None) -> Optional[int]:
        """
        保存基金报告数据
        Save fund report data
        
        Args:
            parsed_data: 解析后的基金数据
            upload_info_id: 原始上传ID
            file_path: 文件路径
            
        Returns:
            保存的报告ID，如果失败返回None
        """
        bound_logger = self.logger.bind(
            fund_code=parsed_data.fund_code,
            upload_info_id=upload_info_id
        )
        
        bound_logger.info("fund_data_service.save_report.start")
        
        try:
            with self.SessionLocal() as session:
                # 检查是否已存在相同的报告
                existing = session.query(FundReport).filter_by(upload_info_id=upload_info_id).first()
                if existing:
                    bound_logger.warning(
                        "fund_data_service.save_report.already_exists",
                        existing_id=existing.id
                    )
                    return existing.id
                
                # 创建基金报告记录
                fund_report = FundReport(
                    fund_code=parsed_data.fund_code,
                    fund_name=parsed_data.fund_name,
                    fund_manager=parsed_data.fund_manager,
                    report_type=parsed_data.report_type,
                    report_period_start=parsed_data.report_period_start,
                    report_period_end=parsed_data.report_period_end,
                    report_year=parsed_data.report_year,
                    report_quarter=parsed_data.report_quarter,
                    upload_info_id=upload_info_id,
                    file_path=str(file_path) if file_path else None,
                    file_size=file_path.stat().st_size if file_path and file_path.exists() else None,
                    total_net_assets=parsed_data.total_net_assets,
                    total_shares=parsed_data.total_shares,
                    net_asset_value=parsed_data.net_asset_value,
                    accumulated_nav=parsed_data.accumulated_nav,
                    parsed_at=datetime.utcnow()
                )
                
                session.add(fund_report)
                session.flush()  # 获取ID
                
                report_id = fund_report.id
                
                # 保存资产配置
                for allocation_data in parsed_data.asset_allocations:
                    allocation = AssetAllocation(
                        fund_report_id=report_id,
                        asset_type=allocation_data.get('asset_type'),
                        asset_name=allocation_data.get('asset_name'),
                        market_value=allocation_data.get('market_value'),
                        percentage=allocation_data.get('percentage')
                    )
                    session.add(allocation)
                
                # 保存前十大持仓
                for holding_data in parsed_data.top_holdings:
                    holding = TopHolding(
                        fund_report_id=report_id,
                        holding_type=holding_data.get('holding_type', '股票'),
                        security_code=holding_data.get('security_code'),
                        security_name=holding_data.get('security_name'),
                        shares=holding_data.get('shares'),
                        market_value=holding_data.get('market_value'),
                        percentage=holding_data.get('percentage'),
                        rank=holding_data.get('rank'),
                        industry=holding_data.get('industry'),
                        exchange=holding_data.get('exchange')
                    )
                    session.add(holding)
                
                # 保存行业配置
                for industry_data in parsed_data.industry_allocations:
                    industry = IndustryAllocation(
                        fund_report_id=report_id,
                        industry_code=industry_data.get('industry_code'),
                        industry_name=industry_data.get('industry_name'),
                        industry_level=industry_data.get('industry_level'),
                        market_value=industry_data.get('market_value'),
                        percentage=industry_data.get('percentage'),
                        rank=industry_data.get('rank')
                    )
                    session.add(industry)
                
                session.commit()
                
                bound_logger.info(
                    "fund_data_service.save_report.success",
                    report_id=report_id,
                    assets_count=len(parsed_data.asset_allocations),
                    holdings_count=len(parsed_data.top_holdings),
                    industries_count=len(parsed_data.industry_allocations)
                )
                
                return report_id
                
        except IntegrityError as e:
            bound_logger.error(
                "fund_data_service.save_report.integrity_error",
                error=str(e)
            )
            return None
        except Exception as e:
            bound_logger.error(
                "fund_data_service.save_report.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def get_fund_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        获取基金报告详情
        Get fund report details
        """
        bound_logger = self.logger.bind(report_id=report_id)
        bound_logger.info("fund_data_service.get_report.start")
        
        try:
            with self.SessionLocal() as session:
                report = session.query(FundReport).filter_by(id=report_id).first()
                if not report:
                    bound_logger.warning("fund_data_service.get_report.not_found")
                    return None
                
                # 获取关联数据
                asset_allocations = session.query(AssetAllocation).filter_by(fund_report_id=report_id).all()
                top_holdings = session.query(TopHolding).filter_by(fund_report_id=report_id).order_by(TopHolding.rank).all()
                industry_allocations = session.query(IndustryAllocation).filter_by(fund_report_id=report_id).order_by(desc(IndustryAllocation.percentage)).all()
                
                # 构建响应数据
                result = {
                    'id': report.id,
                    'fund_code': report.fund_code,
                    'fund_name': report.fund_name,
                    'fund_manager': report.fund_manager,
                    'report_type': report.report_type,
                    'report_period_start': report.report_period_start,
                    'report_period_end': report.report_period_end,
                    'report_year': report.report_year,
                    'report_quarter': report.report_quarter,
                    'upload_info_id': report.upload_info_id,
                    'file_path': report.file_path,
                    'file_size': report.file_size,
                    'total_net_assets': report.total_net_assets,
                    'total_shares': report.total_shares,
                    'net_asset_value': report.net_asset_value,
                    'accumulated_nav': report.accumulated_nav,
                    'created_at': report.created_at,
                    'parsed_at': report.parsed_at,
                    'asset_allocations': [
                        {
                            'asset_type': a.asset_type,
                            'asset_name': a.asset_name,
                            'market_value': a.market_value,
                            'percentage': a.percentage
                        }
                        for a in asset_allocations
                    ],
                    'top_holdings': [
                        {
                            'rank': h.rank,
                            'holding_type': h.holding_type,
                            'security_code': h.security_code,
                            'security_name': h.security_name,
                            'shares': h.shares,
                            'market_value': h.market_value,
                            'percentage': h.percentage,
                            'industry': h.industry,
                            'exchange': h.exchange
                        }
                        for h in top_holdings
                    ],
                    'industry_allocations': [
                        {
                            'industry_code': i.industry_code,
                            'industry_name': i.industry_name,
                            'industry_level': i.industry_level,
                            'market_value': i.market_value,
                            'percentage': i.percentage,
                            'rank': i.rank
                        }
                        for i in industry_allocations
                    ]
                }
                
                bound_logger.info(
                    "fund_data_service.get_report.success",
                    fund_code=report.fund_code,
                    assets_count=len(asset_allocations),
                    holdings_count=len(top_holdings),
                    industries_count=len(industry_allocations)
                )
                
                return result
                
        except Exception as e:
            bound_logger.error(
                "fund_data_service.get_report.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def list_fund_reports(self, fund_code: Optional[str] = None, report_year: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取基金报告列表
        Get fund reports list
        """
        bound_logger = self.logger.bind(
            fund_code=fund_code,
            report_year=report_year,
            limit=limit
        )
        
        bound_logger.info("fund_data_service.list_reports.start")
        
        try:
            with self.SessionLocal() as session:
                query = session.query(FundReport)
                
                # 添加筛选条件
                if fund_code:
                    query = query.filter(FundReport.fund_code == fund_code)
                if report_year:
                    query = query.filter(FundReport.report_year == report_year)
                
                # 排序和限制
                reports = query.order_by(desc(FundReport.report_period_end)).limit(limit).all()
                
                result = [
                    {
                        'id': r.id,
                        'fund_code': r.fund_code,
                        'fund_name': r.fund_name,
                        'report_type': r.report_type,
                        'report_period_end': r.report_period_end,
                        'report_year': r.report_year,
                        'report_quarter': r.report_quarter,
                        'net_asset_value': r.net_asset_value,
                        'total_net_assets': r.total_net_assets,
                        'upload_info_id': r.upload_info_id,
                        'created_at': r.created_at,
                        'parsed_at': r.parsed_at
                    }
                    for r in reports
                ]
                
                bound_logger.info(
                    "fund_data_service.list_reports.success",
                    count=len(result)
                )
                
                return result
                
        except Exception as e:
            bound_logger.error(
                "fund_data_service.list_reports.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据统计信息
        Get data statistics
        """
        self.logger.info("fund_data_service.get_statistics.start")
        
        try:
            with self.SessionLocal() as session:
                total_reports = session.query(FundReport).count()
                total_funds = session.query(FundReport.fund_code).distinct().count()
                
                # 按年度统计
                from sqlalchemy import func
                year_stats = session.query(
                    FundReport.report_year,
                    func.count(FundReport.id)
                ).group_by(FundReport.report_year).all()

                # 按报告类型统计
                type_stats = session.query(
                    FundReport.report_type,
                    func.count(FundReport.id)
                ).group_by(FundReport.report_type).all()
                
                result = {
                    'total_reports': total_reports,
                    'total_funds': total_funds,
                    'by_year': {str(year): count for year, count in year_stats},
                    'by_type': {report_type: count for report_type, count in type_stats}
                }
                
                self.logger.info(
                    "fund_data_service.get_statistics.success",
                    total_reports=total_reports,
                    total_funds=total_funds
                )
                
                return result
                
        except Exception as e:
            self.logger.error(
                "fund_data_service.get_statistics.error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                'total_reports': 0,
                'total_funds': 0,
                'by_year': {},
                'by_type': {}
            }

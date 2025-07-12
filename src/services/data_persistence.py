"""
Data persistence service for fund report data.
基金报告数据持久化服务，负责将解析后的结构化数据存入数据库。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_

from src.core.logging import get_logger
from src.models.connection import get_db_session
from src.models.database import (
    Fund, FundReport, AssetAllocation, TopHolding, IndustryAllocation,
    ReportType, TaskStatus
)
from src.parsers.xbrl_parser import (
    FundBasicInfo, AssetAllocation as ParsedAssetAllocation,
    TopHolding as ParsedTopHolding, IndustryAllocation as ParsedIndustryAllocation
)

logger = get_logger(__name__)


class DataPersistenceError(Exception):
    """数据持久化错误"""
    pass


class FundDataPersistenceService:
    """
    基金数据持久化服务
    
    负责将XBRL解析后的结构化数据保存到数据库，包括：
    - 基金基本信息
    - 基金报告记录
    - 资产配置数据
    - 前十大重仓股
    - 行业配置
    """
    
    def __init__(self, db_session: Session = None):
        """
        初始化持久化服务
        
        Args:
            db_session: 数据库会话，如果未提供则使用默认会话
        """
        self.db_session = db_session
        self._should_close_session = db_session is None
        
        logger.info("data_persistence.service.initialized")
    
    def __enter__(self):
        """上下文管理器入口"""
        if self.db_session is None:
            self.db_session = next(get_db_session())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if self._should_close_session and self.db_session:
            if exc_type is None:
                self.db_session.commit()
            else:
                self.db_session.rollback()
            self.db_session.close()
    
    def save_fund_report_data(
        self,
        fund_info: FundBasicInfo,
        report_type: ReportType,
        file_path: str,
        file_type: str = "XBRL",
        asset_allocation: Optional[ParsedAssetAllocation] = None,
        top_holdings: Optional[List[ParsedTopHolding]] = None,
        industry_allocations: Optional[List[ParsedIndustryAllocation]] = None,
        original_file_url: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> Optional[str]:
        """
        保存完整的基金报告数据
        
        Args:
            fund_info: 基金基本信息
            report_type: 报告类型
            file_path: 文件存储路径
            file_type: 文件类型
            asset_allocation: 资产配置数据
            top_holdings: 前十大重仓股
            industry_allocations: 行业配置
            original_file_url: 原始文件URL
            file_size: 文件大小
            
        Returns:
            保存成功返回报告ID，失败返回None
            
        Raises:
            DataPersistenceError: 保存失败时抛出
        """
        bound_logger = logger.bind(
            fund_code=fund_info.fund_code,
            report_date=fund_info.report_date.isoformat(),
            report_type=report_type.value
        )
        
        bound_logger.info("data_persistence.save_report.start")
        
        try:
            # 确保有数据库会话
            if self.db_session is None:
                raise DataPersistenceError("数据库会话未初始化")
            
            # 1. 保存或更新基金基本信息
            fund = self._save_or_update_fund(fund_info)
            
            # 2. 检查报告是否已存在
            existing_report = self._check_report_exists(
                fund.id, fund_info.report_date, report_type
            )
            
            if existing_report:
                bound_logger.warning(
                    "data_persistence.save_report.already_exists",
                    existing_report_id=str(existing_report.id)
                )
                return str(existing_report.id)
            
            # 3. 创建基金报告记录
            report = self._create_fund_report(
                fund=fund,
                fund_info=fund_info,
                report_type=report_type,
                file_path=file_path,
                file_type=file_type,
                original_file_url=original_file_url,
                file_size=file_size
            )
            
            # 4. 保存资产配置数据
            if asset_allocation:
                self._save_asset_allocation(report, asset_allocation)
            
            # 5. 保存前十大重仓股
            if top_holdings:
                self._save_top_holdings(report, top_holdings)
            
            # 6. 保存行业配置
            if industry_allocations:
                self._save_industry_allocations(report, industry_allocations)
            
            # 7. 更新报告解析状态
            report.is_parsed = True
            report.parsed_at = datetime.utcnow()
            
            # 提交事务
            self.db_session.commit()
            
            bound_logger.info(
                "data_persistence.save_report.success",
                report_id=str(report.id),
                has_asset_allocation=asset_allocation is not None,
                holdings_count=len(top_holdings) if top_holdings else 0,
                industries_count=len(industry_allocations) if industry_allocations else 0
            )
            
            return str(report.id)
            
        except IntegrityError as e:
            self.db_session.rollback()
            bound_logger.error(
                "data_persistence.save_report.integrity_error",
                error=str(e)
            )
            raise DataPersistenceError(f"数据完整性错误: {e}")
        
        except Exception as e:
            if self.db_session:
                self.db_session.rollback()
            bound_logger.error(
                "data_persistence.save_report.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise DataPersistenceError(f"保存报告数据失败: {e}")
    
    def _save_or_update_fund(self, fund_info: FundBasicInfo) -> Fund:
        """保存或更新基金基本信息"""
        # 查找现有基金记录
        existing_fund = self.db_session.query(Fund).filter(
            Fund.fund_code == fund_info.fund_code
        ).first()
        
        if existing_fund:
            # 更新现有记录
            existing_fund.fund_name = fund_info.fund_name
            if fund_info.management_company:
                existing_fund.management_company = fund_info.management_company
            existing_fund.updated_at = datetime.utcnow()
            
            logger.debug(
                "data_persistence.fund.updated",
                fund_code=fund_info.fund_code,
                fund_id=str(existing_fund.id)
            )
            
            return existing_fund
        else:
            # 创建新记录
            new_fund = Fund(
                id=uuid4(),
                fund_code=fund_info.fund_code,
                fund_name=fund_info.fund_name,
                management_company=fund_info.management_company,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db_session.add(new_fund)
            self.db_session.flush()  # 获取ID
            
            logger.debug(
                "data_persistence.fund.created",
                fund_code=fund_info.fund_code,
                fund_id=str(new_fund.id)
            )
            
            return new_fund
    
    def _check_report_exists(
        self, 
        fund_id: str, 
        report_date: datetime, 
        report_type: ReportType
    ) -> Optional[FundReport]:
        """检查报告是否已存在"""
        return self.db_session.query(FundReport).filter(
            and_(
                FundReport.fund_id == fund_id,
                FundReport.report_date == report_date.date(),
                FundReport.report_type == report_type
            )
        ).first()
    
    def _create_fund_report(
        self,
        fund: Fund,
        fund_info: FundBasicInfo,
        report_type: ReportType,
        file_path: str,
        file_type: str,
        original_file_url: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> FundReport:
        """创建基金报告记录"""
        report = FundReport(
            id=uuid4(),
            fund_id=fund.id,
            report_date=fund_info.report_date.date(),
            report_type=report_type,
            report_year=fund_info.report_date.year,
            report_period=self._get_report_period(fund_info.report_date, report_type),
            net_asset_value=fund_info.net_asset_value,
            total_shares=fund_info.total_shares,
            unit_nav=fund_info.unit_nav,
            accumulated_nav=fund_info.accumulated_nav,
            original_file_url=original_file_url,
            original_file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            is_parsed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db_session.add(report)
        self.db_session.flush()  # 获取ID
        
        return report
    
    def _get_report_period(self, report_date: datetime, report_type: ReportType) -> str:
        """根据报告日期和类型确定报告期间"""
        if report_type == ReportType.ANNUAL:
            return "年报"
        elif report_type == ReportType.SEMI_ANNUAL:
            return "中报"
        elif report_type == ReportType.QUARTERLY:
            quarter = (report_date.month - 1) // 3 + 1
            return f"Q{quarter}"
        else:
            return "其他"
    
    def _save_asset_allocation(
        self, 
        report: FundReport, 
        allocation_data: ParsedAssetAllocation
    ) -> None:
        """保存资产配置数据"""
        allocation = AssetAllocation(
            id=uuid4(),
            report_id=report.id,
            stock_investments=allocation_data.stock_investments,
            stock_ratio=allocation_data.stock_ratio,
            bond_investments=allocation_data.bond_investments,
            bond_ratio=allocation_data.bond_ratio,
            fund_investments=allocation_data.fund_investments,
            fund_ratio=allocation_data.fund_ratio,
            cash_and_equivalents=allocation_data.cash_and_equivalents,
            cash_ratio=allocation_data.cash_ratio,
            other_investments=allocation_data.other_investments,
            other_ratio=allocation_data.other_ratio,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db_session.add(allocation)
        
        logger.debug(
            "data_persistence.asset_allocation.saved",
            report_id=str(report.id)
        )
    
    def _save_top_holdings(
        self, 
        report: FundReport, 
        holdings_data: List[ParsedTopHolding]
    ) -> None:
        """保存前十大重仓股数据"""
        for holding_data in holdings_data:
            holding = TopHolding(
                id=uuid4(),
                report_id=report.id,
                rank=holding_data.rank,
                stock_code=holding_data.stock_code,
                stock_name=holding_data.stock_name,
                shares_held=holding_data.shares_held,
                market_value=holding_data.market_value,
                portfolio_ratio=holding_data.portfolio_ratio,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db_session.add(holding)
        
        logger.debug(
            "data_persistence.top_holdings.saved",
            report_id=str(report.id),
            holdings_count=len(holdings_data)
        )
    
    def _save_industry_allocations(
        self, 
        report: FundReport, 
        industries_data: List[ParsedIndustryAllocation]
    ) -> None:
        """保存行业配置数据"""
        for industry_data in industries_data:
            industry = IndustryAllocation(
                id=uuid4(),
                report_id=report.id,
                industry_name=industry_data.industry_name,
                industry_code=industry_data.industry_code,
                market_value=industry_data.market_value,
                portfolio_ratio=industry_data.portfolio_ratio,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.db_session.add(industry)
        
        logger.debug(
            "data_persistence.industry_allocations.saved",
            report_id=str(report.id),
            industries_count=len(industries_data)
        )
    
    def check_data_uniqueness(
        self,
        fund_code: str,
        report_date: datetime,
        report_type: ReportType
    ) -> bool:
        """
        检查数据唯一性
        
        Args:
            fund_code: 基金代码
            report_date: 报告日期
            report_type: 报告类型
            
        Returns:
            如果数据已存在返回True，否则返回False
        """
        if self.db_session is None:
            return False
        
        # 查找基金
        fund = self.db_session.query(Fund).filter(
            Fund.fund_code == fund_code
        ).first()
        
        if not fund:
            return False
        
        # 检查报告是否存在
        existing_report = self._check_report_exists(
            fund.id, report_date, report_type
        )
        
        return existing_report is not None
    
    def get_fund_reports_summary(self, fund_code: str = None) -> Dict[str, Any]:
        """
        获取基金报告汇总信息
        
        Args:
            fund_code: 基金代码，为None时返回所有基金的汇总
            
        Returns:
            汇总信息字典
        """
        if self.db_session is None:
            return {}
        
        query = self.db_session.query(FundReport).join(Fund)
        
        if fund_code:
            query = query.filter(Fund.fund_code == fund_code)
        
        reports = query.all()
        
        summary = {
            "total_reports": len(reports),
            "parsed_reports": sum(1 for r in reports if r.is_parsed),
            "unparsed_reports": sum(1 for r in reports if not r.is_parsed),
            "by_type": {},
            "by_year": {}
        }
        
        # 按类型统计
        for report in reports:
            report_type = report.report_type.value
            if report_type not in summary["by_type"]:
                summary["by_type"][report_type] = 0
            summary["by_type"][report_type] += 1
        
        # 按年份统计
        for report in reports:
            year = str(report.report_year)
            if year not in summary["by_year"]:
                summary["by_year"][year] = 0
            summary["by_year"][year] += 1
        
        return summary
    
    def cleanup_failed_reports(self) -> int:
        """
        清理解析失败的报告记录
        
        Returns:
            清理的记录数量
        """
        if self.db_session is None:
            return 0
        
        # 删除解析失败且有错误信息的报告
        failed_reports = self.db_session.query(FundReport).filter(
            and_(
                FundReport.is_parsed == False,
                FundReport.parse_error.isnot(None)
            )
        ).all()
        
        count = len(failed_reports)
        
        for report in failed_reports:
            # 删除相关的子表数据
            self.db_session.query(AssetAllocation).filter(
                AssetAllocation.report_id == report.id
            ).delete()
            
            self.db_session.query(TopHolding).filter(
                TopHolding.report_id == report.id
            ).delete()
            
            self.db_session.query(IndustryAllocation).filter(
                IndustryAllocation.report_id == report.id
            ).delete()
            
            # 删除报告记录
            self.db_session.delete(report)
        
        self.db_session.commit()
        
        logger.info(
            "data_persistence.cleanup.completed",
            cleaned_reports=count
        )
        
        return count
"""
Enhanced Fund Data Models for Comparative Analysis
增强型基金数据模型，用于比较分析

This module provides Pydantic models for structured fund report data
that facilitates cross-fund comparison and data mining.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from src.core.fund_search_parameters import ReportType

Base = declarative_base()


class AssetType(str, Enum):
    """Asset type enumeration"""
    STOCK = "stock"
    BOND = "bond"
    CASH = "cash"
    FUND = "fund"
    OTHER = "other"


class ValidationStatus(str, Enum):
    """Data validation status"""
    HIGH_QUALITY = "high_quality"
    MEDIUM_QUALITY = "medium_quality"
    LOW_QUALITY = "low_quality"
    NEEDS_REVIEW = "needs_review"


# Pydantic Models for Data Validation and API
class BasicFundInfo(BaseModel):
    """Basic fund information"""
    fund_code: str = Field(..., description="Fund code (6 digits)")
    fund_name: str = Field(..., description="Fund name")
    fund_manager: Optional[str] = Field(None, description="Fund management company")
    custodian: Optional[str] = Field(None, description="Fund custodian")
    
    @validator('fund_code')
    def validate_fund_code(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Fund code must be 6 digits')
        return v


class FinancialMetrics(BaseModel):
    """Financial metrics and performance data"""
    net_asset_value: Optional[Decimal] = Field(None, description="Net asset value per unit")
    accumulated_nav: Optional[Decimal] = Field(None, description="Accumulated net asset value")
    total_net_assets: Optional[Decimal] = Field(None, description="Total net assets")
    total_shares: Optional[Decimal] = Field(None, description="Total fund shares")
    
    # Performance metrics
    return_1d: Optional[Decimal] = Field(None, description="1-day return")
    return_1w: Optional[Decimal] = Field(None, description="1-week return")
    return_1m: Optional[Decimal] = Field(None, description="1-month return")
    return_3m: Optional[Decimal] = Field(None, description="3-month return")
    return_6m: Optional[Decimal] = Field(None, description="6-month return")
    return_1y: Optional[Decimal] = Field(None, description="1-year return")
    return_ytd: Optional[Decimal] = Field(None, description="Year-to-date return")
    
    # Risk metrics
    volatility: Optional[Decimal] = Field(None, description="Volatility")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[Decimal] = Field(None, description="Maximum drawdown")


class AssetAllocationData(BaseModel):
    """Asset allocation data"""
    asset_type: AssetType
    asset_name: Optional[str] = None
    market_value: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    
    class Config:
        use_enum_values = True


class HoldingData(BaseModel):
    """Individual holding data"""
    holding_type: str = Field(..., description="Type of holding (stock/bond)")
    security_code: Optional[str] = Field(None, description="Security code")
    security_name: str = Field(..., description="Security name")
    shares: Optional[Decimal] = Field(None, description="Number of shares")
    market_value: Decimal = Field(..., description="Market value")
    percentage: Decimal = Field(..., description="Percentage of net assets")
    rank: int = Field(..., description="Ranking in portfolio")
    industry: Optional[str] = Field(None, description="Industry classification")
    exchange: Optional[str] = Field(None, description="Exchange")


class IndustryAllocationData(BaseModel):
    """Industry allocation data"""
    industry_code: Optional[str] = None
    industry_name: str
    industry_level: Optional[int] = None
    market_value: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    rank: Optional[int] = None


class ReportMetadata(BaseModel):
    """Report metadata and quality information"""
    report_type: ReportType
    report_period_start: date
    report_period_end: date
    report_year: int
    report_quarter: Optional[int] = None
    
    # File and parsing information
    upload_info_id: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    
    # Parsing quality
    parsing_method: Optional[str] = None
    parsing_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    data_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    validation_status: Optional[ValidationStatus] = None
    llm_assisted: bool = False
    
    # Metadata
    parsing_metadata: Optional[Dict[str, Any]] = None
    validation_issues: Optional[List[str]] = None
    data_completeness: Optional[Dict[str, float]] = None
    
    class Config:
        use_enum_values = True


class ComprehensiveFundReport(BaseModel):
    """Comprehensive fund report data model"""
    basic_info: BasicFundInfo
    financial_metrics: FinancialMetrics
    report_metadata: ReportMetadata
    
    # Portfolio data
    asset_allocations: List[AssetAllocationData] = []
    top_holdings: List[HoldingData] = []
    industry_allocations: List[IndustryAllocationData] = []
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    parsed_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: str,
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }


# Enhanced SQLAlchemy Models for Database Storage
class EnhancedFundReport(Base):
    """Enhanced fund report table with comprehensive data structure"""
    __tablename__ = "enhanced_fund_reports"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Basic fund information
    fund_code = Column(String(20), nullable=False, index=True)
    fund_name = Column(String(200), nullable=False)
    fund_manager = Column(String(200), nullable=True)
    custodian = Column(String(200), nullable=True)
    
    # Report information
    report_type = Column(String(50), nullable=False)
    report_period_start = Column(Date, nullable=False)
    report_period_end = Column(Date, nullable=False)
    report_year = Column(Integer, nullable=False, index=True)
    report_quarter = Column(Integer, nullable=True)
    
    # Financial metrics
    net_asset_value = Column(Numeric(10, 4), nullable=True)
    accumulated_nav = Column(Numeric(10, 4), nullable=True)
    total_net_assets = Column(Numeric(20, 2), nullable=True)
    total_shares = Column(Numeric(20, 2), nullable=True)
    
    # Performance metrics
    return_1d = Column(Numeric(8, 4), nullable=True)
    return_1w = Column(Numeric(8, 4), nullable=True)
    return_1m = Column(Numeric(8, 4), nullable=True)
    return_3m = Column(Numeric(8, 4), nullable=True)
    return_6m = Column(Numeric(8, 4), nullable=True)
    return_1y = Column(Numeric(8, 4), nullable=True)
    return_ytd = Column(Numeric(8, 4), nullable=True)
    
    # Risk metrics
    volatility = Column(Numeric(8, 4), nullable=True)
    sharpe_ratio = Column(Numeric(8, 4), nullable=True)
    max_drawdown = Column(Numeric(8, 4), nullable=True)
    
    # File and parsing information
    upload_info_id = Column(String(50), nullable=False, unique=True, index=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # Parsing quality and metadata
    parsing_method = Column(String(50), nullable=True)
    parsing_confidence = Column(Float, nullable=True)
    data_quality_score = Column(Float, nullable=True)
    validation_status = Column(String(20), nullable=True)
    llm_assisted = Column(Boolean, nullable=False, default=False)
    
    # JSON metadata fields
    parsing_metadata = Column(JSON, nullable=True)
    validation_issues = Column(JSON, nullable=True)
    data_completeness = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    
    # Relationships
    asset_allocations = relationship("EnhancedAssetAllocation", back_populates="fund_report", cascade="all, delete-orphan")
    top_holdings = relationship("EnhancedTopHolding", back_populates="fund_report", cascade="all, delete-orphan")
    industry_allocations = relationship("EnhancedIndustryAllocation", back_populates="fund_report", cascade="all, delete-orphan")
    
    def to_pydantic(self) -> ComprehensiveFundReport:
        """Convert to Pydantic model for API responses"""
        return ComprehensiveFundReport(
            basic_info=BasicFundInfo(
                fund_code=self.fund_code,
                fund_name=self.fund_name,
                fund_manager=self.fund_manager,
                custodian=self.custodian
            ),
            financial_metrics=FinancialMetrics(
                net_asset_value=self.net_asset_value,
                accumulated_nav=self.accumulated_nav,
                total_net_assets=self.total_net_assets,
                total_shares=self.total_shares,
                return_1d=self.return_1d,
                return_1w=self.return_1w,
                return_1m=self.return_1m,
                return_3m=self.return_3m,
                return_6m=self.return_6m,
                return_1y=self.return_1y,
                return_ytd=self.return_ytd,
                volatility=self.volatility,
                sharpe_ratio=self.sharpe_ratio,
                max_drawdown=self.max_drawdown
            ),
            report_metadata=ReportMetadata(
                report_type=ReportType(self.report_type),
                report_period_start=self.report_period_start,
                report_period_end=self.report_period_end,
                report_year=self.report_year,
                report_quarter=self.report_quarter,
                upload_info_id=self.upload_info_id,
                file_path=self.file_path,
                file_size=self.file_size,
                parsing_method=self.parsing_method,
                parsing_confidence=self.parsing_confidence,
                data_quality_score=self.data_quality_score,
                validation_status=ValidationStatus(self.validation_status) if self.validation_status else None,
                llm_assisted=self.llm_assisted,
                parsing_metadata=self.parsing_metadata,
                validation_issues=self.validation_issues,
                data_completeness=self.data_completeness
            ),
            asset_allocations=[alloc.to_pydantic() for alloc in self.asset_allocations],
            top_holdings=[holding.to_pydantic() for holding in self.top_holdings],
            industry_allocations=[industry.to_pydantic() for industry in self.industry_allocations],
            created_at=self.created_at,
            updated_at=self.updated_at,
            parsed_at=self.parsed_at
        )


class EnhancedAssetAllocation(Base):
    """Enhanced asset allocation table"""
    __tablename__ = "enhanced_asset_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_report_id = Column(Integer, ForeignKey("enhanced_fund_reports.id"), nullable=False, index=True)

    asset_type = Column(String(50), nullable=False)
    asset_name = Column(String(200), nullable=True)
    market_value = Column(Numeric(20, 2), nullable=True)
    percentage = Column(Numeric(8, 4), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    fund_report = relationship("EnhancedFundReport", back_populates="asset_allocations")

    def to_pydantic(self) -> AssetAllocationData:
        return AssetAllocationData(
            asset_type=AssetType(self.asset_type),
            asset_name=self.asset_name,
            market_value=self.market_value,
            percentage=self.percentage
        )


class EnhancedTopHolding(Base):
    """Enhanced top holdings table"""
    __tablename__ = "enhanced_top_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_report_id = Column(Integer, ForeignKey("enhanced_fund_reports.id"), nullable=False, index=True)

    holding_type = Column(String(20), nullable=False)
    security_code = Column(String(20), nullable=True, index=True)
    security_name = Column(String(200), nullable=False)
    shares = Column(Numeric(20, 2), nullable=True)
    market_value = Column(Numeric(20, 2), nullable=False)
    percentage = Column(Numeric(8, 4), nullable=False)
    rank = Column(Integer, nullable=False)
    industry = Column(String(100), nullable=True)
    exchange = Column(String(20), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    fund_report = relationship("EnhancedFundReport", back_populates="top_holdings")

    def to_pydantic(self) -> HoldingData:
        return HoldingData(
            holding_type=self.holding_type,
            security_code=self.security_code,
            security_name=self.security_name,
            shares=self.shares,
            market_value=self.market_value,
            percentage=self.percentage,
            rank=self.rank,
            industry=self.industry,
            exchange=self.exchange
        )


class EnhancedIndustryAllocation(Base):
    """Enhanced industry allocation table"""
    __tablename__ = "enhanced_industry_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_report_id = Column(Integer, ForeignKey("enhanced_fund_reports.id"), nullable=False, index=True)

    industry_code = Column(String(20), nullable=True)
    industry_name = Column(String(200), nullable=False)
    industry_level = Column(Integer, nullable=True)
    market_value = Column(Numeric(20, 2), nullable=True)
    percentage = Column(Numeric(8, 4), nullable=True)
    rank = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    fund_report = relationship("EnhancedFundReport", back_populates="industry_allocations")

    def to_pydantic(self) -> IndustryAllocationData:
        return IndustryAllocationData(
            industry_code=self.industry_code,
            industry_name=self.industry_name,
            industry_level=self.industry_level,
            market_value=self.market_value,
            percentage=self.percentage,
            rank=self.rank
        )


def create_enhanced_fund_tables(engine):
    """Create enhanced fund data tables"""
    Base.metadata.create_all(engine)


# Utility functions for data analysis
class FundComparator:
    """Utility class for comparing fund data"""

    @staticmethod
    def compare_performance(funds: List[ComprehensiveFundReport]) -> Dict[str, Any]:
        """Compare performance metrics across funds"""
        comparison = {
            'fund_count': len(funds),
            'metrics': {},
            'rankings': {}
        }

        # Performance metrics to compare
        metrics = ['return_1m', 'return_3m', 'return_6m', 'return_1y', 'volatility', 'sharpe_ratio']

        for metric in metrics:
            values = []
            fund_values = {}

            for fund in funds:
                value = getattr(fund.financial_metrics, metric)
                if value is not None:
                    values.append(float(value))
                    fund_values[fund.basic_info.fund_code] = float(value)

            if values:
                comparison['metrics'][metric] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'fund_values': fund_values
                }

                # Create rankings (higher is better for returns, lower is better for volatility)
                reverse_sort = metric != 'volatility'
                sorted_funds = sorted(fund_values.items(), key=lambda x: x[1], reverse=reverse_sort)
                comparison['rankings'][metric] = {fund_code: rank + 1 for rank, (fund_code, _) in enumerate(sorted_funds)}

        return comparison

    @staticmethod
    def analyze_asset_allocation_trends(funds: List[ComprehensiveFundReport]) -> Dict[str, Any]:
        """Analyze asset allocation trends across funds"""
        allocation_summary = {}

        for fund in funds:
            for allocation in fund.asset_allocations:
                asset_type = allocation.asset_type
                if asset_type not in allocation_summary:
                    allocation_summary[asset_type] = []

                if allocation.percentage:
                    allocation_summary[asset_type].append(float(allocation.percentage))

        # Calculate statistics for each asset type
        trends = {}
        for asset_type, percentages in allocation_summary.items():
            if percentages:
                trends[asset_type] = {
                    'mean_allocation': sum(percentages) / len(percentages),
                    'min_allocation': min(percentages),
                    'max_allocation': max(percentages),
                    'fund_count': len(percentages)
                }

        return trends

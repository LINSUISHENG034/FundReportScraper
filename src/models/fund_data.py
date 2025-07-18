"""
基金数据模型
Fund Data Models

SQLAlchemy模型用于存储解析后的基金报告数据
"""

from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Numeric,
    ForeignKey,
    Index,
    Text,
    Boolean,
    Float,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class FundReport(Base):
    """
    基金报告主表
    Fund Report Main Table

    存储报告的基本信息，作为所有其他解析数据的外键关联中心
    """

    __tablename__ = "fund_reports"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基金基本信息
    fund_code = Column(String(20), nullable=False, index=True)  # 基金代码
    fund_name = Column(String(200), nullable=False)  # 基金名称
    fund_manager = Column(String(200), nullable=True)  # 基金管理人

    # 报告信息
    report_type = Column(String(50), nullable=False)  # 报告类型（年报、半年报、季报）
    report_period_start = Column(Date, nullable=False)  # 报告期开始日期
    report_period_end = Column(Date, nullable=False)  # 报告期结束日期
    report_year = Column(Integer, nullable=False, index=True)  # 报告年度
    report_quarter = Column(Integer, nullable=True)  # 报告季度（1-4，年报为None）

    # 原始文件信息
    upload_info_id = Column(
        String(50), nullable=False, unique=True, index=True
    )  # 原始上传ID
    file_path = Column(String(500), nullable=True)  # 本地文件路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）

    # 基金规模和净值信息
    total_net_assets = Column(Numeric(20, 2), nullable=True)  # 基金总净资产（元）
    total_shares = Column(Numeric(20, 2), nullable=True)  # 基金总份额
    net_asset_value = Column(Numeric(10, 4), nullable=True)  # 单位净值
    accumulated_nav = Column(Numeric(10, 4), nullable=True)  # 累计净值

    # 解析质量和元数据
    parsing_method = Column(String(50), nullable=True)  # 解析方法
    parsing_confidence = Column(Float, nullable=True)  # 解析置信度 (0-1)
    data_quality_score = Column(Float, nullable=True)  # 数据质量得分 (0-1)
    validation_status = Column(String(20), nullable=True)  # 验证状态
    llm_assisted = Column(Boolean, nullable=False, default=False)  # 是否使用LLM辅助
    
    # 解析元数据
    parsing_metadata = Column(JSON, nullable=True)  # 解析过程元数据
    validation_issues = Column(JSON, nullable=True)  # 验证问题列表
    data_completeness = Column(JSON, nullable=True)  # 数据完整性详情
    
    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    parsed_at = Column(DateTime, nullable=True)  # 解析完成时间

    # 关联关系
    asset_allocations = relationship(
        "AssetAllocation", back_populates="fund_report", cascade="all, delete-orphan"
    )
    top_holdings = relationship(
        "TopHolding", back_populates="fund_report", cascade="all, delete-orphan"
    )
    industry_allocations = relationship(
        "IndustryAllocation", back_populates="fund_report", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_fund_report_period", "fund_code", "report_year", "report_quarter"),
        Index("idx_fund_report_upload", "upload_info_id"),
    )

    @property
    def report_date(self):
        """报告日期（report_period_end的别名）"""
        return self.report_period_end
    
    @report_date.setter
    def report_date(self, value):
        """设置报告日期"""
        self.report_period_end = value

    def __repr__(self):
        return f"<FundReport(fund_code='{self.fund_code}', period='{self.report_period_end}', nav={self.net_asset_value})>"


class AssetAllocation(Base):
    """
    资产配置表
    Asset Allocation Table

    存储股票、债券、现金等大类资产的配置比例和金额
    """

    __tablename__ = "asset_allocations"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 外键关联
    fund_report_id = Column(
        Integer, ForeignKey("fund_reports.id"), nullable=False, index=True
    )

    # 资产类型和配置
    asset_type = Column(String(50), nullable=False)  # 资产类型（股票、债券、现金、其他）
    asset_name = Column(String(200), nullable=True)  # 资产名称（具体描述）
    market_value = Column(Numeric(20, 2), nullable=True)  # 市值（元）
    percentage = Column(Numeric(8, 4), nullable=True)  # 占净值比例（%）

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关联关系
    fund_report = relationship("FundReport", back_populates="asset_allocations")

    # 索引
    __table_args__ = (
        Index("idx_asset_allocation_report", "fund_report_id", "asset_type"),
    )

    def __repr__(self):
        return f"<AssetAllocation(type='{self.asset_type}', value={self.market_value}, pct={self.percentage}%)>"


class TopHolding(Base):
    """
    前十大持仓表
    Top Holdings Table

    存储前十大重仓股或重仓债券的详细信息
    """

    __tablename__ = "top_holdings"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 外键关联
    fund_report_id = Column(
        Integer, ForeignKey("fund_reports.id"), nullable=False, index=True
    )

    # 持仓信息
    holding_type = Column(String(20), nullable=False)  # 持仓类型（股票、债券）
    security_code = Column(String(20), nullable=True, index=True)  # 证券代码
    security_name = Column(String(200), nullable=False)  # 证券名称

    # 持仓数据
    shares = Column(Numeric(20, 2), nullable=True)  # 持仓数量（股）
    market_value = Column(Numeric(20, 2), nullable=False)  # 市值（元）
    percentage = Column(Numeric(8, 4), nullable=False)  # 占净值比例（%）
    rank = Column(Integer, nullable=False)  # 排名（1-10）

    # 额外信息
    industry = Column(String(100), nullable=True)  # 所属行业
    exchange = Column(String(20), nullable=True)  # 交易所

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关联关系
    fund_report = relationship("FundReport", back_populates="top_holdings")

    # 索引
    __table_args__ = (
        Index("idx_top_holding_report", "fund_report_id", "rank"),
        Index("idx_top_holding_security", "security_code"),
    )

    def __repr__(self):
        return f"<TopHolding(rank={self.rank}, name='{self.security_name}', value={self.market_value})>"


class IndustryAllocation(Base):
    """
    行业配置表
    Industry Allocation Table

    存储基金在不同行业的投资分布情况
    """

    __tablename__ = "industry_allocations"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 外键关联
    fund_report_id = Column(
        Integer, ForeignKey("fund_reports.id"), nullable=False, index=True
    )

    # 行业信息
    industry_code = Column(String(20), nullable=True)  # 行业代码
    industry_name = Column(String(200), nullable=False)  # 行业名称
    industry_level = Column(Integer, nullable=True)  # 行业分类级别（1级、2级等）

    # 配置数据
    market_value = Column(Numeric(20, 2), nullable=True)  # 市值（元）
    percentage = Column(Numeric(8, 4), nullable=True)  # 占净值比例（%）
    rank = Column(Integer, nullable=True)  # 排名

    # 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关联关系
    fund_report = relationship("FundReport", back_populates="industry_allocations")

    # 索引
    __table_args__ = (
        Index("idx_industry_allocation_report", "fund_report_id", "percentage"),
        Index("idx_industry_allocation_name", "industry_name"),
    )

    def __repr__(self):
        return f"<IndustryAllocation(industry='{self.industry_name}', value={self.market_value}, pct={self.percentage}%)>"


def create_fund_data_tables(engine):
    """
    创建基金数据表
    Create fund data tables
    """
    Base.metadata.create_all(engine)


def get_fund_data_schema_info():
    """
    获取基金数据表结构信息
    Get fund data schema information
    """
    return {
        "tables": [
            {
                "name": "fund_reports",
                "description": "基金报告主表，存储报告基本信息和净值数据",
                "key_fields": [
                    "fund_code",
                    "report_period_end",
                    "upload_info_id",
                    "total_net_assets",
                    "net_asset_value",
                ],
            },
            {
                "name": "asset_allocations",
                "description": "资产配置表，存储大类资产配置比例",
                "key_fields": ["asset_type", "market_value", "percentage"],
            },
            {
                "name": "top_holdings",
                "description": "前十大持仓表，存储重仓股票和债券信息",
                "key_fields": [
                    "security_code",
                    "security_name",
                    "market_value",
                    "percentage",
                    "rank",
                ],
            },
            {
                "name": "industry_allocations",
                "description": "行业配置表，存储行业投资分布",
                "key_fields": ["industry_name", "market_value", "percentage"],
            },
        ],
        "relationships": [
            "fund_reports -> asset_allocations (1:N)",
            "fund_reports -> top_holdings (1:N)",
            "fund_reports -> industry_allocations (1:N)",
        ],
    }

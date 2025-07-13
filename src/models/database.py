"""
Database models for the fund report scraper.
定义基金报告相关的数据表模型，符合PRD中定义的数据结构。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, 
    Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid


Base = declarative_base()


class ReportType(enum.Enum):
    """基金报告类型枚举"""
    QUARTERLY = "QUARTERLY"  # 季报
    SEMI_ANNUAL = "SEMI_ANNUAL"  # 半年报
    ANNUAL = "ANNUAL"  # 年报


class TaskStatus(enum.Enum):
    """任务状态枚举"""
    PENDING = "PENDING"  # 待处理
    IN_PROGRESS = "IN_PROGRESS"  # 处理中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    RETRYING = "RETRYING"  # 重试中


class Fund(Base):
    """基金基础信息表"""
    __tablename__ = "funds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_code = Column(String(10), unique=True, nullable=False, comment="基金代码")
    fund_name = Column(String(100), nullable=False, comment="基金名称")
    fund_type = Column(String(50), comment="基金类型")
    management_company = Column(String(100), comment="管理公司")
    establishment_date = Column(DateTime, comment="成立日期")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联关系
    reports = relationship("FundReport", back_populates="fund")
    
    # 索引
    __table_args__ = (
        Index('idx_fund_code', 'fund_code'),
        Index('idx_fund_name', 'fund_name'),
    )


class FundReport(Base):
    """基金报告主表"""
    __tablename__ = "fund_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id = Column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False)
    
    # 报告基本信息
    report_date = Column(DateTime, nullable=False, comment="报告日期")
    report_type = Column(Enum(ReportType), nullable=False, comment="报告类型")
    report_year = Column(Integer, nullable=False, comment="报告年份")
    report_period = Column(String(20), comment="报告期间，如Q1, H1等")
    
    # 基金规模信息
    net_asset_value = Column(Numeric(20, 2), comment="基金净资产（元）")
    total_shares = Column(Numeric(20, 2), comment="基金份额总额")
    unit_nav = Column(Numeric(10, 4), comment="单位净值（元）")
    accumulated_nav = Column(Numeric(10, 4), comment="累计净值（元）")
    
    # 文件信息
    original_file_url = Column(Text, comment="原始文件URL")
    original_file_path = Column(String(500), comment="MinIO存储路径")
    file_type = Column(String(10), comment="文件类型: XBRL/PDF/HTML")
    file_size = Column(Integer, comment="文件大小（字节）")
    
    # 解析状态
    is_parsed = Column(Boolean, default=False, comment="是否已解析")
    parsed_at = Column(DateTime, comment="解析完成时间")
    parse_error = Column(Text, comment="解析错误信息")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联关系
    fund = relationship("Fund", back_populates="reports")
    asset_allocations = relationship("AssetAllocation", back_populates="report")
    top_holdings = relationship("TopHolding", back_populates="report")
    industry_allocations = relationship("IndustryAllocation", back_populates="report")
    
    # 唯一约束和索引
    __table_args__ = (
        UniqueConstraint('fund_id', 'report_date', 'report_type', name='uq_fund_report'),
        Index('idx_report_date', 'report_date'),
        Index('idx_report_type', 'report_type'),
        Index('idx_fund_report', 'fund_id', 'report_date'),
    )


class AssetAllocation(Base):
    """资产配置表"""
    __tablename__ = "asset_allocations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("fund_reports.id"), nullable=False)
    
    # 资产配置数据
    stock_investments = Column(Numeric(20, 2), comment="股票投资（元）")
    stock_ratio = Column(Numeric(5, 4), comment="股票投资占比")
    
    bond_investments = Column(Numeric(20, 2), comment="债券投资（元）")
    bond_ratio = Column(Numeric(5, 4), comment="债券投资占比")
    
    fund_investments = Column(Numeric(20, 2), comment="基金投资（元）")
    fund_ratio = Column(Numeric(5, 4), comment="基金投资占比")
    
    cash_and_equivalents = Column(Numeric(20, 2), comment="现金及现金等价物（元）")
    cash_ratio = Column(Numeric(5, 4), comment="现金占比")
    
    other_investments = Column(Numeric(20, 2), comment="其他投资（元）")
    other_ratio = Column(Numeric(5, 4), comment="其他投资占比")
    
    # 扩展字段，存储其他资产配置信息
    extended_data = Column(JSONB().with_variant(JSON, "sqlite"), comment="扩展数据（JSON格式）")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联关系
    report = relationship("FundReport", back_populates="asset_allocations")
    
    # 索引
    __table_args__ = (
        Index('idx_asset_report', 'report_id'),
    )


class TopHolding(Base):
    """前十大重仓股表"""
    __tablename__ = "top_holdings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("fund_reports.id"), nullable=False)
    
    # 持仓信息
    rank = Column(Integer, nullable=False, comment="排名（1-10）")
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    stock_name = Column(String(100), nullable=False, comment="股票名称")
    
    # 持仓数据
    shares_held = Column(Numeric(20, 2), comment="持股数量（股）")
    market_value = Column(Numeric(20, 2), comment="持仓市值（元）")
    portfolio_ratio = Column(Numeric(5, 4), comment="占基金净值比例")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联关系
    report = relationship("FundReport", back_populates="top_holdings")
    
    # 索引
    __table_args__ = (
        Index('idx_holding_report', 'report_id'),
        Index('idx_stock_code', 'stock_code'),
        Index('idx_holding_rank', 'report_id', 'rank'),
    )


class IndustryAllocation(Base):
    """行业配置表"""
    __tablename__ = "industry_allocations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("fund_reports.id"), nullable=False)
    
    # 行业信息
    industry_name = Column(String(100), nullable=False, comment="行业名称")
    industry_code = Column(String(20), comment="行业代码")
    
    # 配置数据
    market_value = Column(Numeric(20, 2), comment="行业市值（元）")
    portfolio_ratio = Column(Numeric(5, 4), comment="占基金净值比例")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联关系
    report = relationship("FundReport", back_populates="industry_allocations")
    
    # 索引
    __table_args__ = (
        Index('idx_industry_report', 'report_id'),
        Index('idx_industry_name', 'industry_name'),
    )


class ScrapingTask(Base):
    """爬取任务表"""
    __tablename__ = "scraping_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 任务信息
    task_name = Column(String(200), nullable=False, comment="任务名称")
    task_type = Column(String(50), nullable=False, comment="任务类型")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态")
    
    # 任务参数
    target_year = Column(Integer, comment="目标年份")
    target_report_type = Column(Enum(ReportType), comment="目标报告类型")
    fund_codes = Column(JSONB().with_variant(JSON, "sqlite"), comment="指定基金代码列表（JSON）")
    
    # 执行信息
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    error_message = Column(Text, comment="错误信息")
    
    # 统计信息
    total_reports = Column(Integer, default=0, comment="总报告数")
    processed_reports = Column(Integer, default=0, comment="已处理报告数")
    failed_reports = Column(Integer, default=0, comment="失败报告数")
    
    # 扩展信息
    execution_log = Column(JSONB().with_variant(JSON, "sqlite"), comment="执行日志（JSON格式）")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 索引
    __table_args__ = (
        Index('idx_task_status', 'status'),
        Index('idx_task_type', 'task_type'),
        Index('idx_task_created', 'created_at'),
    )
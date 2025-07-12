"""
Pydantic schemas for API request/response models.
API请求和响应的数据模型定义。
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# 枚举类型定义
class ReportTypeEnum(str, Enum):
    """报告类型枚举"""
    ANNUAL = "年报"
    SEMI_ANNUAL = "中报"
    QUARTERLY = "季报"
    INTERIM = "临时报告"


class TaskStatusEnum(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


# 基础响应模型
class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="操作成功", description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(description="系统状态")
    timestamp: datetime = Field(description="检查时间")
    version: str = Field(description="应用版本")
    services: Dict[str, str] = Field(description="各服务状态")


# 基金相关模型
class FundBaseInfo(BaseModel):
    """基金基础信息"""
    fund_code: str = Field(description="基金代码")
    fund_name: str = Field(description="基金名称")
    fund_company: str = Field(description="基金公司")
    fund_type: Optional[str] = Field(description="基金类型")
    establishment_date: Optional[date] = Field(description="成立日期")


class FundNavInfo(BaseModel):
    """基金净值信息"""
    unit_nav: Optional[float] = Field(description="单位净值")
    cumulative_nav: Optional[float] = Field(description="累计净值")
    nav_date: Optional[date] = Field(description="净值日期")
    daily_change: Optional[float] = Field(description="日涨跌幅")
    one_month_return: Optional[float] = Field(description="近1月收益率")
    one_year_return: Optional[float] = Field(description="近1年收益率")
    since_inception_return: Optional[float] = Field(description="成立以来收益率")


class FundResponse(BaseResponse):
    """基金信息响应"""
    data: FundBaseInfo = Field(description="基金基础信息")
    nav_info: Optional[FundNavInfo] = Field(description="净值信息")


class FundListResponse(BaseResponse):
    """基金列表响应"""
    data: List[FundBaseInfo] = Field(description="基金列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页")
    size: int = Field(description="每页数量")


# 报告相关模型
class AssetAllocation(BaseModel):
    """资产配置"""
    stock_ratio: Optional[float] = Field(description="股票配置比例")
    bond_ratio: Optional[float] = Field(description="债券配置比例")
    cash_ratio: Optional[float] = Field(description="现金配置比例")
    other_ratio: Optional[float] = Field(description="其他配置比例")
    total_assets: Optional[float] = Field(description="总资产")


class TopHolding(BaseModel):
    """前十大重仓股"""
    stock_code: str = Field(description="股票代码")
    stock_name: str = Field(description="股票名称")
    holding_ratio: float = Field(description="持仓比例")
    market_value: Optional[float] = Field(description="市值")
    shares_held: Optional[float] = Field(description="持股数量")


class IndustryAllocation(BaseModel):
    """行业配置"""
    industry_name: str = Field(description="行业名称")
    allocation_ratio: float = Field(description="配置比例")
    market_value: Optional[float] = Field(description="市值")


class ReportDetail(BaseModel):
    """报告详细信息"""
    report_id: str = Field(description="报告ID")
    fund_code: str = Field(description="基金代码")
    fund_name: str = Field(description="基金名称")
    report_type: ReportTypeEnum = Field(description="报告类型")
    report_date: date = Field(description="报告日期")
    file_path: Optional[str] = Field(description="文件路径")
    asset_allocation: Optional[AssetAllocation] = Field(description="资产配置")
    top_holdings: List[TopHolding] = Field(default=[], description="前十大重仓股")
    industry_allocation: List[IndustryAllocation] = Field(default=[], description="行业配置")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class ReportResponse(BaseResponse):
    """单个报告响应"""
    data: ReportDetail = Field(description="报告详细信息")


class ReportListResponse(BaseResponse):
    """报告列表响应"""
    data: List[ReportDetail] = Field(description="报告列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页")
    size: int = Field(description="每页数量")


# 任务相关模型
class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str = Field(description="任务ID")
    task_name: str = Field(description="任务名称")
    status: TaskStatusEnum = Field(description="任务状态")
    progress: int = Field(default=0, description="任务进度(0-100)")
    result: Optional[Dict[str, Any]] = Field(description="任务结果")
    error_message: Optional[str] = Field(description="错误信息")
    created_at: datetime = Field(description="创建时间")
    started_at: Optional[datetime] = Field(description="开始时间")
    completed_at: Optional[datetime] = Field(description="完成时间")


class TaskResponse(BaseResponse):
    """任务响应"""
    data: TaskInfo = Field(description="任务信息")


class TaskListResponse(BaseResponse):
    """任务列表响应"""
    data: List[TaskInfo] = Field(description="任务列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页")
    size: int = Field(description="每页数量")


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    task_type: str = Field(description="任务类型")
    parameters: Dict[str, Any] = Field(default={}, description="任务参数")
    description: Optional[str] = Field(description="任务描述")


# 分析相关模型
class FundAnalysis(BaseModel):
    """基金分析结果"""
    fund_code: str = Field(description="基金代码")
    fund_name: str = Field(description="基金名称")
    analysis_date: date = Field(description="分析日期")
    performance_metrics: Dict[str, float] = Field(description="业绩指标")
    risk_metrics: Dict[str, float] = Field(description="风险指标")
    ranking_info: Dict[str, Any] = Field(description="排名信息")
    recommendations: List[str] = Field(description="投资建议")


class AnalysisResponse(BaseResponse):
    """分析结果响应"""
    data: FundAnalysis = Field(description="分析结果")


# 请求查询参数
class FundQueryParams(BaseModel):
    """基金查询参数"""
    fund_code: Optional[str] = Field(None, description="基金代码")
    fund_name: Optional[str] = Field(None, description="基金名称")
    fund_company: Optional[str] = Field(None, description="基金公司")
    fund_type: Optional[str] = Field(None, description="基金类型")
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")


class ReportQueryParams(BaseModel):
    """报告查询参数"""
    fund_code: Optional[str] = Field(None, description="基金代码")
    report_type: Optional[ReportTypeEnum] = Field(None, description="报告类型")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")
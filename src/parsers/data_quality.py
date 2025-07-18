"""数据质量保证模块

实现基金报告数据的质量监控、验证、修复和报告功能。
"""

import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, asdict
from pathlib import Path

from pydantic import BaseModel, field_validator, Field

from src.core.logging import get_logger
from src.models.fund_data import FundReport, AssetAllocation, TopHolding, IndustryAllocation


@dataclass
class QualityMetrics:
    """质量指标"""
    completeness_score: float  # 完整性得分 (0-1)
    accuracy_score: float      # 准确性得分 (0-1)
    consistency_score: float   # 一致性得分 (0-1)
    timeliness_score: float    # 及时性得分 (0-1)
    overall_score: float       # 综合得分 (0-1)
    
    parsing_time: float        # 解析耗时（秒）
    success_rate: float        # 成功率
    
    issues_count: int          # 问题数量
    warnings_count: int        # 警告数量
    
    timestamp: datetime        # 记录时间
    fund_code: str            # 基金代码
    report_type: str          # 报告类型


class AssetAllocationValidation(BaseModel):
    """资产配置验证模型"""
    asset_type: str = Field(..., min_length=1, max_length=50)
    market_value: Optional[Decimal] = Field(None, ge=0)
    percentage: Optional[Decimal] = Field(None, ge=0, le=1)
    
    @field_validator('asset_type')
    @classmethod
    def validate_asset_type(cls, v):
        valid_keywords = ['股票', '债券', '基金', '存款', '现金', '其他', '货币', '银行']
        if not any(keyword in v for keyword in valid_keywords):
            raise ValueError(f'无效的资产类型: {v}')
        return v
    
    @field_validator('percentage')
    @classmethod
    def validate_percentage_range(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError(f'百分比超出范围 [0,1]: {v}')
        return v


class StockHoldingValidation(BaseModel):
    """股票持仓验证模型"""
    rank: int = Field(..., ge=1, le=10)
    stock_code: str = Field(..., pattern=r'^\d{6}$')
    stock_name: str = Field(..., min_length=1, max_length=100)
    market_value: Optional[Decimal] = Field(None, ge=0)
    percentage: Optional[Decimal] = Field(None, ge=0, le=1)
    
    @field_validator('stock_code')
    @classmethod
    def validate_stock_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError(f'股票代码格式错误: {v}')
        return v


class DataFormatValidators:
    """数据格式验证器"""
    
    @staticmethod
    def validate_fund_code(code: str) -> bool:
        """验证基金代码格式"""
        return bool(re.match(r'^\d{6}$', code))
    
    @staticmethod
    def validate_percentage(value: Any) -> bool:
        """验证百分比格式"""
        try:
            if isinstance(value, str):
                # 移除百分号
                clean_value = value.replace('%', '').strip()
                value = float(clean_value)
            
            if isinstance(value, (int, float, Decimal)):
                return 0 <= float(value) <= 100 if '%' in str(value) else 0 <= float(value) <= 1
            
            return False
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_amount(value: Any) -> bool:
        """验证金额格式"""
        try:
            if isinstance(value, str):
                # 清理金额字符串
                clean_value = re.sub(r'[,，\s元万亿]', '', value)
                value = float(clean_value)
            
            return isinstance(value, (int, float, Decimal)) and float(value) >= 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_date(value: Any) -> bool:
        """验证日期格式"""
        if isinstance(value, datetime):
            return True
        
        if isinstance(value, str):
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',
                r'\d{4}/\d{2}/\d{2}',
                r'\d{4}年\d{1,2}月\d{1,2}日'
            ]
            return any(re.match(pattern, value) for pattern in date_patterns)
        
        return False


class BusinessLogicValidator:
    """业务逻辑验证器"""
    
    def __init__(self):
        self.logger = get_logger("business_logic_validator")
    
    def validate_asset_allocation_sum(self, allocations: List[AssetAllocation]) -> Tuple[bool, List[str]]:
        """验证资产配置总和"""
        issues = []
        
        if not allocations:
            issues.append("资产配置数据为空")
            return False, issues
        
        # 计算百分比总和
        total_percentage = sum(
            float(allocation.percentage) for allocation in allocations 
            if allocation.percentage is not None
        )
        
        # 允许5%的误差
        if abs(total_percentage - 1.0) > 0.05:
            issues.append(f"资产配置百分比总和异常: {total_percentage:.2%} (期望: 100%)")
            return False, issues
        
        # 检查单项配置是否合理
        for allocation in allocations:
            if allocation.percentage and allocation.percentage > 0.95:
                issues.append(f"单项资产配置过高: {allocation.asset_type} {allocation.percentage:.2%}")
        
        return len(issues) == 0, issues
    
    def validate_holding_concentration(self, holdings: List[TopHolding]) -> Tuple[bool, List[str]]:
        """验证持仓集中度（使用HHI指数）"""
        issues = []
        warnings = []
        
        if not holdings:
            return True, []
        
        # 计算HHI指数
        percentages = [
            float(holding.percentage) for holding in holdings 
            if holding.percentage is not None
        ]
        
        if not percentages:
            warnings.append("无法计算持仓集中度：缺少百分比数据")
            return True, warnings
        
        hhi = sum(p * p for p in percentages)
        
        # HHI阈值判断
        if hhi > 0.25:  # 高度集中
            issues.append(f"持仓过度集中，HHI指数: {hhi:.4f} (>0.25)")
        elif hhi > 0.15:  # 中度集中
            warnings.append(f"持仓较为集中，HHI指数: {hhi:.4f}")
        
        # 检查单一持仓比例
        max_percentage = max(percentages)
        if max_percentage > 0.10:  # 单一持仓超过10%
            issues.append(f"单一持仓比例过高: {max_percentage:.2%}")
        
        return len(issues) == 0, issues + warnings
    
    def validate_temporal_consistency(self, current_report: FundReport, 
                                    previous_report: Optional[FundReport]) -> Tuple[bool, List[str]]:
        """验证时间序列一致性"""
        issues = []
        
        if not previous_report:
            return True, []
        
        # 检查基金规模变化
        if (current_report.total_net_assets and previous_report.total_net_assets):
            current_assets = float(current_report.total_net_assets)
            previous_assets = float(previous_report.total_net_assets)
            
            change_rate = abs(current_assets - previous_assets) / previous_assets
            
            # 如果基金规模变化超过50%，标记为异常
            if change_rate > 0.5:
                issues.append(
                    f"基金规模变化异常: {change_rate:.2%} "
                    f"(从 {previous_assets:,.0f} 到 {current_assets:,.0f})"
                )
        
        # 检查持仓变化
        if current_report.top_holdings and previous_report.top_holdings:
            current_stocks = {h.security_code for h in current_report.top_holdings}
            previous_stocks = {h.security_code for h in previous_report.top_holdings}
            
            # 计算持仓重叠度
            overlap = len(current_stocks & previous_stocks)
            total_unique = len(current_stocks | previous_stocks)
            
            if total_unique > 0:
                overlap_rate = overlap / min(len(current_stocks), len(previous_stocks))
                
                # 如果持仓重叠度过低，可能存在问题
                if overlap_rate < 0.3:
                    issues.append(f"持仓变化过大，重叠度仅 {overlap_rate:.2%}")
        
        return len(issues) == 0, issues


class QualityMetricsCollector:
    """质量指标收集器"""
    
    def __init__(self):
        self.logger = get_logger("quality_metrics_collector")
        self.metrics_history: List[QualityMetrics] = []
    
    def collect_parsing_metrics(self, 
                              fund_report: Optional[FundReport],
                              parsing_time: float,
                              success: bool,
                              issues: List[str],
                              warnings: List[str]) -> QualityMetrics:
        """收集解析指标"""
        
        # 计算完整性得分
        completeness_score = self._calculate_completeness_score(fund_report) if fund_report else 0.0
        
        # 计算准确性得分
        accuracy_score = self._calculate_accuracy_score(fund_report, issues) if fund_report else 0.0
        
        # 计算一致性得分
        consistency_score = self._calculate_consistency_score(fund_report, issues) if fund_report else 0.0
        
        # 计算及时性得分
        timeliness_score = self._calculate_timeliness_score(parsing_time)
        
        # 计算综合得分（加权平均）
        weights = {'completeness': 0.3, 'accuracy': 0.3, 'consistency': 0.25, 'timeliness': 0.15}
        overall_score = (
            completeness_score * weights['completeness'] +
            accuracy_score * weights['accuracy'] +
            consistency_score * weights['consistency'] +
            timeliness_score * weights['timeliness']
        )
        
        metrics = QualityMetrics(
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            consistency_score=consistency_score,
            timeliness_score=timeliness_score,
            overall_score=overall_score,
            parsing_time=parsing_time,
            success_rate=1.0 if success else 0.0,
            issues_count=len(issues),
            warnings_count=len(warnings),
            timestamp=datetime.utcnow(),
            fund_code=fund_report.fund_code if fund_report else 'unknown',
            report_type=fund_report.report_type if fund_report else 'unknown'
        )
        
        self.metrics_history.append(metrics)
        self.logger.info("收集质量指标", metrics=asdict(metrics))
        
        return metrics
    
    def _calculate_completeness_score(self, fund_report: FundReport) -> float:
        """计算完整性得分"""
        if not fund_report:
            return 0.0
        
        # 核心字段权重
        core_fields = {
            'fund_code': 0.15,
            'fund_name': 0.15,
            'report_type': 0.1,
            'report_period_end': 0.1,
            'net_asset_value': 0.1,
            'total_net_assets': 0.1,
            'asset_allocations': 0.15,
            'top_holdings': 0.1,
            'industry_allocations': 0.05
        }
        
        score = 0.0
        
        for field, weight in core_fields.items():
            value = getattr(fund_report, field, None)
            
            if field in ['asset_allocations', 'top_holdings', 'industry_allocations']:
                # 对于列表字段，检查是否有数据
                if value and len(value) > 0:
                    score += weight
            else:
                # 对于普通字段，检查是否非空
                if value is not None:
                    score += weight
        
        return min(score, 1.0)
    
    def _calculate_accuracy_score(self, fund_report: FundReport, issues: List[str]) -> float:
        """计算准确性得分"""
        if not fund_report:
            return 0.0
        
        # 基础得分
        base_score = 1.0
        
        # 根据问题数量扣分
        issue_penalty = min(len(issues) * 0.1, 0.5)  # 每个问题扣0.1分，最多扣0.5分
        
        # 数据格式验证
        format_score = 1.0
        
        # 验证基金代码
        if not DataFormatValidators.validate_fund_code(fund_report.fund_code):
            format_score -= 0.2
        
        # 验证资产配置数据
        if fund_report.asset_allocations:
            for allocation in fund_report.asset_allocations:
                if allocation.percentage and not DataFormatValidators.validate_percentage(allocation.percentage):
                    format_score -= 0.1
        
        accuracy_score = base_score - issue_penalty
        accuracy_score *= format_score
        
        return max(accuracy_score, 0.0)
    
    def _calculate_consistency_score(self, fund_report: FundReport, issues: List[str]) -> float:
        """计算一致性得分"""
        if not fund_report:
            return 0.0
        
        consistency_score = 1.0
        
        # 检查资产配置一致性
        if fund_report.asset_allocations:
            total_percentage = sum(
                float(allocation.percentage) for allocation in fund_report.asset_allocations
                if allocation.percentage is not None
            )
            
            # 百分比总和偏差
            deviation = abs(total_percentage - 1.0)
            if deviation > 0.05:
                consistency_score -= min(deviation, 0.3)
        
        # 根据一致性相关问题扣分
        consistency_issues = [issue for issue in issues if '一致性' in issue or '总和' in issue]
        consistency_score -= len(consistency_issues) * 0.15
        
        return max(consistency_score, 0.0)
    
    def _calculate_timeliness_score(self, parsing_time: float) -> float:
        """计算及时性得分"""
        # 基于解析时间计算得分
        if parsing_time <= 10:  # 10秒内完成
            return 1.0
        elif parsing_time <= 30:  # 30秒内完成
            return 0.8
        elif parsing_time <= 60:  # 60秒内完成
            return 0.6
        else:
            return 0.4
    
    def get_recent_metrics(self, hours: int = 24) -> List[QualityMetrics]:
        """获取最近的质量指标"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            metrics for metrics in self.metrics_history 
            if metrics.timestamp >= cutoff_time
        ]
    
    def calculate_success_rate(self, hours: int = 24) -> float:
        """计算成功率"""
        recent_metrics = self.get_recent_metrics(hours)
        if not recent_metrics:
            return 0.0
        
        successful_count = sum(1 for m in recent_metrics if m.success_rate > 0)
        return successful_count / len(recent_metrics)
    
    def calculate_average_quality_score(self, hours: int = 24) -> float:
        """计算平均质量得分"""
        recent_metrics = self.get_recent_metrics(hours)
        if not recent_metrics:
            return 0.0
        
        return sum(m.overall_score for m in recent_metrics) / len(recent_metrics)


class QualityAlertSystem:
    """质量告警系统"""
    
    def __init__(self, 
                 min_success_rate: float = 0.9,
                 min_quality_score: float = 0.8,
                 max_avg_parsing_time: float = 30.0):
        self.min_success_rate = min_success_rate
        self.min_quality_score = min_quality_score
        self.max_avg_parsing_time = max_avg_parsing_time
        self.logger = get_logger("quality_alert_system")
    
    def check_quality_thresholds(self, metrics_collector: QualityMetricsCollector) -> List[str]:
        """检查质量阈值"""
        alerts = []
        
        # 检查成功率
        success_rate = metrics_collector.calculate_success_rate()
        if success_rate < self.min_success_rate:
            alerts.append(
                f"解析成功率过低: {success_rate:.2%} (阈值: {self.min_success_rate:.2%})"
            )
        
        # 检查质量得分
        avg_quality = metrics_collector.calculate_average_quality_score()
        if avg_quality < self.min_quality_score:
            alerts.append(
                f"平均质量得分过低: {avg_quality:.2f} (阈值: {self.min_quality_score:.2f})"
            )
        
        # 检查解析时间
        recent_metrics = metrics_collector.get_recent_metrics()
        if recent_metrics:
            avg_parsing_time = sum(m.parsing_time for m in recent_metrics) / len(recent_metrics)
            if avg_parsing_time > self.max_avg_parsing_time:
                alerts.append(
                    f"平均解析时间过长: {avg_parsing_time:.1f}秒 (阈值: {self.max_avg_parsing_time:.1f}秒)"
                )
        
        if alerts:
            self.logger.warning("质量告警触发", alerts=alerts)
        
        return alerts
    
    def generate_alert_report(self, alerts: List[str]) -> Dict[str, Any]:
        """生成告警报告"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'alert_count': len(alerts),
            'alerts': alerts,
            'severity': 'HIGH' if len(alerts) >= 3 else 'MEDIUM' if len(alerts) >= 1 else 'LOW',
            'recommendations': self._generate_recommendations(alerts)
        }
    
    def _generate_recommendations(self, alerts: List[str]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for alert in alerts:
            if '成功率' in alert:
                recommendations.append("检查解析器配置和输入数据质量")
            elif '质量得分' in alert:
                recommendations.append("优化数据验证规则和修复逻辑")
            elif '解析时间' in alert:
                recommendations.append("优化解析算法性能或增加硬件资源")
        
        return list(set(recommendations))  # 去重


class QualityReportGenerator:
    """质量报告生成器"""
    
    def __init__(self):
        self.logger = get_logger("quality_report_generator")
    
    def generate_daily_report(self, metrics_collector: QualityMetricsCollector) -> Dict[str, Any]:
        """生成日报"""
        recent_metrics = metrics_collector.get_recent_metrics(24)
        
        if not recent_metrics:
            return {
                'date': datetime.utcnow().date().isoformat(),
                'summary': '无数据',
                'metrics': {},
                'trends': {},
                'issues': []
            }
        
        # 计算汇总指标
        summary_metrics = {
            'total_reports': len(recent_metrics),
            'success_rate': sum(m.success_rate for m in recent_metrics) / len(recent_metrics),
            'avg_quality_score': sum(m.overall_score for m in recent_metrics) / len(recent_metrics),
            'avg_parsing_time': sum(m.parsing_time for m in recent_metrics) / len(recent_metrics),
            'total_issues': sum(m.issues_count for m in recent_metrics),
            'total_warnings': sum(m.warnings_count for m in recent_metrics)
        }
        
        # 分析趋势
        trends = self._analyze_trends(recent_metrics)
        
        # 识别主要问题
        issues = self._identify_main_issues(recent_metrics)
        
        report = {
            'date': datetime.utcnow().date().isoformat(),
            'summary': self._generate_summary(summary_metrics),
            'metrics': summary_metrics,
            'trends': trends,
            'issues': issues,
            'recommendations': self._generate_daily_recommendations(summary_metrics, trends)
        }
        
        self.logger.info("生成日质量报告", report_summary=report['summary'])
        return report
    
    def _analyze_trends(self, metrics: List[QualityMetrics]) -> Dict[str, Any]:
        """分析趋势"""
        if len(metrics) < 2:
            return {'trend_analysis': '数据不足，无法分析趋势'}
        
        # 按时间排序
        sorted_metrics = sorted(metrics, key=lambda m: m.timestamp)
        
        # 计算趋势
        first_half = sorted_metrics[:len(sorted_metrics)//2]
        second_half = sorted_metrics[len(sorted_metrics)//2:]
        
        first_avg_quality = sum(m.overall_score for m in first_half) / len(first_half)
        second_avg_quality = sum(m.overall_score for m in second_half) / len(second_half)
        
        quality_trend = 'improving' if second_avg_quality > first_avg_quality else 'declining'
        
        return {
            'quality_trend': quality_trend,
            'quality_change': second_avg_quality - first_avg_quality,
            'parsing_time_trend': self._calculate_time_trend(sorted_metrics)
        }
    
    def _calculate_time_trend(self, metrics: List[QualityMetrics]) -> str:
        """计算时间趋势"""
        if len(metrics) < 2:
            return 'stable'
        
        first_half_time = sum(m.parsing_time for m in metrics[:len(metrics)//2]) / (len(metrics)//2)
        second_half_time = sum(m.parsing_time for m in metrics[len(metrics)//2:]) / (len(metrics) - len(metrics)//2)
        
        if second_half_time > first_half_time * 1.1:
            return 'slowing'
        elif second_half_time < first_half_time * 0.9:
            return 'improving'
        else:
            return 'stable'
    
    def _identify_main_issues(self, metrics: List[QualityMetrics]) -> List[str]:
        """识别主要问题"""
        issues = []
        
        # 统计问题频率
        high_issue_count = sum(1 for m in metrics if m.issues_count > 3)
        if high_issue_count > len(metrics) * 0.3:
            issues.append(f"高问题率：{high_issue_count}/{len(metrics)} 个报告存在较多问题")
        
        # 检查低质量报告
        low_quality_count = sum(1 for m in metrics if m.overall_score < 0.7)
        if low_quality_count > len(metrics) * 0.2:
            issues.append(f"低质量率：{low_quality_count}/{len(metrics)} 个报告质量较低")
        
        return issues
    
    def _generate_summary(self, metrics: Dict[str, Any]) -> str:
        """生成摘要"""
        success_rate = metrics['success_rate']
        quality_score = metrics['avg_quality_score']
        
        if success_rate >= 0.95 and quality_score >= 0.9:
            return "优秀：解析质量和成功率均表现优异"
        elif success_rate >= 0.9 and quality_score >= 0.8:
            return "良好：解析质量和成功率表现良好"
        elif success_rate >= 0.8 and quality_score >= 0.7:
            return "一般：解析质量和成功率需要改进"
        else:
            return "较差：解析质量和成功率需要重点关注"
    
    def _generate_daily_recommendations(self, metrics: Dict[str, Any], trends: Dict[str, Any]) -> List[str]:
        """生成日报建议"""
        recommendations = []
        
        if metrics['success_rate'] < 0.9:
            recommendations.append("提高解析成功率：检查输入数据格式和解析器兼容性")
        
        if metrics['avg_quality_score'] < 0.8:
            recommendations.append("提升数据质量：加强数据验证和清洗规则")
        
        if metrics['avg_parsing_time'] > 30:
            recommendations.append("优化解析性能：考虑算法优化或硬件升级")
        
        if trends.get('quality_trend') == 'declining':
            recommendations.append("质量下降趋势：需要分析原因并采取改进措施")
        
        return recommendations
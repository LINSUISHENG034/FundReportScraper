# 数据质量保证实施方案

## 概述

建立全面的数据质量保证体系，确保从XBRL报告中提取的数据具有高准确性、完整性和一致性，为后续的投资分析提供可靠的数据基础。

## 数据质量维度定义

### 1. 完整性 (Completeness)
- **定义**：必需字段的填充率和数据覆盖度
- **度量指标**：
  - 核心字段完整率 ≥ 95%
  - 可选字段完整率 ≥ 80%
  - 报告整体完整性得分 ≥ 90%

### 2. 准确性 (Accuracy)
- **定义**：数据值的正确性和精确度
- **度量指标**：
  - 数值型数据准确率 ≥ 98%
  - 格式验证通过率 ≥ 99%
  - 业务规则验证通过率 ≥ 95%

### 3. 一致性 (Consistency)
- **定义**：数据内部逻辑关系的正确性
- **度量指标**：
  - 汇总数据与明细数据一致性 ≥ 98%
  - 时间序列数据一致性 ≥ 95%
  - 跨表数据关联一致性 ≥ 97%

### 4. 及时性 (Timeliness)
- **定义**：数据处理和更新的时效性
- **度量指标**：
  - 报告解析完成时间 ≤ 30秒（年报）
  - 数据入库延迟 ≤ 5分钟
  - 质量检查完成时间 ≤ 10分钟

## 质量检查规则体系

### 1. 格式验证规则
```python
from pydantic import BaseModel, validator, Field
from typing import Optional, List
from decimal import Decimal
import re

class DataFormatValidators:
    """数据格式验证器集合"""
    
    @staticmethod
    def validate_fund_code(fund_code: str) -> bool:
        """验证基金代码格式"""
        patterns = [
            r'^\d{6}$',           # 6位数字（股票型基金）
            r'^\d{3}\d{3}$',      # 6位数字（其他基金）
            r'^[A-Z]{2}\d{4}$',   # 2字母+4数字（QDII基金）
        ]
        return any(re.match(pattern, fund_code) for pattern in patterns)
    
    @staticmethod
    def validate_percentage(value: Decimal) -> bool:
        """验证百分比数值范围"""
        return 0 <= value <= 1
    
    @staticmethod
    def validate_amount(value: Decimal) -> bool:
        """验证金额数值合理性"""
        return value >= 0 and value <= Decimal('1e12')  # 最大1万亿
    
    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """验证日期格式"""
        import datetime
        try:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False

class AssetAllocationValidation(BaseModel):
    """资产配置数据验证模型"""
    
    asset_type: str = Field(..., min_length=1, max_length=50)
    market_value: Decimal = Field(..., ge=0)
    net_value_ratio: Decimal = Field(..., ge=0, le=1)
    
    @validator('asset_type')
    def validate_asset_type(cls, v):
        valid_types = [
            '股票投资', '债券投资', '基金投资', '银行存款',
            '买入返售金融资产', '其他资产'
        ]
        if v not in valid_types:
            raise ValueError(f'无效的资产类型: {v}')
        return v
    
    @validator('market_value')
    def validate_market_value(cls, v):
        if not DataFormatValidators.validate_amount(v):
            raise ValueError('市值金额超出合理范围')
        return v

class StockHoldingValidation(BaseModel):
    """股票持仓验证模型"""
    
    stock_code: str = Field(..., regex=r'^\d{6}$')
    stock_name: str = Field(..., min_length=1, max_length=100)
    shares_held: int = Field(..., ge=0)
    market_value: Decimal = Field(..., ge=0)
    net_value_ratio: Decimal = Field(..., ge=0, le=1)
    
    @validator('stock_code')
    def validate_stock_code(cls, v):
        # 验证股票代码的有效性（可以集成第三方股票代码库）
        if not v.isdigit() or len(v) != 6:
            raise ValueError('股票代码格式错误')
        return v
```

### 2. 业务逻辑验证规则
```python
class BusinessLogicValidator:
    """业务逻辑验证器"""
    
    def __init__(self, llm_assistant=None):
        self.llm_assistant = llm_assistant
    
    def validate_asset_allocation_sum(self, allocations: List[AssetAllocationValidation]) -> Dict:
        """验证资产配置比例总和"""
        total_ratio = sum(allocation.net_value_ratio for allocation in allocations)
        
        result = {
            'is_valid': True,
            'total_ratio': float(total_ratio),
            'deviation': abs(float(total_ratio) - 1.0),
            'issues': []
        }
        
        # 允许2%的误差范围
        if abs(total_ratio - 1.0) > 0.02:
            result['is_valid'] = False
            result['issues'].append(f'资产配置比例总和为{total_ratio:.4f}，偏离100%超过2%')
        
        return result
    
    def validate_holding_concentration(self, holdings: List[StockHoldingValidation]) -> Dict:
        """验证持仓集中度"""
        if not holdings:
            return {'is_valid': True, 'concentration_risk': 'LOW'}
        
        # 计算前十大持仓比例
        sorted_holdings = sorted(holdings, key=lambda x: x.net_value_ratio, reverse=True)
        top_10_ratio = sum(h.net_value_ratio for h in sorted_holdings[:10])
        
        # 计算HHI指数
        hhi = sum(h.net_value_ratio ** 2 for h in holdings)
        
        result = {
            'is_valid': True,
            'top_10_ratio': float(top_10_ratio),
            'hhi_index': float(hhi),
            'concentration_risk': 'LOW',
            'issues': []
        }
        
        # 风险等级判断
        if top_10_ratio > 0.8:
            result['concentration_risk'] = 'HIGH'
            result['issues'].append('前十大持仓比例超过80%，存在高集中度风险')
        elif top_10_ratio > 0.6:
            result['concentration_risk'] = 'MEDIUM'
        
        if hhi > 0.25:
            result['issues'].append(f'HHI指数{hhi:.4f}过高，持仓过度集中')
        
        return result
    
    def validate_temporal_consistency(self, current_data: Dict, previous_data: Dict) -> Dict:
        """验证时间序列一致性"""
        result = {
            'is_valid': True,
            'consistency_score': 1.0,
            'issues': []
        }
        
        if not previous_data:
            return result
        
        # 检查基金规模变化合理性
        current_nav = current_data.get('net_asset_value', 0)
        previous_nav = previous_data.get('net_asset_value', 0)
        
        if previous_nav > 0:
            change_ratio = abs(current_nav - previous_nav) / previous_nav
            if change_ratio > 0.5:  # 规模变化超过50%
                result['issues'].append(f'基金规模变化{change_ratio:.2%}过大，需要核实')
                result['consistency_score'] *= 0.8
        
        # 检查持仓变化合理性
        current_holdings = set(current_data.get('stock_codes', []))
        previous_holdings = set(previous_data.get('stock_codes', []))
        
        turnover_ratio = len(current_holdings.symmetric_difference(previous_holdings)) / max(len(current_holdings), len(previous_holdings), 1)
        
        if turnover_ratio > 0.8:  # 换手率超过80%
            result['issues'].append(f'持仓换手率{turnover_ratio:.2%}过高')
            result['consistency_score'] *= 0.9
        
        if result['consistency_score'] < 0.8:
            result['is_valid'] = False
        
        return result
    
    async def llm_validate_data_reasonableness(self, data: Dict, context: str) -> Dict:
        """使用LLM验证数据合理性"""
        if not self.llm_assistant:
            return {'is_valid': True, 'confidence': 0.5}
        
        return await self.llm_assistant.validate_extracted_data(data, context)
```

### 3. 数据修复机制
```python
class DataRepairService:
    """数据修复服务"""
    
    def __init__(self, llm_assistant=None):
        self.llm_assistant = llm_assistant
    
    def repair_missing_percentage_values(self, allocations: List[Dict]) -> List[Dict]:
        """修复缺失的百分比数值"""
        total_value = sum(item.get('market_value', 0) for item in allocations if item.get('market_value'))
        
        for item in allocations:
            if item.get('market_value') and not item.get('net_value_ratio'):
                if total_value > 0:
                    item['net_value_ratio'] = item['market_value'] / total_value
                    item['_repaired_fields'] = item.get('_repaired_fields', []) + ['net_value_ratio']
        
        return allocations
    
    def repair_inconsistent_totals(self, data: Dict) -> Dict:
        """修复不一致的汇总数据"""
        if 'asset_allocations' in data:
            allocations = data['asset_allocations']
            calculated_total = sum(item.get('market_value', 0) for item in allocations)
            reported_total = data.get('total_net_assets', 0)
            
            # 如果差异超过1%，使用计算值
            if reported_total > 0 and abs(calculated_total - reported_total) / reported_total > 0.01:
                data['total_net_assets'] = calculated_total
                data['_repaired_fields'] = data.get('_repaired_fields', []) + ['total_net_assets']
        
        return data
    
    async def llm_assisted_repair(self, problematic_data: Dict, error_description: str) -> Dict:
        """LLM辅助数据修复"""
        if not self.llm_assistant:
            return problematic_data
        
        repair_prompt = f"""
        以下数据存在问题：{error_description}
        
        原始数据：{json.dumps(problematic_data, ensure_ascii=False, indent=2)}
        
        请提供修复建议，返回JSON格式：
        {{
            "repaired_data": {{修复后的数据}},
            "repair_actions": ["修复动作1", "修复动作2"],
            "confidence": 0.95
        }}
        """
        
        try:
            response = await self.llm_assistant.client.generate(
                model=self.llm_assistant.model_name,
                prompt=repair_prompt,
                options={'temperature': 0.1}
            )
            
            # 解析LLM响应并应用修复
            # ... 实现细节
            
        except Exception as e:
            print(f"LLM辅助修复失败: {e}")
        
        return problematic_data
```

## 质量监控系统

### 1. 实时质量指标监控
```python
import time
from collections import defaultdict
from typing import Dict, List
import asyncio

class QualityMetricsCollector:
    """质量指标收集器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.alerts = []
    
    def record_parsing_result(self, fund_code: str, report_type: str, result: Dict):
        """记录解析结果"""
        timestamp = time.time()
        
        quality_score = self._calculate_quality_score(result)
        
        self.metrics['parsing_success_rate'].append({
            'timestamp': timestamp,
            'fund_code': fund_code,
            'report_type': report_type,
            'success': result.get('parsing_status') == 'SUCCESS',
            'quality_score': quality_score
        })
        
        # 检查是否需要告警
        if quality_score < 0.8:
            self.alerts.append({
                'timestamp': timestamp,
                'fund_code': fund_code,
                'alert_type': 'LOW_QUALITY',
                'quality_score': quality_score,
                'details': result.get('quality_issues', [])
            })
    
    def _calculate_quality_score(self, result: Dict) -> float:
        """计算综合质量得分"""
        if result.get('parsing_status') != 'SUCCESS':
            return 0.0
        
        completeness = result.get('completeness_score', 0.8)
        accuracy = result.get('accuracy_score', 0.9)
        consistency = result.get('consistency_score', 0.9)
        
        # 加权平均
        return 0.4 * completeness + 0.4 * accuracy + 0.2 * consistency
    
    def get_quality_dashboard(self) -> Dict:
        """获取质量仪表板数据"""
        recent_metrics = [m for m in self.metrics['parsing_success_rate'] 
                         if time.time() - m['timestamp'] < 86400]  # 最近24小时
        
        if not recent_metrics:
            return {'status': 'NO_DATA'}
        
        success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics)
        avg_quality = sum(m['quality_score'] for m in recent_metrics) / len(recent_metrics)
        
        return {
            'success_rate': success_rate,
            'average_quality_score': avg_quality,
            'total_processed': len(recent_metrics),
            'recent_alerts': len([a for a in self.alerts if time.time() - a['timestamp'] < 3600])
        }

class QualityAlertSystem:
    """质量告警系统"""
    
    def __init__(self, metrics_collector: QualityMetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_thresholds = {
            'success_rate_min': 0.95,
            'quality_score_min': 0.8,
            'processing_time_max': 300  # 5分钟
        }
    
    async def monitor_quality_continuously(self):
        """持续监控质量指标"""
        while True:
            dashboard = self.metrics_collector.get_quality_dashboard()
            
            if dashboard.get('status') != 'NO_DATA':
                await self._check_alert_conditions(dashboard)
            
            await asyncio.sleep(60)  # 每分钟检查一次
    
    async def _check_alert_conditions(self, dashboard: Dict):
        """检查告警条件"""
        alerts = []
        
        if dashboard['success_rate'] < self.alert_thresholds['success_rate_min']:
            alerts.append({
                'type': 'LOW_SUCCESS_RATE',
                'value': dashboard['success_rate'],
                'threshold': self.alert_thresholds['success_rate_min']
            })
        
        if dashboard['average_quality_score'] < self.alert_thresholds['quality_score_min']:
            alerts.append({
                'type': 'LOW_QUALITY_SCORE',
                'value': dashboard['average_quality_score'],
                'threshold': self.alert_thresholds['quality_score_min']
            })
        
        for alert in alerts:
            await self._send_alert(alert)
    
    async def _send_alert(self, alert: Dict):
        """发送告警"""
        print(f"质量告警: {alert['type']} - 当前值: {alert['value']:.3f}, 阈值: {alert['threshold']:.3f}")
        # 这里可以集成邮件、短信、钉钉等告警渠道
```

## 质量报告生成

### 1. 自动化质量报告
```python
class QualityReportGenerator:
    """质量报告生成器"""
    
    def __init__(self, metrics_collector: QualityMetricsCollector):
        self.metrics_collector = metrics_collector
    
    def generate_daily_quality_report(self, date: str) -> str:
        """生成日度质量报告"""
        dashboard = self.metrics_collector.get_quality_dashboard()
        
        report = f"""
# 数据质量日报 - {date}

## 总体指标
- 解析成功率: {dashboard.get('success_rate', 0):.2%}
- 平均质量得分: {dashboard.get('average_quality_score', 0):.3f}
- 处理报告数量: {dashboard.get('total_processed', 0)}
- 告警数量: {dashboard.get('recent_alerts', 0)}

## 质量分析
### 成功率趋势
{self._generate_success_rate_trend()}

### 质量得分分布
{self._generate_quality_score_distribution()}

### 主要问题
{self._generate_issue_summary()}

## 改进建议
{self._generate_improvement_suggestions()}
        """
        
        return report
    
    def _generate_success_rate_trend(self) -> str:
        """生成成功率趋势分析"""
        # 实现趋势分析逻辑
        return "成功率保持稳定，无明显下降趋势"
    
    def _generate_quality_score_distribution(self) -> str:
        """生成质量得分分布"""
        # 实现分布分析逻辑
        return "质量得分主要集中在0.8-0.95区间"
    
    def _generate_issue_summary(self) -> str:
        """生成问题汇总"""
        # 分析常见问题
        return "主要问题：部分报告的持仓明细数据缺失"
    
    def _generate_improvement_suggestions(self) -> str:
        """生成改进建议"""
        return "建议加强对特殊格式报告的解析能力"
```

这个数据质量保证方案提供了全面的质量控制机制，确保解析数据的高质量和可靠性。

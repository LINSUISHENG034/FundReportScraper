# XBRL报告解析器架构设计

## 概述

基于对真实XBRL报告样本的深入分析，设计一个模块化、可扩展的解析器架构，用于从基金定期报告中提取结构化数据。

## 核心设计原则

1. **模块化设计**：每个解析器模块负责特定类型的数据提取
2. **报告类型适配**：支持年报、季报、半年报、基金概况等不同报告类型
3. **数据标准化**：统一数据格式和质量标准
4. **错误处理**：完善的异常处理和数据验证机制

## 架构组件

### 1. 基础解析器 (BaseParser)

```python
class BaseParser:
    """基础HTML解析器，处理通用结构"""
    
    def __init__(self, html_content: str):
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.navigation_tree = self._extract_navigation()
        self.content_sections = self._extract_content_sections()
    
    def _extract_navigation(self) -> Dict:
        """提取报告导航目录结构"""
        pass
    
    def _extract_content_sections(self) -> Dict:
        """提取各内容区域的HTML"""
        pass
    
    def _clean_numeric_value(self, value: str) -> Optional[float]:
        """清洗数值数据：处理千分位、负号、百分比等"""
        pass
    
    def _parse_table(self, table_element) -> List[Dict]:
        """通用表格解析方法"""
        pass
```

### 2. 资产配置解析器 (AssetAllocationParser)

```python
class AssetAllocationParser(BaseParser):
    """解析基金资产组合配置数据"""
    
    def parse_asset_allocation(self) -> List[Dict]:
        """解析期末基金资产组合情况"""
        # 查找资产配置相关表格
        # 提取各类资产的市值和占比
        # 返回标准化的资产配置数据
        pass
    
    def parse_asset_changes(self) -> List[Dict]:
        """解析资产配置变化情况"""
        pass
```

### 3. 持仓明细解析器 (HoldingParser)

```python
class HoldingParser(BaseParser):
    """解析持仓明细数据"""
    
    def parse_stock_holdings(self) -> List[Dict]:
        """解析股票持仓明细"""
        # 按行业分类的股票投资组合
        # 前十大重仓股明细
        # 港股通投资明细
        pass
    
    def parse_bond_holdings(self) -> List[Dict]:
        """解析债券持仓明细"""
        # 按债券品种分类的投资组合
        # 前五大债券投资明细
        # 按信用评级分类的债券投资
        pass
    
    def parse_fund_holdings(self) -> List[Dict]:
        """解析基金投资明细（FOF基金）"""
        pass
    
    def parse_trading_activities(self) -> List[Dict]:
        """解析交易活动记录"""
        # 报告期内股票投资组合的重大变动
        # 累计买入/卖出明细
        pass
```

### 4. 财务指标解析器 (FinancialMetricsParser)

```python
class FinancialMetricsParser(BaseParser):
    """解析财务指标数据"""
    
    def parse_investment_income(self) -> List[Dict]:
        """解析投资收益构成"""
        # 股票投资收益
        # 债券投资收益
        # 基金投资收益
        # 公允价值变动损益
        pass
    
    def parse_fee_structure(self) -> List[Dict]:
        """解析费用结构"""
        # 管理费、托管费、销售服务费等
        pass
    
    def parse_performance_metrics(self) -> List[Dict]:
        """解析业绩指标"""
        # 净值增长率
        # 与基准比较
        pass
```

### 5. 风险分析解析器 (RiskAnalysisParser)

```python
class RiskAnalysisParser(BaseParser):
    """解析风险管理数据"""
    
    def parse_credit_risk(self) -> List[Dict]:
        """解析信用风险指标"""
        # 按信用评级列示的债券投资
        pass
    
    def parse_liquidity_risk(self) -> List[Dict]:
        """解析流动性风险指标"""
        # 金融资产到期期限分析
        pass
    
    def parse_concentration_risk(self) -> List[Dict]:
        """解析集中度风险指标"""
        pass
```

## 报告类型适配器

### 年报适配器 (AnnualReportAdapter)
- 处理最完整的数据结构
- 包含所有投资组合、财务和风险数据
- 支持完整的业绩归因分析

### 季报适配器 (QuarterlyReportAdapter)
- 处理简化的数据结构
- 重点关注持仓变化和基本财务指标
- 适配季度报告的特殊格式

### 基金概况适配器 (FundProfileAdapter)
- 处理基金基本信息
- 费用结构和投资策略
- 风险揭示信息

## 数据流处理

```python
class XBRLReportProcessor:
    """XBRL报告处理主控制器"""
    
    def __init__(self, report_type: str):
        self.adapter = self._get_adapter(report_type)
    
    def process_report(self, html_content: str, report_metadata: Dict) -> Dict:
        """处理完整报告"""
        try:
            # 1. 基础解析
            base_data = self.adapter.parse_basic_info(html_content)
            
            # 2. 资产配置解析
            asset_data = self.adapter.parse_asset_allocation(html_content)
            
            # 3. 持仓明细解析
            holding_data = self.adapter.parse_holdings(html_content)
            
            # 4. 财务指标解析
            financial_data = self.adapter.parse_financial_metrics(html_content)
            
            # 5. 风险指标解析
            risk_data = self.adapter.parse_risk_indicators(html_content)
            
            # 6. 数据验证和清洗
            validated_data = self._validate_and_clean(
                base_data, asset_data, holding_data, financial_data, risk_data
            )
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Report processing failed: {e}")
            raise
    
    def _validate_and_clean(self, *data_sets) -> Dict:
        """数据验证和清洗"""
        # 数据完整性检查
        # 数值合理性验证
        # 数据一致性校验
        pass
```

## 数据质量保证

### 1. 数据验证规则
- 资产配置比例总和应接近100%
- 持仓明细与汇总数据的一致性
- 数值范围的合理性检查
- 必填字段的完整性验证

### 2. 异常处理策略
- 解析失败时的降级处理
- 部分数据缺失时的处理策略
- 格式异常时的自动修复尝试

### 3. 日志和监控
- 详细的解析过程日志
- 数据质量指标监控
- 异常情况的告警机制

## 性能优化

### 1. 解析优化
- 使用lxml解析器提高性能
- 缓存重复计算结果
- 并行处理多个报告

### 2. 内存管理
- 流式处理大文件
- 及时释放不需要的对象
- 合理的批处理大小

## 扩展性设计

### 1. 新报告类型支持
- 通过适配器模式轻松添加新类型
- 配置化的字段映射
- 版本兼容性处理

### 2. 自定义解析规则
- 支持配置文件定义解析规则
- 插件化的解析器扩展
- 用户自定义数据提取逻辑

## 使用示例

```python
# 处理年度报告
processor = XBRLReportProcessor('ANNUAL')
result = processor.process_report(html_content, {
    'fund_code': '000001',
    'report_period': '2024-12-31',
    'report_type': 'ANNUAL'
})

# 保存到数据库
database_service.save_parsed_data(result)
```

这个架构设计确保了解析器的可维护性、可扩展性和数据质量，为后续的投资分析和风险管理提供了可靠的数据基础。
